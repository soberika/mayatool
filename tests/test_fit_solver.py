# -*- coding: utf-8 -*-
"""Checks for mcd_fit_solver (poses, skinning, result files) outside Maya."""

import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mcd_fit_apply as fa  # noqa: E402
import mcd_fit_solver as fs  # noqa: E402


def world(x, y, z):
    m = np.eye(4)
    m[3, :3] = (x, y, z)
    return [float(v) for v in m.reshape(-1)]


class FakeData:
    """Y-up, character faces +Z, left is +X (like the creator's scene)."""

    def __init__(self):
        spec = [('mPelvis', None, (0, 100, 0)),
                ('mHipLeft', 'mPelvis', (10, 95, 0)), ('mKneeLeft', 'mHipLeft', (10, 50, 0)),
                ('mAnkleLeft', 'mKneeLeft', (10, 8, 0)),
                ('mHipRight', 'mPelvis', (-10, 95, 0)), ('mKneeRight', 'mHipRight', (-10, 50, 0)),
                ('mAnkleRight', 'mKneeRight', (-10, 8, 0))]
        paths = {}
        self.joints = []
        for name, parent, pos in spec:
            paths[name] = (paths[parent] if parent else '') + '|' + name
            self.joints.append({'name': name, 'path': paths[name],
                                'parent': paths[parent] if parent else None,
                                'type': 'joint', 'world_matrix': world(*pos)})


class PoseTests(unittest.TestCase):
    def setUp(self):
        self.rig = fs.Rig(FakeData())

    def test_axes(self):
        self.assertTrue(np.allclose(self.rig.axes['up'], (0, 1, 0)))
        self.assertTrue(np.allclose(self.rig.axes['left'], (1, 0, 0)))
        self.assertTrue(np.allclose(self.rig.axes['forward'], (0, 0, 1)))

    def test_flex_moves_knee_forward_and_knee_bend_moves_ankle_back(self):
        posed = self.rig.pose(fs.merge(fs.leg('L', 90, 90)))
        knee = posed[self.rig.index['mKneeLeft'], 3, :3]
        ankle = posed[self.rig.index['mAnkleLeft'], 3, :3]
        self.assertAlmostEqual(knee[1], 95.0, places=6)        # thigh horizontal
        self.assertAlmostEqual(knee[2], 45.0, places=6)        # 45 forward
        self.assertAlmostEqual(ankle[2], 45.0, places=6)       # shin straight down
        self.assertAlmostEqual(ankle[1], 95.0 - 42.0, places=6)
        # The other leg does not move.
        self.assertTrue(np.allclose(posed[self.rig.index['mKneeRight']],
                                    self.rig.rest[self.rig.index['mKneeRight']]))

    def test_adduction_moves_both_legs_to_the_middle(self):
        for side, joint in (('L', 'mKneeLeft'), ('R', 'mKneeRight')):
            posed = self.rig.pose(fs.leg(side, adduct=20))
            rest_x = self.rig.rest[self.rig.index[joint], 3, 0]
            self.assertLess(abs(posed[self.rig.index[joint], 3, 0]), abs(rest_x))


class BreastBounceTests(unittest.TestCase):
    def test_pecs_move_outward_and_rest_is_kept(self):
        data = FakeData()
        for name, x in (('LEFT_PEC', 8), ('RIGHT_PEC', -8)):
            data.joints.append({'name': name, 'path': '|mPelvis|' + name, 'parent': '|mPelvis',
                                'type': 'joint', 'world_matrix': world(x, 130, 5)})
        rig = fs.Rig(data)
        worlds = fs.breast_bounce_worlds(rig, 1.0)
        self.assertEqual(len(worlds), 6)
        self.assertTrue(np.allclose(worlds[0], rig.rest))
        moved_out = worlds[4]                      # sideways, mirrored: both outward
        self.assertAlmostEqual(moved_out[rig.index['LEFT_PEC'], 3, 0], 9.0)
        self.assertAlmostEqual(moved_out[rig.index['RIGHT_PEC'], 3, 0], -9.0)
        self.assertTrue(np.allclose(moved_out[rig.index['mKneeLeft']],
                                    rig.rest[rig.index['mKneeLeft']]))


class ResultFileTests(unittest.TestCase):
    def test_round_trip_and_dense_order(self):
        class Mesh:
            name = 'dress'
            count = 2
            influences = ['mPelvis', 'mHipLeft']
            geom_matrix = np.diag([2.0, 2.0, 2.0, 1.0])

        class Dress:
            mesh = Mesh()

        weights = np.array([[1.0, 0.0], [0.25, 0.75]])
        offsets = np.array([[0.0, 0.0, 0.0], [0.2, 0.0, 0.0]])
        path = os.path.join(tempfile.mkdtemp(), 'r.json.gz')
        fs.save_result(path, None, Dress(), weights, offsets, {}, {})
        data = fa.load_result(path)
        # Offsets are stored in object space: divided by the geomMatrix scale.
        self.assertAlmostEqual(data['offsets_object'][3], 0.1)
        flat = fa.dense_weights(data, ['mHipLeft', 'mPelvis'])
        self.assertEqual(flat, [0.0, 1.0, 0.75, 0.25])


if __name__ == '__main__':
    unittest.main()
