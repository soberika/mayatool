# -*- coding: utf-8 -*-
"""Study: pose-example fit vs. the current v0.4 auto rig, SL constraints.

Run:   python3 experiments/sl_dress_study.py [--quick]
Writes experiments/results/ (report.md, metrics.json, *.png).

IMPORTANT LIMITATION
The "manually corrected target poses" are produced here by a scripted
proxy (rotation field + leg collision + inextensible drape, see
`reference_shape`). There is no real artist data in the repository yet.
The proxy is deliberately NOT linear blend skinning, so no method can hit
it exactly; but conclusions must be re-checked with real Maya sculpts.
"""

import importlib.util
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import dress_pose_fit as dpf  # noqa: E402

OUT = os.path.join(HERE, 'results')


def load_v04():
    spec = importlib.util.spec_from_file_location(
        'mcd_dress_auto_rig', os.path.join(ROOT, 'mcd_dress_auto_rig (3).py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# SL-like skeleton (meters, Y up, character faces +Z, left = +X)
# Proportions after the SL default avatar; joint names as in SL.
# --------------------------------------------------------------------------
JOINTS = ['mPelvis', 'mTorso', 'mHipLeft', 'mHipRight', 'mKneeLeft', 'mKneeRight',
          'mAnkleLeft', 'mAnkleRight']
PARENT = [-1, 0, 0, 0, 2, 3, 4, 5]
OFFSET = np.array([[0, 1.00, 0], [0, 0.085, 0], [0.09, -0.06, 0], [-0.09, -0.06, 0],
                   [0, -0.45, 0.0], [0, -0.45, 0.0], [0, -0.42, 0], [0, -0.42, 0]])
J = len(JOINTS)
IDX = {n: i for i, n in enumerate(JOINTS)}


def rest_positions():
    pos = np.zeros((J, 3))
    for j in range(J):
        pos[j] = OFFSET[j] + (pos[PARENT[j]] if PARENT[j] >= 0 else 0)
    return pos


REST_J = rest_positions()


def rot(flex=0.0, abd=0.0, twist=0.0):
    """Degrees. flex>0 swings a hip forward; for knees flex>0 bends back."""
    rx = dpf.rotvec_to_matrix(np.array([np.radians(flex), 0, 0]))
    rz = dpf.rotvec_to_matrix(np.array([0, 0, np.radians(abd)]))
    ry = dpf.rotvec_to_matrix(np.array([0, np.radians(twist), 0]))
    return ry @ rz @ rx


def pose(hipL=(0, 0, 0), hipR=(0, 0, 0), kneeL=0, kneeR=0, pelvis=(0, 0, 0)):
    """hip tuple: (flex forward, abduction outward, twist outward), degrees."""
    local = [np.eye(3) for _ in range(J)]
    local[IDX['mPelvis']] = rot(*pelvis)
    local[IDX['mHipLeft']] = rot(-hipL[0], hipL[1], hipL[2])
    local[IDX['mHipRight']] = rot(-hipR[0], -hipR[1], -hipR[2])
    local[IDX['mKneeLeft']] = rot(kneeL)
    local[IDX['mKneeRight']] = rot(kneeR)
    return local


def forward(local):
    """-> world rotations (J,3,3), world positions (J,3), skin mats (J,4,4)."""
    Rw = np.zeros((J, 3, 3))
    Pw = np.zeros((J, 3))
    for j in range(J):
        if PARENT[j] < 0:
            Rw[j], Pw[j] = local[j], OFFSET[j]
        else:
            p = PARENT[j]
            Rw[j] = Rw[p] @ local[j]
            Pw[j] = Pw[p] + Rw[p] @ OFFSET[j]
    S = np.zeros((J, 4, 4))
    S[:, :3, :3] = Rw
    S[:, :3, 3] = Pw - np.einsum('jab,jb->ja', Rw, REST_J)   # bind = translation only
    S[:, 3, 3] = 1
    return Rw, Pw, S


def features(local):
    """Pose descriptor for helper-bone drivers: hip + knee rotation vectors."""
    names = ['mHipLeft', 'mHipRight', 'mKneeLeft', 'mKneeRight']
    return np.concatenate([dpf.matrix_to_rotvec(local[IDX[n]]) for n in names])


# training poses = the ones an artist would correct by hand
TRAIN = {
    'walk_L': pose(hipL=(35, 0, 0), hipR=(-20, 0, 0), kneeL=20, kneeR=10),
    'walk_R': pose(hipR=(35, 0, 0), hipL=(-20, 0, 0), kneeR=20, kneeL=10),
    'wide': pose(hipL=(0, 25, 0), hipR=(0, 25, 0)),
    'sit60': pose(hipL=(60, 5, 0), hipR=(60, 5, 0), kneeL=60, kneeR=60),
    'knee_up_L': pose(hipL=(70, 0, 0), kneeL=80),
    'side_L': pose(hipL=(0, 35, 0)),
}
# unseen poses inside the training range (interpolation)
INTERP = {
    'walk_half': pose(hipL=(18, 0, 0), hipR=(-10, 0, 0), kneeL=10, kneeR=5),
    'wide_half_sit': pose(hipL=(30, 15, 0), hipR=(30, 15, 0), kneeL=30, kneeR=30),
    'knee_up_R': pose(hipR=(70, 0, 0), kneeR=80),          # mirror only
    'side_R': pose(hipR=(0, 30, 0)),
}
# unseen EXTREME poses (outside the training range)
EXTREME = {
    'sit90': pose(hipL=(90, 8, 0), hipR=(90, 8, 0), kneeL=90, kneeR=90),
    'high_kick_R': pose(hipR=(110, 0, 0), kneeR=5),
    'split_wide': pose(hipL=(0, 50, 0), hipR=(0, 50, 0)),
    'lunge_L': pose(hipL=(80, 5, 0), hipR=(-35, 0, 0), kneeL=95, kneeR=30),
    'cross_legs': pose(hipL=(75, -18, -10), hipR=(70, 10, 15), kneeL=85, kneeR=95),
    'run_R': pose(hipR=(65, 0, 0), hipL=(-40, 0, 0), kneeR=70, kneeL=45),
    'kneel_R': pose(hipR=(5, 0, 0), kneeR=100, hipL=(85, 5, 0), kneeL=90),
}


# --------------------------------------------------------------------------
# dress mesh: A-line skirt + bodice band, a ring grid
# --------------------------------------------------------------------------
def make_dress(hem_y, hem_r, cols=48, rows=34):
    top_y = 1.10
    ys = np.linspace(top_y, hem_y, rows)
    verts = []
    for y in ys:
        if y > 0.94:   # waist/hip part, hugging the body
            r = 0.135 + (1.10 - y) / 0.16 * 0.055
        else:
            r = 0.19 + (0.94 - y) / (0.94 - hem_y) * (hem_r - 0.19)
        for c in range(cols):
            a = 2 * np.pi * c / cols
            verts.append([r * np.sin(a), y, 0.86 * r * np.cos(a) + 0.01])
    verts = np.array(verts)
    faces = []
    for r_ in range(rows - 1):
        for c in range(cols):
            a = r_ * cols + c
            b = r_ * cols + (c + 1) % cols
            faces.append([a, b, b + cols, a + cols])
    return verts, faces, rows, cols


# --------------------------------------------------------------------------
# leg capsules (collision proxy) + reference ("hand corrected") shapes
# --------------------------------------------------------------------------
CAPS = [('mHipLeft', 'mKneeLeft', 0.078, 0.058), ('mHipRight', 'mKneeRight', 0.078, 0.058),
        ('mKneeLeft', 'mAnkleLeft', 0.055, 0.04), ('mKneeRight', 'mAnkleRight', 0.055, 0.04)]
CLOTH = 0.012


def capsule_push(points, Pw, extra=CLOTH):
    """Return (pushed points, penetration depth per point, before pushing)."""
    pts = points.copy()
    depth = np.zeros(len(points))
    for a, b, ra, rb in CAPS:
        A, B = Pw[IDX[a]], Pw[IDX[b]]
        ab = B - A
        t = np.clip(((pts - A) @ ab) / (ab @ ab), 0, 1)
        c = A + t[:, None] * ab
        r = ra + (rb - ra) * t + extra
        v = pts - c
        dist = np.linalg.norm(v, axis=1)
        inside = dist < r
        depth = np.maximum(depth, np.where(inside, r - dist, 0))
        n = v / np.maximum(dist, 1e-9)[:, None]
        pts = np.where(inside[:, None], c + n * r[:, None], pts)
    return pts, depth


def penetration(points, Pw):
    return capsule_push(points, Pw, extra=0.0)[1]


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def reference_shape(rest, rows, cols, local):
    """Proxy for an artist-corrected pose. Not LBS on purpose:
    1. rotation field: rotation vectors of both hips blended by side
       (rotvec blend, slerp-like, not matrix blend) about a blended pivot,
       plus a partial knee rotation for the lower skirt;
    2. gravity: material that the rotation lifts is allowed to hang;
    3. inextensible columns (follow-the-leader) + leg collision.
    """
    Rw, Pw, _ = forward(local)
    rvL = dpf.matrix_to_rotvec(Rw[IDX['mHipLeft']])
    rvR = dpf.matrix_to_rotvec(Rw[IDX['mHipRight']])
    rkL = dpf.matrix_to_rotvec(Rw[IDX['mHipLeft']].T @ Rw[IDX['mKneeLeft']])
    rkR = dpf.matrix_to_rotvec(Rw[IDX['mHipRight']].T @ Rw[IDX['mKneeRight']])
    hip_y = REST_J[IDX['mHipLeft'], 1]
    knee_y = REST_J[IDX['mKneeLeft'], 1]
    x = rest
    ring_r = np.linalg.norm(x[:, [0, 2]] - [0, 0.01], axis=1)
    u = x[:, 0] / np.maximum(ring_r, 1e-6)                 # -1 right .. 1 left
    aL = 0.5 + 0.5 * np.tanh(2.2 * u)
    aR = 1 - aL
    depth = smoothstep((hip_y + 0.06 - x[:, 1]) / 0.32)
    rv = (aL[:, None] * rvL + aR[:, None] * rvR) * (0.92 * depth)[:, None]
    pivot = aL[:, None] * REST_J[IDX['mHipLeft']] + aR[:, None] * REST_J[IDX['mHipRight']]
    p = pivot + np.einsum('nab,nb->na', dpf.rotvec_to_matrix(rv), x - pivot)
    # knee: cloth below the knee follows the shin partially, on its side
    kdepth = smoothstep((knee_y + 0.05 - x[:, 1]) / 0.25) * 0.55
    for a, rk, side in ((aL, rkL, 'Left'), (aR, rkR, 'Right')):
        w = (a ** 2 * kdepth)[:, None]
        knee_world = Pw[IDX['mKnee' + side]]
        R_hip = Rw[IDX['mHip' + side]]
        Rk = dpf.rotvec_to_matrix(rk[None] * w)
        # partial shin rotation, expressed in world: R_hip Rk R_hip^T, about the knee
        R_world = np.einsum('ab,nbc,dc->nad', R_hip, Rk, R_hip)
        p = knee_world + np.einsum('nab,nb->na', R_world, p - knee_world)
    # constraints on columns
    X = rest.reshape(rows, cols, 3)
    goal = p.reshape(rows, cols, 3).copy()
    # gravity: material that the legs LIFT sags back by half (zero in bind pose)
    hang = smoothstep((hip_y - X[..., 1]) / 0.4)
    goal[..., 1] -= 0.5 * hang * np.maximum(goal[..., 1] - X[..., 1], 0.0)
    seg = np.linalg.norm(np.diff(X, axis=0), axis=2)                # (rows-1, cols)
    ring = np.linalg.norm(X - np.roll(X, -1, axis=1), axis=2)

    def collide_and_ftl(P):
        P = capsule_push(P.reshape(-1, 3), Pw)[0].reshape(P.shape)
        # inextensible columns: follow the leader from the waist down
        P[0] = goal[0]
        for r_ in range(1, rows):
            v = P[r_] - P[r_ - 1]
            n = np.linalg.norm(v, axis=1)
            P[r_] = P[r_ - 1] + v / np.maximum(n, 1e-9)[:, None] * seg[r_ - 1][:, None]
        return P

    P = goal.copy()
    for it in range(40):
        P = P + 0.3 * (goal - P)
        P = collide_and_ftl(P)
        # rings: soft limits, stretch <= +25 %, compression >= -35 %
        for _ in range(2):
            v = np.roll(P, -1, axis=1) - P
            n = np.linalg.norm(v, axis=2)
            target = np.clip(n, 0.65 * ring, 1.25 * ring)
            corr = (v / np.maximum(n, 1e-9)[..., None]) * ((n - target) * 0.5)[..., None]
            P = P + corr - np.roll(corr, 1, axis=1)
    # artist-like smoothing of the displacement, then re-impose constraints
    D = P - X
    for _ in range(3):
        D[1:-1] = 0.5 * D[1:-1] + 0.125 * (D[:-2] + D[2:] + np.roll(D[1:-1], 1, 1)
                                           + np.roll(D[1:-1], -1, 1))
    P = X + D
    for _ in range(4):
        P = collide_and_ftl(P)
    return P.reshape(-1, 3)


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------
def metrics(V, Y, Pw, edges, rest):
    e = np.linalg.norm(V - Y, axis=1) * 100           # cm
    pen = penetration(V, Pw) * 100
    L0 = np.linalg.norm(rest[edges[:, 0]] - rest[edges[:, 1]], axis=1)
    L = np.linalg.norm(V[edges[:, 0]] - V[edges[:, 1]], axis=1)
    strain = L / L0 - 1
    return {'mean_cm': float(e.mean()), 'p95_cm': float(np.percentile(e, 95)),
            'max_cm': float(e.max()), 'pen_pct': float((pen > 0.1).mean() * 100),
            'pen_max_cm': float(pen.max()),
            'stretch_p95_pct': float(np.percentile(np.abs(strain), 95) * 100)}


def evaluate(rest_used, w, poses, refs, edges, rest_orig, helper=None):
    out = {}
    for name, local in poses.items():
        Rw, Pw, S = forward(local)
        mats = S
        if helper is not None:
            mats = np.concatenate([S, helper(features(local)[None])[0]], axis=0)
        V = dpf.skin(rest_used, w, mats)
        out[name] = metrics(V, refs[name], Pw, edges, rest_orig)
    return out


def summarize(per_pose):
    keys = next(iter(per_pose.values())).keys()
    return {k: float(np.mean([m[k] for m in per_pose.values()])) if not k.startswith(('max', 'pen_max'))
            else float(np.max([m[k] for m in per_pose.values()])) for k in keys}


# --------------------------------------------------------------------------
# v0.4 weights
# --------------------------------------------------------------------------
def v04_weights(mod, rest, edges, overrides=None):
    N = len(rest)
    adjacency = dpf.neighbor_lists(N, edges)
    roles = {'pelvis': IDX['mPelvis'], 'left_hip': IDX['mHipLeft'], 'right_hip': IDX['mHipRight'],
             'left_knee': IDX['mKneeLeft'], 'right_knee': IDX['mKneeRight']}
    hipL, hipR = REST_J[IDX['mHipLeft']], REST_J[IDX['mHipRight']]
    lat = hipL - hipR
    params = {'origin': list(REST_J[0]), 'lateral_axis': list(lat / np.linalg.norm(lat)),
              'half_width': float(np.linalg.norm(lat) / 2), 'up_index': 1,
              'leg_length': float(hipL[1] - REST_J[IDX['mKneeLeft'], 1]),
              'knee_height': float(REST_J[IDX['mKneeLeft'], 1]),
              'start_height': float(REST_J[0, 1] - 0.02),     # default derived from pelvis
              'transition': 0.12,
              'leg_follow': 0.75, 'center_hold': 0.65, 'knee_follow': 0.65,
              'center_width': 2.5, 'smooth_passes': 2, 'maximum': 4}
    params.update(overrides or {})
    # body copy for the bodice: pelvis below the torso joint, torso above
    base = []
    for p in rest:
        t = smoothstep((p[1] - REST_J[0, 1]) / 0.08)
        base.append({IDX['mPelvis']: 1 - t, IDX['mTorso']: t} if 0 < t < 1 else
                    {IDX['mTorso'] if t >= 1 else IDX['mPelvis']: 1.0})
    rows, _ = mod.build_weights([tuple(p) for p in rest], base, adjacency, params, roles)
    W = np.zeros((N, J))
    for i, r in enumerate(rows):
        for j, v in r.items():
            W[i, j] = v
    return W


# --------------------------------------------------------------------------
# main study
# --------------------------------------------------------------------------
def run_variant(label, hem_y, hem_r, quick=False, log=print):
    t0 = time.time()
    mod = load_v04()
    rest, faces, rows, cols = make_dress(hem_y, hem_r, cols=40 if quick else 48,
                                         rows=26 if quick else 34)
    edges = dpf.edges_from_faces(faces)
    N = len(rest)
    allposes = {**TRAIN, **INTERP, **EXTREME}
    refs = {k: reference_shape(rest, rows, cols, v) for k, v in allposes.items()}
    train_names = list(TRAIN)
    pose_mats = np.stack([forward(TRAIN[k])[2] for k in train_names])
    targets = np.stack([refs[k] for k in train_names])
    sets = {'train': TRAIN, 'interp': INTERP, 'extreme': EXTREME}

    results = {}

    def record(name, rest_used, w, helper=None, extra=None):
        per = {s: evaluate(rest_used, w, p, refs, edges, rest, helper) for s, p in sets.items()}
        bind = np.linalg.norm(rest_used - rest, axis=1) * 100
        results[name] = {'per_pose': per, 'summary': {s: summarize(v) for s, v in per.items()},
                         'bind_dev_max_cm': float(bind.max()), 'bind_dev_mean_cm': float(bind.mean()),
                         'max_influences': int((w > 1e-6).sum(1).max()), **(extra or {})}
        log('  %-26s train %.2f  interp %.2f  extreme %.2f cm' % (
            name, results[name]['summary']['train']['mean_cm'],
            results[name]['summary']['interp']['mean_cm'],
            results[name]['summary']['extreme']['mean_cm']))

    # A: v0.4 default
    W0 = v04_weights(mod, rest, edges)
    record('A v0.4 Standard', rest, W0)

    # B: v0.4 with sliders tuned on the training poses (fair baseline)
    best = None
    grid = [0.45, 0.6, 0.75, 0.9]
    for lf in grid:
        for ch in [0.35, 0.5, 0.65, 0.8]:
            for kf in [0.3, 0.5, 0.65, 0.85]:
                for cw in ([1.5, 2.5, 3.5] if not quick else [2.5]):
                    o = {'leg_follow': lf, 'center_hold': ch, 'knee_follow': kf, 'center_width': cw}
                    W = v04_weights(mod, rest, edges, o)
                    err = np.mean([np.mean(np.linalg.norm(dpf.skin(rest, W, m) - t, axis=1))
                                   for m, t in zip(pose_mats, targets)])
                    if best is None or err < best[0]:
                        best = (err, o, W)
    record('B v0.4 Regler optimiert', rest, best[2], extra={'params': best[1]})
    WB = best[2]

    # candidates: torso joints everywhere, leg joints only below the waist
    cand = np.ones((N, J), bool)
    cand[rest[:, 1] > REST_J[0, 1] + 0.03, 2:] = False
    locked = rest[:, 1] > REST_J[0, 1] + 0.06       # bodice keeps body-copy weights

    # C: weights only
    cfg = dpf.FitConfig(fit_rest=False, locked=locked, iterations=8)
    WC, _, _ = dpf.fit(rest, edges, pose_mats, targets, WB, cand, cfg)
    record('C Fit: nur Gewichte', rest, WC)

    # D: weights + minimal rest offset (main proposal)
    cfg = dpf.FitConfig(fit_rest=True, locked=locked, iterations=12, rest_limit=0.03)
    WD, dD, histD = dpf.fit(rest, edges, pose_mats, targets, WB, cand, cfg)
    record('D Fit: Gewichte + Ruheform', rest + dD, WD)

    # D2: same, with ankles excluded (only the 5 joints v0.4 uses)
    cand5 = cand.copy()
    cand5[:, [IDX['mAnkleLeft'], IDX['mAnkleRight']]] = False
    WD5, dD5, _ = dpf.fit(rest, edges, pose_mats, targets, WB, cand5, cfg)
    record('D5 wie D, nur v0.4-Joints', rest + dD5, WD5)

    # E: virtual cloth bones (NOT SL-compatible): SSDR + pose regression
    region = ~locked & (rest[:, 1] < REST_J[0, 1] - 0.03)
    WE, HE, piv = dpf.fit_helpers(rest, edges, pose_mats, targets, WB, cand, region,
                                  count=6, iterations=6 if quick else 12,
                                  cfg=dpf.FitConfig(fit_rest=False, locked=locked))
    feats = np.stack([features(TRAIN[k]) for k in train_names])
    # bind pose sample anchors the regression at identity
    feats_b = np.concatenate([np.zeros((1, feats.shape[1])), feats])
    HE_b = np.concatenate([np.broadcast_to(np.eye(4), (1,) + HE.shape[1:]), HE])
    # ridge strength by leave-one-out over the training poses (vertex space)
    best_r = None
    for ridge in (0.01, 0.05, 0.2, 1.0, 5.0):
        err = 0.0
        for k in range(1, len(feats_b)):
            keep = np.arange(len(feats_b)) != k
            drv = dpf.HelperDriver(feats_b[keep], HE_b[keep], piv, ridge=ridge)
            mats = np.concatenate([pose_mats[k - 1], drv(feats_b[k:k + 1])[0]])
            err += np.mean(np.linalg.norm(dpf.skin(rest, WE, mats) - targets[k - 1], axis=1))
        if best_r is None or err < best_r[0]:
            best_r = (err, ridge)
    driver = dpf.HelperDriver(feats_b, HE_b, piv, ridge=best_r[1])
    record('E Virtuelle Stoff-Bones (6)', rest, WE, helper=driver,
           extra={'sl_compatible': False, 'ridge': best_r[1]})

    # F: helper rig as data generator -> distilled into SL weights + offset
    rng = np.random.default_rng(1)
    aug_mats, aug_tgts = [], []
    for _ in range(24 if quick else 48):
        # random mix of training poses (stay inside the trusted range)
        a = rng.dirichlet(np.ones(len(train_names) + 1) * 0.6)
        rvs = feats_b.T @ a
        local = pose()
        for k, n in enumerate(['mHipLeft', 'mHipRight', 'mKneeLeft', 'mKneeRight']):
            local[IDX[n]] = dpf.rotvec_to_matrix(rvs[3 * k:3 * k + 3])
        S = forward(local)[2]
        Hm = driver(features(local)[None])[0]
        aug_mats.append(S)
        aug_tgts.append(dpf.skin(rest, WE, np.concatenate([S, Hm])))
    pm = np.concatenate([pose_mats, np.stack(aug_mats)])
    tg = np.concatenate([targets, np.stack(aug_tgts)])
    pw = np.concatenate([np.ones(len(pose_mats)), np.full(len(aug_mats), 0.15)])
    WF, dF, _ = dpf.fit(rest, edges, pm, tg, WB, cand, cfg, pose_weights=pw)
    record('F D + Stoff-Bone-Destillation', rest + dF, WF)

    # O: oracle - same fit, trained on ALL poses incl. extremes. Not a method,
    # a bound: what fixed SL weights + offset can reach at best for these poses.
    names_all = list(allposes)
    pm_all = np.stack([forward(allposes[k])[2] for k in names_all])
    tg_all = np.stack([refs[k] for k in names_all])
    WO, dO, _ = dpf.fit(rest, edges, pm_all, tg_all, WB, cand, cfg)
    record('O Orakel (LBS-Grenze)', rest + dO, WO, extra={'oracle': True})

    info = {'vertices': N, 'faces': len(faces), 'seconds': time.time() - t0,
            'hem_y': hem_y, 'hem_r': hem_r, 'fit_history_D': histD,
            'rest_offset_D_max_cm': float(np.linalg.norm(dD, axis=1).max() * 100),
            'rest_offset_D_mean_cm': float(np.linalg.norm(dD, axis=1).mean() * 100)}
    arrays = {'rest': rest, 'faces': faces, 'rows': rows, 'cols': cols, 'refs': refs,
              'W': {'A': W0, 'B': WB, 'D': WD, 'F': WF}, 'd': {'D': dD, 'F': dF},
              'driver': driver, 'WE': WE}
    return results, info, arrays


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------
COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#7a5bd6', '#888888']


def plots(variant, results, arrays):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    files = []
    methods = list(results)
    poses = list(EXTREME) + list(INTERP)
    fig, ax = plt.subplots(figsize=(11, 4.2))
    width = 0.8 / len(methods)
    for k, m in enumerate(methods):
        vals = [results[m]['per_pose']['extreme' if p in EXTREME else 'interp'][p]['mean_cm']
                for p in poses]
        ax.bar(np.arange(len(poses)) + k * width, vals, width * 0.92, color=COLORS[k],
               label=m)
    ax.set_xticks(np.arange(len(poses)) + 0.4 - width / 2)
    ax.set_xticklabels(poses, rotation=30, ha='right', fontsize=8)
    ax.axvline(len(EXTREME) - 0.1, color='#999', lw=1, ls='--')
    ax.set_ylabel('mittlerer Fehler zur Zielform [cm]')
    ax.set_title('%s – ungesehene Posen (links: extrem, rechts: im Trainingsbereich)' % variant,
                 fontsize=10)
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='y', color='#ddd', lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=7, frameon=False, ncol=2)
    fig.tight_layout()
    f = os.path.join(OUT, 'fehler_%s.png' % variant)
    fig.savefig(f, dpi=130)
    plt.close(fig)
    files.append(f)

    # silhouettes: side + front view, extreme poses
    rest, rows, cols = arrays['rest'], arrays['rows'], arrays['cols']
    show = ['sit90', 'split_wide', 'lunge_L', 'high_kick_R']
    fig, axes = plt.subplots(2, len(show), figsize=(3.2 * len(show), 6.4))
    for c, pname in enumerate(show):
        local = EXTREME[pname]
        Rw, Pw, S = forward(local)
        shapes = {'Ziel': arrays['refs'][pname],
                  'A v0.4': dpf.skin(rest, arrays['W']['A'], S),
                  'D Fit': dpf.skin(rest + arrays['d']['D'], arrays['W']['D'], S)}
        cols_ = {'Ziel': '#222222', 'A v0.4': COLORS[0], 'D Fit': COLORS[3]}
        for r_, (ix, iy, view) in enumerate(((2, 1, 'Seite'), (0, 1, 'Front'))):
            ax = axes[r_, c]
            for b in [(2, 4, 6), (3, 5, 7)]:
                ax.plot(Pw[list(b), ix], Pw[list(b), iy], color='#999', lw=3, alpha=0.5)
            for name, V in shapes.items():
                G = V.reshape(rows, cols, 3)
                hem = np.vstack([G[-1], G[-1][:1]])
                ax.plot(hem[:, ix], hem[:, iy], color=cols_[name], lw=1.6 if name != 'Ziel' else 2.2,
                        ls='-' if name != 'Ziel' else '--', label=name)
                for cc in range(0, cols, cols // 8):
                    ax.plot(G[:, cc, ix], G[:, cc, iy], color=cols_[name], lw=0.6, alpha=0.6)
            ax.set_aspect('equal')
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title('%s (%s)' % (pname, view), fontsize=9)
            for s in ax.spines.values():
                s.set_visible(False)
    axes[0, 0].legend(fontsize=7, frameon=False, loc='upper left')
    fig.suptitle('%s: Saum + Längslinien, Ziel (gestrichelt) vs. v0.4 vs. Fit D' % variant, fontsize=10)
    fig.tight_layout()
    f = os.path.join(OUT, 'silhouetten_%s.png' % variant)
    fig.savefig(f, dpi=120)
    plt.close(fig)
    files.append(f)
    return files


def table(results, s):
    lines = ['| Methode | Ø Fehler cm | p95 cm | Max cm | Durchdringung % Vtx | max. Eindringtiefe cm | Dehnung p95 % | Bindepose-Abw. max cm |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for m, r in results.items():
        x = r['summary'][s]
        lines.append('| %s | %.2f | %.2f | %.2f | %.1f | %.2f | %.1f | %.2f |' % (
            m, x['mean_cm'], x['p95_cm'], x['max_cm'], x['pen_pct'], x['pen_max_cm'],
            x['stretch_p95_pct'], r['bind_dev_max_cm']))
    return '\n'.join(lines)


def per_pose_table(results, s):
    names = list(next(iter(results.values()))['per_pose'][s])
    lines = ['| Pose | ' + ' | '.join(m.split(' ')[0] for m in results) + ' |',
             '|---|' + '---:|' * len(results)]
    for p in names:
        lines.append('| %s | ' % p + ' | '.join('%.2f' % results[m]['per_pose'][s][p]['mean_cm']
                                               for m in results) + ' |')
    return '\n'.join(lines)


def main():
    quick = '--quick' in sys.argv
    os.makedirs(OUT, exist_ok=True)
    variants = {'knielang': (0.42, 0.30), 'maxi': (0.10, 0.42)}
    all_res, all_info, figs = {}, {}, []
    for v, (hy, hr) in variants.items():
        print('== %s ==' % v)
        res, info, arr = run_variant(v, hy, hr, quick)
        all_res[v], all_info[v] = res, info
        figs += plots(v, res, arr)
    with open(os.path.join(OUT, 'metrics.json'), 'w') as f:
        json.dump({'results': all_res, 'info': all_info}, f, indent=1)
    md = ['# Ergebnisse: Posen-Fit vs. v0.4 (automatisch erzeugt)', '',
          'Erzeugt von `experiments/sl_dress_study.py`%s. Fehler in cm, SL-Maßstab (Meter).' %
          (' --quick' if quick else ''),
          'Zielformen sind ein **skriptbasierter Proxy** für manuell korrigierte Posen, keine echten Sculpts.',
          '']
    for v in variants:
        i = all_info[v]
        md += ['## Kleid „%s“ (%d Vertices, %.0f s)' % (v, i['vertices'], i['seconds']), '']
        for s, title in (('train', 'Trainingsposen (zur Optimierung benutzt)'),
                         ('interp', 'Ungesehene Posen im Trainingsbereich'),
                         ('extreme', 'Ungesehene Extremposen')):
            md += ['### %s' % title, '', table(all_res[v], s), '']
        md += ['### Extremposen einzeln (Ø Fehler cm)', '', per_pose_table(all_res[v], 'extreme'), '',
               '![Fehler](fehler_%s.png)' % v, '', '![Silhouetten](silhouetten_%s.png)' % v, '',
               'B-Reglerwerte: `%s`; Ruheform-Offset D: max %.2f cm, Ø %.2f cm.' % (
                   all_res[v]['B v0.4 Regler optimiert']['params'], i['rest_offset_D_max_cm'],
                   i['rest_offset_D_mean_cm']), '']
    with open(os.path.join(OUT, 'report.md'), 'w') as f:
        f.write('\n'.join(md))
    print('written', OUT)


if __name__ == '__main__':
    main()
