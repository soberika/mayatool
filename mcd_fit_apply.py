# -*- coding: utf-8 -*-
"""mcd. Fit Apply 0.1 — puts a fit result onto a COPY of the dress in Maya.

STAGE 1 (docs/konzept_kleidung_und_bewegung.md). Counterpart of
mcd_fit_export: the solver returns a result file (.json.gz) with new skin
weights and, optionally, a small outward change of the rest shape. This
tool creates '<dress>_fit' next to the selected dress:
  * same topology, UVs and position as the selected dress;
  * pre-skin shape = the dress's original shape plus the result's offsets;
  * new skinCluster on the SAME joints with the SAME bind matrices as the
    selected dress, so it deforms exactly like it apart from the changes;
  * the new weights (max 4 per vertex).
The selected dress is not changed. Ctrl+Z removes the copy.

START (Maya with Python 3 / API 2.0): drag this file into the viewport,
select the dress you exported (the skinned copy), click 'ERGEBNIS LADEN'
and pick the result file. NOT YET VERIFIED IN MAYA.
"""

import gzip
import json
import traceback

VERSION = '0.1'
WINDOW = 'mcdFitApplyWindow'


def load_result(path):
    """Read and validate a result file (pure Python, testable outside Maya)."""
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        data = json.load(handle)
    if data.get('format') != 'mcd-fit-result':
        raise ValueError('Das ist keine mcd-Ergebnisdatei.')
    count = int(data['vertex_count'])
    if len(data['weights']) != count or len(data['offsets_object']) != 3 * count:
        raise ValueError('Ergebnisdatei ist unvollstaendig.')
    n = len(data['influences'])
    for v, row in enumerate(data['weights']):
        if not row or len(row) > 4:
            raise ValueError('Vertex %d hat %d Einfluesse.' % (v, len(row)))
        total = sum(w for _, w in row)
        if abs(total - 1.0) > 1e-3 or any(i < 0 or i >= n or w < 0 for i, w in row):
            raise ValueError('Vertex %d hat ungueltige Gewichte.' % v)
    return data


def dense_weights(data, order):
    """Flat weight list (vertex-major) for the influence order 'order' (names)."""
    index = {name: k for k, name in enumerate(order)}
    mapping = [index[name] for name in data['influences']]
    n = len(order)
    flat = [0.0] * (len(data['weights']) * n)
    for v, row in enumerate(data['weights']):
        total = sum(w for _, w in row)
        for i, w in row:
            flat[v * n + mapping[i]] = w / total
    return flat


def _maya():
    import maya.cmds as cmds
    import maya.api.OpenMaya as om
    import maya.api.OpenMayaAnim as oma
    return cmds, om, oma


def _transform_and_shape(name):
    cmds, _, _ = _maya()
    matches = cmds.ls(name, long=True) or []
    if len(matches) != 1:
        raise ValueError('Objekt nicht eindeutig: %s' % name)
    node = matches[0]
    if cmds.nodeType(node) == 'mesh':
        node = cmds.listRelatives(node, parent=True, fullPath=True)[0]
    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True, fullPath=True,
                               type='mesh') or []
    if len(shapes) != 1:
        raise ValueError('%s muss genau ein sichtbares Polygon-Mesh haben.' % node)
    return node, shapes[0]


def _skin_cluster(shape):
    cmds, om, oma = _maya()
    skins = cmds.ls(cmds.listHistory(shape, pruneDagObjects=True) or [], type='skinCluster') or []
    skins = list(dict.fromkeys(skins))
    if len(skins) != 1:
        raise ValueError('Das ausgewaehlte Kleid braucht genau einen skinCluster '
                         '(gefunden: %d). Bitte die geriggte Kopie waehlen.' % len(skins))
    sel = om.MSelectionList()
    sel.add(skins[0])
    return skins[0], oma.MFnSkinCluster(sel.getDependNode(0))


def _dag(name):
    _, om, _ = _maya()
    sel = om.MSelectionList()
    sel.add(name)
    return sel.getDagPath(0)


def _orig_shape(transform, shape, count):
    cmds, _, _ = _maya()
    candidates = []
    for s in cmds.listRelatives(transform, shapes=True, fullPath=True, type='mesh') or []:
        if s != shape and cmds.getAttr(s + '.intermediateObject'):
            if cmds.polyEvaluate(s, vertex=True) == count:
                candidates.append(s)
    return candidates[0] if len(candidates) == 1 else None


def _leaf(path):
    return path.rsplit('|', 1)[-1].rsplit(':', 1)[-1]


def apply_result(dress, data):
    cmds, om, oma = _maya()
    transform, shape = _transform_and_shape(dress)
    skin, fn_skin = _skin_cluster(shape)
    count = om.MFnMesh(_dag(shape)).numVertices
    if count != data['vertex_count']:
        raise ValueError('Das Kleid hat %d Vertices, das Ergebnis %d. Bitte genau das '
                         'exportierte Kleid auswaehlen.' % (count, data['vertex_count']))
    orig = _orig_shape(transform, shape, count)
    if not orig:
        raise ValueError('Die Originalform (vor dem Skinning) wurde nicht gefunden.')
    influences = {}
    for influence in fn_skin.influenceObjects():
        influences[_leaf(influence.fullPathName())] = (
            influence.fullPathName(), fn_skin.indexForInfluenceObject(influence))
    # Joints new to this skin (e.g. HindLimb cloth bones from stage 2) must
    # exist in the scene. Their bind matrix is derived from mPelvis, so it
    # matches the dress's existing bind (cloth bones are at rest relative to
    # the pelvis in the neutral pose).
    added = {}
    for name in data['influences']:
        if name in influences:
            continue
        found = list(dict.fromkeys((cmds.ls(name, long=True, type='joint') or [])
                                   + (cmds.ls('*:' + name, long=True, type='joint') or [])))
        if len(found) != 1:
            raise ValueError('Joint %s fehlt in der Szene oder ist mehrdeutig (%d). Bitte das '
                             'komplette SL-Skelett laden.' % (name, len(found)))
        added[name] = found[0]
    if added and 'mPelvis' not in influences:
        raise ValueError('mPelvis ist kein Einfluss des Kleides; neue Joints koennen nicht '
                         'passend gebunden werden.')
    pelvis_frame = None
    if added:
        pelvis_path, pelvis_index = influences['mPelvis']
        pelvis_frame = (om.MMatrix(cmds.getAttr('%s.bindPreMatrix[%d]' % (skin, pelvis_index)))
                        * om.MMatrix(cmds.getAttr(pelvis_path + '.worldMatrix[0]')))

    cmds.undoInfo(openChunk=True, chunkName='mcdFitApply')
    copy = None
    try:
        copy = cmds.duplicate(transform, name=_leaf(transform) + '_fit')[0]
        cmds.delete(copy, constructionHistory=True)
        for s in cmds.listRelatives(copy, shapes=True, fullPath=True) or []:
            if cmds.getAttr(s + '.intermediateObject'):
                cmds.delete(s)
        copy_shape = cmds.listRelatives(copy, shapes=True, fullPath=True, type='mesh')[0]
        # Pre-skin shape: original points plus offsets (object space).
        points = om.MFnMesh(_dag(orig)).getPoints(om.MSpace.kObject)
        off = data['offsets_object']
        for v in range(count):
            p = points[v]
            points[v] = om.MPoint(p.x + off[3 * v], p.y + off[3 * v + 1], p.z + off[3 * v + 2])
        om.MFnMesh(_dag(copy_shape)).setPoints(points, om.MSpace.kObject)
        names = list(data['influences'])
        joints = [influences[n][0] if n in influences else added[n] for n in names]
        new_skin = cmds.skinCluster(joints, copy, toSelectedBones=True, bindMethod=0,
                                    normalizeWeights=1, maximumInfluences=4,
                                    obeyMaxInfluences=False,
                                    name=_leaf(transform) + '_fit_skin')[0]
        # Same bind as the source: copy geomMatrix and every bindPreMatrix.
        cmds.setAttr(new_skin + '.geomMatrix', cmds.getAttr(skin + '.geomMatrix'), type='matrix')
        sel = om.MSelectionList()
        sel.add(new_skin)
        fn_new = oma.MFnSkinCluster(sel.getDependNode(0))
        order = []
        logical = []
        for influence in fn_new.influenceObjects():
            leaf = _leaf(influence.fullPathName())
            order.append(leaf)
            logical.append(fn_new.indexForInfluenceObject(influence))
            if leaf in influences:
                matrix = cmds.getAttr('%s.bindPreMatrix[%d]' % (skin, influences[leaf][1]))
            else:
                world = om.MMatrix(cmds.getAttr(added[leaf] + '.worldMatrix[0]'))
                product = pelvis_frame * world.inverse()
                matrix = [product.getElement(r, c) for r in range(4) for c in range(4)]
            cmds.setAttr('%s.bindPreMatrix[%d]' % (new_skin, logical[-1]), matrix,
                         type='matrix')
        # Locks on the NEW skinCluster only, like Dress Auto Rig: the lock plug
        # is usually connected to the joint's lockInfluenceWeights.
        for k in logical:
            attr = '%s.lockWeights[%d]' % (new_skin, k)
            if cmds.objExists(attr):
                for source in cmds.listConnections(attr, source=True, destination=False,
                                                   plugs=True) or []:
                    cmds.disconnectAttr(source, attr)
                cmds.setAttr(attr, False)
        comp_fn = om.MFnSingleIndexedComponent()
        component = comp_fn.create(om.MFn.kMeshVertComponent)
        comp_fn.setCompleteData(count)
        indices = om.MIntArray(list(range(len(order))))
        fn_new.setWeights(_dag(copy_shape), component, indices,
                          om.MDoubleArray(dense_weights(data, order)), False)
    except Exception:
        # Leave no half-built copy behind.
        if copy and cmds.objExists(copy):
            cmds.delete(copy)
        raise
    finally:
        cmds.undoInfo(closeChunk=True)
    return copy


def run():
    cmds, _, _ = _maya()
    selection = cmds.ls(selection=True, long=True, objectsOnly=True) or []
    if len(selection) != 1:
        cmds.confirmDialog(title='mcd. Fit Apply', button=['OK'],
                           message='Bitte genau das exportierte Kleid auswaehlen '
                                   '(die geriggte Kopie).')
        return None
    chosen = cmds.fileDialog2(fileMode=1, caption='Ergebnisdatei waehlen',
                              fileFilter='mcd Ergebnis (*.json.gz)')
    if not chosen:
        return None
    try:
        data = load_result(chosen[0])
        copy = apply_result(selection[0], data)
    except Exception as error:
        traceback.print_exc()
        cmds.confirmDialog(title='mcd. Fit Apply', button=['OK'],
                           message='Fehlgeschlagen:\n%s\n\nBitte diese Meldung schicken.' % error)
        return None
    cmds.select(copy)
    cmds.confirmDialog(title='mcd. Fit Apply', button=['OK'],
                       message='Fertig: %s\n\nDas Original ist unveraendert. Zum Vergleichen '
                               'beide posieren oder eines ausblenden.' % _leaf(copy))
    return copy


def show():
    cmds, _, _ = _maya()
    if cmds.window(WINDOW, exists=True):
        cmds.deleteUI(WINDOW)
    cmds.window(WINDOW, title='mcd. Fit Apply %s' % VERSION, widthHeight=(340, 160),
                sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnAttach=('both', 12))
    cmds.separator(style='none', height=4)
    cmds.text(align='left', label='1. Das exportierte Kleid auswaehlen.')
    cmds.text(align='left', label='2. ERGEBNIS LADEN und die Datei waehlen.')
    cmds.button(label='ERGEBNIS LADEN', height=48, backgroundColor=(0.25, 0.4, 0.45),
                command=lambda *_: run())
    cmds.text(align='left', label='Es entsteht eine Kopie "..._fit".', font='obliqueLabelFont')
    cmds.showWindow(WINDOW)


def onMayaDroppedPythonFile(*args):
    show()
