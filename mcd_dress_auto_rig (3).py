# -*- coding: utf-8 -*-
"""mcd. Dress Auto Rig 0.4 — body transfer + adjustable skirt weights.

FIRST VERSION: the math is checked outside Maya; Maya integration and the
actual dress deformation still need to be checked in Maya. This cannot
guarantee collision-free deformation or infer a garment's construction.

START (Maya with Python 3 / API 2.0):
  Open this file in Script Editor's Python tab, select ALL its contents,
  and execute it. Or put it in your Maya scripts directory and run:
      import mcd_dress_auto_rig
      mcd_dress_auto_rig.show()

WORKFLOW:
  1. Put the existing body rig in its neutral bind pose. Fit the dress to it.
  2. Select the skinned body mesh; click 'Body aus Auswahl'.
  3. Select the dress mesh; click 'Kleid aus Auswahl'.
  4. Check the five detected joints. For custom rigs, select a joint and
     click 'Aus Auswahl' next to its role. All must belong to the body skin.
  5. Optional: select only skirt vertices and click 'Rockauswahl merken'.
     Use this for low sleeves, long straps or other parts below the pelvis.
     Face/edge selections are also converted to vertices. With no mask,
     every vertex below the transition height is considered skirt.
  6. Optionally select a ring of vertices at the top of the skirt and click
     'Rockbeginn aus Auswahl'. Default height derives from the pelvis.
  7. Click 'KLEID AUTOMATISCH RIGGEN'. A new mesh ending in _autoRig is
     created, using existing body influences. No new joints are created.
     'Gespeicherte Bindepose pruefen' is OFF by default. This skips all
     joint-matrix pose checks, but does not put the rig in a neutral pose.
     The output is bound in the current pose: choose that pose deliberately.
  8. Test walking, wide stance, knee bend and sitting. Adjust Beinbindung
     (lower = less pull from legs), Mitte am Becken (higher = a more stable
     middle), and Knie folgen. Re-run on the ORIGINAL dress, not a posed
     output. Every run makes a new copy. This is weight generation, not
     cloth simulation, collision correction or an export tool.

DETAILS:
  Torso/arms: Maya closest-point weight copy from the body.
  Skirt: continuous pelvis / left & right upper-leg / knee weighting,
  a height transition, optional edge-based smoothing and influence cap.
  The center has no calf weights; this keeps the raw skirt field to at
  most four influences before smoothing. Slit edges are not welded.
  Influence locks are disconnected ONLY on the new skinCluster.
  Native undoable skinPercent writes are used so undo/redo includes weights.
  Mesh, UVs, topology and source skin weights are not edited.
  If 'Original ausblenden' is enabled, only its visibility is changed.

  Large meshes can take a while: no weight-paint plugin is required.
  One visible polygon shape per input transform is supported. Combine
  separate dress pieces first, or run separately on each mesh.
  No automatic axis/camera inference: upright Y-up and Z-up rigs supported.

Official API references used:
  https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/CommandsPython/copySkinWeights.html
  https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/CommandsPython/skinPercent.html
  https://help.autodesk.com/cloudhelp/2026/ENU/MAYA-API-REF/py_ref/class_open_maya_anim_1_1_m_fn_skin_cluster.html
"""

import math
import re
import traceback

VERSION = '0.4'
WINDOW = 'mcdDressAutoRigWindow'
SL_COLLISION_VOLUMES = frozenset((
    'PELVIS', 'BELLY', 'CHEST', 'NECK', 'HEAD', 'L_CLAVICLE',
    'L_UPPER_ARM', 'L_LOWER_ARM', 'L_HAND', 'R_CLAVICLE',
    'R_UPPER_ARM', 'R_LOWER_ARM', 'R_HAND', 'L_UPPER_LEG',
    'L_LOWER_LEG', 'L_FOOT', 'R_UPPER_LEG', 'R_LOWER_LEG',
    'R_FOOT', 'BUTT', 'LEFT_PEC', 'RIGHT_PEC', 'LEFT_HANDLE',
    'RIGHT_HANDLE', 'LOWER_BACK', 'UPPER_BACK',
))


def _leaf_joint(name):
    return name.rsplit('|', 1)[-1].rsplit(':', 1)[-1]


def _is_sl_collision(name, pelvis):
    # Only enable this exception for an explicitly identified SL skeleton.
    # Generic skeleton joints called CHEST must still be checked.
    return _leaf_joint(pelvis) == 'mPelvis' and _leaf_joint(name) in SL_COLLISION_VOLUMES


ROLES = ('pelvis', 'left_hip', 'right_hip', 'left_knee', 'right_knee')
LABELS = ('Becken', 'Oberschenkel L', 'Oberschenkel R', 'Knie / Unterschenkel L',
          'Knie / Unterschenkel R')
ALIASES = {
    'pelvis': ('mpelvis', 'pelvis', 'hips', 'hip'),
    'left_hip': ('mhipleft', 'lefthip', 'hipl', 'lhip', 'leftupleg',
                 'thighl', 'lthigh', 'leftthigh'),
    'right_hip': ('mhipright', 'righthip', 'hipr', 'rhip', 'rightupleg',
                  'thighr', 'rthigh', 'rightthigh'),
    'left_knee': ('mkneeleft', 'leftknee', 'kneel', 'lknee', 'leftleg',
                  'calfl', 'lcalf', 'leftcalf'),
    'right_knee': ('mkneeright', 'rightknee', 'kneer', 'rknee', 'rightleg',
                   'calfr', 'rcalf', 'rightcalf'),
}


# Pure calculations: deliberately independent of Maya for validation.
def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def smoothstep(value):
    t = clamp(value)
    return t * t * (3.0 - 2.0 * t)


def normalize(row, maximum=4, fallback=0):
    clean = [(i, float(w)) for i, w in row.items()
             if math.isfinite(w) and w > 1e-10]
    clean.sort(key=lambda item: (-item[1], item[0]))
    clean = clean[:maximum]
    total = sum(w for _, w in clean)
    if total <= 1e-12:
        return {fallback: 1.0}
    return {i: w / total for i, w in clean}


def mix_rows(first, second, amount):
    result = {i: w * (1.0 - amount) for i, w in first.items()}
    for i, w in second.items():
        result[i] = result.get(i, 0.0) + w * amount
    return result


def same_row(first, second, tolerance=1e-7):
    return all(abs(first.get(i, 0.0) - second.get(i, 0.0)) <= tolerance
               for i in set(first) | set(second))


def skirt_row(lateral, height, params, roles):
    """Symmetric continuous field in the pelvis frame, before smoothing."""
    half_width = params['half_width']
    side = clamp(lateral / (half_width * params['center_width']), -1.0, 1.0)
    left = smoothstep(0.5 * (side + 1.0))
    outer = smoothstep(abs(side))
    # Higher pelvis retention in the middle limits opposite-leg stretching.
    retention = params['center_hold'] * (1.0 - outer) + 0.12 * outer
    leg_amount = params['leg_follow'] * (1.0 - retention)
    knee_depth = smoothstep((params['knee_height'] + 0.18 * params['leg_length']
                             - height) / (0.65 * params['leg_length']))
    knee_amount = params['knee_follow'] * knee_depth * outer
    row = {roles['pelvis']: 1.0 - leg_amount,
           roles['left_hip']: leg_amount * left,
           roles['right_hip']: leg_amount * (1.0 - left)}
    # Only the dominant-side calf receives weight, fading continuously to 0
    # at the center. Both opposite thighs may contribute to draped material.
    if side > 0.0:
        moved = row[roles['left_hip']] * knee_amount
        row[roles['left_hip']] -= moved
        row[roles['left_knee']] = moved
    elif side < 0.0:
        moved = row[roles['right_hip']] * knee_amount
        row[roles['right_hip']] -= moved
        row[roles['right_knee']] = moved
    return row


def build_weights(points, base, adjacency, params, roles, mask=None,
                  progress=None):
    """Return rows + transition factors. No geometry or Maya state is edited."""
    count = len(points)
    if count != len(base) or count != len(adjacency):
        raise ValueError('Vertexzahlen der Eingaben stimmen nicht ueberein.')
    if mask is not None and (not mask or min(mask) < 0 or max(mask) >= count):
        raise ValueError('Die gespeicherte Rockauswahl ist ungueltig.')
    factors, rows = [], []
    fallback = roles['pelvis']
    for index, point in enumerate(points):
        height = point[params['up_index']]
        active = mask is None or index in mask
        alpha = (smoothstep((params['start_height'] - height)
                            / params['transition']) if active else 0.0)
        factors.append(alpha)
        if alpha > 0.0:
            offset = [point[j] - params['origin'][j] for j in range(3)]
            lateral = sum(offset[j] * params['lateral_axis'][j] for j in range(3))
            raw = skirt_row(lateral, height, params, roles)
            rows.append(mix_rows(base[index], raw, alpha))
        else:
            rows.append(dict(base[index]))
        if progress and index % 512 == 0:
            progress('Rockgewichte berechnen', 25 + int(15 * index / max(count, 1)))
    # Graph neighbors only; no spatial welding across slits/separate panels.
    for iteration in range(params['smooth_passes']):
        smoothed = []
        for index, row in enumerate(rows):
            neighbors = adjacency[index]
            if factors[index] > 0.0 and neighbors:
                average = {}
                for neighbor in neighbors:
                    for influence, weight in rows[neighbor].items():
                        average[influence] = average.get(influence, 0.0) + weight / len(neighbors)
                smoothed.append(mix_rows(row, average, 0.35 * factors[index]))
            else:
                smoothed.append(row)
            if progress and index % 1024 == 0:
                progress('Rockgewichte glaetten', 40 + int(5 * (iteration + index / max(count, 1))
                                                          / max(params['smooth_passes'], 1)))
        rows = smoothed
    result = []
    for index, row in enumerate(rows):
        if factors[index] > 0.0:
            # Neighbor averaging can introduce the opposite calf at the
            # center. Return that contribution to its thigh continuously,
            # so a four-influence cap cannot choose one calf arbitrarily.
            offset = [points[index][j] - params['origin'][j] for j in range(3)]
            lateral = sum(offset[j] * params['lateral_axis'][j] for j in range(3))
            side = clamp(lateral / (params['half_width'] * params['center_width']), -1.0, 1.0)
            taper = smoothstep(abs(side))
            row = dict(row)
            for knee, hip, active in (('left_knee', 'left_hip', side > 0.0),
                                      ('right_knee', 'right_hip', side < 0.0)):
                current = row.get(roles[knee], 0.0)
                kept = current * taper if active else 0.0
                row[roles[knee]] = kept
                row[roles[hip]] = row.get(roles[hip], 0.0) + current - kept
        result.append(normalize(row, params['maximum'], fallback))
    return result, factors


def _maya():
    import maya.cmds as cmds
    import maya.api.OpenMaya as om
    import maya.api.OpenMayaAnim as oma
    return cmds, om, oma


def _mesh(name):
    cmds, _, _ = _maya()
    matches = cmds.ls(name, long=True) or []
    if len(matches) != 1:
        raise ValueError('Bitte genau ein Mesh waehlen: %s' % name)
    node = matches[0]
    if cmds.nodeType(node) == 'mesh':
        node = cmds.listRelatives(node, parent=True, fullPath=True)[0]
    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True,
                               fullPath=True, type='mesh') or []
    if len(shapes) != 1 or cmds.listRelatives(node, children=True, type='transform'):
        raise ValueError('Genau ein Polygon-Mesh je Eingabe; keine Mesh-Gruppe.')
    if len(cmds.ls(shapes[0], allPaths=True, long=True) or []) != 1:
        raise ValueError('Instanziertes Mesh zuerst in eine eigenstaendige Kopie umwandeln.')
    return node, shapes[0]


def _dag(name):
    _, om, _ = _maya()
    selection = om.MSelectionList()
    selection.add(name)
    return selection.getDagPath(0)


def _skin(shape):
    cmds, om, oma = _maya()
    skins = cmds.ls(cmds.listHistory(shape, pruneDagObjects=True) or [], type='skinCluster') or []
    skins = list(dict.fromkeys(skins))
    if len(skins) != 1:
        raise ValueError('Der Body braucht genau einen skinCluster; gefunden: %d.' % len(skins))
    selection = om.MSelectionList()
    selection.add(skins[0])
    fn = oma.MFnSkinCluster(selection.getDependNode(0))
    return skins[0], fn


def _component(indices):
    _, om, _ = _maya()
    fn = om.MFnSingleIndexedComponent()
    component = fn.create(om.MFn.kMeshVertComponent)
    fn.addElements(list(indices))
    return component


def _read_rows(fn, dag, count, progress=None):
    rows = []
    for first in range(0, count, 512):
        last = min(count, first + 512)
        weights, influences = fn.getWeights(dag, _component(range(first, last)))
        if any(not math.isfinite(w) or w < -1e-8 for w in weights):
            raise RuntimeError('Die Body-Uebertragung enthaelt ungueltige Gewichte.')
        for local in range(last - first):
            offset = local * influences
            rows.append({i: weights[offset + i] for i in range(influences)
                         if weights[offset + i] > 1e-10})
        if progress:
            progress('Body-Gewichte lesen', 15 + int(10 * last / max(count, 1)))
    return rows


def _auto_roles(influences):
    result = {}
    for role in ROLES:
        candidates = []
        for name in influences:
            leaf = name.rsplit('|', 1)[-1].rsplit(':', 1)[-1]
            clean = re.sub('[^a-z0-9]', '', leaf.lower())
            if clean in ALIASES[role]:
                candidates.append(name)
        # Ambiguous labels are deliberately left empty for explicit choice.
        result[role] = candidates[0] if len(candidates) == 1 else ''
    return result


def _rig_frame(joints, up_index):
    cmds, _, _ = _maya()
    positions = {role: cmds.xform(name, query=True, worldSpace=True, translation=True)
                 for role, name in joints.items()}
    lateral = [positions['left_hip'][i] - positions['right_hip'][i] for i in range(3)]
    lateral[up_index] = 0.0
    width = math.sqrt(sum(v * v for v in lateral))
    if width < 1e-7:
        raise ValueError('Linker/rechter Oberschenkel nicht erkennbar; Joint-Zuordnung pruefen.')
    length = 0.5 * sum(positions[side + '_hip'][up_index] - positions[side + '_knee'][up_index]
                       for side in ('left', 'right'))
    if length <= 1e-7:
        raise ValueError('Knie muessen unter den Oberschenkel-Joints liegen. Aufrechte Bindepose pruefen.')
    return {'origin': positions['pelvis'], 'lateral_axis': [v / width for v in lateral],
            'half_width': width * 0.5, 'leg_length': length,
            'knee_height': 0.5 * (positions['left_knee'][up_index] + positions['right_knee'][up_index]),
            'up_index': up_index}


def _check_rest_pose(skin, fn, pelvis):
    """Check skeleton pose; allow SL collision-volume shape adjustments."""
    cmds, om, _ = _maya()
    deltas = []
    reference = None
    for influence in fn.influenceObjects():
        name = influence.fullPathName()
        logical = fn.indexForInfluenceObject(influence)
        bind_pre = om.MMatrix(cmds.getAttr('%s.bindPreMatrix[%d]' % (skin, logical)))
        current = om.MMatrix(cmds.getAttr('%s.matrix[%d]' % (skin, logical)))
        delta = bind_pre * current
        deltas.append((name, delta))
        if name == pelvis:
            reference = delta
    if reference is None:
        raise ValueError('Becken-Joint ist kein Einfluss des Body-skinClusters.')
    for name, delta in deltas:
        if not delta.isEquivalent(reference, 1e-4):
            if _is_sl_collision(name, pelvis):
                continue
            raise ValueError('Body ist nicht in seiner gespeicherten Bindepose (%s). '
                             'Rig ueber seine Controls in die Bindepose bringen und erneut starten.'
                             % name.rsplit('|', 1)[-1])


def _unlock_new_skin(skin, fn):
    """Only change lock plugs on our newly created output skinCluster."""
    cmds, _, _ = _maya()
    for influence in fn.influenceObjects():
        logical = fn.indexForInfluenceObject(influence)
        plug = '%s.lockWeights[%d]' % (skin, logical)
        if cmds.objExists(plug):
            for source in cmds.listConnections(plug, source=True, destination=False, plugs=True) or []:
                cmds.disconnectAttr(source, plug)
            cmds.setAttr(plug, False)


def _write_rows(skin, shape, influences, rows, original, progress):
    cmds, _, _ = _maya()
    groups = {}
    for index, row in enumerate(rows):
        # Removing a tiny fifth influence is a real edit even if its weight
        # falls below the numerical comparison tolerance.
        if set(row) != set(original[index]) or not same_row(row, original[index], 1e-10):
            key = tuple(sorted(row.items()))
            groups.setdefault(key, []).append(index)
    total = sum(len(ids) for ids in groups.values())
    done = 0
    for key, ids in groups.items():
        values = [(influences[index], weight) for index, weight in key]
        for start in range(0, len(ids), 256):
            batch = ids[start:start + 256]
            cmds.skinPercent(skin, ['%s.vtx[%d]' % (shape, index) for index in batch],
                             transformValue=values, zeroRemainingInfluences=True,
                             normalize=False)
            done += len(batch)
            if done % 64 < len(batch) or done == total:
                progress('Gewichte schreiben (%d / %d)' % (done, total),
                         45 + int(45 * done / max(total, 1)))
    return total


def _verify(fn, dag, rows, maximum):
    count = len(rows)
    for first in range(0, count, 512):
        last = min(count, first + 512)
        weights, influences = fn.getWeights(dag, _component(range(first, last)))
        if any(not math.isfinite(w) or w < -1e-8 for w in weights):
            raise RuntimeError('Die neue Kopie enthaelt ungueltige Gewichte.')
        for local, index in enumerate(range(first, last)):
            offset = local * influences
            actual = {i: weights[offset + i] for i in range(influences)
                      if weights[offset + i] > 1e-8}
            if (len(actual) > maximum or abs(sum(actual.values()) - 1.0) > 1e-5
                    or not same_row(actual, rows[index], 1e-5)):
                delta = max(abs(actual.get(i, 0.0) - rows[index].get(i, 0.0))
                            for i in set(actual) | set(rows[index]))
                raise RuntimeError('Gewichtspruefung fehlgeschlagen an Vertex %d: '
                                   '%d Joints (Maximum %d), Summe %.9f, groesste Abweichung %.9g. '
                                   'Die neue Kopie wird rueckgaengig gemacht.'
                                   % (index, len(actual), maximum, sum(actual.values()), delta))


class DressRigUI:
    def __init__(self):
        self.cmds, self.om, _ = _maya()
        self.body = None
        self.dress = None
        self.mask = None
        self.mask_count = None
        self.controls = {}
        self.joint_controls = {}
        self._make_ui()

    def _make_ui(self):
        cmds = self.cmds
        if cmds.window(WINDOW, exists=True):
            cmds.deleteUI(WINDOW)
        cmds.window(WINDOW, title='mcd. Dress Auto Rig ' + VERSION, widthHeight=(570, 700))
        cmds.scrollLayout(childResizable=True)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=8)
        cmds.text(label='Body-Gewichte oben | eigene Rockgewichte unten', height=26, font='boldLabelFont')
        cmds.text(label='Erste Version: Grundriggung, danach Posen am echten Kleid pruefen.', align='left')
        for key, label in (('body', 'Body'), ('dress', 'Kleid')):
            self.controls[key] = cmds.textFieldButtonGrp(
                label=label, buttonLabel=label + ' aus Auswahl', editable=False,
                columnWidth3=(65, 290, 160),
                buttonCommand=lambda *_, k=key: self._safe(lambda: self._load_mesh(k)))
        cmds.separator(height=10)
        cmds.text(label='Bestehende Joints des Body-skinClusters', align='left')
        for role, label in zip(ROLES, LABELS):
            self.joint_controls[role] = cmds.textFieldButtonGrp(
                label=label, buttonLabel='Aus Auswahl', editable=False,
                columnWidth3=(170, 220, 110),
                buttonCommand=lambda *_, r=role: self._safe(lambda: self._load_joint(r)))
        cmds.button(label='Joints automatisch erkennen + Hoehen setzen',
                    command=lambda *_: self._safe(self._detect))
        cmds.separator(height=10)
        self.controls['mask_info'] = cmds.text(label='Rock: automatisch alle Vertices unter Rockbeginn', align='left')
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1)
        cmds.button(label='Rockauswahl merken (optional)', command=lambda *_: self._safe(self._load_mask))
        cmds.button(label='Auswahl loeschen', command=lambda *_: self._clear_mask())
        cmds.setParent('..')
        self.controls['start_height'] = cmds.floatFieldGrp(
            label='Rockbeginn (Welt-Hoehe)', numberOfFields=1, value1=0.0, precision=4,
            columnWidth2=(240, 100))
        cmds.button(label='Rockbeginn aus ausgewaehlten Vertices',
                    command=lambda *_: self._safe(self._load_height))
        self.controls['transition'] = cmds.floatFieldGrp(
            label='Uebergangsbreite (Szeneneinheit)', numberOfFields=1, value1=1.0, precision=4,
            columnWidth2=(240, 100))
        for key, label, value, minimum, maximum in (
                ('leg_follow', 'Beinbindung', 0.75, 0.0, 1.0),
                ('center_hold', 'Mitte am Becken', 0.65, 0.0, 1.0),
                ('knee_follow', 'Knie folgen', 0.65, 0.0, 1.0),
                ('center_width', 'Breite des Mittelbereichs', 2.5, 0.5, 5.0)):
            self.controls[key] = cmds.floatSliderGrp(
                label=label, field=True, minValue=minimum, maxValue=maximum,
                value=value, precision=2, columnWidth3=(210, 55, 240))
        self.controls['smooth_passes'] = cmds.intSliderGrp(
            label='Rock glaetten (Durchlaeufe)', field=True, minValue=0, maxValue=8,
            value=2, columnWidth3=(210, 55, 240))
        self.controls['maximum'] = cmds.intSliderGrp(
            label='Max. Joints pro Vertex', field=True, minValue=1, maxValue=8,
            value=4, columnWidth3=(210, 55, 240))
        self.controls['hide'] = cmds.checkBox(label='Original nach Erfolg ausblenden', value=True)
        self.controls['check_pose'] = cmds.checkBox(
            label='Gespeicherte Bindepose pruefen (optional)', value=False)
        cmds.text(label='Body und Kleid muessen aufeinander passen und in Bindepose stehen.\n'
                        'Ohne Pruefung wird in der aktuellen Pose gebunden.\n'
                        'Bei tiefen Aermeln / Straps die Rockvertices gezielt auswaehlen.', align='left')
        cmds.button(label='KLEID AUTOMATISCH RIGGEN', height=42, backgroundColor=(0.22, 0.43, 0.36),
                    command=lambda *_: self._safe(self._run))
        self.controls['status'] = cmds.text(label='Body laden, Kleid laden, Joints pruefen.', align='left', wordWrap=True)
        cmds.showWindow(WINDOW)

    def _safe(self, function):
        try:
            function()
        except Exception as error:
            traceback.print_exc()
            self.cmds.text(self.controls['status'], edit=True, label=str(error))
            self.cmds.warning('mcd. Dress Auto Rig: %s' % error)

    def _load_mesh(self, key):
        selection = self.cmds.ls(selection=True, objectsOnly=True, long=True) or []
        if len(selection) != 1:
            raise ValueError('Bitte genau ein Mesh auswaehlen.')
        transform, _ = _mesh(selection[0])
        setattr(self, key, transform)
        self.cmds.textFieldButtonGrp(self.controls[key], edit=True, text=transform)
        if key == 'body':
            self._detect()
        else:
            self._clear_mask()

    def _joints(self):
        names = {role: self.cmds.textFieldButtonGrp(control, query=True, text=True)
                 for role, control in self.joint_controls.items()}
        if not all(names.values()):
            raise ValueError('Alle fuenf Joint-Rollen zuordnen; leere Felder manuell laden.')
        if len(set(names.values())) != len(ROLES):
            raise ValueError('Jede Joint-Rolle braucht einen anderen Joint.')
        return names

    def _detect(self):
        if not self.body:
            raise ValueError('Zuerst den geriggten Body laden.')
        _, shape = _mesh(self.body)
        _, fn = _skin(shape)
        names = [p.fullPathName() for p in fn.influenceObjects()]
        roles = _auto_roles(names)
        for role, name in roles.items():
            self.cmds.textFieldButtonGrp(self.joint_controls[role], edit=True, text=name)
        if all(roles.values()):
            self._defaults(roles)
        else:
            self.cmds.text(self.controls['status'], edit=True,
                           label='Eigene Joint-Namen: leere Rollen manuell zuordnen.')

    def _defaults(self, joints):
        up = 1 if self.cmds.upAxis(query=True, axis=True) == 'y' else 2
        frame = _rig_frame(joints, up)
        self.cmds.floatFieldGrp(self.controls['start_height'], edit=True,
                               value1=frame['origin'][up] + 0.15 * frame['leg_length'])
        self.cmds.floatFieldGrp(self.controls['transition'], edit=True,
                               value1=0.35 * frame['leg_length'])

    def _load_joint(self, role):
        selected = self.cmds.ls(selection=True, long=True, type='joint') or []
        if len(selected) != 1 or not self.body:
            raise ValueError('Body laden und genau einen Joint auswaehlen.')
        _, shape = _mesh(self.body)
        _, fn = _skin(shape)
        if selected[0] not in [p.fullPathName() for p in fn.influenceObjects()]:
            raise ValueError('Dieser Joint beeinflusst den geladenen Body nicht.')
        self.cmds.textFieldButtonGrp(self.joint_controls[role], edit=True, text=selected[0])
        values = {r: self.cmds.textFieldButtonGrp(c, query=True, text=True)
                  for r, c in self.joint_controls.items()}
        if all(values.values()):
            self._defaults(values)

    def _selected_vertices(self):
        if not self.dress:
            raise ValueError('Zuerst das Kleid laden.')
        transform, shape = _mesh(self.dress)
        selection = self.cmds.ls(selection=True, flatten=True, long=True) or []
        if not selection or any('.' not in name for name in selection):
            raise ValueError('Vertices, Kanten oder Faces am geladenen Kleid auswaehlen.')
        for name in selection:
            if name.split('.', 1)[0] not in (transform, shape):
                raise ValueError('Die Auswahl muss ausschliesslich zum geladenen Kleid gehoeren.')
        converted = self.cmds.polyListComponentConversion(selection, toVertex=True)
        vertices = self.cmds.ls(converted, flatten=True, long=True) or []
        ids = set()
        for name in vertices:
            match = re.search(r'\.vtx\[(\d+)\]$', name)
            if match:
                ids.add(int(match.group(1)))
        if not ids:
            raise ValueError('Keine gueltigen Polygon-Vertices ausgewaehlt.')
        return ids, shape

    def _load_mask(self):
        ids, shape = self._selected_vertices()
        self.mask = ids
        self.mask_count = self.om.MFnMesh(_dag(shape)).numVertices
        self.cmds.text(self.controls['mask_info'], edit=True,
                       label='Rock: %d gespeicherte Vertices' % len(ids))

    def _clear_mask(self):
        self.mask = self.mask_count = None
        self.cmds.text(self.controls['mask_info'], edit=True,
                       label='Rock: automatisch alle Vertices unter Rockbeginn')

    def _load_height(self):
        ids, shape = self._selected_vertices()
        up = 1 if self.cmds.upAxis(query=True, axis=True) == 'y' else 2
        points = self.om.MFnMesh(_dag(shape)).getPoints(self.om.MSpace.kWorld)
        height = sum(points[index][up] for index in ids) / len(ids)
        self.cmds.floatFieldGrp(self.controls['start_height'], edit=True, value1=height)

    def _progress(self, text, value):
        if self.cmds.progressWindow(query=True, isCancelled=True):
            raise RuntimeError('Abgebrochen. Die neue Rig-Kopie wird rueckgaengig gemacht.')
        self.cmds.progressWindow(edit=True, progress=value, status=text)

    def _run(self):
        cmds, om, _ = _maya()
        if not self.body or not self.dress:
            raise ValueError('Body und Kleid zuerst laden.')
        body, body_shape = _mesh(self.body)
        dress, dress_shape = _mesh(self.dress)
        if body == dress:
            raise ValueError('Body und Kleid muessen verschiedene Meshes sein.')
        if not cmds.undoInfo(query=True, state=True):
            raise ValueError('Maya Undo muss fuer diesen Vorgang aktiviert sein.')
        source_skin, source_fn = _skin(body_shape)
        source_influences = [p.fullPathName() for p in source_fn.influenceObjects()]
        if any(cmds.nodeType(name) != 'joint' for name in source_influences):
            raise ValueError('Diese Version unterstuetzt Body-Skins mit Joint-Einfluessen.')
        joints = self._joints()
        if any(name not in source_influences for name in joints.values()):
            raise ValueError('Alle Rock-Joints muessen zum geladenen Body-skinCluster gehoeren.')
        if cmds.checkBox(self.controls['check_pose'], query=True, value=True):
            _check_rest_pose(source_skin, source_fn, joints['pelvis'])
        up = 1 if cmds.upAxis(query=True, axis=True) == 'y' else 2
        params = _rig_frame(joints, up)
        for key in ('start_height', 'transition'):
            params[key] = cmds.floatFieldGrp(self.controls[key], query=True, value1=True)
        for key in ('leg_follow', 'center_hold', 'knee_follow', 'center_width'):
            params[key] = cmds.floatSliderGrp(self.controls[key], query=True, value=True)
        for key in ('smooth_passes', 'maximum'):
            params[key] = cmds.intSliderGrp(self.controls[key], query=True, value=True)
        if (not all(math.isfinite(v) for v in params.values() if isinstance(v, (float, int)))
                or params['transition'] <= 1e-7 or params['center_width'] <= 0.0
                or not 1 <= params['maximum'] <= 8 or not 0 <= params['smooth_passes'] <= 8
                or any(not 0.0 <= params[k] <= 1.0 for k in ('leg_follow', 'center_hold', 'knee_follow'))):
            raise ValueError('Uebergang muss positiv sein; Reglerwerte innerhalb der angegebenen Bereiche halten.')
        input_mesh = om.MFnMesh(_dag(dress_shape))
        if self.mask is not None and input_mesh.numVertices != self.mask_count:
            raise ValueError('Vertexzahl geaendert: Rockauswahl erneut speichern.')
        input_points = input_mesh.getPoints(om.MSpace.kWorld)
        if not any(p[up] < params['start_height'] for i, p in enumerate(input_points)
                   if self.mask is None or i in self.mask):
            raise ValueError('Keine Rockvertices unter dem Rockbeginn. Hoehe/Auswahl pruefen.')
        output = None
        mutated = False
        error = None
        cmds.progressWindow(title='mcd. Dress Auto Rig', progress=0, maxValue=100,
                            status='Neue Kleid-Kopie erstellen', isInterruptable=True)
        cmds.undoInfo(openChunk=True, chunkName='mcdDressAutoRig')
        try:
            leaf = dress.rsplit('|', 1)[-1].rsplit(':', 1)[-1]
            output = cmds.duplicate(dress, name=leaf + '_autoRig',
                                    returnRootsOnly=True, inputConnections=False,
                                    upstreamNodes=False)[0]
            mutated = True
            # This acts exclusively on the newly created, disconnected copy.
            cmds.delete(output, constructionHistory=True)
            for attribute in ('translateX', 'translateY', 'translateZ', 'rotateX', 'rotateY',
                              'rotateZ', 'scaleX', 'scaleY', 'scaleZ', 'visibility'):
                cmds.setAttr(output + '.' + attribute, lock=False)
            if cmds.listRelatives(output, parent=True):
                output = cmds.parent(output, world=True)[0]
            cmds.setAttr(output + '.visibility', True)
            output, output_shape = _mesh(output)
            dag = _dag(output_shape)
            mesh = om.MFnMesh(dag)
            if mesh.numVertices != input_mesh.numVertices:
                raise RuntimeError('Vertexzahl beim Duplizieren geaendert.')
            points = [tuple(p[i] for i in range(3)) for p in mesh.getPoints(om.MSpace.kWorld)]
            self._progress('Kopie an bestehende Body-Joints binden', 5)
            destination = cmds.skinCluster(source_influences, output, toSelectedBones=True,
                                           maximumInfluences=params['maximum'], obeyMaxInfluences=False,
                                           normalizeWeights=1, skinMethod=0,
                                           name=leaf + '_autoRig_skin')[0]
            _, target_fn = _skin(output_shape)
            _unlock_new_skin(destination, target_fn)
            self._progress('Body-Gewichte uebertragen', 10)
            cmds.copySkinWeights(sourceSkin=source_skin, destinationSkin=destination,
                                 noMirror=True, surfaceAssociation='closestPoint',
                                 influenceAssociation='name', sampleSpace=0,
                                 smooth=True, normalize=True, noBlendWeight=True)
            target_names = [p.fullPathName() for p in target_fn.influenceObjects()]
            roles = {role: target_names.index(name) for role, name in joints.items()}
            base = _read_rows(target_fn, dag, mesh.numVertices, self._progress)
            adjacency = [[] for _ in points]
            if params['smooth_passes']:
                iterator = om.MItMeshVertex(dag)
                while not iterator.isDone():
                    adjacency[iterator.index()] = list(iterator.getConnectedVertices())
                    iterator.next()
            rows, factors = build_weights(points, base, adjacency, params, roles,
                                           self.mask, self._progress)
            # Our rows already sum to one. Disable Maya's automatic edits
            # while writing exact values; all changes use undoable commands.
            cmds.setAttr(destination + '.maintainMaxInfluences', False)
            cmds.setAttr(destination + '.normalizeWeights', 0)
            try:
                written = _write_rows(destination, output_shape, target_names, rows, base, self._progress)
            finally:
                cmds.setAttr(destination + '.normalizeWeights', 1)
            self._progress('Neue Gewichte pruefen', 93)
            _verify(target_fn, dag, rows, params['maximum'])
            cmds.setAttr(destination + '.maintainMaxInfluences', True)
            if cmds.checkBox(self.controls['hide'], query=True, value=True):
                visibility = dress + '.visibility'
                if cmds.getAttr(visibility, settable=True):
                    cmds.setAttr(visibility, False)
                else:
                    cmds.warning('Original-Sichtbarkeit gesteuert/gesperrt; Original manuell ausblenden.')
            cmds.select(output, replace=True)
            self._progress('Fertig', 100)
            cmds.text(self.controls['status'], edit=True,
                      label='%s erstellt. %d Rockvertices, %d Gewichte geaendert. Jetzt Posen pruefen.'
                      % (output.rsplit('|', 1)[-1], sum(f > 0 for f in factors), written))
            print('mcd. Dress Auto Rig: %s | skinCluster: %s' % (output, destination))
        except Exception as caught:
            error = caught
        finally:
            cmds.undoInfo(closeChunk=True)
            cmds.progressWindow(endProgress=True)
        if error is not None:
            if mutated:
                cmds.undo()
            raise error


_UI = None


def show():
    """Open the tool. Reopening resets loaded objects, mask and options."""
    global _UI
    _UI = DressRigUI()
    return _UI


def onMayaDroppedPythonFile(*args):
    show()


if __name__ == '__main__':
    show()
