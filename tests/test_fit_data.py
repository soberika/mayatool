# -*- coding: utf-8 -*-
"""Checks for mcd_fit_data with a synthetic export in Maya's conventions."""

import gzip
import json
import math
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mcd_fit_data as fd  # noqa: E402


def translation(x, y, z):
    m = np.eye(4)
    m[3, :3] = (x, y, z)            # Maya: row vectors, translation in the last row
    return m


def rotation_x(deg):
    a = math.radians(deg)
    m = np.eye(4)
    m[1, 1], m[1, 2], m[2, 1], m[2, 2] = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
    return m


def flat(m):
    return [float(v) for v in np.asarray(m).reshape(-1)]


def synthetic(pose_deg=0.0, mesh_offset=(0.0, 0.0, 0.0)):
    """Two joints: hip at y=100, knee at y=50 (child). A 'leg' of 4 points:
    two near the hip (weight hip), two below the knee (weight knee)."""
    hip_bind = translation(0, 100, 0)
    knee_local = translation(0, -50, 0)
    knee_bind = knee_local @ hip_bind
    geom = translation(*mesh_offset)
    orig = np.array([[1.0, 90.0, 0.0], [-1.0, 90.0, 0.0], [1.0, 20.0, 0.0], [-1.0, 20.0, 0.0]])
    orig_obj = orig - np.array(mesh_offset)
    hip_now = hip_bind
    knee_now = rotation_x(pose_deg) @ knee_local @ hip_now
    weights = [[[0, 1.0]], [[0, 1.0]], [[1, 1.0]], [[1, 1.0]]]
    pre = [np.linalg.inv(hip_bind), np.linalg.inv(knee_bind)]
    now = [hip_now, knee_now]
    world = []
    for p, row in zip(orig_obj, weights):
        h = np.append(p, 1.0) @ geom
        acc = np.zeros(4)
        for j, w in row:
            acc += w * (h @ pre[j] @ now[j])
        world.append(acc[:3])
    mesh = {
        'name': 'leg', 'path': '|leg', 'skin_cluster': 'skinCluster1', 'vertex_count': 4,
        'face_counts': [4], 'face_vertices': [0, 1, 3, 2],
        'points_world': [float(c) for p in world for c in p],
        'points_orig_object': [float(c) for p in orig_obj for c in p],
        'world_matrix': flat(geom), 'geom_matrix': flat(geom), 'max_influences': 4,
        'influences': [
            {'name': 'mHipLeft', 'path': '|mPelvis|mHipLeft', 'bind_pre_matrix': flat(pre[0]),
             'matrix': flat(now[0])},
            {'name': 'mKneeLeft', 'path': '|mPelvis|mHipLeft|mKneeLeft',
             'bind_pre_matrix': flat(pre[1]), 'matrix': flat(now[1])}],
        'weights': weights, 'bind_deviation': 0.0,
    }
    return {'format': 'mcd-fit-data', 'format_version': 1, 'exporter': 'test',
            'linear_unit': 'cm', 'up_axis': 'y', 'warnings': [],
            'body': mesh, 'dress': dict(mesh, name='dress'),
            'joints': [{'name': 'mPelvis', 'path': '|mPelvis', 'parent': None, 'type': 'joint',
                        'world_matrix': flat(np.eye(4))}]}, np.array(world)


class FitDataTests(unittest.TestCase):
    def test_bind_pose_round_trip(self):
        payload, _ = synthetic(0.0, mesh_offset=(3.0, 0.0, -2.0))
        data = fd.FitData(payload)
        check = data.check()
        self.assertLess(max(check.values()), 1e-9)

    def test_posed_knee_matches_rotation_about_pivot(self):
        payload, world = synthetic(90.0)
        data = fd.FitData(payload)
        self.assertLess(max(data.check().values()), 1e-9)
        # Lower points rotate 90 deg about the knee (y=50) around X:
        # (1, 20, 0) -> 30 below the knee becomes 30 along -Z or +Z.
        lower = world[2]
        self.assertAlmostEqual(lower[1], 50.0, places=6)
        self.assertAlmostEqual(abs(lower[2]), 30.0, places=6)

    def test_skin_with_new_pose(self):
        payload, _ = synthetic(0.0)
        data = fd.FitData(payload)
        posed = data.dress.matrix.copy()
        posed[1] = rotation_x(45) @ translation(0, -50, 0) @ translation(0, 100, 0)
        points = data.dress.skin(posed)
        self.assertAlmostEqual(np.linalg.norm(points[2] - np.array([1.0, 50.0, 0.0])), 30.0)

    def test_load_gz_and_summary(self):
        payload, _ = synthetic(0.0)
        path = os.path.join(tempfile.mkdtemp(), 'x.json.gz')
        with gzip.open(path, 'wt', encoding='utf-8') as handle:
            json.dump(payload, handle)
        data = fd.load(path)
        text = data.summary()
        self.assertIn('4 Vertices', text)
        self.assertIn('Skinning-Nachrechnung', text)


if __name__ == '__main__':
    unittest.main()
