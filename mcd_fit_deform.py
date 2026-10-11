# -*- coding: utf-8 -*-
"""Move a garment from one mesh body to another (e.g. Legacy -> Reborn).

Both exports (mcd_fit_export) hold the SAME garment on the same SL skeleton,
once with the source body and once with the target body. Scenes may differ in
up axis; the target is matched to the source by its skeleton.

1. Body field: every source body vertex gets the offset to the target surface
   (along the target's normal), where the bodies correspond (close, similar
   normals). Smoothed and filled over the source body (spatial neighbours, so
   separate body parts agree).
2. Garment: kernel average of the field at nearby body points, harmonized
   across garment parts (slit trims, lining), so folds and silhouette stay.
3. Optional correction ('exact'): push outward along the target normals
   until the garment keeps its original gap (0.2..1 cm), smoothed.

Weights are not changed. The result is written for the TARGET scene
(mcd_fit_apply on the target export's skinned garment).

Usage:  python mcd_fit_deform.py source.json.gz target.json.gz out.json.gz [--soft]
"""

import sys

import numpy as np
from scipy.spatial import cKDTree

import mcd_fit_data as fd
import mcd_fit_solver as fs


def axis_map(source_rig, target_rig, names=('mPelvis', 'mHipLeft', 'mKneeLeft', 'mChest',
                                             'mShoulderLeft', 'mAnkleRight')):
    """Rotation R (row vectors: p_source = p_target @ R) from matching joints."""
    names = [n for n in names if n in source_rig.index and n in target_rig.index]
    a = np.array([source_rig.position(n) for n in names])
    b = np.array([target_rig.position(n) for n in names])
    a0, b0 = a - a.mean(0), b - b.mean(0)
    u, _, vt = np.linalg.svd(b0.T @ a0)
    d = np.sign(np.linalg.det(u @ vt))
    rot = u @ np.diag([1.0, 1.0, d]) @ vt
    shift = a.mean(0) - b.mean(0) @ rot
    return rot, shift


def _spatial_links(points, radius, edges=None):
    pairs = cKDTree(points).query_pairs(radius, output_type='ndarray')
    if edges is not None:
        pairs = np.vstack([edges, pairs]) if len(pairs) else edges
    return pairs, np.bincount(pairs.ravel(), minlength=len(points)).astype(float)


def _average(values, links, degree, iterations):
    for _ in range(iterations):
        acc = np.zeros_like(values)
        np.add.at(acc, links[:, 0], values[links[:, 1]])
        np.add.at(acc, links[:, 1], values[links[:, 0]])
        avg = acc / np.maximum(degree, 1.0).reshape((-1,) + (1,) * (values.ndim - 1))
        values = 0.5 * values + 0.5 * avg
    return values


def body_field(source_pts, source_surface, target_surface, up, max_distance=9.0, smooth=15):
    """Per source body vertex: offset to the target surface, and a confidence.
    Only heights the target body covers count (devkits often lack head/feet)."""
    signed, near, normals = target_surface.signed_distance(source_pts, k=6)
    covered = target_surface.points @ up
    lo, hi = covered.min(), covered.max()
    h = source_pts @ up
    valid = ((near < max_distance) & ((source_surface.normals * normals).sum(1) > 0.3)
             & (h > lo + 2.0) & (h < hi - 2.0))
    offset = np.where(valid[:, None], -signed[:, None] * normals, 0.0)
    links, degree = _spatial_links(source_pts, 2.5)
    weight = valid.astype(float)
    total = _average(offset * weight[:, None], links, degree, smooth)
    weight = _average(weight, links, degree, smooth)
    field = np.where(weight[:, None] > 1e-4, total / np.maximum(weight, 1e-6)[:, None], 0.0)
    return field, weight


def garment_offsets(garment_pts, garment_edges, source_surface, field, weight, k=24):
    dist, idx = source_surface.tree.query(garment_pts, k=k)
    sigma = np.maximum(dist[:, :1], 1.0) * 1.5
    kw = np.exp(-(dist / sigma) ** 2) * weight[idx]
    disp = (field[idx] * kw[:, :, None]).sum(1) / np.maximum(kw.sum(1), 1e-9)[:, None]
    links, degree = _spatial_links(garment_pts, 2.0, garment_edges)
    return _average(disp, links, degree, 20), (links, degree)


def keep_gap(garment_pts, disp, gap_source, target_surface, links, passes=12):
    """Push outward (target normals) until the original gap is kept again."""
    target = np.clip(gap_source, 0.2, 1.0)
    amount = np.zeros(len(garment_pts))
    extra = np.zeros_like(disp)
    signed, _, normals = target_surface.signed_distance(garment_pts + disp)
    for _ in range(passes):
        need = np.clip(target - signed, 0.0, 3.0)
        amount = amount + _average(need, links[0], links[1], 40)
        extra = _average(normals * amount[:, None], links[0], links[1], 30)
        signed, _, _ = target_surface.signed_distance(garment_pts + disp + extra)
        if (signed < -0.2).sum() < 50:
            break
    return disp + extra


def deform(source, target, exact=True):
    """Returns (target data, target garment skin, offsets in target pre-skin space)."""
    rs, bs, gs = fs.prepare(source)
    rt, bt, gt = fs.prepare(target)
    if gs.mesh.count != gt.mesh.count:
        raise ValueError('Die beiden Exporte enthalten nicht dasselbe Kleid.')
    rot, shift = axis_map(rs, rt)
    to_source = lambda p: p @ rot + shift
    src_body = bs.deform(rs.rest)
    src_surface = fs.BodySurface(src_body, bs.tris)
    tgt_surface = fs.BodySurface(to_source(bt.deform(rt.rest)), bt.tris)
    garment = gs.deform(rs.rest)
    mismatch = np.abs(to_source(gt.deform(rt.rest)) - garment).max()
    if mismatch > 0.5:
        raise ValueError('Das Kleid liegt in beiden Szenen nicht gleich (%.1f cm).' % mismatch)
    field, weight = body_field(src_body, src_surface, tgt_surface, rs.axes['up'])
    disp, links = garment_offsets(garment, gs.edges, src_surface, field, weight)
    if exact:
        gap, _, _ = src_surface.signed_distance(garment)
        disp = keep_gap(garment, disp, gap, tgt_surface, links)
    world = disp @ rot.T                                      # back to target axes
    blend = np.einsum('vj,jab->vab', gt.weights,
                      np.einsum('jab,jbc->jac', gt.bind, rt.rest[gt.joint]))
    return rt, gt, np.einsum('va,vab->vb', world, np.linalg.inv(blend[:, :3, :3]))


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    source, target = fd.load(argv[0]), fd.load(argv[1])
    _, garment, offsets = deform(source, target, exact='--soft' not in argv)
    fs.save_result(argv[2], target, garment, garment.weights, offsets,
                   {'deform': 'soft' if '--soft' in argv else 'exact'}, {})
    print('gespeichert:', argv[2])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
