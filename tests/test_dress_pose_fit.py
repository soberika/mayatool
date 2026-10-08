"""Sanity tests for dress_pose_fit. Run: python3 tests/test_dress_pose_fit.py"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dress_pose_fit as dpf  # noqa: E402


def test_rotvec_roundtrip():
    rng = np.random.default_rng(0)
    rv = rng.normal(size=(50, 3))
    rv *= (rng.uniform(0, 3.0, 50) / np.linalg.norm(rv, axis=1))[:, None]
    R = dpf.rotvec_to_matrix(rv)
    assert np.allclose(R @ R.transpose(0, 2, 1), np.eye(3), atol=1e-10)
    assert np.allclose(dpf.matrix_to_rotvec(R), rv, atol=1e-6)


def test_simplex_projection():
    rng = np.random.default_rng(1)
    v = rng.normal(size=(200, 6))
    mask = rng.random((200, 6)) < 0.7
    mask[:, 0] = True
    w = dpf.project_simplex(v, mask)
    assert np.all(w >= 0) and np.allclose(w.sum(1), 1) and np.all(w[~mask] == 0)


def _grid(n=12, m=10):
    xs, ys = np.meshgrid(np.linspace(-0.3, 0.3, n), np.linspace(0.2, 1.0, m))
    rest = np.stack([xs.ravel(), ys.ravel(), 0.1 * np.sin(4 * xs.ravel())], 1)
    faces = [[r * n + c, r * n + c + 1, (r + 1) * n + c + 1, (r + 1) * n + c]
             for r in range(m - 1) for c in range(n - 1)]
    return rest, dpf.edges_from_faces(faces)


def _mats(rng, P, J):
    M = np.zeros((P, J, 4, 4))
    M[..., :3, :3] = dpf.rotvec_to_matrix(rng.normal(scale=0.5, size=(P, J, 3)))
    M[..., :3, 3] = rng.normal(scale=0.1, size=(P, J, 3))
    M[..., 3, 3] = 1
    return M


def test_recovers_lbs_weights():
    """Targets made by LBS with smooth 4-sparse weights -> near-exact fit."""
    rng = np.random.default_rng(2)
    rest, edges = _grid()
    N, J, P = len(rest), 5, 8
    centers = rng.uniform(-0.3, 0.3, size=(J, 2))
    raw = np.exp(-((rest[:, None, :2] - centers[None]) ** 2).sum(-1) / 0.05)
    np.put_along_axis(raw, np.argsort(raw, 1)[:, :J - 4], 0.0, axis=1)
    W = raw / raw.sum(1, keepdims=True)
    mats = _mats(rng, P, J)
    targets = np.stack([dpf.skin(rest, W, m) for m in mats])
    w0 = np.full((N, J), 1.0 / J)
    cfg = dpf.FitConfig(fit_rest=False, weight_smooth=1e-4, weight_prior=0.0, iterations=6)
    Wf, _, hist = dpf.fit(rest, edges, mats, targets, w0, np.ones((N, J), bool), cfg)
    assert hist[-1] < 2e-3, hist
    assert (Wf > 1e-6).sum(1).max() <= 4


def test_rest_offset_recovers_shift():
    """Known weights, targets made from a shifted rest -> offset is found."""
    rng = np.random.default_rng(3)
    rest, edges = _grid()
    N, J = len(rest), 3
    W = np.zeros((N, J))
    W[:, 0] = 1 - (rest[:, 1] - 0.2) / 0.8
    W[:, 1] = 1 - W[:, 0]
    mats = _mats(rng, 6, J)
    shift = np.zeros_like(rest)
    shift[:, 2] = 0.02 * np.exp(-((rest[:, 0]) ** 2 + (rest[:, 1] - 0.6) ** 2) / 0.02)
    targets = np.stack([dpf.skin(rest + shift, W, m) for m in mats])
    cfg = dpf.FitConfig(fit_rest=True, locked=None, iterations=4, rest_damping=1e-4,
                        rest_smooth=1e-3, bind_weight=1e-6, weight_smooth=0, weight_prior=1.0)
    cand = W > 0
    _, d, hist = dpf.fit(rest, edges, mats, targets, W, cand, cfg)
    assert np.abs(d - shift).max() < 2e-3, np.abs(d - shift).max()


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
