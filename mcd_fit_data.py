# -*- coding: utf-8 -*-
"""mcd. Fit Data 0.1 — reads and checks files written by mcd_fit_export.

Runs OUTSIDE Maya (needs numpy). It is the solver's entry point:
  * load(path)              -> FitData with numpy arrays
  * FitData.check()         -> recomputes Maya's linear blend skinning from
                               the exported bind data and compares it with
                               the exported world points (must match)
  * FitData.summary()       -> short German report for the creator

Maya conventions used (row vectors, matrices stored row-major, 16 floats):
    p_world = sum_j w_j * (p_orig * geomMatrix * bindPreMatrix_j * matrix_j)
where matrix_j is the influence's world matrix (skinCluster.matrix[j]).

START:
    python mcd_fit_data.py export.json.gz
"""

import gzip
import json

import numpy as np

VERSION = '0.1'


def _mat(values):
    return np.asarray(values, dtype=float).reshape(4, 4)


class SkinnedMesh:
    def __init__(self, data):
        self.name = data['name']
        self.count = int(data['vertex_count'])
        self.points_world = np.asarray(data['points_world'], dtype=float).reshape(-1, 3)
        orig = data.get('points_orig_object')
        self.points_orig = (np.asarray(orig, dtype=float).reshape(-1, 3)
                            if orig is not None else None)
        self.geom_matrix = _mat(data['geom_matrix'])
        self.world_matrix = _mat(data['world_matrix'])
        self.influences = [i['name'] for i in data['influences']]
        self.influence_paths = [i['path'] for i in data['influences']]
        self.bind_pre = np.stack([_mat(i['bind_pre_matrix']) for i in data['influences']])
        self.matrix = np.stack([_mat(i['matrix']) for i in data['influences']])
        self.max_influences = data.get('max_influences')
        self.bind_deviation = data.get('bind_deviation', 0.0)
        counts = data['face_counts']
        flat = data['face_vertices']
        self.faces, k = [], 0
        for c in counts:
            self.faces.append(flat[k:k + c])
            k += c
        # Dense weights (vertices x influences); garments and bodies are small enough.
        self.weights = np.zeros((self.count, len(self.influences)))
        for v, row in enumerate(data['weights']):
            for i, w in row:
                self.weights[v, i] = w
        if self.points_world.shape[0] != self.count or len(data['weights']) != self.count:
            raise ValueError('%s: Vertexzahlen passen nicht zusammen.' % self.name)

    def rest_object_points(self):
        """Pre-skin points; falls back to world points if no orig shape was found."""
        if self.points_orig is not None:
            return self.points_orig, True
        return self.points_world, False

    def skin(self, joint_world=None):
        """Linear blend skinning with Maya's formula. joint_world: (n, 4, 4) world
        matrices per influence (default: the exported current matrices)."""
        mats = self.matrix if joint_world is None else joint_world
        rest, is_orig = self.rest_object_points()
        homog = np.hstack([rest, np.ones((len(rest), 1))])
        if is_orig:
            homog = homog @ self.geom_matrix
        out = np.zeros((len(rest), 4))
        for j in range(len(self.influences)):
            w = self.weights[:, j]
            idx = np.nonzero(w)[0]
            if len(idx):
                out[idx] += w[idx, None] * (homog[idx] @ (self.bind_pre[j] @ mats[j]))
        return out[:, :3]

    def influences_per_vertex(self):
        return (self.weights > 1e-6).sum(axis=1)


class FitData:
    def __init__(self, payload):
        if payload.get('format') != 'mcd-fit-data':
            raise ValueError('Keine mcd-Fit-Datei.')
        self.meta = {k: payload.get(k) for k in (
            'exporter', 'exported_at', 'maya_version', 'scene', 'linear_unit', 'up_axis',
            'current_frame', 'warnings')}
        self.body = SkinnedMesh(payload['body'])
        self.dress = SkinnedMesh(payload['dress'])
        self.joints = payload['joints']
        self.joint_by_path = {j['path']: j for j in self.joints}

    def check(self):
        """Max distance between recomputed LBS and exported points, per mesh."""
        result = {}
        for label, mesh in (('body', self.body), ('dress', self.dress)):
            diff = np.linalg.norm(mesh.skin() - mesh.points_world, axis=1)
            result[label] = float(diff.max()) if len(diff) else 0.0
        return result

    def summary(self):
        unit = self.meta.get('linear_unit') or '?'
        lines = ['Export: %s, Maya %s, Einheit %s, Up-Achse %s'
                 % (self.meta.get('exported_at'), self.meta.get('maya_version'), unit,
                    self.meta.get('up_axis'))]
        for label, mesh in (('Body', self.body), ('Kleid', self.dress)):
            per_vertex = mesh.influences_per_vertex()
            lines.append('%s "%s": %d Vertices, %d Flaechen, %d Einfluesse, bis %d pro Vertex, '
                         'Originalform %s, Abweichung zur Bindepose %.4f'
                         % (label, mesh.name, mesh.count, len(mesh.faces), len(mesh.influences),
                            int(per_vertex.max()) if len(per_vertex) else 0,
                            'ja' if mesh.points_orig is not None else 'nein',
                            mesh.bind_deviation))
        shared = sorted(set(self.dress.influences) - set(self.body.influences))
        if shared:
            lines.append('Kleid-Joints ohne Body-Gewicht: ' + ', '.join(shared))
        check = self.check()
        lines.append('Skinning-Nachrechnung (groesste Abweichung): Body %.5f, Kleid %.5f %s'
                     % (check['body'], check['dress'], unit))
        lines.append('Joints im Skelett: %d' % len(self.joints))
        for warning in self.meta.get('warnings') or []:
            lines.append('Hinweis: ' + warning)
        return '\n'.join(lines)


def load(path):
    opener = gzip.open if path.endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as handle:
        return FitData(json.load(handle))


def _main(argv):
    if not argv:
        print(__doc__)
        return 1
    data = load(argv[0])
    print(data.summary())
    check = data.check()
    return 0 if max(check.values()) < 1e-3 * max(1.0, _scale(data)) else 2


def _scale(data):
    pts = data.body.points_world
    return float(np.ptp(pts, axis=0).max()) / 100.0 if len(pts) else 1.0


if __name__ == '__main__':
    import sys
    sys.exit(_main(sys.argv[1:]))
