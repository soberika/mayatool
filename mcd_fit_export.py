# -*- coding: utf-8 -*-
"""mcd. Fit Export 0.1 — one-click export of body + dress for the fit solver.

STAGE 1 (docs/konzept_kleidung_und_bewegung.md). Exports everything the
solver needs from Maya into ONE file (.json.gz):
  * the skinned body and the skinned dress (e.g. the _autoRig output of
    Dress Auto Rig 0.4): points, polygons, skin weights, bind matrices;
  * every joint of their skeleton (incl. SL collision volumes) with its
    parent and world matrix in the current pose.
Nothing in the scene is changed: no selection, weight, pose or file edits.

START (Maya with Python 3 / API 2.0):
  Drag this file into the Maya viewport, OR in the Script Editor (Python):
      import mcd_fit_export
      mcd_fit_export.show()

ONE CLICK:
  1. Put the rig in its neutral bind pose (the pose you rigged the dress in).
  2. Select the body AND the dress (any order; click, then Shift+click).
  3. Click 'EXPORTIEREN'. The tool tells which mesh it took as body and
     which as dress (the taller one is the body) and lets you swap them.
  4. Upload the written .json.gz file in the chat.

The file contains your body geometry. Only share it where the body's
dev-kit license allows it. It is NOT added to the git repository.
NOT YET VERIFIED IN MAYA.
"""

import gzip
import json
import os
import time
import traceback

VERSION = '0.1'
FORMAT = 'mcd-fit-data'
FORMAT_VERSION = 1
WINDOW = 'mcdFitExportWindow'
DIGITS = 6


def _maya():
    import maya.cmds as cmds
    import maya.api.OpenMaya as om
    import maya.api.OpenMayaAnim as oma
    return cmds, om, oma


def _round(values, digits=DIGITS):
    return [round(float(v), digits) for v in values]


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
        raise ValueError('%s braucht genau einen skinCluster (gefunden: %d).'
                         % (shape.rsplit('|', 1)[-1], len(skins)))
    sel = om.MSelectionList()
    sel.add(skins[0])
    return skins[0], oma.MFnSkinCluster(sel.getDependNode(0))


def _dag(name):
    _, om, _ = _maya()
    sel = om.MSelectionList()
    sel.add(name)
    return sel.getDagPath(0)


def _orig_shape(transform, shape, count):
    """The intermediate (pre-skin) shape with the same vertex count, if unique."""
    cmds, _, _ = _maya()
    candidates = []
    for s in cmds.listRelatives(transform, shapes=True, fullPath=True, type='mesh') or []:
        if s != shape and cmds.getAttr(s + '.intermediateObject'):
            if cmds.polyEvaluate(s, vertex=True) == count:
                candidates.append(s)
    return candidates[0] if len(candidates) == 1 else None


def _mesh_data(name, label, progress):
    cmds, om, oma = _maya()
    transform, shape = _transform_and_shape(name)
    skin, fn_skin = _skin_cluster(shape)
    dag = _dag(shape)
    fn_mesh = om.MFnMesh(dag)
    count = fn_mesh.numVertices
    counts, indices = fn_mesh.getVertices()
    world = fn_mesh.getPoints(om.MSpace.kWorld)
    data = {
        'name': transform.rsplit('|', 1)[-1],
        'path': transform,
        'skin_cluster': skin,
        'vertex_count': count,
        'face_counts': list(counts),
        'face_vertices': list(indices),
        'points_world': _round([c for p in world for c in (p.x, p.y, p.z)]),
        'world_matrix': _round(cmds.xform(transform, q=True, ws=True, m=True)),
        'geom_matrix': _round(cmds.getAttr(skin + '.geomMatrix')),
        'max_influences': cmds.getAttr(skin + '.maxInfluences'),
    }
    orig = _orig_shape(transform, shape, count)
    if orig:
        fn_orig = om.MFnMesh(_dag(orig))
        pts = fn_orig.getPoints(om.MSpace.kObject)
        data['points_orig_object'] = _round([c for p in pts for c in (p.x, p.y, p.z)])
    influences = []
    for influence in fn_skin.influenceObjects():
        logical = fn_skin.indexForInfluenceObject(influence)
        path = influence.fullPathName()
        influences.append({
            'name': path.rsplit('|', 1)[-1].rsplit(':', 1)[-1],
            'path': path,
            'bind_pre_matrix': _round(cmds.getAttr('%s.bindPreMatrix[%d]' % (skin, logical))),
            'matrix': _round(cmds.getAttr('%s.matrix[%d]' % (skin, logical))),
        })
    data['influences'] = influences
    rows = []
    comp_fn = om.MFnSingleIndexedComponent()
    for first in range(0, count, 1024):
        last = min(count, first + 1024)
        component = comp_fn.create(om.MFn.kMeshVertComponent)
        comp_fn.addElements(list(range(first, last)))
        weights, n = fn_skin.getWeights(dag, component)
        for local in range(last - first):
            offset = local * n
            row = [[i, round(weights[offset + i], DIGITS)] for i in range(n)
                   if weights[offset + i] > 1e-7]
            rows.append(row)
        progress('%s: Gewichte lesen (%d / %d)' % (label, last, count))
    data['weights'] = rows
    return data


def _skeleton(meshes):
    """All joints of the skeletons used by the meshes, with parents and world matrices."""
    cmds, _, _ = _maya()
    nodes = set()
    roots = set()
    for mesh in meshes:
        for influence in mesh['influences']:
            path = influence['path']
            nodes.add(path)
            parent = path
            while True:
                up = cmds.listRelatives(parent, parent=True, fullPath=True)
                if not up:
                    break
                parent = up[0]
                nodes.add(parent)
                if cmds.nodeType(parent) == 'joint':
                    roots.add(parent)
    for root in list(roots):
        top = root
        while True:
            up = cmds.listRelatives(top, parent=True, fullPath=True, type='joint')
            if not up:
                break
            top = up[0]
        nodes.add(top)
        nodes.update(cmds.listRelatives(top, allDescendents=True, fullPath=True,
                                        type='joint') or [])
    joints = []
    for path in sorted(nodes, key=lambda p: (p.count('|'), p)):
        up = cmds.listRelatives(path, parent=True, fullPath=True)
        joints.append({
            'name': path.rsplit('|', 1)[-1].rsplit(':', 1)[-1],
            'path': path,
            'parent': up[0] if up else None,
            'type': cmds.nodeType(path),
            'world_matrix': _round(cmds.xform(path, q=True, ws=True, m=True)),
        })
    return joints


def _bind_deviation(mesh):
    """Largest difference between bindPreMatrix*matrix and identity (0 = bind pose)."""
    worst = 0.0
    for influence in mesh['influences']:
        a = influence['bind_pre_matrix']
        b = influence['matrix']
        product = [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4))
                   for r in range(4) for c in range(4)]
        identity = [1.0 if r == c else 0.0 for r in range(4) for c in range(4)]
        worst = max(worst, max(abs(p - q) for p, q in zip(product, identity)))
    return worst


def _height(name):
    cmds, _, _ = _maya()
    box = cmds.exactWorldBoundingBox(name)
    up = 1 if cmds.upAxis(q=True, axis=True) == 'y' else 2
    return box[3 + up] - box[up]


def export(body, dress, path, progress=None):
    """Write the fit data file. Returns (path, size_bytes, warnings)."""
    cmds, _, _ = _maya()
    progress = progress or (lambda message: None)
    warnings = []
    body_data = _mesh_data(body, 'Body', progress)
    dress_data = _mesh_data(dress, 'Kleid', progress)
    progress('Skelett lesen')
    joints = _skeleton([body_data, dress_data])
    body_joints = {i['path'] for i in body_data['influences']}
    missing = [i['name'] for i in dress_data['influences'] if i['path'] not in body_joints]
    if missing:
        warnings.append('Das Kleid nutzt Joints, die den Body nicht beeinflussen: %s'
                        % ', '.join(missing[:8]))
    for label, data in (('Body', body_data), ('Kleid', dress_data)):
        deviation = _bind_deviation(data)
        data['bind_deviation'] = round(deviation, DIGITS)
        if deviation > 1e-3:
            warnings.append('%s ist nicht exakt in seiner Bindepose (Abweichung %.4f). '
                            'Bei SL-Collision-Volumes durch Shape-Anpassungen ist das normal.'
                            % (label, deviation))
    payload = {
        'format': FORMAT,
        'format_version': FORMAT_VERSION,
        'exporter': 'mcd_fit_export %s' % VERSION,
        'exported_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'maya_version': cmds.about(version=True),
        'scene': cmds.file(q=True, sceneName=True) or '',
        'linear_unit': cmds.currentUnit(q=True, linear=True),
        'up_axis': cmds.upAxis(q=True, axis=True),
        'current_frame': cmds.currentTime(q=True),
        'warnings': warnings,
        'body': body_data,
        'dress': dress_data,
        'joints': joints,
    }
    progress('Datei schreiben')
    with gzip.open(path, 'wt', encoding='utf-8') as handle:
        json.dump(payload, handle, separators=(',', ':'))
    return path, os.path.getsize(path), warnings


# --- UI ------------------------------------------------------------------------------
def _pick_meshes():
    cmds, _, _ = _maya()
    picked = []
    for node in cmds.ls(selection=True, long=True, objectsOnly=True) or []:
        if cmds.nodeType(node) == 'mesh':
            node = cmds.listRelatives(node, parent=True, fullPath=True)[0]
        if cmds.listRelatives(node, shapes=True, noIntermediate=True, type='mesh'):
            if node not in picked:
                picked.append(node)
    if len(picked) != 2:
        raise ValueError('Bitte genau zwei Meshes auswaehlen: den Body und das Kleid '
                         '(gewaehlt: %d).' % len(picked))
    picked = [_skinned_version(node) for node in picked]
    picked.sort(key=_height, reverse=True)
    return picked[0], picked[1]


def _has_skin(node):
    cmds, _, _ = _maya()
    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True, fullPath=True,
                               type='mesh') or []
    return bool(shapes) and bool(cmds.ls(cmds.listHistory(shapes[0], pruneDagObjects=True)
                                         or [], type='skinCluster'))


def _autorig_copies(node):
    """Skinned meshes named like Dress Auto Rig 0.4's output for this mesh."""
    cmds, _, _ = _maya()
    base = node.rsplit('|', 1)[-1].rsplit(':', 1)[-1]
    found = []
    for pattern in ('%s_autoRig*' % base, '*:%s_autoRig*' % base):
        for match in cmds.ls(pattern, long=True, type='transform') or []:
            if match not in found and _has_skin(match):
                found.append(match)
    return found


def _skinned_version(node):
    """The mesh itself if skinned, else its unique _autoRig copy (after asking)."""
    cmds, _, _ = _maya()
    if _has_skin(node):
        return node
    short = node.rsplit('|', 1)[-1]
    copies = _autorig_copies(node)
    if len(copies) == 1:
        answer = cmds.confirmDialog(
            title='mcd. Fit Export',
            message='"%s" ist nicht geriggt (das ist das Original).\n\n'
                    'Gefunden: die geriggte Kopie "%s".\nDiese stattdessen nehmen?'
                    % (short, copies[0].rsplit('|', 1)[-1]),
            button=['Ja, Kopie nehmen', 'Abbrechen'], defaultButton='Ja, Kopie nehmen',
            cancelButton='Abbrechen', dismissString='Abbrechen')
        if answer != 'Abbrechen':
            return copies[0]
        raise ValueError('Abgebrochen.')
    if copies:
        raise ValueError('"%s" ist nicht geriggt. Es gibt mehrere geriggte Kopien:\n%s\n\n'
                         'Bitte die richtige Kopie direkt auswaehlen.'
                         % (short, '\n'.join(c.rsplit('|', 1)[-1] for c in copies)))
    raise ValueError('"%s" ist nicht geriggt (kein skinCluster).\n\n'
                     'Bitte zuerst mit Dress Auto Rig 0.4 riggen. Das erzeugt eine Kopie '
                     'mit "_autoRig" am Ende. Dann Body + diese Kopie auswaehlen und erneut '
                     'exportieren.' % short)


def run_export():
    cmds, _, _ = _maya()
    try:
        body, dress = _pick_meshes()
    except Exception as error:
        cmds.confirmDialog(title='mcd. Fit Export', message=str(error), button=['OK'])
        return None
    short = lambda n: n.rsplit('|', 1)[-1]
    answer = cmds.confirmDialog(
        title='mcd. Fit Export',
        message='Body:   %s\nKleid:  %s\n\nStimmt das?' % (short(body), short(dress)),
        button=['Exportieren', 'Tauschen', 'Abbrechen'], defaultButton='Exportieren',
        cancelButton='Abbrechen', dismissString='Abbrechen')
    if answer == 'Abbrechen':
        return None
    if answer == 'Tauschen':
        body, dress = dress, body
    default = os.path.join(cmds.internalVar(userWorkspaceDir=True),
                           'mcd_fit_%s.json.gz' % short(dress))
    chosen = cmds.fileDialog2(fileMode=0, caption='Exportdatei speichern',
                              fileFilter='mcd Fit-Daten (*.json.gz)', startingDirectory=default)
    if not chosen:
        return None
    path = chosen[0]
    if not path.endswith('.json.gz'):
        path = path.rsplit('.', 1)[0] + '.json.gz' if path.endswith('.json') else path + '.json.gz'
    cmds.progressWindow(title='mcd. Fit Export', status='Start', isInterruptable=False)
    try:
        def progress(message):
            cmds.progressWindow(edit=True, status=message)
        path, size, warnings = export(body, dress, path, progress)
    except Exception as error:
        traceback.print_exc()
        cmds.progressWindow(endProgress=True)
        cmds.confirmDialog(title='mcd. Fit Export',
                           message='Export fehlgeschlagen:\n%s\n\nDetails im Script Editor. '
                                   'Bitte diese Meldung schicken.' % error, button=['OK'])
        return None
    cmds.progressWindow(endProgress=True)
    text = 'Fertig: %s\n(%.1f MB)\n\nBitte diese Datei im Chat hochladen.' % (path, size / 1e6)
    if warnings:
        text += '\n\nHinweise:\n- ' + '\n- '.join(warnings)
    cmds.confirmDialog(title='mcd. Fit Export', message=text, button=['OK'])
    print('mcd. Fit Export: %s' % path)
    return path


def show():
    cmds, _, _ = _maya()
    if cmds.window(WINDOW, exists=True):
        cmds.deleteUI(WINDOW)
    cmds.window(WINDOW, title='mcd. Fit Export %s' % VERSION, widthHeight=(340, 190),
                sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnAttach=('both', 12))
    cmds.separator(style='none', height=4)
    cmds.text(align='left', label='1. Rig in die neutrale Bindepose bringen.')
    cmds.text(align='left', label='2. Body UND Kleid auswaehlen (Shift+Klick).')
    cmds.text(align='left', label='3. Auf EXPORTIEREN klicken.')
    cmds.button(label='EXPORTIEREN', height=48, backgroundColor=(0.45, 0.25, 0.45),
                command=lambda *_: run_export())
    cmds.text(align='left', label='Die Datei danach im Chat hochladen.', font='obliqueLabelFont')
    cmds.showWindow(WINDOW)


def onMayaDroppedPythonFile(*args):
    show()
