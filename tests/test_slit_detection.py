"""Synthetic check for core.detect_slit_strips. Run: python3 tests/test_slit_detection.py"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcd_dress_rig import core  # noqa: E402


def grid(cols, rows, point, closed):
    verts = [point(c, r) for r in range(rows) for c in range(cols)]
    tris = []
    for r in range(rows - 1):
        for c in range(cols if closed else cols - 1):
            a, b = r * cols + c, r * cols + (c + 1) % cols
            tris += [(a, b, b + cols), (a, b + cols, a + cols)]
    return verts, tris


def skirt_with_slit():
    # Open cylinder (cm, Y up, left = +X): the gap at +X is a slit up to y=90.
    cols, rows = 40, 30
    def skirt(c, r):
        a = 0.15 + (2 * math.pi - 0.3) * c / (cols - 1)       # leave a gap around angle 0 (+X)
        y = 10 + 85 * r / (rows - 1)
        rad = 25 - 0.1 * (y - 10)
        return (rad * math.cos(a), y, rad * math.sin(a))
    verts, tris = grid(cols, rows, skirt, closed=False)
    # The slit only goes up to y=90: close the top rows by joining the first and last column there.
    top = [r for r in range(rows) if 10 + 85 * r / (rows - 1) > 90]
    for r in top[:-1]:
        a, b = r * cols + cols - 1, r * cols
        tris += [(a, b, b + cols), (a, b + cols, a + cols)]
    # A narrow facing strip next to the slit (own shell).
    off = len(verts)
    strip, stris = grid(3, 25, lambda c, r: (23.0 - 0.1 * (10 + 3 * r - 10), 12 + 3 * r, -1.0 + c), False)
    verts += strip
    tris += [(a + off, b + off, c + off) for a, b, c in stris]
    shell_of = [0] * off + [1] * len(strip)
    return verts, tris, shell_of


def test_finds_left_slit_and_strip():
    verts, tris, shell_of = skirt_with_slit()
    frame = core.make_frame((0, 100, 0), (9, 94, 0), (-9, 94, 0), (9, 49, 0), (-9, 49, 0))
    found = core.detect_slit_strips(verts, tris, shell_of, frame, 7.0)
    assert [s['side'] for s in found['slits']] == [1], found['slits']
    assert len(found['strips']) == 1 and found['strips'][0]['side'] == 1, found['strips']
    assert found['strips'][0]['shell'] == 1


def test_closed_skirt_has_no_slit():
    verts, tris = grid(40, 30, lambda c, r: (20 * math.cos(2 * math.pi * c / 40), 10 + 3 * r,
                                             20 * math.sin(2 * math.pi * c / 40)), closed=True)
    frame = core.make_frame((0, 100, 0), (9, 94, 0), (-9, 94, 0), (9, 49, 0), (-9, 49, 0))
    found = core.detect_slit_strips(verts, tris, [0] * len(verts), frame, 7.0)
    assert found == {'slits': [], 'strips': []}, found


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
