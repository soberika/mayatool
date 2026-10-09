# -*- coding: utf-8 -*-
"""Checks for mcd_sl_anim outside Maya: python -m unittest discover tests"""

import math
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mcd_sl_anim as sa  # noqa: E402


def quat_angle(a, b):
    dot = abs(sum(x * y for x, y in zip(a, b)))
    return 2.0 * math.acos(min(1.0, dot))


def rot_matrix(axis, angle):
    q = sa.quat_from_axis_angle(axis, angle)
    x, y, z, w = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


class FormatTests(unittest.TestCase):
    def test_header_layout_matches_viewer(self):
        anim = sa.make_hold(['mTail1'], duration=1.5, priority=2, ease=0.25)
        data = sa.write_anim(anim)
        version, sub, prio, duration = struct.unpack_from('<HHif', data, 0)
        self.assertEqual((version, sub, prio), (1, 0, 2))
        self.assertAlmostEqual(duration, 1.5, places=6)
        self.assertEqual(data[12:13], b'\0')            # empty emote string
        loop_in, loop_out, loop, ease_in, ease_out, hand, joints = \
            struct.unpack_from('<ffiffII', data, 13)
        self.assertEqual((loop, hand, joints), (1, sa.HAND_POSE_RELAXED, 1))
        self.assertAlmostEqual(ease_in, 0.25, places=6)
        self.assertEqual(data[41:48], b'mTail1\0')
        self.assertEqual(data[-4:], b'\0\0\0\0')        # zero constraints

    def test_round_trip_within_quantization(self):
        anim = sa.make_sway_test(sa.BONE_SETS['hindlimbs'], duration=2.0, fps=24)
        back = sa.read_anim(sa.write_anim(anim))
        self.assertEqual([t.name for t in back.tracks], [t.name for t in anim.tracks])
        pos_step = 2 * sa.POS_LIMIT / sa.U16MAX
        for src, dst in zip(anim.tracks, back.tracks):
            self.assertEqual(len(src.rot_keys), len(dst.rot_keys))
            for (t0, q0), (t1, q1) in zip(src.rot_keys, dst.rot_keys):
                self.assertLess(abs(t0 - t1), 2.0 / sa.U16MAX * 2)
                self.assertLess(quat_angle(q0, q1), math.radians(0.02))
            for (_, p0), (_, p1) in zip(src.pos_keys, dst.pos_keys):
                for a, b in zip(p0, p1):
                    self.assertLessEqual(abs(a - b), pos_step + 1e-9)

    def test_negative_w_is_flipped(self):
        q = (0.1, 0.2, 0.3, -0.927)
        x, y, z = sa.pack_rotation(q)
        self.assertLess(x, 0)
        restored = sa.unpack_rotation((x, y, z))
        self.assertLess(quat_angle(sa.quat_normalize(q), restored), 1e-6)

    def test_dump_size_is_small(self):
        anim = sa.make_sway_test(sa.BONE_SETS['tail'], duration=2.0, fps=24)
        self.assertLess(len(sa.write_anim(anim)), 5000)


class ValidationTests(unittest.TestCase):
    def test_body_bones_refused_by_default(self):
        track = sa.JointTrack('mHipLeft', 1, [(0.0, (0, 0, 0, 1)), (1.0, (0, 0, 0, 1))])
        anim = sa.Anim([track], 1.0)
        self.assertTrue(any('kein Stoff-Bone' in p for p in sa.validate(anim)))
        self.assertEqual(sa.validate(anim, allow_body_bones=True), [])

    def test_duration_limit(self):
        anim = sa.make_hold(['mTail1'], duration=61.0)
        self.assertTrue(any('60' in p for p in sa.validate(anim)))

    def test_position_limit(self):
        anim = sa.make_hold(['mTail1'], offsets={'mTail1': (6.0, 0, 0)})
        self.assertTrue(any('5 m' in p for p in sa.validate(anim)))

    def test_too_dense_keys(self):
        q = (0, 0, 0, 1)
        track = sa.JointTrack('mTail1', 1, [(0.0, q), (0.0000001, q), (60.0, q)])
        anim = sa.Anim([track], 60.0)
        self.assertTrue(any('zu dicht' in p for p in sa.validate(anim)))

    def test_bad_priority_and_loop(self):
        anim = sa.make_hold(['mTail1'], priority=7)
        anim.loop_in, anim.loop_out = 0.8, 0.2
        problems = sa.validate(anim)
        self.assertTrue(any('Prioritaet' in p for p in problems))
        self.assertTrue(any('Loop' in p for p in problems))

    def test_write_raises(self):
        with self.assertRaises(sa.AnimError):
            sa.write_anim(sa.make_hold(['mTail1'], duration=0.0))


class AxisTests(unittest.TestCase):
    basis = sa.AXIS_PRESETS['y_up_front_z']
    identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

    def test_rest_pose_gives_identity_and_offset(self):
        parent = (self.identity, (0.0, 100.0, 0.0))
        # Maya Y-up, character faces +Z: Maya (x=12.9, y=-12.5, z=-20.4) cm
        # is SL (forward -0.204, left 0.129, up -0.125) m.
        child = (self.identity, (12.9, 87.5, -20.4))
        rot, pos = sa.sl_local_pose(parent, child, parent, child, self.basis, 0.01)
        self.assertLess(quat_angle(rot, (0, 0, 0, 1)), 1e-9)
        for a, b in zip(pos, (-0.204, 0.129, -0.125)):
            self.assertAlmostEqual(a, b, places=9)

    def test_forward_swing_maps_to_sl_pitch(self):
        # Rotate the child about Maya +X (= SL +Y, the left axis).
        angle = math.radians(20)
        parent = (self.identity, (0.0, 0.0, 0.0))
        rest = (self.identity, (0.0, -50.0, 0.0))
        posed = (rot_matrix((1, 0, 0), angle), (0.0, -50.0, 0.0))
        rot, _ = sa.sl_local_pose(parent, posed, parent, rest, self.basis, 0.01)
        expected = sa.quat_from_axis_angle((0, 1, 0), angle)
        self.assertLess(quat_angle(rot, expected), 1e-9)

    def test_parent_rotation_is_removed(self):
        angle = math.radians(35)
        r = rot_matrix((0, 1, 0), angle)   # Maya Y = SL up
        parent_rest = (self.identity, (0.0, 0.0, 0.0))
        child_rest = (self.identity, (0.0, 0.0, -20.0))
        child_pos = sa._mat_vec(r, (0.0, 0.0, -20.0))
        parent = (r, (0.0, 0.0, 0.0))
        child = (r, child_pos)
        rot, pos = sa.sl_local_pose(parent, child, parent_rest, child_rest, self.basis, 0.01)
        self.assertLess(quat_angle(rot, (0, 0, 0, 1)), 1e-9)
        for a, b in zip(pos, (-0.2, 0.0, 0.0)):
            self.assertAlmostEqual(a, b, places=9)

    def test_quat_from_matrix_all_branches(self):
        for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0)):
            for deg in (10, 170, 179.9):
                q = sa.quat_from_axis_angle(axis, math.radians(deg))
                back = sa.quat_from_matrix(rot_matrix(axis, math.radians(deg)))
                self.assertLess(quat_angle(q, back), 1e-6)


if __name__ == '__main__':
    unittest.main()
