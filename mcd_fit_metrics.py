# -*- coding: utf-8 -*-
"""mcd. Fit Metrics 0.1 — measures garment deformation for rig comparisons.

STAGE 0 OF THE STATE CLOTH LAYER (docs/konzept_kleidung_und_bewegung.md).
Compares rig variants (e.g. A = Dress Auto Rig 0.4, B = new solver) on the
SAME body, poses and clips, split into training and held-out test frames.
It only measures: it never edits meshes, weights or animation.

Metrics per variant and frame:
  clip_frac    share of garment vertices deeper than clip_tol inside the body
  clip_max     deepest penetration (scene units)
  strain_p95   95th percentile of |edge length / rest length - 1|
  strain_max   maximum of the same
  area_p95     95th percentile of |triangle area / rest area - 1|
  jump_max     largest vertex step to the previous frame (consecutive frames)
  accel_max    largest second difference (consecutive frames): popping/jerk
  iou_front    silhouette overlap with a reference mesh, orthographic front
  iou_side     same, orthographic side (the back view equals the front one)
  chamfer_*    mean silhouette contour distance to the reference (scene units)

Every number is reported per frame; summaries show mean AND worst frame, so
a good average cannot hide a broken pose.

START (Maya with Python 3 / API 2.0), with a body and the garment variants
deforming in the scene:
    import mcd_fit_metrics as fm
    fm.report_maya(body='body', variants={'A': 'dress_v04', 'B': 'dress_new'},
                   frames={'train': [1, 10, 20], 'test': [30, 40]},
                   csv_path='C:/temp/vergleich.csv', reference='dress_target')
NOT YET VERIFIED IN MAYA. The pure functions are tested outside Maya.
"""

import math

VERSION = '0.1'


# --- pure geometry ---------------------------------------------------------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _length(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def triangulate(faces):
    """Fan-triangulate polygons given as vertex index lists."""
    tris = []
    for face in faces:
        for i in range(1, len(face) - 1):
            tris.append((face[0], face[i], face[i + 1]))
    return tris


def edges_from_faces(faces):
    edges = set()
    for face in faces:
        for i, a in enumerate(face):
            b = face[(i + 1) % len(face)]
            edges.add((a, b) if a < b else (b, a))
    return sorted(edges)


def percentile(values, p):
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * p / 100.0
    low = int(math.floor(k))
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (k - low)


def edge_strain(rest, posed, edges):
    out = []
    for a, b in edges:
        r = _length(_sub(rest[a], rest[b]))
        if r > 1e-9:
            out.append(abs(_length(_sub(posed[a], posed[b])) / r - 1.0))
    return out


def area_change(rest, posed, tris):
    out = []
    for a, b, c in tris:
        r = _length(_cross(_sub(rest[b], rest[a]), _sub(rest[c], rest[a])))
        if r > 1e-12:
            p = _length(_cross(_sub(posed[b], posed[a]), _sub(posed[c], posed[a])))
            out.append(abs(p / r - 1.0))
    return out


def penetration(signed, clip_tol):
    """signed: distance to the body surface, negative inside."""
    if not signed:
        return 0.0, 0.0
    inside = [d for d in signed if d < -clip_tol]
    return len(inside) / float(len(signed)), (-min(inside) if inside else 0.0)


def motion_steps(previous, current, before_previous=None):
    """Largest vertex step and largest second difference between frames."""
    step = max(_length(_sub(c, p)) for c, p in zip(current, previous)) if current else 0.0
    accel = 0.0
    if before_previous is not None:
        accel = max(_length((c[0] - 2 * p[0] + q[0], c[1] - 2 * p[1] + q[1],
                             c[2] - 2 * p[2] + q[2]))
                    for c, p, q in zip(current, previous, before_previous))
    return step, accel


# --- silhouettes -------------------------------------------------------------------
class Raster:
    """Orthographic binary mask on a fixed square window (shared by variants)."""

    def __init__(self, center, half_size, resolution=160):
        self.center = center
        self.half = float(half_size)
        self.res = int(resolution)
        self.cell = 2.0 * self.half / self.res

    def mask(self, points2d, tris):
        res, cell = self.res, self.cell
        x0, y0 = self.center[0] - self.half, self.center[1] - self.half
        grid = bytearray(res * res)
        for a, b, c in tris:
            pa, pb, pc = points2d[a], points2d[b], points2d[c]
            det = (pb[0] - pa[0]) * (pc[1] - pa[1]) - (pc[0] - pa[0]) * (pb[1] - pa[1])
            if abs(det) < 1e-18:
                continue
            xs = (pa[0], pb[0], pc[0])
            ys = (pa[1], pb[1], pc[1])
            i0 = max(0, int((min(xs) - x0) / cell))
            i1 = min(res - 1, int((max(xs) - x0) / cell))
            j0 = max(0, int((min(ys) - y0) / cell))
            j1 = min(res - 1, int((max(ys) - y0) / cell))
            for j in range(j0, j1 + 1):
                py = y0 + (j + 0.5) * cell
                row = j * res
                for i in range(i0, i1 + 1):
                    px = x0 + (i + 0.5) * cell
                    u = ((pb[0] - px) * (pc[1] - py) - (pc[0] - px) * (pb[1] - py)) / det
                    v = ((pc[0] - px) * (pa[1] - py) - (pa[0] - px) * (pc[1] - py)) / det
                    if u >= -1e-9 and v >= -1e-9 and 1.0 - u - v >= -1e-9:
                        grid[row + i] = 1
        return grid

    def boundary(self, grid):
        res = self.res
        cells = []
        for j in range(res):
            for i in range(res):
                if grid[j * res + i] and (
                        i == 0 or j == 0 or i == res - 1 or j == res - 1
                        or not grid[j * res + i - 1] or not grid[j * res + i + 1]
                        or not grid[(j - 1) * res + i] or not grid[(j + 1) * res + i]):
                    cells.append((i, j))
        return cells


def iou(a, b):
    union = sum(1 for x, y in zip(a, b) if x or y)
    if not union:
        return 1.0
    return sum(1 for x, y in zip(a, b) if x and y) / float(union)


def chamfer(raster, a, b):
    """Mean symmetric contour distance in scene units (brute force, small grids)."""
    ca, cb = raster.boundary(a), raster.boundary(b)
    if not ca or not cb:
        return float('inf') if (ca or cb) else 0.0

    def one_way(src, dst):
        total = 0.0
        for i, j in src:
            total += min((i - k) ** 2 + (j - m) ** 2 for k, m in dst)
        return total

    # Sum of squared nearest distances is cheap to compare; report RMS.
    rms = math.sqrt((one_way(ca, cb) + one_way(cb, ca)) / float(len(ca) + len(cb)))
    return rms * raster.cell


def project(points, view, up_index=1):
    """Orthographic projection. 'front' drops the depth axis, 'side' the lateral one.
    Assumes a Y-up scene facing +Z (up_index=1) or Z-up facing +X (up_index=2)."""
    if up_index == 1:
        lateral, depth, up = 0, 2, 1
    else:
        lateral, depth, up = 1, 0, 2
    keep = lateral if view == 'front' else depth
    return [(p[keep], p[up]) for p in points]


def silhouette_scores(points, reference, tris, ref_tris, raster_by_view, up_index=1):
    scores = {}
    for view, raster in raster_by_view.items():
        a = raster.mask(project(points, view, up_index), tris)
        b = raster.mask(project(reference, view, up_index), ref_tris)
        scores['iou_' + view] = iou(a, b)
        scores['chamfer_' + view] = chamfer(raster, a, b)
    return scores


def frame_metrics(rest, posed, edges, tris, signed=None, clip_tol=0.1):
    strain = edge_strain(rest, posed, edges)
    area = area_change(rest, posed, tris)
    row = {'strain_p95': percentile(strain, 95), 'strain_max': max(strain or [0.0]),
           'area_p95': percentile(area, 95)}
    if signed is not None:
        row['clip_frac'], row['clip_max'] = penetration(signed, clip_tol)
    return row


def summarize(rows, keys=('clip_frac', 'clip_max', 'strain_p95', 'strain_max',
                          'area_p95', 'jump_max', 'accel_max', 'iou_front', 'iou_side',
                          'chamfer_front', 'chamfer_side')):
    """Mean and worst value per (variant, set). 'Worst' is max, or min for IoU."""
    groups = {}
    for row in rows:
        groups.setdefault((row['variant'], row['set']), []).append(row)
    out = []
    for (variant, label), items in sorted(groups.items()):
        entry = {'variant': variant, 'set': label, 'frames': len(items)}
        for key in keys:
            values = [r[key] for r in items if key in r and r[key] is not None
                      and math.isfinite(r[key])]
            if not values:
                continue
            worst = min(values) if key.startswith('iou') else max(values)
            worst_frame = next(r['frame'] for r in items if r.get(key) == worst)
            entry[key + '_mean'] = sum(values) / len(values)
            entry[key + '_worst'] = worst
            entry[key + '_worst_frame'] = worst_frame
        out.append(entry)
    return out


def write_csv(rows, path):
    keys = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with open(path, 'w') as handle:
        handle.write(';'.join(keys) + '\n')
        for row in rows:
            cells = []
            for key in keys:
                value = row.get(key, '')
                cells.append('%.6g' % value if isinstance(value, float) else str(value))
            handle.write(';'.join(cells) + '\n')


# --- Maya ----------------------------------------------------------------------------
def _maya_mesh(name):
    import maya.api.OpenMaya as om
    sel = om.MSelectionList()
    sel.add(name)
    dag = sel.getDagPath(0)
    if dag.apiType() == om.MFn.kTransform:
        dag.extendToShape()
    return om.MFnMesh(dag)


def _maya_faces(fn):
    counts, verts = fn.getVertices()
    faces, k = [], 0
    for count in counts:
        faces.append(list(verts[k:k + count]))
        k += count
    return faces


def _maya_points(fn):
    import maya.api.OpenMaya as om
    return [(p.x, p.y, p.z) for p in fn.getPoints(om.MSpace.kWorld)]


def _signed_distances(body_fn, points):
    import maya.api.OpenMaya as om
    out = []
    for p in points:
        point = om.MPoint(p[0], p[1], p[2])
        closest, normal, _ = body_fn.getClosestPointAndNormal(point, om.MSpace.kWorld)
        delta = point - closest
        sign = 1.0 if (delta.x * normal.x + delta.y * normal.y + delta.z * normal.z) >= 0 else -1.0
        out.append(sign * delta.length())
    return out


def report_maya(body, variants, frames, csv_path, reference=None, rest_frame=None,
                clip_tol=0.1, resolution=160, up_index=1, progress=print):
    """Measure every variant on the same frames and write per-frame + summary CSVs.

    body: deforming body mesh. variants: {label: garment mesh}. frames:
    {'train': [...], 'test': [...]} (any labels). reference: optional mesh
    with the target silhouette per frame (e.g. a sculpted/corrected dress).
    rest_frame: frame of the bind pose for strain (default: first frame).
    clip_tol: tolerance in scene units (0.1 = 1 mm in centimetres).
    """
    import maya.cmds as cmds

    all_frames = sorted({f for values in frames.values() for f in values})
    if not all_frames:
        raise ValueError('Keine Frames angegeben.')
    rest_frame = all_frames[0] if rest_frame is None else rest_frame
    body_fn = _maya_mesh(body)
    fns = {label: _maya_mesh(name) for label, name in variants.items()}
    ref_fn = _maya_mesh(reference) if reference else None
    topo = {}
    for label, fn in fns.items():
        faces = _maya_faces(fn)
        topo[label] = (edges_from_faces(faces), triangulate(faces))
    ref_tris = triangulate(_maya_faces(ref_fn)) if ref_fn else None
    current = cmds.currentTime(q=True)
    rows = []
    try:
        cmds.currentTime(rest_frame, edit=True)
        rest = {label: _maya_points(fn) for label, fn in fns.items()}
        rasters = None
        history = {label: [] for label in fns}
        for frame in all_frames:
            cmds.currentTime(frame, edit=True)
            ref_pts = _maya_points(ref_fn) if ref_fn else None
            if ref_pts and rasters is None:
                # One fixed window for all frames and variants, from the reference.
                lo = [min(p[i] for p in ref_pts) for i in range(3)]
                hi = [max(p[i] for p in ref_pts) for i in range(3)]
                half = 0.65 * max(hi[i] - lo[i] for i in range(3))
                mid = [(lo[i] + hi[i]) / 2.0 for i in range(3)]
                rasters = {'front': Raster((mid[0] if up_index == 1 else mid[1], mid[up_index]),
                                           half, resolution),
                           'side': Raster((mid[2] if up_index == 1 else mid[0], mid[up_index]),
                                          half, resolution)}
            labels = [label for label, values in frames.items() if frame in values]
            for variant, fn in fns.items():
                pts = _maya_points(fn)
                edges, tris = topo[variant]
                row = frame_metrics(rest[variant], pts, edges, tris,
                                    _signed_distances(body_fn, pts), clip_tol)
                hist = history[variant]
                if hist and hist[-1][0] == frame - 1:
                    before = hist[-2][1] if len(hist) > 1 and hist[-2][0] == frame - 2 else None
                    row['jump_max'], accel = motion_steps(hist[-1][1], pts, before)
                    if before is not None:
                        row['accel_max'] = accel
                hist.append((frame, pts))
                del hist[:-2]
                if ref_pts:
                    row.update(silhouette_scores(pts, ref_pts, tris, ref_tris, rasters, up_index))
                for label in labels:
                    entry = dict(row, variant=variant, set=label, frame=frame)
                    rows.append(entry)
            if progress:
                progress('Frame %s gemessen' % frame)
    finally:
        cmds.currentTime(current, edit=True)
    write_csv(rows, csv_path)
    summary = summarize(rows)
    stem = csv_path[:-4] if csv_path.lower().endswith('.csv') else csv_path
    write_csv(summary, stem + '_zusammenfassung.csv')
    return rows, summary
