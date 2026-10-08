# -*- coding: utf-8 -*-
"""mcd. Dress Pose Fit 0.1 — weights + rest-shape fit from corrected poses.

RESEARCH PROTOTYPE, NOT YET A MAYA TOOL. Pure numpy (no scipy), so it can
later run inside mayapy. Nothing here touches a Maya scene.

Problem
-------
Given P example poses of a skeleton (joint skinning matrices S_j^p =
G_j^p * inverse(bind_j)) and, for each pose, a manually corrected dress
shape y_i^p, find ONE set of skinning weights w_ij (SL rules: >= 0, sum 1,
at most 4 joints per vertex) and a SMALL rest-shape offset d_i such that

    v_i^p = sum_j w_ij * S_j^p * (x_i + d_i)      ~=  y_i^p   for all p.

The bind pose itself is always a training pose with the original mesh as
its target, so d is pulled towards zero: it only moves where the poses pay
for it. The weights and offsets are fixed per vertex, i.e. the result is
an ordinary linear-blend-skinned mesh that SL can display.

The problem is bilinear; it is solved by alternating
  * weights  : per-vertex quadratic program on the (support-limited)
               probability simplex, batched projected gradient (FISTA),
               with neighbor smoothing and a prior (e.g. the v0.4 weights);
  * offsets  : one global sparse least-squares solve with a mesh-Laplacian
               smoothness term, matrix-free conjugate gradient;
  * optional : free rigid "helper bones" per training pose (SSDR, Le & Deng
               2012) plus a ridge regression pose -> helper transform, as in
               example-based helper-bone rigs (Mukai 2015/2016). SL cannot
               evaluate such drivers at runtime; see sl_dress_study.py for
               how they are used only as a generator of extra training data.

Units: anything consistent. All regularisers are scale free.
"""

import numpy as np

VERSION = '0.1'


# --------------------------------------------------------------------------
# small geometry helpers
# --------------------------------------------------------------------------
def rotvec_to_matrix(rv):
    """Rodrigues; rv (..., 3) -> (..., 3, 3)."""
    rv = np.asarray(rv, dtype=float)
    theta = np.linalg.norm(rv, axis=-1)[..., None, None]
    safe = np.where(theta > 1e-12, theta, 1.0)
    k = rv / safe[..., 0]
    K = np.zeros(rv.shape[:-1] + (3, 3))
    K[..., 0, 1], K[..., 0, 2] = -k[..., 2], k[..., 1]
    K[..., 1, 0], K[..., 1, 2] = k[..., 2], -k[..., 0]
    K[..., 2, 0], K[..., 2, 1] = -k[..., 1], k[..., 0]
    eye = np.broadcast_to(np.eye(3), K.shape)
    R = eye + np.sin(theta) * K + (1.0 - np.cos(theta)) * (K @ K)
    return np.where(theta > 1e-12, R, eye)


def matrix_to_rotvec(R):
    R = np.asarray(R, dtype=float)
    cos = np.clip((np.trace(R, axis1=-2, axis2=-1) - 1.0) * 0.5, -1.0, 1.0)
    theta = np.arccos(cos)
    axis = np.stack([R[..., 2, 1] - R[..., 1, 2], R[..., 0, 2] - R[..., 2, 0],
                     R[..., 1, 0] - R[..., 0, 1]], axis=-1)
    sin = np.sin(theta)
    out = axis * np.where(sin > 1e-9, theta / (2.0 * np.where(sin > 1e-9, sin, 1.0)), 0.5)[..., None]
    # near pi: use the symmetric part (rare for cloth helpers; good enough)
    near_pi = theta > np.pi - 1e-4
    if np.any(near_pi):
        S = (R[near_pi] + np.eye(3)) * 0.5
        ax = np.sqrt(np.clip(np.diagonal(S, axis1=-2, axis2=-1), 0.0, None))
        out[near_pi] = ax * np.pi
    return out


def apply(M, x):
    """M (...,4,4), x (...,3) -> (...,3)."""
    return np.einsum('...ab,...b->...a', M[..., :3, :3], x) + M[..., :3, 3]


def edges_from_faces(faces):
    e = set()
    for f in faces:
        for a, b in zip(f, list(f[1:]) + [f[0]]):
            e.add((min(a, b), max(a, b)))
    return np.array(sorted(e), dtype=int)


def neighbor_lists(count, edges):
    nb = [[] for _ in range(count)]
    for a, b in edges:
        nb[a].append(b)
        nb[b].append(a)
    return nb


def _laplacian_apply(d, edges, count):
    """(L d) for the graph Laplacian with unit edge weights; d (N, k)."""
    out = np.zeros_like(d)
    diff = d[edges[:, 0]] - d[edges[:, 1]]
    np.add.at(out, edges[:, 0], diff)
    np.add.at(out, edges[:, 1], -diff)
    return out


def _neighbor_mean(w, edges, count):
    acc = np.zeros_like(w)
    deg = np.zeros(count)
    np.add.at(acc, edges[:, 0], w[edges[:, 1]])
    np.add.at(acc, edges[:, 1], w[edges[:, 0]])
    np.add.at(deg, edges[:, 0], 1.0)
    np.add.at(deg, edges[:, 1], 1.0)
    return np.where(deg[:, None] > 0, acc / np.maximum(deg, 1.0)[:, None], w)


# --------------------------------------------------------------------------
# skinning
# --------------------------------------------------------------------------
def skin(rest, weights, mats):
    """Linear blend skinning.

    rest (N,3), weights (N,J) dense, mats (J,4,4) skinning matrices of ONE
    pose  ->  (N,3).
    """
    blended = np.einsum('nj,jab->nab', weights, mats)
    return apply(blended, rest)


def skin_all(rest, weights, pose_mats):
    return np.stack([skin(rest, weights, m) for m in pose_mats])


# --------------------------------------------------------------------------
# simplex QP (batched)
# --------------------------------------------------------------------------
def project_simplex(v, active):
    """Euclidean projection of each row of v onto {w>=0, sum w=1, w=0 off
    the active mask}. Inactive entries are pushed to -inf before sorting."""
    v = np.where(active, v, -1e18)
    u = -np.sort(-v, axis=1)
    css = np.cumsum(u, axis=1) - 1.0
    k = np.arange(1, v.shape[1] + 1)
    cond = (u - css / k) > 0
    rho = cond.shape[1] - 1 - np.argmax(cond[:, ::-1], axis=1)
    tau = css[np.arange(len(v)), rho] / (rho + 1.0)
    return np.where(active, np.maximum(v - tau[:, None], 0.0), 0.0)


def simplex_qp(H, g, w0, active, iterations=200):
    """min 0.5 w'Hw - g'w on the masked simplex, FISTA, batched over rows."""
    L = np.linalg.eigvalsh(H)[:, -1]
    step = 1.0 / np.maximum(L, 1e-12)
    w = project_simplex(w0, active)
    z, t = w.copy(), 1.0
    for _ in range(iterations):
        grad = np.einsum('nab,nb->na', H, z) - g
        w_new = project_simplex(z - step[:, None] * grad, active)
        t_new = 0.5 * (1.0 + np.sqrt(1.0 + 4.0 * t * t))
        z = w_new + ((t - 1.0) / t_new) * (w_new - w)
        w, t = w_new, t_new
    return w


# --------------------------------------------------------------------------
# the fitter
# --------------------------------------------------------------------------
class FitConfig:
    def __init__(self, **kw):
        self.max_influences = 4       # SL limit
        self.iterations = 12          # outer alternations
        self.fit_rest = True          # False -> weights only
        self.weight_smooth = 0.05     # neighbor-mean pull, relative to data term
        self.weight_prior = 0.005     # pull towards the start weights
        self.rest_damping = 0.5       # |d|^2, relative to one pose
        self.rest_smooth = 4.0        # Laplacian on d, relative to one pose
        self.rest_limit = None        # hard cap |d_i| (scene units), or None
        self.bind_weight = 3.0        # importance of the unchanged bind pose
        self.locked = None            # bool (N,) vertices whose weights stay
        for k, v in kw.items():
            if not hasattr(self, k):
                raise KeyError(k)
            setattr(self, k, v)


def fit(rest, edges, pose_mats, targets, w_init, candidates, cfg=None,
        pose_weights=None, log=None):
    """Joint fit of SL weights and a rest-shape offset.

    rest       (N,3)   original dress in bind pose
    edges      (E,2)   mesh edges (for smoothing)
    pose_mats  (P,J,4,4) skinning matrices; the bind pose (identity) is
               added automatically with target = rest
    targets    (P,N,3) corrected shapes
    w_init     (N,J)   start weights (e.g. v0.4)
    candidates (N,J) bool - which joints a vertex may use at all
    returns    weights (N,J), offset (N,3), history
    """
    cfg = cfg or FitConfig()
    N, J = w_init.shape
    eye = np.broadcast_to(np.eye(4), (1, J, 4, 4))
    mats = np.concatenate([eye, pose_mats], axis=0)
    Y = np.concatenate([rest[None], targets], axis=0)
    alpha = np.ones(len(mats))
    if pose_weights is not None:
        alpha[1:] = pose_weights
    alpha[0] = cfg.bind_weight
    sa = np.sqrt(alpha)[:, None, None]
    P = alpha.sum()
    locked = np.zeros(N, bool) if cfg.locked is None else np.asarray(cfg.locked, bool)
    cand = np.asarray(candidates, bool) | (w_init > 0)
    w = w_init.copy()
    d = np.zeros_like(rest)
    history = []
    for it in range(cfg.iterations):
        # ---- weights ----------------------------------------------------
        xr = rest + d
        # Q[n, p, :, j] = S_j^p xr_n   (weighted by sqrt alpha)
        Q = np.einsum('pjab,nb->npaj', mats[:, :, :3, :3], xr) + \
            mats[:, :, :3, 3].transpose(0, 2, 1)[None]
        Q = Q * sa[None]
        G = Q.reshape(N, -1, J)
        y = (Y.transpose(1, 0, 2) * sa[None, :, :, 0]).reshape(N, -1)
        H = np.einsum('nka,nkb->nab', G, G)
        g = np.einsum('nka,nk->na', G, y)
        scale = np.trace(H, axis1=1, axis2=2) / J
        wbar = _neighbor_mean(w, edges, N)
        bs = cfg.weight_smooth * scale
        bp = cfg.weight_prior * scale
        Hreg = H + (bs + bp)[:, None, None] * np.eye(J)
        greg = g + bs[:, None] * wbar + bp[:, None] * w_init
        w_full = simplex_qp(Hreg, greg, w, cand)
        # keep the strongest max_influences joints, re-solve on that support
        order = np.argsort(-w_full, axis=1)
        support = np.zeros_like(cand)
        np.put_along_axis(support, order[:, :cfg.max_influences], True, axis=1)
        support &= cand
        w_new = simplex_qp(Hreg, greg, w_full * support, support)
        w = np.where(locked[:, None], w_init, w_new)
        # ---- rest offsets -----------------------------------------------
        if cfg.fit_rest:
            d = _solve_rest(rest, d, w, mats, Y, alpha, edges, cfg, P, locked)
        err = _error(rest + d, w, mats, Y)
        history.append(err)
        if log:
            log('iter %2d  rms %.5f  |d|max %.5f' % (it, err, np.abs(d).max() if len(d) else 0))
    return w, d, history


def _solve_rest(rest, d0, w, mats, Y, alpha, edges, cfg, P, locked):
    N = len(rest)
    B = np.einsum('nj,pjab->pnab', w, mats[:, :, :3, :3])           # linear part
    t = np.einsum('nj,pja->pna', w, mats[:, :, :3, 3])
    r = Y - (np.einsum('pnab,nb->pna', B, rest) + t)                 # residual at d=0
    A = np.einsum('p,pnba,pnbc->nac', alpha, B, B) + cfg.rest_damping * P * np.eye(3)
    b = np.einsum('p,pnba,pnb->na', alpha, B, r)
    mu = cfg.rest_smooth * P
    free = ~locked

    def op(x):
        y = np.einsum('nab,nb->na', A, x) + mu * _laplacian_apply(x, edges, N)
        return np.where(free[:, None], y, x)

    rhs = np.where(free[:, None], b, 0.0)
    x = np.where(free[:, None], d0, 0.0)
    res = rhs - op(x)
    p = res.copy()
    rs = np.sum(res * res)
    for _ in range(400):
        Ap = op(p)
        a = rs / max(np.sum(p * Ap), 1e-30)
        x += a * p
        res -= a * Ap
        rs_new = np.sum(res * res)
        if rs_new < 1e-20 * max(np.sum(rhs * rhs), 1e-30):
            break
        p = res + (rs_new / rs) * p
        rs = rs_new
    if cfg.rest_limit is not None:
        n = np.linalg.norm(x, axis=1, keepdims=True)
        x = x * np.minimum(1.0, cfg.rest_limit / np.maximum(n, 1e-12))
    return x


def _error(rest, w, mats, Y):
    V = skin_all(rest, w, mats)
    return float(np.sqrt(np.mean(np.sum((V - Y) ** 2, axis=-1))))


# --------------------------------------------------------------------------
# virtual cloth bones (SSDR-style helper bones + pose-driven regression)
# --------------------------------------------------------------------------
def _kabsch(p, q, wt):
    """Weighted rigid fit q ~ R p + t, batched over leading dim."""
    ws = wt.sum(axis=-1, keepdims=True)
    ws = np.maximum(ws, 1e-12)
    pc = np.einsum('...n,...na->...a', wt, p) / ws
    qc = np.einsum('...n,...na->...a', wt, q) / ws
    Hm = np.einsum('...n,...na,...nb->...ab', wt, p - pc[..., None, :], q - qc[..., None, :])
    U, _, Vt = np.linalg.svd(Hm)
    D = np.sign(np.linalg.det(np.einsum('...ab,...bc->...ac', U, Vt)))
    Dm = np.zeros(Hm.shape)
    Dm[..., 0, 0] = 1.0
    Dm[..., 1, 1] = 1.0
    Dm[..., 2, 2] = D
    R = np.einsum('...ba,...bc,...dc->...ad', Vt, Dm, U)  # V D U^T
    t = qc - np.einsum('...ab,...b->...a', R, pc)
    return R, t


def _rigid(R, t):
    M = np.zeros(R.shape[:-2] + (4, 4))
    M[..., :3, :3] = R
    M[..., :3, 3] = t
    M[..., 3, 3] = 1.0
    return M


def fit_helpers(rest, edges, pose_mats, targets, w_init, candidates, region,
                count=6, iterations=15, seed=0, cfg=None, log=None):
    """Add `count` free rigid helper bones for the vertices in `region` and
    fit weights + per-pose helper transforms (SSDR). Rest shape is kept.

    returns weights (N, J+K), helper transforms (P, K, 4, 4) for the given
    training poses, helper pivots (K,3)
    """
    cfg = cfg or FitConfig(fit_rest=False)
    rng = np.random.default_rng(seed)
    N, J = w_init.shape
    P = len(pose_mats)
    idx = np.flatnonzero(region)
    # k-means on rest positions of the region -> initial helper clusters
    centers = rest[rng.choice(idx, count, replace=False)]
    for _ in range(30):
        lab = np.argmin(((rest[idx, None] - centers[None]) ** 2).sum(-1), axis=1)
        centers = np.stack([rest[idx][lab == k].mean(0) if np.any(lab == k) else centers[k]
                            for k in range(count)])
    # initial transforms: rigid fit of each cluster to its targets
    H = np.zeros((P, count, 4, 4))
    for k in range(count):
        members = idx[lab == k]
        R, t = _kabsch(np.broadcast_to(rest[members], (P,) + rest[members].shape),
                       targets[:, members], np.ones((P, len(members))))
        H[:, k] = _rigid(R, t)
    # initial weights: blend v0.4 with a soft helper assignment
    w = np.zeros((N, J + count))
    w[:, :J] = w_init
    soft = np.exp(-((rest[idx, None] - centers[None]) ** 2).sum(-1) / (2 * 0.05 ** 2))
    soft /= soft.sum(1, keepdims=True)
    w[idx] = 0.3 * w[idx]
    w[idx, J:] = 0.7 * soft
    cand = np.zeros((N, J + count), bool)
    cand[:, :J] = candidates
    cand[idx, J:] = True
    for it in range(iterations):
        mats = np.concatenate([pose_mats, H], axis=1)
        w, _, hist = fit(rest, edges, mats, targets, w, cand,
                         FitConfig(**{**cfg.__dict__, 'iterations': 1, 'fit_rest': False}))
        # SSDR transform update, one helper at a time
        for k in range(count):
            mats = np.concatenate([pose_mats, H], axis=1)
            wk = w[:, J + k]
            sel = wk > 1e-4
            if sel.sum() < 4:
                continue
            others = skin_all(rest[sel], np.where(np.arange(J + count) == J + k, 0.0, w[sel]), mats)
            q = (targets[:, sel] - others) / wk[sel][None, :, None]
            R, t = _kabsch(np.broadcast_to(rest[sel], (P,) + rest[sel].shape), q,
                           np.broadcast_to(wk[sel] ** 2, (P, sel.sum())))
            H[:, k] = _rigid(R, t)
        if log:
            mats = np.concatenate([pose_mats, H], axis=1)
            log('helper iter %2d  rms %.5f' % (it, _error(rest, w, mats, targets)))
    return w, H, centers


class HelperDriver:
    """Ridge regression pose features -> helper (rotvec, pivot displacement).

    A stand-in for whatever the runtime would have to evaluate. It needs
    a driver per helper bone at runtime, which SL does not provide.
    """

    def __init__(self, features, helpers, pivots, ridge=1e-2):
        X = np.concatenate([features, np.ones((len(features), 1))], axis=1)
        R = helpers[:, :, :3, :3]
        rv = matrix_to_rotvec(R)                                   # (P,K,3)
        disp = np.einsum('pkab,kb->pka', R, pivots) + helpers[:, :, :3, 3] - pivots[None]
        Yd = np.concatenate([rv, disp], axis=2).reshape(len(X), -1)
        reg = ridge * np.eye(X.shape[1])
        reg[-1, -1] = 0.0
        self.coef = np.linalg.solve(X.T @ X + reg, X.T @ Yd)
        self.pivots = pivots

    def __call__(self, features):
        X = np.concatenate([features, np.ones((len(features), 1))], axis=1)
        out = (X @ self.coef).reshape(len(X), len(self.pivots), 6)
        R = rotvec_to_matrix(out[..., :3])
        t = self.pivots[None] + out[..., 3:] - np.einsum('pkab,kb->pka', R, self.pivots)
        return _rigid(R, t)


# --------------------------------------------------------------------------
# data exchange (for Maya export / reproducible studies)
# --------------------------------------------------------------------------
def save_training_set(path, rest, faces, joint_names, bind, pose_mats, targets,
                      pose_names, w_init):
    np.savez_compressed(path, rest=rest, faces=np.asarray(faces), joint_names=np.array(joint_names),
                        bind=bind, pose_mats=pose_mats, targets=targets,
                        pose_names=np.array(pose_names), w_init=w_init)


def load_training_set(path):
    data = np.load(path, allow_pickle=False)
    return {k: data[k] for k in data.files}
