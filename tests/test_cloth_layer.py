# -*- coding: utf-8 -*-
"""Checks for mcd_cloth_layer's SL animation conversion."""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mcd_cloth_layer as cl  # noqa: E402
import mcd_sl_anim as sa  # noqa: E402


class FakeRig:
    # Maya Y-up, character faces +Z, left is +X (centimetres).
    axes = {'up': np.array([0.0, 1.0, 0.0]), 'left': np.array([1.0, 0.0, 0.0]),
            'forward': np.array([0.0, 0.0, 1.0])}


class StateAnimTests(unittest.TestCase):
    def test_child_key_is_relative_to_moved_parent(self):
        back = np.array([0.0, 0.0, -3.0])          # 3 cm backwards in Maya
        offsets = {'mHindLimb1Left': back, 'mHindLimb2Left': back,
                   'mHindLimb1Right': np.zeros(3), 'mHindLimb2Right': np.zeros(3)}
        anim = sa.read_anim(sa.write_anim(cl.state_anim(FakeRig(), offsets)))
        keys = {t.name: np.array(t.pos_keys[0][1]) for t in anim.tracks}
        d1 = np.array(sa.CLOTH_BONES['mHindLimb1Left'][1])
        d2 = np.array(sa.CLOTH_BONES['mHindLimb2Left'][1])
        # Upper bone: 3 cm back in SL (-X); lower bone: unchanged relative to it.
        self.assertTrue(np.allclose(keys['mHindLimb1Left'], d1 + [-0.03, 0, 0], atol=2e-4))
        self.assertTrue(np.allclose(keys['mHindLimb2Left'], d2, atol=2e-4))
        self.assertTrue(np.allclose(keys['mHindLimb1Right'],
                                    sa.CLOTH_BONES['mHindLimb1Right'][1], atol=2e-4))

    def test_axis_mapping(self):
        v = cl.maya_to_sl([1.0, 2.0, 3.0], FakeRig())
        self.assertTrue(np.allclose(v, [0.03, 0.01, 0.02]))


if __name__ == '__main__':
    unittest.main()
