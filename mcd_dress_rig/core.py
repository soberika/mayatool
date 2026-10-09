# -*- coding: utf-8 -*-
"""Pure weight math for mcd. Dress Rig. No Maya import: testable outside Maya.

Conventions
-----------
* A weight row is a dict {influence_index: weight}.
* Matrices are 4x4 nested lists in Maya's row-vector convention:
  point_out = point_in * M (translation in the last row).
* The skirt frame is given by the caller: origin (pelvis), unit up, unit
  lateral (towards the character's left) and unit forward axes.
"""
from __future__ import division

import math


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def smoothstep(value):
    t = clamp(value)
    return t * t * (3.0 - 2.0 * t)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def normalize_row(row, maximum=4, fallback=None, floor=1e-6):
    """Keep the strongest `maximum` finite weights above `floor`, sum to 1."""
    clean = [(i, float(w)) for i, w in row.items() if math.isfinite(w) and w > floor]
    clean.sort(key=lambda item: (-item[1], item[0]))
    clean = clean[:maximum]
    total = sum(w for _, w in clean)
    if total <= 1e-12:
        if fallback is None:
            raise ValueError('Gewichtszeile ohne gueltige Werte und ohne Ersatz-Influence.')
        return {fallback: 1.0}
    return {i: w / total for i, w in clean}


def mix_rows(first, second, amount):
    result = {i: w * (1.0 - amount) for i, w in first.items()}
    for i, w in second.items():
        result[i] = result.get(i, 0.0) + w * amount
    return result


def blend_rows(rows, factors):
    """Weighted sum of rows (e.g. barycentric interpolation)."""
    result = {}
    for row, factor in zip(rows, factors):
        if factor <= 0.0:
            continue
        for i, w in row.items():
            result[i] = result.get(i, 0.0) + w * factor
    return result


def barycentric(point, a, b, c):
    """Barycentric coordinates of the projection of point onto triangle abc."""
    v0, v1, v2 = sub(b, a), sub(c, a), sub(point, a)
    d00, d01, d11 = dot(v0, v0), dot(v0, v1), dot(v1, v1)
    d20, d21 = dot(v2, v0), dot(v2, v1)
    denom = d00 * d11 - d01 * d01
    if abs(denom) < 1e-20:
        # Degenerate triangle: use the nearest corner.
        distances = [dot(sub(point, p), sub(point, p)) for p in (a, b, c)]
        best = distances.index(min(distances))
        return tuple(1.0 if k == best else 0.0 for k in range(3))
    v = (d11 * d20 - d01 * d21) / denom
    w = (d00 * d21 - d01 * d20) / denom
    u = 1.0 - v - w
    coords = [clamp(u), clamp(v), clamp(w)]
    total = sum(coords) or 1.0
    return tuple(x / total for x in coords)


# ------------------------------------------------------------------ skirt
SKIRT_DEFAULTS = {
    'center_width': 1.0,   # 1.0 = full leg weight on the leg line; larger = softer centre
    'center_hold': 0.55,   # pelvis share kept in the centre (between the legs)
    'leg_follow': 0.75,    # overall amount given to the legs
    'knee_follow': 0.6,    # amount moved from thigh to lower leg below the knee
    'outer_follow': 0.9,   # leg share at the outer sides (skirt covers a spread leg)
    'front_follow': 0.25,  # front centre follows the thighs more (sitting)
    'back_hold': 0.0,      # back centre stays more with the pelvis (0: back follows legs)
}


def _unit(v):
    length = math.sqrt(dot(v, v))
    if length < 1e-9:
        raise ValueError('Skeleton-Achse nicht bestimmbar (Joints liegen aufeinander).')
    return (v[0] / length, v[1] / length, v[2] / length)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def make_frame(pelvis, hip_l, hip_r, knee_l, knee_r, ankle_l=None, ankle_r=None):
    """Skirt frame from joint positions; axes come from the skeleton, not the scene.

    Also stores the leg line (height -> lateral distance and forward offset of
    the legs) so the skirt field knows where the leg really is at each height.
    """
    knees = tuple((knee_l[i] + knee_r[i]) * 0.5 for i in range(3))
    hips = tuple((hip_l[i] + hip_r[i]) * 0.5 for i in range(3))
    up = _unit(sub(hips, knees))
    across = sub(hip_l, hip_r)
    across = tuple(across[i] - dot(across, up) * up[i] for i in range(3))
    lateral = _unit(across)
    forward = _unit(cross(lateral, up))
    frame = {
        'hip_l': tuple(hip_l), 'hip_r': tuple(hip_r), 'knee_l': tuple(knee_l), 'knee_r': tuple(knee_r),
        'origin': tuple(pelvis), 'up': up, 'lateral': lateral, 'forward': forward,
        'half_width': 0.5 * math.sqrt(dot(across, across)),
        'leg_length': dot(sub(hips, knees), up),
        'knee_height': dot(sub(knees, pelvis), up),
    }
    pairs = [(hip_l, hip_r), (knee_l, knee_r)]
    if ankle_l is not None and ankle_r is not None:
        pairs.append((ankle_l, ankle_r))
    line = []
    for left, right in pairs:
        l, r = sub(left, pelvis), sub(right, pelvis)
        height = 0.5 * (dot(l, up) + dot(r, up))
        side = 0.5 * (dot(l, lateral) - dot(r, lateral))
        depth = 0.5 * (dot(l, forward) + dot(r, forward))
        line.append((height, side, depth))
    frame['leg_line'] = sorted(line, reverse=True)   # from hip (top) down
    return frame


def leg_line_at(frame, height):
    """Lateral distance and forward offset of the legs at a height (linear, clamped)."""
    line = frame.get('leg_line')
    if not line:
        return frame['half_width'], 0.0
    if height >= line[0][0]:
        return line[0][1], line[0][2]
    for (h0, s0, d0), (h1, s1, d1) in zip(line, line[1:]):
        if height >= h1:
            t = (h0 - height) / (h0 - h1) if h0 != h1 else 0.0
            return s0 + (s1 - s0) * t, d0 + (d1 - d0) * t
    return line[-1][1], line[-1][2]


def skirt_frame_coords(point, frame):
    offset = sub(point, frame['origin'])
    return (dot(offset, frame['lateral']), dot(offset, frame['up']), dot(offset, frame['forward']))


def skirt_roles(lateral, height, forward, frame, params):
    """Role weights before splitting into m-bones / collision volumes.

    Returns {role: weight} with roles pelvis, thigh_l, thigh_r, knee_l, knee_r.
    Symmetric (left/right mirror), continuous, sums to 1. Only the dominant
    side gets lower-leg weight, fading to zero at the centre.
    """
    half = frame['half_width']
    leg_side, leg_depth = leg_line_at(frame, height)
    # side = +-1 on the leg line (times center_width): fabric next to, behind or
    # in front of a leg follows that leg; the centre between the legs blends.
    side = clamp(lateral / (max(leg_side, 0.25 * half) * params['center_width']), -1.0, 1.0)
    left = smoothstep(0.5 * (side + 1.0))
    outer = smoothstep(abs(side))
    depth = clamp((forward - leg_depth) / half, -1.0, 1.0)
    centre_hold = clamp(params['center_hold'] - params['front_follow'] * max(0.0, depth)
                        + params['back_hold'] * max(0.0, -depth))
    legs = params['leg_follow'] * (1.0 - centre_hold) * (1.0 - outer) + params['outer_follow'] * outer
    length = frame['leg_length']
    knee_depth = smoothstep((frame['knee_height'] + 0.18 * length - height) / (0.65 * length))
    knee = params['knee_follow'] * knee_depth * outer
    roles = {'pelvis': 1.0 - legs, 'thigh_l': legs * left, 'thigh_r': legs * (1.0 - left),
             'knee_l': 0.0, 'knee_r': 0.0}
    if side > 0.0:
        roles['knee_l'] = roles['thigh_l'] * knee
        roles['thigh_l'] -= roles['knee_l']
    elif side < 0.0:
        roles['knee_r'] = roles['thigh_r'] * knee
        roles['thigh_r'] -= roles['knee_r']
    return roles, side


def widen_offset(point, frame, start, transition, amount, back_extra):
    """Horizontal push away from the vertical axis through the pelvis.

    Fades in like the skirt field (start above the pelvis, over `transition`).
    `back_extra` is added at the back centre: full straight behind, half at
    45 degrees, zero at the sides and front. All layers at one place move the
    same way, so stacked fabric stays together. Returns an offset vector.
    """
    if amount <= 0.0 and back_extra <= 0.0:
        return (0.0, 0.0, 0.0)
    lateral, height, forward = skirt_frame_coords(point, frame)
    fade = smoothstep((start - height) / transition) if transition > 0.0 else 0.0
    radius = math.sqrt(lateral * lateral + forward * forward)
    if fade <= 0.0 or radius < 1e-9:
        return (0.0, 0.0, 0.0)
    back = max(0.0, -forward / radius)
    push = fade * (amount + back_extra * back * back)
    lat_axis, fwd_axis = frame['lateral'], frame['forward']
    return tuple(push * (lateral * lat_axis[k] + forward * fwd_axis[k]) / radius for k in range(3))


def rotation(axis, degrees):
    """3x3 rotation about a unit axis (right-hand rule), row-major nested lists."""
    a = math.radians(degrees)
    c, s, t = math.cos(a), math.sin(a), 1.0 - math.cos(a)
    x, y, z = axis
    return [[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c]]


def rotate_about(point, pivot, m):
    d = sub(point, pivot)
    return tuple(pivot[r] + m[r][0] * d[0] + m[r][1] * d[1] + m[r][2] * d[2] for r in range(3))


# Test motions for the leg sweep: (name, hip forward L, hip forward R, spread, knee bend).
# spread is one value for both legs or a tuple (left, right).
# Degrees; hip forward > 0 moves the foot forward, knee bend > 0 moves the shin back.
LEG_SWEEP = (
    ('Schritt links vor', 30.0, -20.0, 0.0, 15.0),
    ('Schritt rechts vor', -20.0, 30.0, 0.0, 15.0),
    ('Beine zurueck', -20.0, -20.0, 0.0, 0.0),
    ('Beine gespreizt', 0.0, 0.0, 15.0, 0.0),
)
LEG_SWEEP_SIT = (('Sitzen', 80.0, 80.0, 5.0, 80.0),)
# One leg lifted sideways (slit dresses): the fabric behind/next to that leg
# is tested in small steps so a 40 degree sweep does not skip any fabric.
LEG_SWEEP_SIDE = (('Bein links seitlich', 0.0, 0.0, (40.0, 0.0), 0.0),
                  ('Bein rechts seitlich', 0.0, 0.0, (0.0, 40.0), 0.0))
SIDE_STEPS = (0.25, 0.5, 0.75, 1.0)


def swept_leg_points(points, rows, chain, frame, hip_fwd_l, hip_fwd_r, spread, knee_bend, steps=(0.5, 1.0)):
    """Yield posed copies of `points` for intermediate steps of one test motion.

    chain[i] for each influence: (side, level) with side +1/-1 (0 = not a leg)
    and level 1 = thigh, 2 = shin/foot. Pivots: hips and knees from the frame.
    Only vertices with leg weight move; the rig is never touched.
    """
    lateral, forward = frame['lateral'], frame['forward']
    spreads = tuple(spread) if isinstance(spread, (tuple, list)) else (spread, spread)
    for step in steps:
        mats = {}
        for side, fwd, spread_side in ((1, hip_fwd_l, spreads[0]), (-1, hip_fwd_r, spreads[1])):
            hip_m = rotation(lateral, -fwd * step)
            hip_m = mat3_mul(rotation(forward, side * spread_side * step), hip_m)
            knee_m = rotation(lateral, knee_bend * step)
            hip = frame['hip_l'] if side > 0 else frame['hip_r']
            knee = frame['knee_l'] if side > 0 else frame['knee_r']
            knee_moved = rotate_about(knee, hip, hip_m)
            mats[side] = (hip, hip_m, knee_moved, knee_m)
        posed = []
        for p, row in zip(points, rows):
            out, rest = [0.0, 0.0, 0.0], 0.0
            for i, w in row.items():
                side, level = chain[i]
                if not side:
                    rest += w
                    continue
                hip, hip_m, knee_moved, knee_m = mats[side]
                q = rotate_about(p, hip, hip_m)
                if level == 2:
                    q = rotate_about(q, knee_moved, knee_m)
                for k in range(3):
                    out[k] += w * q[k]
            for k in range(3):
                out[k] += rest * p[k]
            posed.append(tuple(out))
        yield posed


def mat3_mul(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)] for r in range(3)]


def contact_factor(distance, full, fade):
    """1 while the fabric lies within `full` of the leg, fading to 0 at full + fade."""
    if fade <= 0.0:
        return 1.0 if distance <= full else 0.0
    return 1.0 - smoothstep((distance - full) / fade)


def roles_to_row(roles, pairs, shares):
    """Split each role between its m-bone and collision volume.

    pairs:  {role: (m_index, cv_index_or_None)}
    shares: {role: collision-volume share 0..1}
    """
    row = {}
    for role, weight in roles.items():
        if weight <= 0.0:
            continue
        m_index, cv_index = pairs[role]
        share = shares.get(role, 0.0) if cv_index is not None else 0.0
        if share < 1.0:
            row[m_index] = row.get(m_index, 0.0) + weight * (1.0 - share)
        if share > 0.0:
            row[cv_index] = row.get(cv_index, 0.0) + weight * share
    return row


def local_shares(body_row, pairs, global_shares):
    """CV share per role taken from the body row where it has data."""
    shares = {}
    for role, (m_index, cv_index) in pairs.items():
        if cv_index is None:
            shares[role] = 0.0
            continue
        m_w, cv_w = body_row.get(m_index, 0.0), body_row.get(cv_index, 0.0)
        shares[role] = cv_w / (m_w + cv_w) if m_w + cv_w > 0.05 else global_shares[role]
    return shares


def smooth_rows(rows, adjacency, factors, passes, strength=0.35):
    passes = int(passes)
    """Graph Laplacian smoothing; only vertices with factor > 0 change.

    Neighbours come from mesh edges, so separate shells and the two sides of
    a slit never exchange weights.
    """
    for _ in range(passes):
        smoothed = []
        for index, row in enumerate(rows):
            neighbours = adjacency[index]
            amount = strength * factors[index]
            if amount <= 0.0 or not neighbours:
                smoothed.append(row)
                continue
            average = {}
            share = 1.0 / len(neighbours)
            for n in neighbours:
                for i, w in rows[n].items():
                    average[i] = average.get(i, 0.0) + w * share
            smoothed.append(mix_rows(row, average, amount))
        rows = smoothed
    return rows


def smooth_within_sets(rows, adjacency, factors, passes, strength=0.5):
    """Smooth after capping without adding influences.

    Each vertex keeps its own (capped) influence set; only the values move
    towards the neighbour average and are renormalised. This removes steps
    where neighbouring vertices kept different joints.
    """
    passes = int(passes)
    for _ in range(passes):
        smoothed = []
        for index, row in enumerate(rows):
            neighbours = adjacency[index]
            amount = strength * factors[index]
            if amount <= 0.0 or not neighbours:
                smoothed.append(row)
                continue
            share = 1.0 / len(neighbours)
            mixed = {}
            for i, w in row.items():
                average = sum(rows[n].get(i, 0.0) for n in neighbours) * share
                mixed[i] = w * (1.0 - amount) + average * amount
            total = sum(mixed.values())
            smoothed.append({i: w / total for i, w in mixed.items()} if total > 1e-12 else row)
        rows = smoothed
    return rows


def detect_slit_strips(points, triangles, shell_of, frame, skirt_top, skip=None, distance=None):
    """Find slits and narrow fabric strips along them (facings, wrap edges).

    points/triangles/shell_of: the base mesh; frame: skirt frame; skirt_top:
    height (frame coords) where the skirt starts; skip: per-vertex flag for
    vertices to ignore (sleeves). Pure geometry, no weights.

    Slit = open (boundary) edge of a large skirt shell that runs well above
    that shell's hem. Strip = a separate, long and narrow shell in the skirt
    lying next to such a slit. Returns {'slits': [...], 'strips': [...]}.
    """
    count = len(points)
    skip = skip or [False] * count
    leg = frame['leg_length']
    distance = distance if distance is not None else 0.12 * leg
    coords = [skirt_frame_coords(p, frame) for p in points]
    shells = {}
    for v, s in enumerate(shell_of):
        shells.setdefault(s, []).append(v)
    in_skirt = [coords[v][1] < skirt_top and not skip[v] for v in range(count)]
    skirt_size = {s: sum(1 for v in vs if in_skirt[v]) for s, vs in shells.items()}
    largest = max(skirt_size.values()) if skirt_size else 0
    big = set(s for s, n in skirt_size.items() if largest and n >= 0.1 * largest)
    edge_use = {}
    for tri in triangles:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            key = (a, b) if a < b else (b, a)
            edge_use[key] = edge_use.get(key, 0) + 1
    # Only open edges that run mostly up/down: a slit is vertical, while a
    # hem or a separate skirt's waistband is horizontal.
    border = set()
    for (a, b), n in edge_use.items():
        if n != 1:
            continue
        d = sub(points[a], points[b])
        rise = abs(dot(d, frame['up']))
        if rise >= 0.7 * math.sqrt(dot(d, d)):
            border.update((a, b))
    hem = {s: min(coords[v][1] for v in vs) for s, vs in shells.items()}
    slit_vertices = {1: [], -1: []}
    edge_vertices = {1: [], -1: []}
    for v in border:
        s = shell_of[v]
        if s in big and in_skirt[v]:
            side = 1 if coords[v][0] >= 0.0 else -1
            edge_vertices[side].append(v)          # whole edge, down to the hem
            if coords[v][1] > hem[s] + 0.3 * leg:
                slit_vertices[side].append(v)      # the part that makes it a slit
    slits = [{'side': side, 'vertices': vs, 'top': max(coords[v][1] for v in vs),
              'edge': edge_vertices[side]}
             for side, vs in slit_vertices.items() if len(vs) >= 10]
    strips = []
    for s, vs in shells.items():
        if s in big or len(vs) < 20 or not slits:
            continue
        if sum(1 for v in vs if in_skirt[v]) < 0.7 * len(vs):
            continue
        heights = [coords[v][1] for v in vs]
        low, high = min(heights), max(heights)
        length = high - low
        if length < 0.5 * leg:
            continue
        # width: median horizontal size of 8 height bands
        bands = [[] for _ in range(8)]
        for v in vs:
            bands[min(7, int(8 * (coords[v][1] - low) / length))].append(v)
        widths = []
        for band in bands:
            if len(band) < 2:
                continue
            lat = [coords[v][0] for v in band]
            fwd = [coords[v][2] for v in band]
            widths.append(math.hypot(max(lat) - min(lat), max(fwd) - min(fwd)))
        if not widths:
            continue
        width = sorted(widths)[len(widths) // 2]
        if width > 0.3 * length:
            continue
        # The strip belongs to the leg on its own side (a wrap edge may cross
        # the centre near the waist, so the nearest open edge is not enough).
        side = 1 if sum(coords[v][0] for v in vs) >= 0.0 else -1
        gap = None
        for slit in slits:
            d = min(math.sqrt(dot(sub(points[v], points[w]), sub(points[v], points[w])))
                    for v in vs[::max(1, len(vs) // 60)] for w in slit['vertices'][::max(1, len(slit['vertices']) // 60)])
            gap = d if gap is None else min(gap, d)
        if gap is not None and gap <= distance and any(sl['side'] == side for sl in slits):
            strips.append({'shell': s, 'side': side, 'vertices': vs, 'length': length,
                           'width': width, 'gap': gap})
    return {'slits': slits, 'strips': strips}


def edge_band(points, adjacency, seeds, width):
    """Geodesic distance (along mesh edges) from `seeds`, up to `width`."""
    import heapq
    best = {v: 0.0 for v in seeds}
    heap = [(0.0, v) for v in seeds]
    heapq.heapify(heap)
    while heap:
        d, v = heapq.heappop(heap)
        if d > best.get(v, 1e30):
            continue
        for n in adjacency[v]:
            step = sub(points[v], points[n])
            nd = d + math.sqrt(dot(step, step))
            if nd <= width and nd < best.get(n, 1e30):
                best[n] = nd
                heapq.heappush(heap, (nd, n))
    return best


def average_row(rows, indices, maximum, fallback):
    """One common row for a selection: the mean of its rows, capped to `maximum`."""
    total = {}
    for v in indices:
        for i, w in rows[v].items():
            total[i] = total.get(i, 0.0) + w
    return normalize_row(total, maximum, fallback=fallback)


def hold_selection(rows, adjacency, selected, target, strength, rings, maximum, fallback):
    """Pull selected vertices to one common row (e.g. pelvis only).

    Every selected vertex gets the same mix, so a panel/strip moves as one
    piece and keeps its shape. The pull fades out over `rings` edge rings
    around the selection so the neighbouring fabric blends in.
    Returns (rows, number of changed vertices).
    """
    if not selected or strength <= 0.0:
        return rows, 0
    rings = max(0, int(rings))
    distance = {v: 0 for v in selected}
    frontier = list(selected)
    for ring in range(1, rings + 1):
        nxt = []
        for v in frontier:
            for n in adjacency[v]:
                if n not in distance:
                    distance[n] = ring
                    nxt.append(n)
        frontier = nxt
    rows = list(rows)
    for v, d in distance.items():
        amount = strength * (1.0 - smoothstep(d / float(rings + 1)))
        if amount > 0.0:
            rows[v] = normalize_row(mix_rows(rows[v], target, amount), maximum, fallback=fallback)
    return rows, len(distance)


def remove_opposite_knee(row, side, pairs):
    """Move lower-leg weight of the non-dominant side back to its thigh."""
    if side == 0.0:
        return row
    wrong = 'knee_r' if side > 0.0 else 'knee_l'
    thigh = 'thigh_r' if side > 0.0 else 'thigh_l'
    row = dict(row)
    for k_index, t_index in zip(pairs[wrong], pairs[thigh]):
        if k_index is None or t_index is None:
            continue
        moved = row.pop(k_index, 0.0)
        if moved:
            row[t_index] = row.get(t_index, 0.0) + moved
    return row


# ------------------------------------------------------------- matrices
def mat_identity():
    return [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]


def mat_mul(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def mat_from_flat(values):
    return [list(values[r * 4:r * 4 + 4]) for r in range(4)]


def mat_inverse(m):
    n = 4
    a = [list(m[r]) + [1.0 if r == c else 0.0 for c in range(n)] for r in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-14:
            raise ValueError('Matrix ist nicht invertierbar.')
        a[col], a[pivot] = a[pivot], a[col]
        p = a[col][col]
        a[col] = [x / p for x in a[col]]
        for r in range(n):
            if r != col and a[r][col]:
                f = a[r][col]
                a[r] = [x - f * y for x, y in zip(a[r], a[col])]
    return [row[n:] for row in a]


def transform_point(point, m):
    x, y, z = point
    out = [x * m[0][c] + y * m[1][c] + z * m[2][c] + m[3][c] for c in range(4)]
    return (out[0] / out[3], out[1] / out[3], out[2] / out[3]) if abs(out[3] - 1.0) > 1e-12 else tuple(out[:3])


def skin_point(rest, row, skin_mats):
    """Linear blend skinning: rest * sum(w * bindPre_j * world_j)."""
    blended = [[0.0] * 4 for _ in range(4)]
    for i, w in row.items():
        m = skin_mats[i]
        for r in range(4):
            for c in range(4):
                blended[r][c] += w * m[r][c]
    return transform_point(rest, blended)


def unskin_point(posed, row, skin_mats):
    """Inverse linear blend skinning: rest point that skins to `posed`."""
    blended = [[0.0] * 4 for _ in range(4)]
    for i, w in row.items():
        m = skin_mats[i]
        for r in range(4):
            for c in range(4):
                blended[r][c] += w * m[r][c]
    return transform_point(posed, mat_inverse(blended))
