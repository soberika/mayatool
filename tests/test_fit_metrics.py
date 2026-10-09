# -*- coding: utf-8 -*-
"""Checks for mcd_fit_metrics outside Maya: python -m unittest discover tests"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mcd_fit_metrics as fm  # noqa: E402

QUAD = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
FACES = [[0, 1, 2, 3]]


class GeometryTests(unittest.TestCase):
    def test_strain_and_area(self):
        edges = fm.edges_from_faces(FACES)
        tris = fm.triangulate(FACES)
        stretched = [(x * 2.0, y, z) for x, y, z in QUAD]
        strain = fm.edge_strain(QUAD, stretched, edges)
        self.assertAlmostEqual(max(strain), 1.0)
        self.assertAlmostEqual(min(strain), 0.0)
        self.assertTrue(all(abs(a - 1.0) < 1e-9 for a in fm.area_change(QUAD, stretched, tris)))

    def test_penetration(self):
        frac, depth = fm.penetration([0.5, -0.05, -0.3, -1.2], clip_tol=0.1)
        self.assertAlmostEqual(frac, 0.5)
        self.assertAlmostEqual(depth, 1.2)

    def test_motion_steps(self):
        a = [(0.0, 0.0, 0.0)]
        b = [(1.0, 0.0, 0.0)]
        c = [(3.0, 0.0, 0.0)]
        step, accel = fm.motion_steps(b, c, a)
        self.assertAlmostEqual(step, 2.0)
        self.assertAlmostEqual(accel, 1.0)

    def test_percentile(self):
        self.assertAlmostEqual(fm.percentile([0, 10], 50), 5.0)
        self.assertEqual(fm.percentile([], 95), 0.0)


class SilhouetteTests(unittest.TestCase):
    def setUp(self):
        self.raster = fm.Raster((0.5, 0.5), 1.0, resolution=40)
        self.tris = fm.triangulate(FACES)

    def test_identical_masks(self):
        mask = self.raster.mask([(p[0], p[1]) for p in QUAD], self.tris)
        self.assertEqual(fm.iou(mask, mask), 1.0)
        self.assertEqual(fm.chamfer(self.raster, mask, mask), 0.0)
        # A unit square covers a quarter of the 2x2 window.
        self.assertAlmostEqual(sum(mask) / float(len(mask)), 0.25, delta=0.03)

    def test_shifted_masks(self):
        a = self.raster.mask([(p[0], p[1]) for p in QUAD], self.tris)
        b = self.raster.mask([(p[0] + 0.5, p[1]) for p in QUAD], self.tris)
        self.assertAlmostEqual(fm.iou(a, b), 1.0 / 3.0, delta=0.05)
        self.assertGreater(fm.chamfer(self.raster, a, b), 0.1)

    def test_projection_views(self):
        pts = [(1.0, 2.0, 3.0)]
        self.assertEqual(fm.project(pts, 'front'), [(1.0, 2.0)])
        self.assertEqual(fm.project(pts, 'side'), [(3.0, 2.0)])
        self.assertEqual(fm.project(pts, 'front', up_index=2), [(2.0, 3.0)])


class ReportTests(unittest.TestCase):
    def test_summary_keeps_worst_frame(self):
        rows = [{'variant': 'A', 'set': 'test', 'frame': 1, 'clip_frac': 0.0, 'iou_front': 0.9},
                {'variant': 'A', 'set': 'test', 'frame': 2, 'clip_frac': 0.2, 'iou_front': 0.6}]
        entry = fm.summarize(rows)[0]
        self.assertAlmostEqual(entry['clip_frac_mean'], 0.1)
        self.assertEqual(entry['clip_frac_worst_frame'], 2)
        self.assertEqual(entry['iou_front_worst'], 0.6)

    def test_write_csv(self):
        path = os.path.join(tempfile.mkdtemp(), 'x.csv')
        fm.write_csv([{'a': 1.5, 'b': 'x'}, {'a': 2.0, 'c': 3}], path)
        with open(path) as handle:
            lines = handle.read().splitlines()
        self.assertEqual(lines[0], 'a;b;c')
        self.assertEqual(lines[2], '2;;3')


if __name__ == '__main__':
    unittest.main()
