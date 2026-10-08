# -*- coding: utf-8 -*-
"""Maya access for mcd. Dress Rig: reading meshes, skins, joints, closest points.

Everything here reads the scene, except create_output(), which only works on
nodes it created itself.
"""
from __future__ import division

import collections
import re

# Collision volume names (MayaStar collision_volume_bones_scales.json, Legacy body).
COLLISION_VOLUMES = frozenset((
    'PELVIS', 'BUTT', 'BELLY', 'LEFT_HANDLE', 'RIGHT_HANDLE', 'LOWER_BACK',
    'CHEST', 'LEFT_PEC', 'RIGHT_PEC', 'UPPER_BACK', 'NECK', 'HEAD',
    'L_CLAVICLE', 'L_UPPER_ARM', 'L_LOWER_ARM', 'L_HAND', 'R_CLAVICLE',
    'R_UPPER_ARM', 'R_LOWER_ARM', 'R_HAND', 'R_UPPER_LEG', 'R_LOWER_LEG',
    'R_FOOT', 'L_UPPER_LEG', 'L_LOWER_LEG', 'L_FOOT'))
# Skeleton joints listed for the SL skin block (wiki: Mesh Asset Format).
SL_BASE_JOINTS = (
    'mPelvis', 'mTorso', 'mChest', 'mNeck', 'mHead', 'mCollarLeft', 'mShoulderLeft',
    'mElbowLeft', 'mWristLeft', 'mCollarRight', 'mShoulderRight', 'mElbowRight',
    'mWristRight', 'mHipRight', 'mKneeRight', 'mFootRight', 'mHipLeft', 'mKneeLeft',
    'mFootLeft')
# Role -> (m-bone, collision volume) for the skirt field.
ROLE_JOINTS = {
    'pelvis': ('mPelvis', 'PELVIS'),
    'thigh_l': ('mHipLeft', 'L_UPPER_LEG'),
    'thigh_r': ('mHipRight', 'R_UPPER_LEG'),
    'knee_l': ('mKneeLeft', 'L_LOWER_LEG'),
    'knee_r': ('mKneeRight', 'R_LOWER_LEG'),
}
# Influences a dress never follows (face, fingers, feet, extra Bento limbs).
EXCLUDE_PATTERNS = (r'^mFace', r'^mHand', r'^mHead$', r'^mSkull$', r'^mEye', r'^HEAD$',
                    r'^[LR]_FOOT$', r'^mAnkle', r'^mFoot', r'^mToe', r'^mTail',
                    r'^mWing', r'^mHindLimb', r'^mGroin')
# Arm chain: allowed for sleeves, kept out of the skirt (hands hang next to it).
ARM_PATTERNS = (r'^mShoulder', r'^mElbow', r'^mWrist', r'^[LR]_UPPER_ARM$',
                r'^[LR]_LOWER_ARM$', r'^[LR]_HAND$')


class RigError(Exception):
    """Error with a message meant for the user."""


def api():
    import maya.cmds as cmds
    import maya.api.OpenMaya as om
    import maya.api.OpenMayaAnim as oma
    return cmds, om, oma


def leaf(path):
    return path.rsplit('|', 1)[-1].rsplit(':', 1)[-1]


def short(path):
    return path.rsplit('|', 1)[-1]


def mesh_nodes(name):
    """Return (transform, shape) of exactly one non-instanced polygon mesh."""
    cmds = api()[0]
    found = cmds.ls(name, long=True) or []
    if len(found) != 1:
        raise RigError('"%s" ist nicht eindeutig oder existiert nicht (%d Treffer).' % (name, len(found)))
    node = found[0]
    if cmds.nodeType(node) == 'mesh':
        node = cmds.listRelatives(node, parent=True, fullPath=True)[0]
    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True, fullPath=True, type='mesh') or []
    if len(shapes) != 1:
        raise RigError('%s: genau ein sichtbares Polygon-Mesh erwartet, gefunden: %d.' % (short(node), len(shapes)))
    if len(cmds.ls(shapes[0], allPaths=True) or []) > 1:
        raise RigError('%s ist instanziert. Bitte zuerst eine eigenstaendige Kopie machen.' % short(node))
    return node, shapes[0]


def dag_path(name):
    _, om, _ = api()
    selection = om.MSelectionList()
    selection.add(name)
    return selection.getDagPath(0)


def skin_cluster(shape):
    cmds = api()[0]
    skins = list(dict.fromkeys(cmds.ls(cmds.listHistory(shape, pruneDagObjects=True) or [],
                                       type='skinCluster') or []))
    if len(skins) != 1:
        raise RigError('%s: genau ein skinCluster erwartet, gefunden: %d.' % (short(shape), len(skins)))
    return skins[0]


def fn_skin(skin):
    _, om, oma = api()
    selection = om.MSelectionList()
    selection.add(skin)
    return oma.MFnSkinCluster(selection.getDependNode(0))


def complete_component(count):
    _, om, _ = api()
    fn = om.MFnSingleIndexedComponent()
    component = fn.create(om.MFn.kMeshVertComponent)
    fn.setCompleteData(count)
    return component


class MeshData(object):
    """World-space snapshot of a mesh (current evaluated shape)."""

    def __init__(self, transform, shape):
        _, om, _ = api()
        self.transform, self.shape = transform, shape
        self.dag = dag_path(shape)
        fn = om.MFnMesh(self.dag)
        self.points = [(p.x, p.y, p.z) for p in fn.getPoints(om.MSpace.kWorld)]
        counts, vertices = fn.getTriangles()
        self.triangles = [tuple(vertices[i:i + 3]) for i in range(0, len(vertices), 3)]
        self.adjacency = [[] for _ in self.points]
        iterator = om.MItMeshVertex(self.dag)
        while not iterator.isDone():
            self.adjacency[iterator.index()] = list(iterator.getConnectedVertices())
            iterator.next()
        self.shell_of = self._shells()

    def _shells(self):
        parent = list(range(len(self.points)))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for a, b, c in self.triangles:
            ra = find(a)
            for v in (b, c):
                rv = find(v)
                if rv != ra:
                    parent[rv] = ra
        roots, result = {}, []
        for v in range(len(self.points)):
            result.append(roots.setdefault(find(v), len(roots)))
        return result

    @property
    def shell_count(self):
        return max(self.shell_of) + 1 if self.shell_of else 0


class ClosestPoint(object):
    """Closest point on a triangle subset, returns (triangle vertex ids, barycentric, distance)."""

    def __init__(self, points, triangles):
        _, om, _ = api()
        from . import core
        self._core = core
        if not triangles:
            raise RigError('Keine Dreiecke fuer die Closest-Point-Suche.')
        self.points, self.triangles = points, triangles
        used = sorted(set(v for tri in triangles for v in tri))
        local = {v: i for i, v in enumerate(used)}
        vertices = om.MPointArray([om.MPoint(*points[v]) for v in used])
        counts = om.MIntArray([3] * len(triangles))
        connects = om.MIntArray([local[v] for tri in triangles for v in tri])
        data = om.MFnMeshData().create()
        om.MFnMesh().create(vertices, counts, connects, parent=data)
        self._data = data
        self._om = om
        self._intersector = om.MMeshIntersector()
        try:
            self._intersector.create(data, om.MMatrix())
        except RuntimeError:
            # Fallback: plain closest-point query on the mesh data (slower).
            self._intersector = None
            self._fn = om.MFnMesh(data)

    def query(self, point):
        om = self._om
        if self._intersector is not None:
            hit = self._intersector.getClosestPoint(om.MPoint(*point))
            face, hit_point = hit.face, hit.point
        else:
            hit_point, face = self._fn.getClosestPoint(om.MPoint(*point), om.MSpace.kObject)
        tri = self.triangles[face]
        closest = (hit_point.x, hit_point.y, hit_point.z)
        bary = self._core.barycentric(closest, *(self.points[v] for v in tri))
        distance = sum((a - b) ** 2 for a, b in zip(point, closest)) ** 0.5
        return tri, bary, distance


class BodyData(MeshData):
    """Skinned body: weights, influences, bind and current matrices."""

    def __init__(self, transform, shape):
        MeshData.__init__(self, transform, shape)
        cmds, om, _ = api()
        self.skin = skin_cluster(shape)
        fn = fn_skin(self.skin)
        paths = fn.influenceObjects()
        self.influences = [p.fullPathName() for p in paths]
        self.leaves = [leaf(n) for n in self.influences]
        bad = [n for n in self.influences if cmds.nodeType(n) != 'joint']
        if bad:
            raise RigError('Body-Influences muessen Joints sein: %s' % ', '.join(short(n) for n in bad[:5]))
        self.bind_pre, self.world = [], []
        for p in paths:
            logical = fn.indexForInfluenceObject(p)
            self.bind_pre.append(list(cmds.getAttr('%s.bindPreMatrix[%d]' % (self.skin, logical))))
            self.world.append(list(cmds.getAttr(p.fullPathName() + '.worldMatrix[0]')))
        weights, stride = fn.getWeights(self.dag, complete_component(len(self.points)))
        self.rows = []
        for v in range(len(self.points)):
            base = v * stride
            self.rows.append({i: weights[base + i] for i in range(stride) if weights[base + i] > 1e-6})
        self.index_of = {}
        duplicates = set()
        for i, name in enumerate(self.leaves):
            if name in self.index_of:
                duplicates.add(name)
            self.index_of[name] = i
        for name in duplicates:
            del self.index_of[name]
        self.duplicates = sorted(duplicates)

    def skin_matrix(self, index):
        """bindPre * world (row-vector convention), as om.MMatrix."""
        _, om, _ = api()
        return om.MMatrix(self.bind_pre[index]) * om.MMatrix(self.world[index])


def joint_position(name):
    cmds = api()[0]
    return tuple(cmds.xform(name, query=True, worldSpace=True, translation=True))


def find_joint(body, name):
    """Influence of the body by leaf name, else a joint below the body's skeleton."""
    cmds = api()[0]
    if name in body.index_of:
        return body.influences[body.index_of[name]]
    roots = set()
    for path in body.influences:
        roots.add('|'.join(path.split('|')[:2]))
    found = []
    for root in roots:
        for node in cmds.listRelatives(root, allDescendents=True, fullPath=True, type='joint') or []:
            if leaf(node) == name:
                found.append(node)
    return found[0] if len(found) == 1 else None


def is_excluded(leaf_name):
    return any(re.search(p, leaf_name) for p in EXCLUDE_PATTERNS)


LEG_LEFT = frozenset(('mHipLeft', 'L_UPPER_LEG', 'mKneeLeft', 'L_LOWER_LEG'))
LEG_RIGHT = frozenset(('mHipRight', 'R_UPPER_LEG', 'mKneeRight', 'R_LOWER_LEG'))


LEG_LOWER = frozenset(('mKneeLeft', 'L_LOWER_LEG', 'mAnkleLeft', 'L_FOOT', 'mFootLeft', 'mToeLeft',
                       'mKneeRight', 'R_LOWER_LEG', 'mAnkleRight', 'R_FOOT', 'mFootRight', 'mToeRight'))


def leg_chain(leaf_name):
    """(side, level) for the leg sweep: level 1 thigh, 2 shin/foot; side 0 = not a leg."""
    if leaf_name in LEG_LOWER:
        return (1 if ('Left' in leaf_name or leaf_name.startswith('L_')) else -1), 2
    side = leg_side(leaf_name)
    return side, (1 if side else 0)


def leg_side(leaf_name):
    """+1 left leg, -1 right leg, 0 otherwise (thigh and lower leg only, no feet)."""
    return 1 if leaf_name in LEG_LEFT else (-1 if leaf_name in LEG_RIGHT else 0)


def is_arm(leaf_name):
    return any(re.search(p, leaf_name) for p in ARM_PATTERNS)


def delete_nodes(nodes):
    cmds = api()[0]
    existing = [n for n in nodes if n and cmds.objExists(n)]
    if existing:
        cmds.delete(existing)


def reset_transform(node):
    """Set a transform WE created to identity (it is a fresh duplicate)."""
    cmds = api()[0]
    for attr, value in (('translate', (0, 0, 0)), ('rotate', (0, 0, 0)), ('scale', (1, 1, 1)),
                        ('shear', (0, 0, 0)), ('rotateAxis', (0, 0, 0)), ('rotatePivot', (0, 0, 0)),
                        ('scalePivot', (0, 0, 0)), ('rotatePivotTranslate', (0, 0, 0)),
                        ('scalePivotTranslate', (0, 0, 0))):
        for axis in 'XYZ':
            plug = '%s.%s%s' % (node, attr, axis)
            if cmds.objExists(plug):
                cmds.setAttr(plug, lock=False)
        cmds.setAttr('%s.%s' % (node, attr), *value)
    world = cmds.xform(node, query=True, matrix=True, worldSpace=True)
    identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    if any(abs(a - b) > 1e-9 for a, b in zip(world, identity)):
        raise RigError('Transform der Kopie %s laesst sich nicht auf Identitaet setzen.' % short(node))


def duplicate_mesh(transform, suffix):
    """Fresh, history-free duplicate under the world with identity transform."""
    cmds = api()[0]
    name = leaf(transform) + suffix
    out = cmds.duplicate(transform, name=name, returnRootsOnly=True, inputConnections=False)[0]
    created = [out]
    try:
        cmds.delete(out, constructionHistory=True)
        if cmds.listRelatives(out, parent=True):
            out = cmds.parent(out, world=True)[0]
            created = [out]
        out = cmds.ls(out, long=True)[0]
        created = [out]
        extra = [s for s in (cmds.listRelatives(out, shapes=True, fullPath=True) or [])
                 if cmds.getAttr(s + '.intermediateObject')]
        if extra:
            cmds.delete(extra)
        kids = cmds.listRelatives(out, children=True, type='transform', fullPath=True)
        if kids:
            cmds.delete(kids)
        cmds.setAttr(out + '.visibility', lock=False)
        cmds.setAttr(out + '.visibility', True)
        reset_transform(out)
        return out
    except Exception:
        delete_nodes(created)
        raise


def build_skin_node(mesh, joints, name):
    """skinCluster node wired by hand: joint.worldMatrix -> matrix[i] (no dagPose)."""
    cmds = api()[0]
    skin = cmds.deformer(mesh, type='skinCluster', name=name)[0]
    for index, joint in enumerate(joints):
        cmds.connectAttr(joint + '.worldMatrix[0]', '%s.matrix[%d]' % (skin, index))
        if cmds.objExists(joint + '.lockInfluenceWeights'):
            cmds.connectAttr(joint + '.lockInfluenceWeights', '%s.lockWeights[%d]' % (skin, index))
    cmds.setAttr(skin + '.skinningMethod', 0)
    cmds.setAttr(skin + '.normalizeWeights', 1)
    return skin


def influence_usage(rows):
    usage = collections.Counter()
    for row in rows:
        for i in row:
            usage[i] += 1
    return usage
