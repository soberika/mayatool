# -*- coding: utf-8 -*-
"""mcd. Fit Solver 0.1 — poses, clipping measurement and weight fitting.

Stage 1 (docs/konzept_kleidung_und_bewegung.md). Runs OUTSIDE Maya on a file
from mcd_fit_export (read with mcd_fit_data). Needs numpy and scipy.

Pipeline:
  1. Rig: the exported skeleton in its CURRENT pose is the rest pose. Poses
     are rotations about world axes at joint pivots, applied by forward
     kinematics (collision volumes follow their parent bones).
  2. Both meshes are skinned exactly like Maya's skinCluster:
         p = sum_j w_j * (p_orig * geomMatrix * bindPreMatrix_j * matrix_j)
     The body's pre-skin shape is recovered per vertex by inverting its
     blended matrix when the export has no orig shape.
  3. Clipping: signed distance of garment vertices to the posed body
     (nearest body vertex and its normal; negative = inside).
  4. Fit: per-vertex weights (max 4, non-negative, sum 1) that move garment
     vertices out of the body in TRAINING poses, stay close to the original
     weights and are smoothed over mesh edges (slit edges stay separate,
     because only real edges are used). Optionally a small outward rest
     offset per vertex. Test poses are never used for fitting.

The world axes are detected from the skeleton (up, left, forward).
"""

import math

import numpy as np
from scipy.optimize import nnls
from scipy.spatial import cKDTree

VERSION = '0.1'


# --- small matrix helpers (Maya row-vector convention) -----------------------------
def rotation_row(axis, degrees):
    """4x4 row-vector rotation (p' = p @ R) about a unit axis through the origin."""
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    a = math.radians(degrees)
    x, y, z = axis
    c, s, t = math.cos(a), math.sin(a), 1 - math.cos(a)
    col = np.array([[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
                    [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
                    [t * x * z - s * y, t * y * z + s * x, t * z * z + c]])
    m = np.eye(4)
    m[:3, :3] = col.T
    return m


def about_pivot(rot, pivot):
    m = np.eye(4)
    m[3, :3] = -np.asarray(pivot)
    back = np.eye(4)
    back[3, :3] = pivot
    return m @ rot @ back


# --- rig ------------------------------------------------------------------------------
class Rig:
    def __init__(self, data):
        self.names = [j['name'] for j in data.joints]
        self.paths = [j['path'] for j in data.joints]
        self.index = {}
        for i, name in enumerate(self.names):
            self.index.setdefault(name, i)
        path_index = {p: i for i, p in enumerate(self.paths)}
        self.parent = [path_index.get(j['parent']) for j in data.joints]
        self.rest = np.stack([np.asarray(j['world_matrix'], float).reshape(4, 4)
                              for j in data.joints])
        self.order = sorted(range(len(self.names)), key=lambda i: self.paths[i].count('|'))
        self.axes = self._detect_axes()

    def position(self, name):
        return self.rest[self.index[name], 3, :3].copy()

    def _detect_axes(self):
        up = self.position('mPelvis') - (self.position('mAnkleLeft')
                                         + self.position('mAnkleRight')) / 2
        left = self.position('mHipLeft') - self.position('mHipRight')
        up /= np.linalg.norm(up)
        left -= up * left.dot(up)
        left /= np.linalg.norm(left)
        forward = np.cross(left, up)          # SL: left = up x forward
        return {'up': up, 'left': left, 'forward': forward}

    def pose(self, rotations):
        """rotations: {joint: [(axis_name or vector, degrees), ...]} in world axes
        at rest. Returns posed world matrices (n, 4, 4)."""
        total = [None] * len(self.names)
        for i in self.order:
            parent = self.parent[i]
            up_total = total[parent] if parent is not None else np.eye(4)
            local = np.eye(4)
            for axis, degrees in rotations.get(self.names[i], ()):
                vector = self.axes[axis] if isinstance(axis, str) else axis
                local = local @ rotation_row(vector, degrees)
            own = about_pivot(local, self.rest[i, 3, :3])
            total[i] = own @ up_total
        return np.stack([self.rest[i] @ total[i] for i in range(len(self.names))])


# --- skinned meshes ----------------------------------------------------------------
class Skin:
    """Precomputed per-influence rest products for fast posing."""

    def __init__(self, mesh, rig):
        self.mesh = mesh
        self.joint = [rig.index[n] for n in mesh.influences]
        _normalize_rows(mesh)
        if mesh.points_orig is not None:
            base = np.hstack([mesh.points_orig, np.ones((mesh.count, 1))]) @ mesh.geom_matrix
        else:
            base = self._recover_orig(mesh)
        self.base = base                                  # (v, 4) points * geomMatrix
        self.bind = mesh.bind_pre                         # (j, 4, 4)
        self.weights = mesh.weights.copy()
        self.faces = mesh.faces
        self.edges = _edges(mesh.faces)
        self.tris = _triangulate(mesh.faces)

    @staticmethod
    def _recover_orig(mesh):
        """Invert each vertex's blended skin matrix (exact for linear blend skinning)."""
        blend = np.einsum('vj,jab->vab', mesh.weights,
                          np.einsum('jab,jbc->jac', mesh.bind_pre, mesh.matrix))
        homog = np.hstack([mesh.points_world, np.ones((mesh.count, 1))])
        # Unweighted vertices (some dev-kit bodies have a few at the head) have
        # a singular blend; they keep their world position as rest.
        det = np.abs(np.linalg.det(blend[:, :3, :3]))
        ok = det > 1e-9 * max(det.max(), 1e-30)
        out = homog.copy()
        out[ok] = np.einsum('va,vab->vb', homog[ok], np.linalg.inv(blend[ok]))
        return out

    def influence_points(self, world, vertices=None, offsets=None):
        """(v, j, 3): each vertex transformed rigidly by every influence."""
        base = self.base if vertices is None else self.base[vertices]
        if offsets is not None:
            base = base.copy()
            base[:, :3] += offsets if vertices is None else offsets[vertices]
        mats = np.einsum('jab,jbc->jac', self.bind, world[self.joint])
        return np.einsum('va,jab->vjb', base, mats)[:, :, :3]

    def deform(self, world, weights=None, offsets=None):
        weights = self.weights if weights is None else weights
        mats = np.einsum('jab,jbc->jac', self.bind, world[self.joint])
        base = self.base
        if offsets is not None:
            base = base.copy()
            base[:, :3] += offsets
        out = np.zeros((len(base), 3))
        for j in range(len(self.joint)):
            idx = np.nonzero(weights[:, j])[0]
            if len(idx):
                out[idx] += weights[idx, j, None] * (base[idx] @ mats[j])[:, :3]
        return out


def _normalize_rows(mesh):
    """Rows that do not sum to 1 (skinCluster with post normalization, as in some
    dev-kit bodies) are normalized like Maya does at deform time. Unweighted
    vertices take the weights of their nearest weighted vertex."""
    sums = mesh.weights.sum(axis=1)
    empty = sums <= 1e-6
    if empty.any() and (~empty).any():
        _, near = cKDTree(mesh.points_world[~empty]).query(mesh.points_world[empty])
        mesh.weights[empty] = mesh.weights[~empty][near]
        sums = mesh.weights.sum(axis=1)
    mesh.weights /= np.maximum(sums, 1e-12)[:, None]


def _triangulate(faces):
    tris = []
    for f in faces:
        for i in range(1, len(f) - 1):
            tris.append((f[0], f[i], f[i + 1]))
    return np.asarray(tris, dtype=np.int64)


def _edges(faces):
    edges = set()
    for f in faces:
        for i, a in enumerate(f):
            b = f[(i + 1) % len(f)]
            edges.add((a, b) if a < b else (b, a))
    return np.asarray(sorted(edges), dtype=np.int64)


def vertex_normals(points, tris):
    n = np.cross(points[tris[:, 1]] - points[tris[:, 0]], points[tris[:, 2]] - points[tris[:, 0]])
    out = np.zeros_like(points)
    for k in range(3):
        np.add.at(out, tris[:, k], n)
    length = np.linalg.norm(out, axis=1, keepdims=True)
    return out / np.maximum(length, 1e-12)


class BodySurface:
    def __init__(self, points, tris):
        self.points = points
        self.normals = vertex_normals(points, tris)
        self.tree = cKDTree(points)

    def signed_distance(self, query, k=4):
        """Approximate signed distance: average over the k nearest body vertices
        of the offset along their normals (negative = inside the body)."""
        dist, idx = self.tree.query(query, k=k)
        offsets = query[:, None, :] - self.points[idx]
        along = np.einsum('vkc,vkc->vk', offsets, self.normals[idx])
        w = 1.0 / np.maximum(dist, 1e-6)
        return (along * w).sum(1) / w.sum(1), dist[:, 0], self.normals[idx[:, 0]]


# --- poses ------------------------------------------------------------------------------
def leg(side, flex=0.0, knee=0.0, adduct=0.0, twist=0.0):
    """Rotations for one leg. flex > 0: thigh forward; knee > 0: shin back;
    adduct > 0: thigh toward the other leg; twist > 0: knee turns inward."""
    hip, kn = ('mHipLeft', 'mKneeLeft') if side == 'L' else ('mHipRight', 'mKneeRight')
    s = 1.0 if side == 'L' else -1.0
    # Left axis rotation by -a swings 'down' toward forward (see tests).
    out = {hip: [('left', -flex), ('forward', -s * adduct), ('up', -s * twist)],
           kn: [('left', knee)]}
    return out


def merge(*parts):
    out = {}
    for part in parts:
        for k, v in part.items():
            out.setdefault(k, []).extend(v)
    return out


def standard_poses():
    """(name, set, rotations). 'train' poses fit the weights, 'test' poses only judge."""
    return [
        ('Schritt L 25', 'train', merge(leg('L', 25, 10), leg('R', -15, 15))),
        ('Schritt R 25', 'train', merge(leg('R', 25, 10), leg('L', -15, 15))),
        ('Beine gekreuzt stehend', 'train', merge(leg('L', 10, 5, 15), leg('R', 0, 0, 5))),
        ('Sitzen', 'train', merge(leg('L', 85, 85), leg('R', 85, 85))),
        ('Bein ueber Bein leicht', 'train', merge(leg('L', 90, 80, 12), leg('R', 85, 85))),
        ('Schritt L 40', 'test', merge(leg('L', 40, 20), leg('R', -25, 25))),
        ('Schritt R 40', 'test', merge(leg('R', 40, 20), leg('L', -25, 25))),
        ('Ausfallschritt L', 'test', merge(leg('L', 55, 50), leg('R', -30, 10))),
        ('Bein ueber Bein', 'test', merge(leg('L', 95, 70, 25, 5), leg('R', 85, 85))),
        ('Bein ueber Bein R', 'test', merge(leg('R', 95, 70, 25, 5), leg('L', 85, 85))),
        ('Beine stark gekreuzt', 'test', merge(leg('L', 15, 5, 25), leg('R', 0, 0, 10))),
    ]


# --- measurement ----------------------------------------------------------------------
def measure(body_skin, dress_skin, world, weights=None, offsets=None, tol=0.2):
    body_pts = body_skin.deform(world)
    dress_pts = dress_skin.deform(world, weights, offsets)
    surface = BodySurface(body_pts, body_skin.tris)
    signed, _, _ = surface.signed_distance(dress_pts)
    rest_len = dress_skin._rest_lengths
    e = dress_skin.edges
    lengths = np.linalg.norm(dress_pts[e[:, 0]] - dress_pts[e[:, 1]], axis=1)
    strain = np.abs(lengths / np.maximum(rest_len, 1e-9) - 1.0)
    inside = signed < -tol
    return {
        'clip_frac': float(inside.mean()),
        'clip_p99': float(max(0.0, -np.percentile(signed, 1))),
        'clip_max': float(max(0.0, -signed.min())),
        'strain_p95': float(np.percentile(strain, 95)),
        'strain_p99': float(np.percentile(strain, 99)),
        'signed': signed, 'strain': strain, 'body': body_pts, 'dress': dress_pts,
    }


def prepare(data):
    rig = Rig(data)
    body = Skin(data.body, rig)
    dress = Skin(data.dress, rig)
    rest = dress.deform(rig.rest)
    e = dress.edges
    dress._rest_lengths = np.linalg.norm(rest[e[:, 0]] - rest[e[:, 1]], axis=1)
    return rig, body, dress


# --- fitting --------------------------------------------------------------------------
def candidate_influences(dress, body, rig, max_candidates=6):
    """Per garment vertex: its own influences plus the strongest influences of
    the nearest body vertices (by joint name), mapped into the garment's list."""
    rest_dress = dress.deform(rig.rest)
    rest_body = body.deform(rig.rest)
    _, near = cKDTree(rest_body).query(rest_dress, k=3)
    name_to_dress = {n: i for i, n in enumerate(dress.mesh.influences)}
    body_names = body.mesh.influences
    cands = []
    for v in range(dress.mesh.count):
        score = {}
        for j in np.nonzero(dress.weights[v])[0]:
            score[j] = score.get(j, 0.0) + 1.0 + dress.weights[v, j]
        for b in near[v]:
            for bj in np.nonzero(body.weights[b])[0]:
                dj = name_to_dress.get(body_names[bj])
                if dj is not None:
                    score[dj] = score.get(dj, 0.0) + body.weights[b, bj] / 3.0
        ranked = sorted(score, key=lambda j: -score[j])[:max_candidates]
        cands.append(ranked)
    return cands


def fit_weights(rig, body, dress, poses, margin=0.3, keep=0.6, smooth=0.3,
                passes=3, max_influences=4, offset_limit=0.0, rest_weight=3.0,
                progress=print):
    """Fit weights on the training poses. Returns (weights, offsets, history).

    margin: wanted clearance outside the body (scene units; 0.3 = 3 mm in cm).
    keep: pull toward the original weights (higher = closer to the input rig).
    smooth: blend toward the edge-neighbour average after each pass.
    offset_limit: max outward rest offset per vertex (0 = geometry unchanged).
    rest_weight: how strongly new weights must keep the rest shape (the rest
    pose is solved as an extra pose whose target is the original rest shape).
    """
    train = [(name, rig.pose(rot)) for name, kind, rot in poses if kind == 'train']
    weights = dress.weights.copy()
    original = dress.weights.copy()
    offsets = np.zeros((dress.mesh.count, 3))
    cands = candidate_influences(dress, body, rig)
    surfaces = [BodySurface(body.deform(w), body.tris) for _, w in train]
    n = dress.mesh.count
    neighbours = [[] for _ in range(n)]
    for a, b in dress.edges:
        neighbours[a].append(b)
        neighbours[b].append(a)
    history = []
    for it in range(passes):
        # Targets: posed position pushed out of the body to the margin.
        targets, posed = [], []
        active = np.zeros(n, dtype=bool)
        for (name, world), surface in zip(train, surfaces):
            p = dress.deform(world, weights, offsets)
            signed, _, normal = surface.signed_distance(p)
            push = np.clip(margin - signed, 0.0, None)
            active |= push > 1e-4
            targets.append(p + normal * push[:, None])
            posed.append(world)
        history.append({'pass': it, 'active_vertices': int(active.sum())})
        progress('Durchgang %d: %d Vertices clippen in Trainingsposen' % (it + 1, active.sum()))
        idx = np.nonzero(active)[0]
        if not len(idx):
            break
        # Influence positions per active vertex, pose and influence.
        stacks = [dress.influence_points(world, idx, offsets) for world in posed]
        rest_stack = dress.influence_points(rig.rest, idx, offsets)
        rest_target = dress.deform(rig.rest, original, offsets)
        new_rows = weights.copy()
        for k, v in enumerate(idx):
            cj = cands[v]
            a_rows = []
            b_rows = []
            for p_i in range(len(train)):
                pts = stacks[p_i][k][cj]               # (c, 3)
                a_rows.append(pts.T)                   # 3 x c
                b_rows.append(targets[p_i][v])
            a_rows.append(rest_weight * rest_stack[k][cj].T)
            b_rows.append(rest_weight * rest_target[v])
            A = np.vstack(a_rows)
            b = np.concatenate(b_rows)
            scale = max(np.abs(A).max(), 1.0)
            # keep: stay near original weights; sum-to-one as a heavy row.
            reg = math.sqrt(keep) * scale * np.eye(len(cj))
            A_full = np.vstack([A, reg, 50.0 * scale * np.ones((1, len(cj)))])
            b_full = np.concatenate([b, reg @ original[v, cj], [50.0 * scale]])
            w, _ = nnls(A_full, b_full, maxiter=200)
            row = np.zeros(weights.shape[1])
            row[cj] = w
            new_rows[v] = _cap(row, max_influences)
        weights = new_rows
        weights = _smooth(weights, neighbours, active, smooth, max_influences)
        if offset_limit > 0.0:
            offsets = _rest_offsets(rig, body, dress, weights, train, surfaces, margin,
                                    offset_limit, offsets)
    return weights, offsets, history


def _cap(row, maximum):
    order = np.argsort(-row)
    out = np.zeros_like(row)
    keep = order[:maximum]
    out[keep] = np.clip(row[keep], 0.0, None)
    total = out.sum()
    if total <= 1e-12:
        return row / max(row.sum(), 1e-12)
    return out / total


def _smooth(weights, neighbours, active, amount, maximum):
    if amount <= 0.0:
        return weights
    out = weights.copy()
    grow = set(np.nonzero(active)[0])
    for v in list(grow):
        grow.update(neighbours[v])
    for v in grow:
        nb = neighbours[v]
        if nb:
            avg = weights[nb].mean(axis=0)
            out[v] = _cap((1 - amount) * weights[v] + amount * avg, maximum)
    return out


def smooth_field(values, edges, iterations=10, amount=0.5):
    """Laplacian smoothing of a per-vertex field along mesh edges."""
    degree = np.bincount(edges.ravel(), minlength=len(values)).astype(float)
    out = values.astype(float).copy()
    for _ in range(iterations):
        acc = np.zeros_like(out)
        np.add.at(acc, edges[:, 0], out[edges[:, 1]])
        np.add.at(acc, edges[:, 1], out[edges[:, 0]])
        avg = np.where(degree > 0, acc / np.maximum(degree, 1.0), out)
        out = (1 - amount) * out + amount * avg
    return out


def offsets_amount(offsets, rig, dress, weights):
    """World-space length of pre-skin offsets in the rest pose."""
    if not np.any(offsets):
        return np.zeros(len(offsets))
    blend = np.einsum('vj,jab->vab', weights,
                      np.einsum('jab,jbc->jac', dress.bind, rig.rest[dress.joint]))
    return np.linalg.norm(np.einsum('va,vab->vb', offsets, blend[:, :3, :3]), axis=1)


def _rest_offsets(rig, body, dress, weights, train, surfaces, margin, limit, offsets):
    """Small outward rest offset where clipping remains. 'Outward' is the body's
    surface normal at the nearest body point in the rest pose: garment normals
    can be noisy or flipped, the body's are smooth."""
    rest = dress.deform(rig.rest, weights)
    _, _, normals = BodySurface(body.deform(rig.rest), body.tris).signed_distance(rest, k=8)
    need = np.zeros(dress.mesh.count)
    for (name, world), surface in zip(train, surfaces):
        p = dress.deform(world, weights, offsets)
        signed, _, _ = surface.signed_distance(p)
        need = np.maximum(need, margin - signed)
    # Offsets accumulate over passes: 'need' is measured WITH the current
    # offsets, so it is the additional amount still missing.
    previous = offsets_amount(offsets, rig, dress, weights)
    extra = np.clip(need, 0.0, limit)
    # Smooth over mesh edges (plain averaging) so the rest shape changes as a
    # gentle swelling, not as single raised vertices.
    extra = smooth_field(extra, dress.edges, iterations=20)
    amount = np.clip(previous + extra, 0.0, limit)
    # Rest offsets are in pre-skin space; with near-rigid rest blend this is
    # close to world space. Converted through each vertex's rest blend matrix.
    blend = np.einsum('vj,jab->vab', weights,
                      np.einsum('jab,jbc->jac', dress.bind, rig.rest[dress.joint]))
    world_offset = normals * amount[:, None]
    inv = np.linalg.inv(blend[:, :3, :3])
    return np.einsum('va,vab->vb', world_offset, inv)


# --- result file for mcd_fit_apply (Maya) ------------------------------------------------
def save_result(path, data, dress, weights, offsets, settings, report):
    """Write weights (sparse, by influence name) and pre-skin offsets in the
    dress's OBJECT space, ready for mcd_fit_apply.py. No body data is stored."""
    import gzip
    import json
    g_inv = np.linalg.inv(dress.mesh.geom_matrix[:3, :3])
    obj_offsets = offsets @ g_inv
    rows = []
    for v in range(dress.mesh.count):
        nz = np.nonzero(weights[v] > 1e-6)[0]
        rows.append([[int(j), round(float(weights[v, j]), 6)] for j in nz])
    payload = {
        'format': 'mcd-fit-result', 'format_version': 1, 'solver': 'mcd_fit_solver %s' % VERSION,
        'dress_name': dress.mesh.name, 'vertex_count': int(dress.mesh.count),
        'influences': list(dress.mesh.influences), 'weights': rows,
        'offsets_object': [round(float(c), 5) for c in obj_offsets.reshape(-1)],
        'settings': settings, 'report': report,
    }
    with gzip.open(path, 'wt', encoding='utf-8') as handle:
        json.dump(payload, handle, separators=(',', ':'))
