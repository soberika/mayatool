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


def cloth_candidates(rig, body, dress, cloth_cols):
    """Stage 1 candidates, plus the same-side cloth bones for skirt vertices
    below the hips (the bodice never gets cloth weights)."""
    cands = fs.candidate_influences(dress, body, rig)
    rest = dress.deform(rig.rest)
    hip_y = rig.position('mHipLeft').dot(rig.axes['up'])
    centre = rig.position('mPelvis')
    left = rig.axes['left']
    l1, l2, r1, r2 = cloth_cols
    for v in range(dress.mesh.count):
        if rest[v].dot(rig.axes['up']) >= hip_y:
            continue
        side = (rest[v] - centre).dot(left)
        extra = (l1, l2) if side >= 0 else (r1, r2)
        cands[v] = list(cands[v][:4]) + [c for c in extra if c not in cands[v]]
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
    cands = cloth_candidates(rig, body, dress, cloth_cols)
    states = state_poses()
    up = rig.axes['up']
    back = -rig.axes['forward']
    # Start: walk moves the lower cloth bones back, sit the upper ones back/up.
    offsets = {
        'stand': {b: np.zeros(3) for b in CLOTH_BONES},
        'walk': {b: (3.0 * back if '2' in b else 1.0 * back) for b in CLOTH_BONES},
        'sit': {b: (2.0 * back + 1.0 * up if '1' in b else 2.0 * back) for b in CLOTH_BONES},
    }
    # Seed: give back-skirt vertices below the knee a share of the lower cloth
    # bones, so the offsets have something to act on in the first pass.
    rest = dress.deform(rig.rest)
    knee_y = rig.position('mKneeLeft').dot(up)
    hip_y = rig.position('mHipLeft').dot(up)
    centre_z = rig.position('mPelvis').dot(rig.axes['forward'])
    for v in range(dress.mesh.count):
        y = rest[v].dot(up)
        behind = rest[v].dot(rig.axes['forward']) < centre_z
        if y < hip_y and behind:
            side = (rest[v] - rig.position('mPelvis')).dot(rig.axes['left']) >= 0
            col = cloth_cols[1] if side else cloth_cols[3]
            if y >= knee_y:
                col = cloth_cols[0] if side else cloth_cols[2]
            share = seed_share
            weights[v] *= 1.0 - share
            weights[v, col] += share
            weights[v] = fs._cap(weights[v], 4)
    history = []
    for it in range(iterations):
        worlds = []
        for state, poses in states.items():
            worlds += [('%s/%s' % (state, n), state_world(rig, r, offsets[state]))
                       for n, k, r in poses if k == 'train']
        weights, rest_offsets, _ = fs.fit_weights(
            rig, body, dress, None, worlds=worlds, init_weights=weights,
            init_offsets=stage1_offsets, reference=reference, candidates=cands,
            margin=margin, keep=keep, smooth=0.3, passes=2, offset_limit=0.0,
            progress=lambda m: None)
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
