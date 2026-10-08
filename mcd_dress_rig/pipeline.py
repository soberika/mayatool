# -*- coding: utf-8 -*-
"""M1 pipeline: base mesh weights -> transfer to dress parts -> bind in body bind pose.

Ablauf
  1. Pruefen: Body-Skin, Skeleton-Achsen, Rollen-Joints, Arbeitspose (nur Bericht).
  2. Basis gewichten (Kleid ohne Dicke, in der aktuellen Pose, in der es passt):
     Body-Transfer per Closest Point (ohne Hand/Kopf/Fuss) + Rockfeld unterhalb
     des Rockbeginns, Glaettung nur ueber Mesh-Kanten.
  3. Jedes Kleidteil uebernimmt die Gewichte der Basis per Closest Point
     (passende Basis-Shell, falls eindeutig, sonst die ganze Basis).
  3b. Optional: Rock minimal aufweiten (nur die neuen Kopien, Original bleibt).
  4. Zurueckrechnen in die Bindepose des Bodys (inverses Linear Blend Skinning)
     und Binden mit exakt den bindPreMatrix-Werten des Bodys. Das Rig wird
     dabei NICHT bewegt.
  5. Pruefen: Gewichte (endlich, >= 0, Summe 1, <= 4 Influences) und Form
     (die neue Kopie muss in der aktuellen Pose exakt wie das Original liegen,
     bzw. wie das aufgeweitete Original).

Nur neue Nodes werden erzeugt; Original, Body, Rig und Animation bleiben unveraendert.
"""
from __future__ import division

import collections
import math
import time

from . import core
from . import scene
from .scene import RigError

PROFILES = {
    # Tested in Maya on a long slit dress (walking, hand on hip, leg sideways).
    # Besides the sliders it also sets fields and checkboxes (see ui.py).
    'Kleid mit Schlitz (getestet)': dict(center_width=1.2, center_hold=0.55, leg_follow=0.75, knee_follow=0.6,
                                         outer_follow=0.9, front_follow=0.35, back_hold=0.3,
                                         contact_strength=0.7, sweep_scale=1.0, skirt=True,
                                         leg_contact=1.5, widen=0.0, widen_back=1.0,
                                         smooth_passes=3, upper_smooth=5, sweep_sit=True, sweep_side=True),
    'Kleid mit Schlitz': dict(center_width=1.5, center_hold=0.55, leg_follow=0.75, knee_follow=0.6,
                              outer_follow=0.9, front_follow=0.25, back_hold=0.15, contact_strength=0.9,
                              skirt=True),
    'Enges Kleid': dict(center_width=1.2, center_hold=0.45, leg_follow=0.85, knee_follow=0.7,
                        outer_follow=0.95, front_follow=0.2, back_hold=0.1, contact_strength=0.95,
                        skirt=True),
    'Weites Kleid / Rock': dict(center_width=2.5, center_hold=0.7, leg_follow=0.6, knee_follow=0.4,
                                outer_follow=0.75, front_follow=0.25, back_hold=0.2, contact_strength=0.8,
                                skirt=True),
    'Allgemein (nur Transfer)': dict(skirt=False),
}
DEFAULTS = dict(core.SKIRT_DEFAULTS, skirt=True, start_offset=None, transition=None,
                smooth_passes=3, maximum=4, hide_original=False, keep_all_influences=False,
                skirt_on_cv=True, layer_distance=None, leg_contact=None, contact_strength=0.9,
                sweep_sit=True, sweep_side=False, contact_smooth=8, sweep_scale=0.5, widen=0.0, widen_back=0.0,
                upper_smooth=0)
SUFFIX = '_mcdRig'
TOLERANCE_SUM = 1e-4
TOLERANCE_SHAPE = 1e-3   # scene units (cm)


class Report(object):
    def __init__(self):
        self.lines, self.warnings, self.errors = [], [], []

    def add(self, text, *args):
        self.lines.append(text % args if args else text)

    def warn(self, text, *args):
        self.warnings.append(text % args if args else text)

    def error(self, text, *args):
        self.errors.append(text % args if args else text)

    def text(self):
        out = list(self.lines)
        if self.warnings:
            out += ['', 'HINWEISE:'] + ['  - ' + w for w in self.warnings]
        if self.errors:
            out += ['', 'FEHLER:'] + ['  - ' + e for e in self.errors]
        return '\n'.join(out)


def body_setup(body_name):
    """Load the body and detect everything needed. Returns (body, info)."""
    transform, shape = scene.mesh_nodes(body_name)
    body = scene.BodyData(transform, shape)
    info = {'roles': {}, 'missing_cv': [], 'problems': []}
    if body.duplicates:
        info['problems'].append('Mehrdeutige Influence-Namen: %s' % ', '.join(body.duplicates))
    for role, (m_name, cv_name) in scene.ROLE_JOINTS.items():
        m_index = body.index_of.get(m_name)
        cv_index = body.index_of.get(cv_name)
        if m_index is None:
            info['problems'].append('Joint %s (Rolle %s) ist kein Influence des Body-Skins.' % (m_name, role))
        if cv_index is None:
            info['missing_cv'].append(cv_name)
        info['roles'][role] = (m_index, cv_index)
    if info['problems']:
        return body, info
    pos = {name: scene.joint_position(body.influences[body.index_of[name]])
           for name in ('mPelvis', 'mHipLeft', 'mHipRight', 'mKneeLeft', 'mKneeRight')}
    ankles = [scene.find_joint(body, name) for name in ('mAnkleLeft', 'mAnkleRight')]
    ankle_pos = [scene.joint_position(a) for a in ankles] if all(ankles) else [None, None]
    if not all(ankles):
        info['missing_cv'].append('mAnkleLeft/mAnkleRight (Beinlinie endet am Knie)')
    try:
        info['frame'] = core.make_frame(pos['mPelvis'], pos['mHipLeft'], pos['mHipRight'],
                                        pos['mKneeLeft'], pos['mKneeRight'], *ankle_pos)
    except ValueError as error:
        info['problems'].append(str(error))
        return body, info
    # Global CV share per role from the body's own weights.
    shares = {}
    for role, (m_index, cv_index) in info['roles'].items():
        if cv_index is None:
            shares[role] = 0.0
            continue
        m_sum = sum(r.get(m_index, 0.0) for r in body.rows)
        cv_sum = sum(r.get(cv_index, 0.0) for r in body.rows)
        shares[role] = cv_sum / (m_sum + cv_sum) if m_sum + cv_sum > 0 else 0.0
    info['shares'] = shares
    info['allowed'] = [not scene.is_excluded(name) for name in body.leaves]
    info['arm'] = [scene.is_arm(name) for name in body.leaves]
    info['leg_side'] = [scene.leg_side(name) for name in body.leaves]
    return body, info


def pose_summary(body):
    """Informational: how far the current pose is from the skin's bind pose."""
    _, om, _ = scene.api()
    pelvis = body.index_of.get('mPelvis')
    reference = body.skin_matrix(pelvis) if pelvis is not None else om.MMatrix()
    rotated = []
    for i, name in enumerate(body.leaves):
        rel = body.skin_matrix(i) * reference.inverse()
        q = om.MTransformationMatrix(rel).rotation(asQuaternion=True)
        angle = math.degrees(2.0 * math.acos(min(1.0, abs(q.w))))
        if angle > 0.05:
            rotated.append((angle, name))
    rotated.sort(reverse=True)
    return rotated


def _body_row(body, hit_tri, bary, allowed):
    row = core.blend_rows([body.rows[v] for v in hit_tri], bary)
    return {i: w for i, w in row.items() if allowed[i]}


def _finder(body, keep):
    dominant = [max(r, key=r.get) if r else None for r in body.rows]
    tris = [t for t in body.triangles if all(dominant[v] is not None and keep[dominant[v]] for v in t)]
    return scene.ClosestPoint(body.points, tris)


def weight_base(base, body, info, params, progress):
    """Weights for the base mesh in the current pose. Returns rows, factors.

    1. Body lookups (with arms for sleeves, without arms for the skirt).
    2. Soft skirt field (natural drape).
    3. Leg sweep: the body's legs are moved mathematically through test motions
       (steps, legs back, spread, optional sitting / one leg sideways). Skirt fabric that a leg
       touches or passes through follows that leg; everything else keeps the
       soft field. The rig is never moved.
    """
    allowed, arm = info['allowed'], info['arm']
    torso = [a and not b for a, b in zip(allowed, arm)]
    finder_all, finder_torso = _finder(body, allowed), _finder(body, torso)
    frame, roles = info['frame'], info['roles']
    pelvis_m = roles['pelvis'][0]
    start, transition = params['start_offset'], params['transition']
    # Skirt roles go to ONE joint each (collision volume if present): splitting
    # every role over m-bone + volume would need up to 8 influences and the
    # 4-cap would cut different joints on neighbouring vertices (steps).
    on_cv = params['skirt_on_cv']
    skirt_shares = {role: 1.0 if (on_cv and cv is not None) else 0.0 for role, (_, cv) in roles.items()}
    count = len(base.points)
    data = []
    sleeves = 0
    for index, point in enumerate(base.points):
        tri, bary, _ = finder_all.query(point)
        row_all = _body_row(body, tri, bary, allowed)
        total = sum(row_all.values()) or 1.0
        arm_share = sum(w for i, w in row_all.items() if arm[i]) / total
        sleeve = core.smoothstep((arm_share - 0.3) / 0.4)
        alpha = 0.0
        row = row_all
        if sleeve < 1.0:
            tri, bary, _ = finder_torso.query(point)
            row = _body_row(body, tri, bary, torso)
            if params['skirt']:
                height = core.skirt_frame_coords(point, frame)[1]
                alpha = core.smoothstep((start - height) / transition)
        sleeves += sleeve >= 0.5
        data.append((row, row_all, sleeve, alpha))
        if index % 2000 == 0:
            progress('Basis gewichten', 10 + int(15 * index / max(count, 1)))
    info['sleeve_vertices'] = sleeves
    skirt = [i for i, d in enumerate(data) if d[3] > 0.0 and d[2] < 1.0]
    raw = leg_sweep_contact(base, skirt, body, info, params, progress)
    contact = _smooth_contact(base, raw, params.get('contact_smooth', 8))
    rows, factors, sides = [], [], []
    touching = 0
    for index, (row, row_all, sleeve, alpha) in enumerate(data):
        side = 0.0
        if alpha > 0.0 and sleeve < 1.0:
            lateral, height, forward = core.skirt_frame_coords(base.points[index], frame)
            skirt_roles, side = core.skirt_roles(lateral, height, forward, frame, params)
            hit = contact.get(index)
            if hit:
                amount, leg_roles, sign = hit
                skirt_roles = core.mix_rows(skirt_roles, leg_roles, amount * params['contact_strength'])
                if amount > 0.3 and sign:
                    side = float(sign)
                touching += amount >= 0.5
            row = core.mix_rows(row, core.roles_to_row(skirt_roles, roles, skirt_shares), alpha)
        if sleeve > 0.0:
            row = core.mix_rows(row, row_all, sleeve)
        rows.append(row)
        factors.append(alpha * (1.0 - sleeve))
        sides.append(side)
    info['contact_vertices'] = touching
    progress('Basis glaetten', 36)
    rows = core.smooth_rows(rows, base.adjacency, factors, params['smooth_passes'])
    # Bodice / sleeves / shoulder band: the closest-point transfer jumps between
    # arm and chest triangles; optional smoothing makes those borders gradual.
    upper = [1.0 - f for f in factors] if params.get('upper_smooth') else [0.0] * len(factors)
    if params.get('upper_smooth'):
        progress('Oberteil glaetten', 37)
        rows = core.smooth_rows(rows, base.adjacency, upper, params['upper_smooth'])
    result = []
    for row, alpha, side in zip(rows, factors, sides):
        if alpha > 0.0:
            row = core.remove_opposite_knee(row, side, roles)
        result.append(core.normalize_row(row, params['maximum'], fallback=pelvis_m))
    coupled = couple_layers(base, result, params['layer_distance'], params['maximum'], pelvis_m)
    info['coupled_vertices'] = sum(1 for c in coupled if c > 0.5)
    result = core.smooth_within_sets(result, base.adjacency,
                                     [1.0 if f > 0 or c > 0 or u > 0 else 0.0
                                      for f, c, u in zip(factors, coupled, upper)],
                                     max(params['smooth_passes'], params.get('upper_smooth') or 0))
    return result, factors


def _smooth_contact(base, raw, passes):
    """Spread the per-leg contact amounts over mesh edges so the switch between
    'follows the leg' and 'soft drape' is gradual (less stretching), then turn
    them into {vertex: (amount, leg roles, side)}."""
    if not raw:
        return {}
    keys = ('al', 'kl', 'ar', 'kr')
    values = {k: {} for k in keys}
    for v, ((al, kl), (ar, kr)) in raw.items():
        values['al'][v], values['kl'][v], values['ar'][v], values['kr'][v] = al, kl, ar, kr
    region = set(raw)
    for v in list(raw):
        region.update(base.adjacency[v])
    for _ in range(int(passes)):
        for amount_key, knee_key in (('al', 'kl'), ('ar', 'kr')):
            amounts, knees = values[amount_key], values[knee_key]
            new_amounts, new_knees = {}, {}
            for v in region:
                neighbours = base.adjacency[v]
                if not neighbours:
                    continue
                own = amounts.get(v, 0.0)
                avg = sum(amounts.get(n, 0.0) for n in neighbours) / len(neighbours)
                value = 0.5 * own + 0.5 * avg
                if value > 1e-4:
                    new_amounts[v] = value
                    weight = sum(amounts.get(n, 0.0) for n in neighbours) + own
                    if weight > 0:
                        new_knees[v] = (own * knees.get(v, 0.0) + sum(amounts.get(n, 0.0) * knees.get(n, 0.0)
                                                                         for n in neighbours)) / weight
            values[amount_key], values[knee_key] = new_amounts, new_knees
        grown = set()
        for v in region:
            grown.update(base.adjacency[v])
        region |= grown
    result = {}
    for v in set(values['al']) | set(values['ar']):
        a_l, a_r = values['al'].get(v, 0.0), values['ar'].get(v, 0.0)
        total = a_l + a_r
        if total <= 1e-4:
            continue
        k_l, k_r = values['kl'].get(v, 0.0), values['kr'].get(v, 0.0)
        roles = {'pelvis': 0.0, 'thigh_l': a_l / total * (1.0 - k_l), 'knee_l': a_l / total * k_l,
                 'thigh_r': a_r / total * (1.0 - k_r), 'knee_r': a_r / total * k_r}
        sign = (1 if a_l > a_r else -1) if abs(a_l - a_r) > 0.2 else 0
        result[v] = (min(1.0, max(a_l, a_r)), roles, sign)
    return result


def leg_sweep_contact(base, vertices, body, info, params, progress):
    """{vertex: ((amount_l, knee_share_l), (amount_r, knee_share_r))} for skirt vertices a leg
    touches or sweeps through."""
    full = params['leg_contact'] or 0.0
    if full <= 0.0 or not vertices:
        return {}
    frame = info['frame']
    chain = [scene.leg_chain(name) for name in body.leaves]
    leg_side = info['leg_side']
    dominant = [max(r, key=r.get) if r else None for r in body.rows]
    leg_tris = [t for t in body.triangles
                if all(dominant[v] is not None and leg_side[dominant[v]] for v in t)]
    if not leg_tris:
        return {}
    used = sorted(set(v for t in leg_tris for v in t))
    local = {v: k for k, v in enumerate(used)}
    tris = [tuple(local[v] for v in t) for t in leg_tris]
    pts = [body.points[v] for v in used]
    rws = [body.rows[v] for v in used]
    wanted = params.get('sweep_motions')
    motions = [('Ruhe', 0.0, 0.0, 0.0, 0.0)] + [m for m in core.LEG_SWEEP if not wanted or m[0] in wanted]
    if params.get('sweep_sit', True):
        motions += list(core.LEG_SWEEP_SIT)
    if params.get('sweep_side', False):
        motions += list(core.LEG_SWEEP_SIDE)
    full_range = [m[0] for m in core.LEG_SWEEP_SIT + core.LEG_SWEEP_SIDE]
    # Best contact per vertex and leg; fabric touched by both legs (in different
    # motions) is shared between them instead of jumping from one to the other.
    best = {}
    for number, (name, fwd_l, fwd_r, spread, knee) in enumerate(motions):
        progress('Beinbewegung pruefen: %s' % name, 26 + int(9 * number / len(motions)))
        steps = (1.0,) if name == 'Ruhe' else (0.5, 1.0)
        if name in [m[0] for m in core.LEG_SWEEP_SIDE]:
            steps = core.SIDE_STEPS
        # Walking motions scale with 'Bewegungsbereich'; sitting and sideways are tested fully.
        scale = 1.0 if name in full_range else params.get('sweep_scale', 1.0)
        spread = tuple(s * scale for s in spread) if isinstance(spread, tuple) else spread * scale
        for posed in core.swept_leg_points(pts, rws, chain, frame, fwd_l * scale, fwd_r * scale,
                                           spread, knee * scale, steps):
            finder = scene.ClosestPoint(posed, tris)
            for v in vertices:
                tri, bary, distance = finder.query(base.points[v])
                amount = core.contact_factor(distance, full, full * params.get('contact_fade', 1.0))
                if amount <= 0.0:
                    continue
                row = core.blend_rows([rws[t] for t in tri], bary)
                sides, shins = {1: 0.0, -1: 0.0}, {1: 0.0, -1: 0.0}
                for i, w in row.items():
                    side, level = chain[i]
                    if side:
                        sides[side] += w
                        if level == 2:
                            shins[side] += w
                sign = 1 if sides[1] >= sides[-1] else -1
                entry = best.setdefault(v, {})
                if amount > entry.get(sign, (0.0, 0.0))[0]:
                    entry[sign] = (amount, core.clamp(shins[sign] / (sides[sign] or 1.0)))
    return {v: (entry.get(1, (0.0, 0.0)), entry.get(-1, (0.0, 0.0))) for v, entry in best.items()}


def couple_layers(base, rows, distance, maximum, fallback):
    """Keep stacked fabric layers together (in place on rows).

    Shells are processed from largest to smallest. A vertex of a smaller shell
    that lies within `distance` of a larger shell takes over that shell's
    weights (fully up to 60 % of `distance`, fading out towards `distance`). Overlay
    panels and slit facings then move with the fabric beneath them.
    Returns the coupling factor per vertex.
    """
    coupled = [0.0] * len(rows)
    if not distance or distance <= 0:
        return coupled
    sizes = collections.Counter(base.shell_of)
    order = [s for s, _ in sizes.most_common()]
    tris_of = collections.defaultdict(list)
    for tri in base.triangles:
        tris_of[base.shell_of[tri[0]]].append(tri)
    vertices_of = collections.defaultdict(list)
    for v, s in enumerate(base.shell_of):
        vertices_of[s].append(v)
    below = []
    for shell in order:
        if below:
            finder = scene.ClosestPoint(base.points, below)
            for v in vertices_of[shell]:
                tri, bary, d = finder.query(base.points[v])
                # Full coupling up to 60 % of the distance, then fade out.
                c = 1.0 - core.smoothstep((d - 0.6 * distance) / (0.4 * distance))
                if c <= 0.0:
                    continue
                under = core.blend_rows([rows[t] for t in tri], bary)
                rows[v] = core.normalize_row(core.mix_rows(rows[v], under, c), maximum, fallback=fallback)
                coupled[v] = c
        below = below + tris_of[shell]
    return coupled


def transfer(part, base, base_rows, params, fallback, report):
    """Closest-point transfer from base to one dress part, per shell."""
    whole = scene.ClosestPoint(base.points, base.triangles)
    by_shell = collections.defaultdict(list)
    for tri in base.triangles:
        by_shell[base.shell_of[tri[0]]].append(tri)
    finders = {}
    shell_vertices = collections.defaultdict(list)
    for v, s in enumerate(part.shell_of):
        shell_vertices[s].append(v)
    limit = 1.0  # cm: a thickness layer lies on the base within this distance
    matched = 0
    rows = [None] * len(part.points)
    for shell, vertices in shell_vertices.items():
        step = max(1, len(vertices) // 200)
        votes, distances = collections.Counter(), []
        for v in vertices[::step]:
            tri, _, distance = whole.query(part.points[v])
            votes[base.shell_of[tri[0]]] += 1
            distances.append(distance)
        target, hits = votes.most_common(1)[0]
        distances.sort()
        finder = whole
        if hits >= 0.8 * sum(votes.values()) and distances[len(distances) // 2] <= limit:
            if target not in finders:
                finders[target] = scene.ClosestPoint(base.points, by_shell[target])
            finder = finders[target]
            matched += 1
        for v in vertices:
            tri, bary, _ = finder.query(part.points[v])
            row = core.blend_rows([base_rows[t] for t in tri], bary)
            rows[v] = core.normalize_row(row, params['maximum'], fallback=fallback)
    report.add('  Shells: %d, davon einer Basis-Shell zugeordnet: %d (Rest: ganze Basis)',
               len(shell_vertices), matched)
    return rows


def widen_points(points, frame, params, report):
    """Skirt points pushed outwards ('Rock aufweiten'); the original is untouched."""
    amount, back = params.get('widen') or 0.0, params.get('widen_back') or 0.0
    if not params['skirt'] or (amount <= 0.0 and back <= 0.0):
        return points
    out, moved, largest = [], 0, 0.0
    for p in points:
        o = core.widen_offset(p, frame, params['start_offset'], params['transition'], amount, back)
        length = math.sqrt(core.dot(o, o))
        if length > 1e-6:
            moved += 1
            largest = max(largest, length)
        out.append((p[0] + o[0], p[1] + o[1], p[2] + o[2]))
    report.add('  Rock aufgeweitet: %d Vertices, bis %.2f cm (Basis %.2f cm + hinten Mitte %.2f cm)',
               moved, largest, amount, back)
    return out


def unskin(points, rows, skin_mats):
    _, om, _ = scene.api()
    rest = []
    for point, row in zip(points, rows):
        blended = None
        for i, w in row.items():
            term = skin_mats[i] * w
            blended = term if blended is None else blended + term
        p = om.MPoint(*point) * blended.inverse()
        rest.append((p.x, p.y, p.z))
    return rest


def create_output(part, body, rows, rest, influences, params, report, created):
    """Duplicate part, set bind-pose points, bind with the body's bindPreMatrix, write weights."""
    cmds, om, _ = scene.api()
    out = scene.duplicate_mesh(part.transform, SUFFIX)
    created.append(out)
    _, out_shape = scene.mesh_nodes(out)
    fn_mesh = om.MFnMesh(scene.dag_path(out_shape))
    if fn_mesh.numVertices != len(rest):
        raise RigError('%s: Vertexzahl der Kopie weicht ab.' % scene.short(out))
    fn_mesh.setPoints(om.MPointArray([om.MPoint(*p) for p in rest]), om.MSpace.kObject)
    poses_before = {p: len(cmds.listConnections(p + '.members') or []) for p in cmds.ls(type='dagPose') or []}
    names = [body.influences[i] for i in influences]
    try:
        skin = cmds.skinCluster(names, out, toSelectedBones=True, bindMethod=0, skinMethod=0,
                                normalizeWeights=1, maximumInfluences=params['maximum'],
                                obeyMaxInfluences=False, name=scene.leaf(out) + 'Skin')[0]
    except RuntimeError as error:
        # Maya can refuse when the joints belong to a stored bind pose they are
        # not in. Build the skinCluster node directly instead (no pose needed).
        report.warn('skinCluster-Befehl abgelehnt (%s); Skin wurde direkt aufgebaut.', str(error).strip())
        skin = scene.build_skin_node(out, names, scene.leaf(out) + 'Skin')
    created.append(skin)
    # A new pose node would store the working pose, not the bind pose used
    # here; the Legacy body skin has none either. Only nodes created now are removed.
    new_poses = [p for p in (cmds.ls(type='dagPose') or []) if p not in poses_before]
    scene.delete_nodes(new_poses)
    for pose, count in poses_before.items():
        if cmds.objExists(pose) and len(cmds.listConnections(pose + '.members') or []) != count:
            report.warn('Maya hat die vorhandene Pose %s beim Binden erweitert (nicht vom Tool geaendert).', pose)
    fn = scene.fn_skin(skin)
    paths = fn.influenceObjects()
    column = {}
    for physical, p in enumerate(paths):
        logical = fn.indexForInfluenceObject(p)
        body_index = body.influences.index(p.fullPathName())
        column[body_index] = physical
        cmds.setAttr('%s.bindPreMatrix[%d]' % (skin, logical), *body.bind_pre[body_index], type='matrix')
    k = len(paths)
    flat = [0.0] * (len(rows) * k)
    for v, row in enumerate(rows):
        base = v * k
        for i, w in row.items():
            flat[base + column[i]] = w
    dag = scene.dag_path(out_shape)
    fn.setWeights(dag, scene.complete_component(len(rows)), om.MIntArray(list(range(k))),
                  om.MDoubleArray(flat), False)
    cmds.setAttr(skin + '.maintainMaxInfluences', True)
    cmds.setAttr(skin + '.maxInfluences', params['maximum'])
    return out, out_shape, skin


def validate(out, out_shape, skin, original_points, maximum, report):
    """All vertices: weights and shape. Returns number of problems."""
    _, om, _ = scene.api()
    fn = scene.fn_skin(skin)
    dag = scene.dag_path(out_shape)
    count = len(original_points)
    weights, k = fn.getWeights(dag, scene.complete_component(count))
    names = [scene.leaf(p.fullPathName()) for p in fn.influenceObjects()]
    problems = []
    for v in range(count):
        values = [weights[v * k + i] for i in range(k)]
        bad = [(names[i], w) for i, w in enumerate(values) if not math.isfinite(w) or w < -1e-9]
        used = [w for w in values if w > 1e-6]
        total = sum(w for w in values if math.isfinite(w))
        if bad:
            problems.append('vtx[%d]: ungueltiger Wert %s = %r (erwartet endlich und >= 0)' % (v, bad[0][0], bad[0][1]))
        elif abs(total - 1.0) > TOLERANCE_SUM:
            problems.append('vtx[%d]: Summe %.6f (erwartet 1 +- %g)' % (v, total, TOLERANCE_SUM))
        elif len(used) > maximum:
            problems.append('vtx[%d]: %d Influences (erlaubt %d)' % (v, len(used), maximum))
    deformed = om.MFnMesh(dag).getPoints(om.MSpace.kWorld)
    worst, worst_v = 0.0, -1
    for v in range(count):
        p, q = deformed[v], original_points[v]
        d = math.sqrt((p.x - q[0]) ** 2 + (p.y - q[1]) ** 2 + (p.z - q[2]) ** 2)
        if d > worst:
            worst, worst_v = d, v
    if worst > TOLERANCE_SHAPE:
        problems.append('vtx[%d]: liegt %.4f cm neben dem Original (erwartet <= %g cm)'
                        % (worst_v, worst, TOLERANCE_SHAPE))
    report.add('  Pruefung: %d Vertices, groesste Formabweichung %.6f cm (vtx[%d])', count, worst, max(worst_v, 0))
    for line in problems[:10]:
        report.error('%s.%s', scene.short(out), line)
    if len(problems) > 10:
        report.error('%s: ... %d weitere Probleme', scene.short(out), len(problems) - 10)
    return len(problems)


def run(body_name, base_name, part_names, params, progress=None):
    """Create rigged copies of part_names. Returns (Report, created output transforms)."""
    cmds, om, _ = scene.api()
    progress = progress or (lambda text, value: None)
    params = dict(DEFAULTS, **params)
    report = Report()
    started = time.time()
    report.add('mcd. Dress Rig M1 - Bericht')
    progress('Body lesen', 2)
    body, info = body_setup(body_name)
    if info['problems']:
        raise RigError('Body nicht verwendbar:\n  ' + '\n  '.join(info['problems']))
    frame = info['frame']
    if params['start_offset'] is None:
        params['start_offset'] = 0.15 * frame['leg_length']
    if params['transition'] is None:
        params['transition'] = 0.35 * frame['leg_length']
    if params['layer_distance'] is None:
        params['layer_distance'] = 0.08 * frame['leg_length']
    if params['leg_contact'] is None:
        params['leg_contact'] = 0.06 * frame['leg_length']
    if params['transition'] <= 0:
        raise RigError('Uebergangsbreite muss groesser als 0 sein.')
    report.add('Body: %s (%s, %d Influences)', scene.short(body.transform), body.skin, len(body.influences))
    report.add('Achsen aus dem Skeleton: hoch %s, links %s, vorne %s',
               tuple(round(x, 3) for x in frame['up']),
               tuple(round(x, 3) for x in frame['lateral']), tuple(round(x, 3) for x in frame['forward']))
    if params['widen'] < 0 or params['widen_back'] < 0:
        raise RigError('Aufweiten: nur Werte >= 0 (cm).')
    report.add('Rockbeginn %.2f cm ueber dem Becken, Uebergang %.2f cm, Profilwerte: %s',
               params['start_offset'], params['transition'],
               ', '.join('%s=%s' % (k, params[k]) for k in sorted(core.SKIRT_DEFAULTS)))
    if info['missing_cv']:
        report.warn('Keine Collision Volumes fuer %s: Rock folgt Koerperform-Slidern dort nicht.',
                    ', '.join(info['missing_cv']))
    rotated = pose_summary(body)
    report.add('Arbeitspose: %d Influences weichen in der Rotation von der Bindung ab (groesste: %s).',
               len(rotated), ', '.join('%s %.1f Grad' % (n, a) for a, n in rotated[:3]) or '-')
    report.add('  (Das ist erlaubt: gewichtet wird in der aktuellen Pose, gebunden in der Body-Bindepose.)')
    base_t, base_s = scene.mesh_nodes(base_name)
    if scene.has_skin(base_s):
        raise RigError('Basis %s ist schon geriggt. Bitte die ungeriggte Basis laden.' % scene.short(base_t))
    base = scene.MeshData(base_t, base_s)
    tiny = collections.Counter(base.shell_of)
    tiny_shells = sum(1 for n in tiny.values() if n <= 4)
    if tiny_shells:
        report.warn('Basis %s enthaelt %d Mini-Shells (<= 4 Vertices), vermutlich Reste.', scene.short(base_t), tiny_shells)
    progress('Basis gewichten', 8)
    base_rows, factors = weight_base(base, body, info, params, progress)
    report.add('Basis %s: %d Vertices, %d Shells, %d im Rockbereich, %d als Aermel erkannt, '
               '%d an darunterliegende Lage gekoppelt (bis %.1f cm), %d liegen am Bein an (bis %.1f cm)',
               scene.short(base_t), len(base.points), base.shell_count, sum(1 for f in factors if f > 0),
               info.get('sleeve_vertices', 0), info.get('coupled_vertices', 0), params['layer_distance'],
               info.get('contact_vertices', 0), params['leg_contact'])
    report.add('Glaetten: Rock %d, Oberteil %d Durchlaeufe', params['smooth_passes'], params['upper_smooth'])
    tests = ['Schritte/Spreizen x%.2f' % params['sweep_scale']]
    if params['sweep_sit']:
        tests.append('Sitzen')
    if params['sweep_side']:
        tests.append('Bein seitlich 40 Grad')
    report.add('Beinpruefung: %s; Am Bein anliegend folgt %.2f', ', '.join(tests), params['contact_strength'])
    skirt_count = sum(1 for f in factors if f > 0)
    if skirt_count and info.get('contact_vertices', 0) > 0.5 * skirt_count:
        report.warn('%d %% des Rocks gilt als am Bein anliegend und folgt den Beinen. Die Mitte-Regler '
                    '(Mitte am Becken, Mitte weich, Vorne/Hinten) wirken dort kaum. Zum Vergleich '
                    '"Am Bein anliegend bis" kleiner stellen oder 0 (aus).',
                    round(100.0 * info['contact_vertices'] / skirt_count))
    skin_mats = {}
    created, outputs = [], []
    cmds.undoInfo(openChunk=True, chunkName='mcdDressRig')
    try:
        parts = []
        for name in part_names:
            t, s = scene.mesh_nodes(name)
            if t == body.transform:
                raise RigError('Der Body kann nicht als Kleidteil verwendet werden.')
            if scene.has_skin(s):
                raise RigError('%s ist schon geriggt (Ergebnis eines frueheren Laufs?). Bitte das '
                               'ungeriggte ORIGINAL als Kleidteil verwenden: Liste leeren, Original '
                               'auswaehlen, Auswahl hinzufuegen.' % scene.short(t))
            parts.append(scene.MeshData(t, s))
        total = len(parts)
        for number, part in enumerate(parts):
            step = 40 + int(50 * number / max(total, 1))
            report.add('')
            report.add('Kleidteil %s: %d Vertices', scene.short(part.transform), len(part.points))
            progress('Uebertragen: %s' % scene.short(part.transform), step)
            rows = transfer(part, base, base_rows, params, info['roles']['pelvis'][0], report)
            for row in rows:
                for i in row:
                    if i not in skin_mats:
                        skin_mats[i] = body.skin_matrix(i)
            target = widen_points(part.points, frame, params, report)
            progress('Bindepose berechnen: %s' % scene.short(part.transform), step + 10)
            rest = unskin(target, rows, skin_mats)
            used = sorted(set(i for row in rows for i in row))
            influences = list(used)
            if params['keep_all_influences']:
                influences = list(range(len(body.influences)))
            else:
                for name in scene.SL_BASE_JOINTS:
                    i = body.index_of.get(name)
                    if i is not None and i not in influences:
                        influences.append(i)
            progress('Binden: %s' % scene.short(part.transform), step + 20)
            out, out_shape, skin = create_output(part, body, rows, rest, influences, params, report, created)
            outputs.append(out)
            usage = scene.influence_usage(rows)
            report.add('  -> %s (%s): %d Influences im Skin, %d mit Gewicht', scene.short(out), skin,
                       len(influences), len(used))
            report.add('     staerkste: %s', ', '.join('%s %d' % (body.leaves[i], n) for i, n in usage.most_common(6)))
            if len(influences) > 32:
                report.warn('%s: %d Joints im Skin. Die (vor Bento verfasste) SL-Formatseite nennt Joint-Index <= 31; '
                            'beim Upload pruefen.', scene.short(out), len(influences))
            validate(out, out_shape, skin, target, params['maximum'], report)
            if params['hide_original']:
                plug = part.transform + '.visibility'
                if cmds.getAttr(plug, settable=True):
                    cmds.setAttr(plug, False)
                else:
                    report.warn('Sichtbarkeit von %s ist gesperrt/verbunden; nicht ausgeblendet.', scene.short(part.transform))
    except Exception:
        scene.delete_nodes(list(reversed(created)))
        raise
    finally:
        cmds.undoInfo(closeChunk=True)
    report.add('')
    report.add('Fertig in %.1f s. Erzeugt: %s', time.time() - started, ', '.join(scene.short(o) for o in outputs))
    report.add('Original, Body, Rig und Animation wurden nicht veraendert.')
    report.add('Rueckgaengig (Strg+Z) entfernt die Kopien; Wiederherstellen (Redo) der Gewichte wird nicht unterstuetzt.')
    if report.errors:
        report.add('ACHTUNG: Pruefung hat Probleme gefunden (siehe FEHLER).')
    return report, outputs
