# -*- coding: utf-8 -*-
"""mcd. Kleid aufweiten 0.1 — widen the skirt of an UNRIGGED dress slightly.

Works with any version of the auto rig: run this first, then rig the copy.

START: Script Editor, Python tab, paste everything, execute. Or:
    import mcd_dress_widen; mcd_dress_widen.show()

USE:
  1. Body/skeleton in bind pose (SL joint names: mPelvis, mHipLeft/Right,
     optionally mFootLeft + mToeLeft to detect the front).
  2. Select the ORIGINAL dress (not the rigged _autoRig copy).
  3. Set the values, click 'Kopie aufweiten'. A copy '<name>_weiter' is
     created and selected; the original is not touched. Rig that copy.

WHAT IT DOES:
  Skirt vertices move horizontally away from the vertical axis through the
  pelvis. All layers (lining, slit overlaps) move the same way, so they
  stay together. Fades in below 'Beginn ueber Becken' over 'Uebergang'.
  'Extra hinten Mitte' adds more at the back centre, fading towards the
  sides (that area loses volume most when both thighs blend).
Values are in cm and converted to the scene unit.
"""

import math

VERSION = '0.1'
WINDOW = 'mcdDressWidenWindow'
UNIT_CM = {'mm': 10.0, 'cm': 1.0, 'm': 0.01, 'km': 0.00001,
           'in': 1 / 2.54, 'ft': 1 / 30.48, 'yd': 1 / 91.44, 'mi': 1 / 160934.4}


def _smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def widen_offsets(points, pelvis, up, lateral, forward, half_width, p):
    """Pure math (no Maya). Returns one offset vector per point.

    points: list of (x,y,z) in scene units; pelvis: (x,y,z);
    up/lateral/forward: unit vectors; half_width: half the hip distance;
    p: dict with amount, back_extra, start, transition (scene units).
    """
    out = []
    for q in points:
        d = [q[i] - pelvis[i] for i in range(3)]
        h = sum(d[i] * up[i] for i in range(3))
        fade = _smoothstep((p['start'] - h) / max(p['transition'], 1e-9))
        radial = [d[i] - h * up[i] for i in range(3)]
        r = math.sqrt(sum(c * c for c in radial))
        if fade <= 0.0 or r < 1e-9:
            out.append((0.0, 0.0, 0.0))
            continue
        radial = [c / r for c in radial]
        back = max(0.0, -sum(radial[i] * forward[i] for i in range(3)))
        # full at the back centre, half at 45 degrees, zero at the sides/front
        amount = fade * (p['amount'] + p['back_extra'] * back * back)
        out.append(tuple(c * amount for c in radial))
    return out


# --------------------------------------------------------------------------
# Maya part
# --------------------------------------------------------------------------
def _joint(cmds, name):
    found = cmds.ls(name, '*:' + name, type='joint', long=True) or []
    return found[0] if found else None


def _pos(cmds, node):
    return cmds.xform(node, query=True, worldSpace=True, translation=True)


def _norm(v):
    n = math.sqrt(sum(c * c for c in v))
    if n < 1e-9:
        raise ValueError('Achsen nicht bestimmbar (Joints liegen aufeinander).')
    return [c / n for c in v]


def _frame(cmds):
    up = [0.0, 1.0, 0.0] if cmds.upAxis(query=True, axis=True) == 'y' else [0.0, 0.0, 1.0]
    pelvis, hl, hr = (_joint(cmds, n) for n in ('mPelvis', 'mHipLeft', 'mHipRight'))
    if not (pelvis and hl and hr):
        raise ValueError('mPelvis / mHipLeft / mHipRight nicht gefunden. '
                         'SL-Skelett in die Szene laden.')
    lat = [a - b for a, b in zip(_pos(cmds, hl), _pos(cmds, hr))]
    half_width = 0.5 * math.sqrt(sum(c * c for c in lat))
    lat = _norm([c - sum(c2 * u for c2, u in zip(lat, up)) * u for c, u in zip(lat, up)])
    foot, toe = _joint(cmds, 'mFootLeft'), _joint(cmds, 'mToeLeft')
    if foot and toe:
        fwd = [a - b for a, b in zip(_pos(cmds, toe), _pos(cmds, foot))]
        h = sum(c * u for c, u in zip(fwd, up))
        fwd = _norm([c - h * u for c, u in zip(fwd, up)])
    else:
        # up x lateral, with lateral pointing to the character's left
        fwd = _norm([lat[1] * up[2] - lat[2] * up[1], lat[2] * up[0] - lat[0] * up[2],
                     lat[0] * up[1] - lat[1] * up[0]])
        fwd = [-c for c in fwd]
    return _pos(cmds, pelvis), up, lat, fwd, half_width, bool(foot and toe)


def widen_selected(amount_cm, back_cm, start_cm, transition_cm):
    import maya.cmds as cmds
    import maya.api.OpenMaya as om
    sel = cmds.ls(selection=True, objectsOnly=True, long=True) or []
    if len(sel) != 1:
        raise ValueError('Bitte genau EIN Kleid (das Original) auswaehlen.')
    node = sel[0]
    if cmds.nodeType(node) == 'mesh':
        node = cmds.listRelatives(node, parent=True, fullPath=True)[0]
    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True, fullPath=True, type='mesh')
    if not shapes:
        raise ValueError('Auswahl ist kein Polygon-Mesh.')
    if cmds.ls(cmds.listHistory(shapes[0], pruneDagObjects=True) or [], type='skinCluster'):
        raise ValueError('Dieses Mesh ist schon geriggt. Bitte das ungeriggte ORIGINAL waehlen.')
    k = 1.0 / UNIT_CM[cmds.currentUnit(query=True, linear=True)]
    pelvis, up, lat, fwd, half_width, front_ok = _frame(cmds)
    params = {'amount': amount_cm * k, 'back_extra': back_cm * k,
              'start': start_cm * k, 'transition': transition_cm * k}
    cmds.undoInfo(openChunk=True, chunkName='mcdDressWiden')
    try:
        copy = cmds.duplicate(node, name=node.rsplit('|', 1)[-1] + '_weiter')[0]
        shape = cmds.listRelatives(copy, shapes=True, noIntermediate=True, fullPath=True)[0]
        selection = om.MSelectionList()
        selection.add(shape)
        fn = om.MFnMesh(selection.getDagPath(0))
        pts = fn.getPoints(om.MSpace.kWorld)
        offsets = widen_offsets([(p.x, p.y, p.z) for p in pts], pelvis, up, lat, fwd,
                                half_width, params)
        moved = 0
        for i, o in enumerate(offsets):
            if o != (0.0, 0.0, 0.0):
                pts[i] = om.MPoint(pts[i].x + o[0], pts[i].y + o[1], pts[i].z + o[2])
                moved += 1
        fn.setPoints(pts, om.MSpace.kWorld)
        cmds.select(copy)
    finally:
        cmds.undoInfo(closeChunk=True)
    note = '' if front_ok else ('\nHinweis: mFootLeft/mToeLeft fehlen, vorne wurde aus den '
                                'Hueften geschaetzt. Ergebnis von hinten pruefen.')
    return '%s erstellt, %d Vertices verschoben.%s' % (copy.rsplit('|', 1)[-1], moved, note)


def show():
    import maya.cmds as cmds
    if cmds.window(WINDOW, exists=True):
        cmds.deleteUI(WINDOW)
    cmds.window(WINDOW, title='mcd. Kleid aufweiten %s' % VERSION, sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6, columnAttach=('both', 8))
    cmds.text(label='ORIGINAL-Kleid waehlen (ungeriggt), Body in Bindepose.', align='left')
    fields = {}
    for key, label, value in (('amount', 'Rock aufweiten (cm)', 0.6),
                              ('back', 'Extra hinten Mitte (cm)', 0.6),
                              ('start', 'Beginn ueber Becken (cm)', 0.0),
                              ('transition', 'Uebergang nach unten (cm)', 15.0)):
        fields[key] = cmds.floatFieldGrp(label=label, numberOfFields=1, value1=value,
                                         precision=2, columnWidth2=(190, 70))

    def run(*_):
        v = {k: cmds.floatFieldGrp(f, query=True, value1=True) for k, f in fields.items()}
        try:
            msg = widen_selected(v['amount'], v['back'], v['start'], v['transition'])
            cmds.confirmDialog(title='Fertig', message=msg + '\nJetzt diese Kopie riggen.')
        except Exception as exc:  # show every problem to the user
            cmds.confirmDialog(title='Fehler', message=str(exc))

    cmds.button(label='Kopie aufweiten', height=34, command=run)
    cmds.showWindow(WINDOW)


if __name__ == '__main__':
    try:
        show()
    except ImportError:
        pass
