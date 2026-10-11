# -*- coding: utf-8 -*-
"""Checks for mcd_fit_deform outside Maya."""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mcd_fit_deform as fdf  # noqa: E402
import mcd_fit_solver as fs  # noqa: E402
from test_fit_solver import FakeData  # noqa: E402


class AxisMapTests(unittest.TestCase):
    def test_y_up_scene_matches_z_up_scene(self):
        source = FakeData()
        target = FakeData()
        for joint in target.joints:            # same skeleton, Z-up scene: (x, y, z) -> (z, x, y)
            m = np.array(joint['world_matrix']).reshape(4, 4)
            m[3, :3] = m[3, [2, 0, 1]]
            joint['world_matrix'] = [float(v) for v in m.reshape(-1)]
        rs, rt = fs.Rig(source), fs.Rig(target)
        rot, shift = fdf.axis_map(rs, rt)
        for name in ('mPelvis', 'mKneeLeft', 'mAnkleRight'):
            self.assertTrue(np.allclose(rt.position(name) @ rot + shift, rs.position(name)))


class FieldTests(unittest.TestCase):
    def test_bigger_target_pushes_outward(self):
        # Two spheres-ish point sets: target 2 cm larger.
        rng = np.random.default_rng(0)
        d = rng.normal(size=(800, 3))
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        from scipy.spatial import ConvexHull
        tris = ConvexHull(d).simplices.copy()
        # Consistent outward winding, like a real body mesh.
        n = np.cross(d[tris[:, 1]] - d[tris[:, 0]], d[tris[:, 2]] - d[tris[:, 0]])
        flip = (n * d[tris].mean(1)).sum(1) < 0
        tris[flip] = tris[flip][:, ::-1]
        src = fs.BodySurface(d * 10.0, tris)
        tgt = fs.BodySurface(d * 12.0, tris)
        field, weight = fdf.body_field(src.points, src, tgt, np.array([0.0, 1.0, 0.0]),
                                       max_distance=5.0)
        mid = np.abs(src.points[:, 1]) < 5.0
        radial = (field[mid] * d[mid]).sum(1)
        self.assertTrue(np.all(weight[mid] > 0.5))
        self.assertAlmostEqual(float(np.median(radial)), 2.0, delta=0.3)


if __name__ == '__main__':
    unittest.main()
