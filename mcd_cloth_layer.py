# -*- coding: utf-8 -*-
"""mcd. Cloth Layer 0.1 — state cloth poses on spare Bento bones (stage 2).

Solves, together with the garment's weights, one cloth pose per avatar state
(stand / walk / sit) on HindLimb bones, so that e.g. the back hem gives the
calf room while walking and the seat crease opens while sitting. Runs OUTSIDE
Maya on a mcd_fit_export file. See docs/konzept_kleidung_und_bewegung.md.

What SL plays at runtime (tested in stage 0): one looped .anim per state that
keys ONLY the cloth bones; lsl/mcd_cloth_state.lsl switches them by state.
The wearer's AO keeps all body bones.

Model:
  * Cloth bones hang from mPelvis (via mHindLimbsRoot). None of our poses
    moves the pelvis, so in every pose a cloth bone's world matrix is its rest
    matrix translated by the current state's offset t_s,k.
  * Per state, the offsets are found by least squares on the clipping
    residuals of that state's training poses; per vertex, the weights (now
    including cloth bones) by the stage 1 solver over ALL states' poses.
  * Translations only (no rotation) in this version: simple, robust, and
    exactly representable as SL position keys.
"""

import numpy as np

import mcd_fit_solver as fs
import mcd_sl_anim as sa

VERSION = '0.1'
CLOTH_BONES = ('mHindLimb1Left', 'mHindLimb2Left', 'mHindLimb1Right', 'mHindLimb2Right')


def state_poses():
    """{state: [(name, 'train'|'test', rotations)]}; 'stand' keeps the closed line."""
    leg, merge, gait = fs.leg, fs.merge, fs.gait_pose
    return {
        'stand': [
            ('Ruhe', 'train', {}),
            ('Beine gekreuzt stehend', 'train', merge(leg('L', 10, 5, 15), leg('R', 0, 0, 5))),
            ('Standbein R', 'train', merge(leg('L', 8, 15, 5), leg('R', 0, 0))),
            ('Beine stark gekreuzt', 'test', merge(leg('L', 15, 5, 25), leg('R', 0, 0, 10))),
        ],
        'walk': [
            ('Gehen 0%', 'train', gait(0)), ('Gehen 30%', 'train', gait(30)),
            ('Gehen 60%', 'train', gait(60)), ('Gehen 70%', 'train', gait(70)),
            ('Gehen 85%', 'train', gait(85)), ('Gehen 20%', 'train', gait(20)),
            ('Gehen 15%', 'test', gait(15)), ('Gehen 50% gross', 'test', gait(50, 1.25)),
            ('Gehen 65% gross', 'test', gait(65, 1.25)),
            ('Gehen 75% gross', 'test', gait(75, 1.25)),
            ('Schritt L 40', 'test', merge(leg('L', 40, 20), leg('R', -25, 25))),
        ],
        'sit': [
            ('Sitzen', 'train', merge(leg('L', 85, 85), leg('R', 85, 85))),
            ('Bein ueber Bein leicht', 'train', merge(leg('L', 90, 80, 12), leg('R', 85, 85))),
            ('Bein ueber Bein', 'test', merge(leg('L', 95, 70, 25, 5), leg('R', 85, 85))),
            ('Bein ueber Bein R', 'test', merge(leg('R', 95, 70, 25, 5), leg('L', 85, 85))),
        ],
    }


def add_cloth_influences(rig, dress, bones=CLOTH_BONES):
    """Append cloth bones to the garment's skin with bind matrices consistent
    with its existing bind (taken from mPelvis, which is unposed at rest)."""
    pelvis = dress.mesh.influences.index('mPelvis')
    pelvis_joint = dress.joint[pelvis]
    s = dress.bind[pelvis] @ rig.rest[pelvis_joint]
    new_bind = []
    for name in bones:
        if name in dress.mesh.influences:
            continue
        if name not in rig.index:
            raise ValueError('%s fehlt im Skelett.' % name)
        j = rig.index[name]
        dress.joint.append(j)
        dress.mesh.influences.append(name)
        new_bind.append(s @ np.linalg.inv(rig.rest[j]))
    if new_bind:
        dress.bind = np.concatenate([dress.bind, np.stack(new_bind)])
        dress.weights = np.hstack([dress.weights, np.zeros((dress.mesh.count, len(new_bind)))])
        dress.mesh.weights = dress.weights
    return [dress.mesh.influences.index(b) for b in bones]


def state_world(rig, rotations, offsets):
    """Posed world matrices with cloth bones translated by {bone: (dx, dy, dz)}."""
    world = rig.pose(rotations)
    for bone, t in offsets.items():
        world[rig.index[bone], 3, :3] += t
    return world


def cloth_slots(rig, dress, weights, cloth_cols, threshold=0.01):
    """Which cloth bone (column) each vertex may use, or -1.

    Only skirt vertices below the hips whose current row has at most 3
    influences above 'threshold' get ONE cloth bone: the free 4th slot. A cloth
    bone never pushes a leg bone or collision volume out of the 4-influence
    limit, because that drop differs between neighbours and tears the mesh.
    Above the knee the upper cloth bone, below it the lower one, by side.
    """
    rest = dress.deform(rig.rest)
    up, left = rig.axes['up'], rig.axes['left']
    hip_y = rig.position('mHipLeft').dot(up)
    knee_y = rig.position('mKneeLeft').dot(up)
    centre = rig.position('mPelvis')
    l1, l2, r1, r2 = cloth_cols
    slots = np.full(dress.mesh.count, -1)
    used = (weights > threshold).sum(1)
    for v in range(dress.mesh.count):
        y = rest[v].dot(up)
        if y >= hip_y or used[v] > 3:
            continue
        side = (rest[v] - centre).dot(left) >= 0
        if y >= knee_y:
            slots[v] = l1 if side else r1
        else:
            slots[v] = l2 if side else r2
    return slots


def cloth_candidates(rig, body, dress, weights, slots, threshold=0.01):
    """Each vertex keeps exactly its current influences, plus its cloth slot."""
    cands = []
    for v in range(dress.mesh.count):
        own = [int(j) for j in np.nonzero(weights[v] > threshold)[0]]
        if slots[v] >= 0:
            own.append(int(slots[v]))
        cands.append(own)
    return cands


def solve_offsets(rig, body, dress, weights, rest_offsets, poses, current, margin,
                  limit, damping):
    """Least-squares translation per cloth bone for one state's training poses."""
    cols = [dress.mesh.influences.index(b) for b in CLOTH_BONES]
    k = len(cols)
    ata = damping * np.eye(3 * k)
    atb = np.zeros(3 * k)
    for name, kind, rot in poses:
        if kind != 'train':
            continue
        world = state_world(rig, rot, current)
        p = dress.deform(world, weights, rest_offsets)
        surface = fs.BodySurface(body.deform(world), body.tris)
        signed, _, normal = surface.signed_distance(p)
        push = np.clip(margin - signed, 0.0, None)
        w = weights[:, cols]                                   # (v, k)
        use = (w.sum(1) > 1e-4)
        if not use.any():
            continue
        r = normal[use] * push[use, None]                      # wanted displacement
        wu = w[use]
        # Displacement of vertex v = sum_k w_vk * t_k  (LBS is linear in translation).
        wtw = wu.T @ wu                                        # (k, k)
        for a in range(3):
            ata[a::3, a::3] += wtw
            atb[a::3] += wu.T @ r[:, a]
    delta = np.linalg.solve(ata, atb).reshape(k, 3)
    out = {}
    for i, bone in enumerate(CLOTH_BONES):
        t = np.asarray(current.get(bone, np.zeros(3))) + delta[i]
        length = np.linalg.norm(t)
        out[bone] = t * (limit / length) if length > limit else t
    return out


def solve(rig, body, dress, stage1_weights, stage1_offsets, iterations=4, margin=0.5,
          limit=6.0, damping=50.0, keep=0.1, seed_share=0.3, progress=print):
    """Alternate cloth offsets per state and garment weights over all states."""
    cloth_cols = add_cloth_influences(rig, dress)
    weights = np.hstack([stage1_weights, np.zeros((dress.mesh.count,
                                                   len(dress.mesh.influences)
                                                   - stage1_weights.shape[1]))])
    # The solver stays close to the STAGE 1 weights (no cloth share): cloth
    # weights must earn their place in the poses, the seed only starts them.
    reference = weights.copy()
    # Drop tiny weights first so slots are judged on real influences.
    weights = np.where(weights > 0.01, weights, 0.0)
    weights /= weights.sum(1, keepdims=True)
    reference = weights.copy()
    slots = cloth_slots(rig, dress, weights, cloth_cols)
    cands = cloth_candidates(rig, body, dress, weights, slots)
    editable = slots >= 0
    states = state_poses()
    up = rig.axes['up']
    back = -rig.axes['forward']
    offsets = {
        'stand': {b: np.zeros(3) for b in CLOTH_BONES},
        'walk': {b: (3.0 * back if '2' in b else 1.0 * back) for b in CLOTH_BONES},
        'sit': {b: (2.0 * back + 1.0 * up if '1' in b else 2.0 * back) for b in CLOTH_BONES},
    }
    # Seed a small cloth share in the free slot of vertices behind the body.
    rest = dress.deform(rig.rest)
    centre_z = rig.position('mPelvis').dot(rig.axes['forward'])
    behind = rest.dot(rig.axes['forward']) < centre_z
    for v in np.nonzero(editable & behind)[0]:
        weights[v] *= 1.0 - seed_share
        weights[v, slots[v]] += seed_share
    history = []
    for it in range(iterations):
        worlds = []
        for state, poses in states.items():
            worlds += [('%s/%s' % (state, n), state_world(rig, r, offsets[state]))
                       for n, k, r in poses if k == 'train']
        weights, rest_offsets, _ = fs.fit_weights(
            rig, body, dress, None, worlds=worlds, init_weights=weights,
            init_offsets=stage1_offsets, reference=reference, candidates=cands,
            margin=margin, keep=keep, smooth=0.0, passes=2, offset_limit=0.0,
            editable=editable, progress=lambda m: None)
        # Smooth only the cloth share, only where a slot exists.
        weights = smooth_cloth_share(dress, weights, cloth_cols, editable=editable)
        stage1_offsets = rest_offsets
        for state in ('walk', 'sit'):
            offsets[state] = solve_offsets(rig, body, dress, weights, stage1_offsets,
                                           states[state], offsets[state], margin, limit,
                                           damping)
        history.append({s: {b: np.round(t, 2).tolist() for b, t in o.items()}
                        for s, o in offsets.items()})
        progress('Runde %d: walk %s | sit %s' % (
            it + 1, {b[-8:]: np.round(t, 1).tolist() for b, t in offsets['walk'].items()},
            {b[-8:]: np.round(t, 1).tolist() for b, t in offsets['sit'].items()}))
    return weights, stage1_offsets, offsets, history


# --- SL animations ---------------------------------------------------------------------
def maya_to_sl(vector, rig, scale=0.01):
    """Maya world vector -> SL axes (X forward, Y left, Z up), metres."""
    v = np.asarray(vector, dtype=float)
    return np.array([v.dot(rig.axes['forward']), v.dot(rig.axes['left']),
                     v.dot(rig.axes['up'])]) * scale


def state_anim(rig, offsets, priority=1, ease=0.5, duration=1.0):
    """A looped hold that places every cloth bone at default + its offset.

    SL position keys are ABSOLUTE local positions relative to the parent, so a
    child's key is its default local position plus (own offset - parent offset).
    """
    local = {}
    for bone in CLOTH_BONES:
        parent = sa.CLOTH_BONES[bone][0]
        own = maya_to_sl(offsets.get(bone, np.zeros(3)), rig)
        par = maya_to_sl(offsets.get(parent, np.zeros(3)), rig) if parent in offsets \
            else np.zeros(3)
        local[bone] = tuple(own - par)
    return sa.make_hold(list(CLOTH_BONES), offsets=local, duration=duration,
                        priority=priority, ease=ease)


def limit_rest_change(rig, dress, weights, reference, offsets, tolerance=0.2,
                      smooth_iterations=10):
    """Blend new weights back toward 'reference' wherever they would move the
    garment's REST shape by more than 'tolerance' (scene units).

    Why: the neutral Maya pose differs from the bind pose (e.g. legs 5 deg
    apart), so moving weight from a leg bone to a pelvis-rigid cloth bone also
    moves the rest shape. At the hem, a metre below the hip, that is several
    centimetres and tears the hem. Rest deformation is linear in the weights,
    so the allowed blend factor per vertex is tolerance / full displacement.
    The factor field is smoothed (only ever lowered) so neighbours agree.
    """
    a = dress.deform(rig.rest, reference, offsets)
    b = dress.deform(rig.rest, weights, offsets)
    full = np.linalg.norm(b - a, axis=1)
    alpha = np.clip(tolerance / np.maximum(full, 1e-9), 0.0, 1.0)
    e = dress.edges
    for _ in range(smooth_iterations):
        neighbour_min = alpha.copy()
        np.minimum.at(neighbour_min, e[:, 0], alpha[e[:, 1]])
        np.minimum.at(neighbour_min, e[:, 1], alpha[e[:, 0]])
        alpha = 0.5 * alpha + 0.5 * neighbour_min
    blended = (1.0 - alpha)[:, None] * reference + alpha[:, None] * weights
    return np.array([fs._cap(row, 4) for row in blended]), alpha


def smooth_cloth_share(dress, weights, cols, iterations=20, editable=None):
    """Laplacian-smooth the total cloth share over mesh edges. Vertices without
    a slot are fixed at 0, so the share fades out toward them. Each vertex
    keeps its own single cloth bone; its other weights are rescaled."""
    out = weights.copy()
    share = out[:, cols].sum(1)
    mask = np.ones(len(share), bool) if editable is None else editable
    e = dress.edges
    degree = np.bincount(e.ravel(), minlength=len(share)).astype(float)
    s = np.where(mask, share, 0.0)
    for _ in range(iterations):
        acc = np.zeros_like(s)
        np.add.at(acc, e[:, 0], s[e[:, 1]])
        np.add.at(acc, e[:, 1], s[e[:, 0]])
        avg = np.where(degree > 0, acc / np.maximum(degree, 1.0), s)
        s = np.where(mask, 0.5 * s + 0.5 * avg, 0.0)
    for v in np.nonzero(mask)[0]:
        row = out[v]
        cloth = row[cols]
        if cloth.sum() > 1e-9:
            direction = cloth / cloth.sum()
        else:
            continue
        others = row.copy()
        others[cols] = 0.0
        total = others.sum()
        if total <= 1e-9:
            continue
        out[v] = others * ((1.0 - s[v]) / total)
        out[v, cols] = direction * s[v]
    return out


def edge_strain_report(rig, dress, weights, offsets, world, region=None):
    """Max and 99th percentile edge strain against the original rest shape."""
    rest = dress.deform(rig.rest)
    p = dress.deform(world, weights, offsets)
    e = dress.edges
    if region is not None:
        e = e[region[e[:, 0]]]
    l0 = np.linalg.norm(rest[e[:, 0]] - rest[e[:, 1]], axis=1)
    keep = l0 > 0.05                       # ignore degenerate (< 0.5 mm) edges
    l1 = np.linalg.norm(p[e[keep, 0]] - p[e[keep, 1]], axis=1)
    s = np.abs(l1 / l0[keep] - 1.0)
    return float(np.percentile(s, 99)), float(s.max())


# --- version 2: smooth cloth share on top of fixed stage 1 weights ------------------
FIELD_BONES = ('mHindLimb1Left', 'mHindLimb1Right')


def solve_field(rig, body, dress, stage1_weights, stage1_offsets, share_max=0.3,
                margin=0.5, limit=6.0, damping=50.0, diffusion=60, iterations=3):
    """Robust stage 2: stage 1 weights stay as they are; a SMOOTH scalar field
    s (0..share_max) blends each skirt vertex toward ONE cloth bone on its
    side, in its free 4th slot. Left and right cloth bones always get the SAME
    translation per state, so the centre back cannot tear.

        w = (1 - s) * w_stage1 + s * e_cloth

    Per-vertex solving is avoided on purpose: independent per-vertex weights are
    noisy and, with scaled collision volumes, tear neighbouring vertices apart.
    Returns (weights, offsets_per_state {state: {bone: t}}, share).
    """
    for name in FIELD_BONES:
        if name not in dress.mesh.influences:
            add_cloth_influences(rig, dress, FIELD_BONES)
            break
    n_cols = len(dress.mesh.influences)
    w1 = np.hstack([stage1_weights, np.zeros((dress.mesh.count, n_cols - stage1_weights.shape[1]))])
    w1 = np.where(w1 > 0.01, w1, 0.0)
    w1 /= w1.sum(1, keepdims=True)
    left_col = dress.mesh.influences.index(FIELD_BONES[0])
    right_col = dress.mesh.influences.index(FIELD_BONES[1])
    rest = dress.deform(rig.rest)
    up, left, fwd = rig.axes['up'], rig.axes['left'], rig.axes['forward']
    hip_y = rig.position('mHipLeft').dot(up)
    centre = rig.position('mPelvis')
    free = ((w1 > 0.01).sum(1) <= 3) & (rest.dot(up) < hip_y)
    side_col = np.where((rest - centre).dot(left) >= 0, left_col, right_col)
    states = state_poses()
    # Where would the skirt like to move away from the body? Clipping depth in
    # the walk/sit training poses under stage 1, behind the legs.
    need = np.zeros(dress.mesh.count)
    for state in ('walk', 'sit'):
        for name, kind, rot in states[state]:
            if kind != 'train':
                continue
            world = rig.pose(rot)
            p = dress.deform(world, w1, stage1_offsets)
            signed, _, _ = fs.BodySurface(body.deform(world), body.tris).signed_distance(p)
            need = np.maximum(need, np.clip(margin - signed, 0.0, None))
    seed = np.where(free & (need > 0), 1.0, 0.0)
    field = fs.smooth_field(seed, dress.edges, iterations=diffusion)
    field = np.where(free, field, 0.0)
    for _ in range(diffusion // 3):                # fade to zero at non-free vertices
        field = np.where(free, fs.smooth_field(field, dress.edges, iterations=1), 0.0)
    if field.max() > 0:
        field = field / field.max()
    share = share_max * field

    def blend(s):
        w = w1 * (1.0 - s)[:, None]
        w[np.arange(len(s)), side_col] += s
        return w

    weights = blend(share)
    offsets = {'stand': {b: np.zeros(3) for b in CLOTH_BONES}}
    back = -fwd
    start = {'walk': 3.0 * back, 'sit': 2.0 * back + 1.0 * up}
    for state in ('walk', 'sit'):
        t = start[state].copy()
        for _ in range(iterations):
            t = _symmetric_offset(rig, body, dress, weights, stage1_offsets, states[state],
                                  t, (left_col, right_col), margin, limit, damping)
        offsets[state] = {FIELD_BONES[0]: t, FIELD_BONES[1]: t.copy()}
    return weights, offsets, share


def _symmetric_offset(rig, body, dress, weights, rest_offsets, poses, t, cols, margin,
                      limit, damping):
    ata = damping * np.eye(3)
    atb = np.zeros(3)
    off = {FIELD_BONES[0]: t, FIELD_BONES[1]: t}
    for name, kind, rot in poses:
        if kind != 'train':
            continue
        world = state_world(rig, rot, off)
        p = dress.deform(world, weights, rest_offsets)
        signed, _, normal = fs.BodySurface(body.deform(world), body.tris).signed_distance(p)
        push = np.clip(margin - signed, 0.0, None)
        s = weights[:, cols[0]] + weights[:, cols[1]]
        use = s > 1e-4
        ata += np.eye(3) * float((s[use] ** 2).sum())
        atb += (s[use, None] * normal[use] * push[use, None]).sum(0)
    new = t + np.linalg.solve(ata, atb)
    length = np.linalg.norm(new)
    return new * (limit / length) if length > limit else new


def field_anim(rig, offsets, priority=1, ease=0.5, duration=1.0):
    """State hold for the field version: only mHindLimb1Left/Right are keyed."""
    local = {}
    for bone in FIELD_BONES:
        local[bone] = tuple(maya_to_sl(offsets.get(bone, np.zeros(3)), rig))
    return sa.make_hold(list(FIELD_BONES), offsets=local, duration=duration,
                        priority=priority, ease=ease)
