# -*- coding: utf-8 -*-
"""mcd. SL Anim 0.1 — writes Second Life .anim files for cloth bones.

STAGE 0 OF THE STATE CLOTH LAYER (docs/konzept_kleidung_und_bewegung.md).
The byte layout follows the official viewer source (secondlife/viewer,
indra/llcharacter/llkeyframemotion.cpp, LLKeyframeMotion::serialize and
deserialize). Upload and playback in Second Life are NOT verified yet:
that is exactly what the stage 0 test (docs/stufe0_testprotokoll.md) checks.

What this module does:
  * write_anim / read_anim: binary .anim (version 1.0) with rotation AND
    position keys per joint, joint priorities, loop and ease settings.
  * validate: the viewer's own rejections (duration > 60 s, bad priority,
    hand pose, ...) plus the 250 000 byte asset limit, BEFORE uploading.
  * make_sway_test: a procedural test loop on cloth bones, no Maya needed.
  * Maya (optional): build_test_ribbons() creates simple ribbons skinned to
    the cloth bones of an existing SL skeleton in the scene; bake_from_maya()
    samples animated cloth bones and writes an .anim.

AO NEUTRALITY: by default only cloth bones (tail, hind limbs, groin, wings)
may be keyed. Body bones are refused unless allow_body_bones=True, so the
wearer's AO keeps every body joint.

Facts from the viewer source that this module relies on:
  * Animated positions are ABSOLUTE local positions (relative to the parent
    joint), not offsets: llkeyframemotion.cpp sets the joint state position
    directly from the curve, llpose.cpp blends to it.
  * Positions are clamped to +-5 m and stored as U16; rotations are stored
    as the x, y, z of a unit quaternion with w >= 0, also as U16.
  * Key times are U16 fractions of the duration; keys that collapse to the
    same U16 time are removed by the viewer (we report them as an error).
  * An animation can override the system hand pose when its highest joint
    priority is >= the current hand pose priority. Keep cloth priorities low.

START (outside Maya):
    python mcd_sl_anim.py --sway out_dir     # writes test loops
    python mcd_sl_anim.py --dump file.anim   # prints a file's contents
"""

import math
import struct

VERSION = '0.1'

ANIM_VERSION = 1
ANIM_SUBVERSION = 0
MAX_DURATION = 60.0          # llbvhconsts.h MAX_ANIM_DURATION
MAX_ASSET_BYTES = 250000     # SL wiki "Limit": animation asset size
POS_LIMIT = 5.0              # lljoint.h LL_MAX_PELVIS_OFFSET
MAX_ANIMATED_JOINTS = 216    # lljoint.h LL_CHARACTER_MAX_ANIMATED_JOINTS
USE_MOTION_PRIORITY = -1
MAX_PRIORITY = 6             # 7 is ADDITIVE_PRIORITY; the viewer clamps to 6
NUM_HAND_POSES = 14          # llhandmotion.h
HAND_POSE_RELAXED = 1        # the BVH importer's default
U16MAX = 65535

# Default local positions (metres, SL axes: X forward, Y left, Z up) and
# parents, copied from indra/newview/character/avatar_skeleton.xml.
# All of these bones have a default rotation of zero.
CLOTH_BONES = {
    'mTail1': ('mPelvis', (-0.116, 0.000, 0.047)),
    'mTail2': ('mTail1', (-0.197, 0.000, 0.000)),
    'mTail3': ('mTail2', (-0.168, 0.000, 0.000)),
    'mTail4': ('mTail3', (-0.142, 0.000, 0.000)),
    'mTail5': ('mTail4', (-0.112, 0.000, 0.000)),
    'mTail6': ('mTail5', (-0.094, 0.000, 0.000)),
    'mGroin': ('mPelvis', (0.064, 0.000, -0.097)),
    'mHindLimbsRoot': ('mPelvis', (-0.200, 0.000, 0.084)),
    'mHindLimb1Left': ('mHindLimbsRoot', (-0.204, 0.129, -0.125)),
    'mHindLimb2Left': ('mHindLimb1Left', (0.002, -0.046, -0.491)),
    'mHindLimb3Left': ('mHindLimb2Left', (-0.030, -0.003, -0.468)),
    'mHindLimb4Left': ('mHindLimb3Left', (0.112, 0.000, -0.061)),
    'mHindLimb1Right': ('mHindLimbsRoot', (-0.204, -0.129, -0.125)),
    'mHindLimb2Right': ('mHindLimb1Right', (0.002, 0.046, -0.491)),
    'mHindLimb3Right': ('mHindLimb2Right', (-0.030, 0.003, -0.468)),
    'mHindLimb4Right': ('mHindLimb3Right', (0.112, 0.000, -0.061)),
    'mWingsRoot': ('mChest', (-0.014, 0.000, 0.000)),
    'mWing1Left': ('mWingsRoot', (-0.099, 0.105, 0.181)),
    'mWing2Left': ('mWing1Left', (-0.168, 0.169, 0.067)),
    'mWing3Left': ('mWing2Left', (-0.181, 0.183, 0.000)),
    'mWing4Left': ('mWing3Left', (-0.171, 0.173, 0.000)),
    'mWing4FanLeft': ('mWing3Left', (-0.171, 0.173, 0.000)),
    'mWing1Right': ('mWingsRoot', (-0.099, -0.105, 0.181)),
    'mWing2Right': ('mWing1Right', (-0.168, -0.169, 0.067)),
    'mWing3Right': ('mWing2Right', (-0.181, -0.183, 0.000)),
    'mWing4Right': ('mWing3Right', (-0.171, -0.173, 0.000)),
    'mWing4FanRight': ('mWing3Right', (-0.171, -0.173, 0.000)),
}

# Bone sets offered for the stage 0 test and the later solver.
BONE_SETS = {
    'hindlimbs': ('mHindLimb1Left', 'mHindLimb2Left', 'mHindLimb1Right',
                  'mHindLimb2Right'),
    'tail': ('mTail1', 'mTail2', 'mTail3'),
    'groin': ('mGroin',),
}


class AnimError(ValueError):
    pass


# --- quaternions (x, y, z, w), Hamilton convention, column vectors ---------
def quat_normalize(q):
    length = math.sqrt(sum(c * c for c in q))
    if length <= 1e-12 or not math.isfinite(length):
        raise AnimError('Ungueltige Rotation (Quaternion mit Laenge 0).')
    return tuple(c / length for c in q)


def quat_from_axis_angle(axis, angle):
    ax = quat_normalize(tuple(axis) + (0.0,))[:3]
    s = math.sin(0.5 * angle)
    return (ax[0] * s, ax[1] * s, ax[2] * s, math.cos(0.5 * angle))


def quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def quat_from_matrix(m):
    """Unit quaternion from a 3x3 rotation matrix (rows of columns-convention R)."""
    trace = m[0][0] + m[1][1] + m[2][2]
    if trace > 0.0:
        s = 2.0 * math.sqrt(trace + 1.0)
        q = ((m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s,
             (m[1][0] - m[0][1]) / s, 0.25 * s)
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = 2.0 * math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2])
        q = (0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s,
             (m[2][1] - m[1][2]) / s)
    elif m[1][1] > m[2][2]:
        s = 2.0 * math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2])
        q = ((m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s,
             (m[0][2] - m[2][0]) / s)
    else:
        s = 2.0 * math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1])
        q = ((m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s,
             (m[1][0] - m[0][1]) / s)
    return quat_normalize(q)


# --- quantization exactly as llquantize.h -----------------------------------
def f32_to_u16(value, lower, upper):
    value = max(lower, min(upper, value))
    return int(math.floor((value - lower) / (upper - lower) * U16MAX))


def u16_to_f32(ival, lower, upper):
    delta = upper - lower
    value = ival / float(U16MAX) * delta + lower
    # The viewer snaps values within one step of zero to exactly zero.
    if abs(value) < delta / U16MAX:
        value = 0.0
    return value


def pack_rotation(q):
    """x, y, z of the unit quaternion with w >= 0 (LLQuaternion::packToVector3)."""
    q = quat_normalize(q)
    if q[3] < 0.0:
        q = tuple(-c for c in q)
    return q[:3]


def unpack_rotation(vec):
    x, y, z = vec
    t = 1.0 - (x * x + y * y + z * z)
    return (x, y, z, math.sqrt(t) if t > 0.0 else 0.0)


# --- data model ---------------------------------------------------------------
class JointTrack:
    """Keys of one joint. Times in seconds; rotations as (x, y, z, w);
    positions as ABSOLUTE local positions in metres (SL axes)."""

    def __init__(self, name, priority=USE_MOTION_PRIORITY, rot_keys=None,
                 pos_keys=None):
        self.name = name
        self.priority = priority
        self.rot_keys = list(rot_keys or [])
        self.pos_keys = list(pos_keys or [])


class Anim:
    def __init__(self, tracks, duration, loop=True, loop_in=0.0, loop_out=None,
                 ease_in=0.4, ease_out=0.4, base_priority=1,
                 hand_pose=HAND_POSE_RELAXED, emote=''):
        self.tracks = list(tracks)
        self.duration = float(duration)
        self.loop = bool(loop)
        self.loop_in = float(loop_in)
        self.loop_out = float(duration if loop_out is None else loop_out)
        self.ease_in = float(ease_in)
        self.ease_out = float(ease_out)
        self.base_priority = int(base_priority)
        self.hand_pose = int(hand_pose)
        self.emote = emote


def validate(anim, allow_body_bones=False):
    """Return a list of problems. Empty list = would pass the viewer checks."""
    problems = []
    d = anim.duration
    if not math.isfinite(d) or d <= 0.0:
        problems.append('Dauer muss groesser als 0 sein.')
    elif d > MAX_DURATION:
        problems.append('Dauer %.2f s ueberschreitet %.0f s.' % (d, MAX_DURATION))
    for label, value in (('Loop-Start', anim.loop_in), ('Loop-Ende', anim.loop_out),
                         ('Ease-In', anim.ease_in), ('Ease-Out', anim.ease_out)):
        if not math.isfinite(value) or value < 0.0:
            problems.append('%s ist ungueltig.' % label)
    if anim.loop and not (0.0 <= anim.loop_in < anim.loop_out <= d + 1e-9):
        problems.append('Loop-Punkte muessen 0 <= Start < Ende <= Dauer erfuellen.')
    if not USE_MOTION_PRIORITY <= anim.base_priority <= MAX_PRIORITY:
        problems.append('Basisprioritaet muss zwischen -1 und %d liegen.' % MAX_PRIORITY)
    if not 0 <= anim.hand_pose <= NUM_HAND_POSES:
        problems.append('Handpose %d ist ungueltig.' % anim.hand_pose)
    if not anim.tracks:
        problems.append('Keine Gelenke.')
    if len(anim.tracks) > MAX_ANIMATED_JOINTS:
        problems.append('Zu viele Gelenke.')
    seen = set()
    for track in anim.tracks:
        name = track.name
        if name in seen:
            problems.append('%s ist doppelt vorhanden.' % name)
        seen.add(name)
        if name in ('mScreen', 'mRoot') or not name:
            problems.append('%s darf nicht animiert werden.' % (name or '(leer)'))
        elif name not in CLOTH_BONES and not allow_body_bones:
            problems.append('%s ist kein Stoff-Bone. Die AO der Traegerin bliebe '
                            'nicht unberuehrt (allow_body_bones=False).' % name)
        if not USE_MOTION_PRIORITY <= track.priority <= MAX_PRIORITY:
            problems.append('%s: Prioritaet ausserhalb -1..%d.' % (name, MAX_PRIORITY))
        if not track.rot_keys and not track.pos_keys:
            problems.append('%s hat keine Keys.' % name)
        for kind, keys in (('Rotations', track.rot_keys), ('Positions', track.pos_keys)):
            stamps = set()
            for t, value in keys:
                if not math.isfinite(t) or t < 0.0 or t > d + 1e-9:
                    problems.append('%s: %skey bei %.4f s liegt ausserhalb der Dauer.'
                                    % (name, kind, t))
                    continue
                if not all(math.isfinite(c) for c in value):
                    problems.append('%s: %skey bei %.4f s ist nicht endlich.' % (name, kind, t))
                if kind == 'Positions' and any(abs(c) > POS_LIMIT for c in value):
                    problems.append('%s: Position bei %.4f s ueberschreitet +-%.0f m.'
                                    % (name, t, POS_LIMIT))
                if d > 0.0:
                    stamp = f32_to_u16(t, 0.0, d)
                    if stamp in stamps:
                        problems.append('%s: %skeys zu dicht, Zeit %.5f s faellt beim '
                                        'Quantisieren mit einem anderen Key zusammen.'
                                        % (name, kind, t))
                    stamps.add(stamp)
    if not problems:
        size = len(_serialize(anim))
        if size > MAX_ASSET_BYTES:
            problems.append('Datei hat %d Bytes, erlaubt sind %d.' % (size, MAX_ASSET_BYTES))
    return problems


def _pack_string(text):
    raw = text.encode('utf-8')
    if b'\0' in raw:
        raise AnimError('Text darf kein Nullzeichen enthalten.')
    return raw + b'\0'


def _serialize(anim):
    out = [struct.pack('<HHif', ANIM_VERSION, ANIM_SUBVERSION, anim.base_priority,
                       anim.duration),
           _pack_string(anim.emote),
           struct.pack('<ffiffII', anim.loop_in, anim.loop_out, int(anim.loop),
                       anim.ease_in, anim.ease_out, anim.hand_pose, len(anim.tracks))]
    d = anim.duration
    for track in anim.tracks:
        out.append(_pack_string(track.name))
        out.append(struct.pack('<ii', track.priority, len(track.rot_keys)))
        for t, q in sorted(track.rot_keys, key=lambda k: k[0]):
            x, y, z = pack_rotation(q)
            out.append(struct.pack('<HHHH', f32_to_u16(t, 0.0, d), f32_to_u16(x, -1.0, 1.0),
                                   f32_to_u16(y, -1.0, 1.0), f32_to_u16(z, -1.0, 1.0)))
        out.append(struct.pack('<i', len(track.pos_keys)))
        for t, p in sorted(track.pos_keys, key=lambda k: k[0]):
            out.append(struct.pack('<HHHH', f32_to_u16(t, 0.0, d),
                                   f32_to_u16(p[0], -POS_LIMIT, POS_LIMIT),
                                   f32_to_u16(p[1], -POS_LIMIT, POS_LIMIT),
                                   f32_to_u16(p[2], -POS_LIMIT, POS_LIMIT)))
    out.append(struct.pack('<i', 0))  # no constraints
    return b''.join(out)


def write_anim(anim, allow_body_bones=False):
    """Return the .anim bytes, or raise AnimError listing every problem."""
    problems = validate(anim, allow_body_bones)
    if problems:
        raise AnimError('\n'.join(problems))
    return _serialize(anim)


def read_anim(data):
    """Parse .anim bytes (version 1.0) into an Anim with dequantized keys."""
    offset = [0]

    def take(fmt):
        size = struct.calcsize(fmt)
        if offset[0] + size > len(data):
            raise AnimError('Datei ist abgeschnitten.')
        values = struct.unpack_from(fmt, data, offset[0])
        offset[0] += size
        return values

    def take_string():
        end = data.find(b'\0', offset[0])
        if end < 0:
            raise AnimError('Text ohne Abschluss.')
        text = data[offset[0]:end].decode('utf-8', 'replace')
        offset[0] = end + 1
        return text

    version, subversion, base_priority, duration = take('<HHif')
    if (version, subversion) != (ANIM_VERSION, ANIM_SUBVERSION):
        raise AnimError('Nur Version 1.0 wird gelesen (gefunden %d.%d).'
                        % (version, subversion))
    emote = take_string()
    loop_in, loop_out, loop, ease_in, ease_out, hand_pose, count = take('<ffiffII')
    tracks = []
    for _ in range(count):
        name = take_string()
        priority, rot_count = take('<ii')
        rot_keys = []
        for _ in range(rot_count):
            t, x, y, z = take('<HHHH')
            vec = tuple(u16_to_f32(v, -1.0, 1.0) for v in (x, y, z))
            rot_keys.append((u16_to_f32(t, 0.0, duration), unpack_rotation(vec)))
        pos_count, = take('<i')
        pos_keys = []
        for _ in range(pos_count):
            t, x, y, z = take('<HHHH')
            pos_keys.append((u16_to_f32(t, 0.0, duration),
                             tuple(u16_to_f32(v, -POS_LIMIT, POS_LIMIT) for v in (x, y, z))))
        tracks.append(JointTrack(name, priority, rot_keys, pos_keys))
    constraints, = take('<i')
    if constraints:
        raise AnimError('Constraints werden nicht gelesen (%d vorhanden).' % constraints)
    return Anim(tracks, duration, bool(loop), loop_in, loop_out, ease_in, ease_out,
                base_priority, hand_pose, emote)


# --- procedural stage 0 test ---------------------------------------------------
def make_sway_test(bones, duration=2.0, fps=24, swing_deg=15.0, shift=0.04,
                   priority=1, ease=0.5, phase_step=0.25):
    """A looped, clearly visible sway on cloth bones.

    Rotation: swing around the local Y axis (pitch; front edge rises forward).
    Position: the default local position plus a forward (X) shift. If SL plays
    position keys on these bones, the ribbons visibly move forward AND swing;
    if it plays rotations only, they swing in place. Each bone is phase
    shifted so the chain reads as a wave. The loop closes exactly.
    """
    if duration <= 0.0 or fps <= 0:
        raise AnimError('Dauer und fps muessen groesser als 0 sein.')
    frames = int(round(duration * fps))
    tracks = []
    for index, name in enumerate(bones):
        if name not in CLOTH_BONES:
            raise AnimError('%s ist kein Stoff-Bone.' % name)
        rest = CLOTH_BONES[name][1]
        rot_keys, pos_keys = [], []
        for frame in range(frames + 1):
            t = min(duration, frame / float(fps))
            phase = 2.0 * math.pi * (t / duration - index * phase_step)
            angle = math.radians(swing_deg) * math.sin(phase)
            rot_keys.append((t, quat_from_axis_angle((0.0, 1.0, 0.0), angle)))
            offset = shift * 0.5 * (1.0 - math.cos(phase))
            pos_keys.append((t, (rest[0] + offset, rest[1], rest[2])))
        tracks.append(JointTrack(name, priority, rot_keys, pos_keys))
    return Anim(tracks, duration, loop=True, loop_in=0.0, loop_out=duration,
                ease_in=ease, ease_out=ease, base_priority=priority)


def make_hold(bones, offsets=None, rotations=None, duration=1.0, priority=1, ease=0.5):
    """A static state pose (e.g. 'sit': panels moved aside) as a looped hold.

    offsets: {bone: (dx, dy, dz)} added to the default position (metres).
    rotations: {bone: (x, y, z, w)} local rotations. Two identical keys at the
    start and end keep the pose constant over the loop.
    """
    offsets = offsets or {}
    rotations = rotations or {}
    tracks = []
    for name in bones:
        if name not in CLOTH_BONES:
            raise AnimError('%s ist kein Stoff-Bone.' % name)
        rest = CLOTH_BONES[name][1]
        d = offsets.get(name, (0.0, 0.0, 0.0))
        pos = (rest[0] + d[0], rest[1] + d[1], rest[2] + d[2])
        rot = rotations.get(name, (0.0, 0.0, 0.0, 1.0))
        tracks.append(JointTrack(name, priority, [(0.0, rot), (duration, rot)],
                                 [(0.0, pos), (duration, pos)]))
    return Anim(tracks, duration, loop=True, loop_in=0.0, loop_out=duration,
                ease_in=ease, ease_out=ease, base_priority=priority)


def describe(anim):
    lines = ['Dauer %.3f s, Loop %s (%.3f-%.3f), Ease %.2f/%.2f s, Prioritaet %d, '
             'Handpose %d, %d Gelenke'
             % (anim.duration, 'ja' if anim.loop else 'nein', anim.loop_in, anim.loop_out,
                anim.ease_in, anim.ease_out, anim.base_priority, anim.hand_pose,
                len(anim.tracks))]
    for track in anim.tracks:
        lines.append('  %-16s Prio %2d  Rot-Keys %4d  Pos-Keys %4d'
                     % (track.name, track.priority, len(track.rot_keys), len(track.pos_keys)))
    return '\n'.join(lines)


# --- Maya (optional) ------------------------------------------------------------
# Basis change from Maya world axes to SL axes. Each entry lists, for the SL
# axes X (forward), Y (left), Z (up), the Maya world vector it corresponds to.
AXIS_PRESETS = {
    'y_up_front_z': ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
    'z_up_front_x': ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    'z_up_front_neg_y': ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
}


def _mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _mat_t(a):
    return [[a[j][i] for j in range(3)] for i in range(3)]


def _mat_vec(a, v):
    return tuple(sum(a[i][k] * v[k] for k in range(3)) for i in range(3))


def _orthonormal(rows):
    # Gram-Schmidt on rows: removes joint scale and small shear from Maya.
    out = []
    for row in rows:
        v = list(row)
        for u in out:
            dot = sum(v[i] * u[i] for i in range(3))
            v = [v[i] - dot * u[i] for i in range(3)]
        length = math.sqrt(sum(c * c for c in v))
        if length <= 1e-12:
            raise AnimError('Gelenkmatrix ist entartet (Skalierung 0?).')
        out.append([c / length for c in v])
    return out


def _maya_world(cmds, joint):
    """Column-convention rotation R and translation of a Maya world matrix."""
    m = cmds.xform(joint, q=True, ws=True, m=True)
    rows = _orthonormal([m[0:3], m[4:7], m[8:11]])
    return _mat_t(rows), (m[12], m[13], m[14])


def sl_local_pose(parent_world, child_world, parent_rest, child_rest, basis, scale):
    """SL local rotation and absolute local position of a child joint.

    Every SL cloth bone and its ancestors have a default rotation of zero, so
    a joint's SL world rotation is its Maya world rotation relative to its
    rest (bind) rotation, expressed in SL axes. Pure function for testing.
    """
    c = [list(row) for row in basis]          # rows: SL axes in Maya coordinates
    ct = _mat_t(c)

    def sl_rot(world, rest):
        delta = _mat_mul(world[0], _mat_t(rest[0]))
        return _mat_mul(_mat_mul(c, delta), ct)

    r_parent = sl_rot(parent_world, parent_rest)
    r_child = sl_rot(child_world, child_rest)
    local_rot = quat_from_matrix(_mat_mul(_mat_t(r_parent), r_child))
    offset = [child_world[1][i] - parent_world[1][i] for i in range(3)]
    local_pos = _mat_vec(_mat_t(r_parent), _mat_vec(c, offset))
    return local_rot, tuple(v * scale for v in local_pos)


def bake_from_maya(bones, start, end, path, fps=24.0, rest_frame=None,
                   axes='y_up_front_z', scale=0.01, priority=1, ease_in=0.5,
                   ease_out=0.5, loop=True, tolerance=0.002):
    """Sample cloth bones in the open Maya scene and write an .anim.

    rest_frame: frame where the skeleton is in the SL default (bind) pose;
    defaults to start. scale: Maya units to metres (0.01 for centimetres).
    Joints must carry their SL names (namespaces are ignored). Returns a list
    of warnings, e.g. when the Maya rest positions differ from SL defaults.
    NOT YET VERIFIED IN MAYA.
    """
    import maya.cmds as cmds

    basis = AXIS_PRESETS[axes]
    rest_frame = start if rest_frame is None else rest_frame
    found = {}
    for name in set(bones) | {CLOTH_BONES[b][0] for b in bones if b in CLOTH_BONES}:
        matches = [j for j in (cmds.ls('*:%s' % name, type='joint') or [])
                   + (cmds.ls(name, type='joint') or [])]
        if not matches:
            raise AnimError('Gelenk %s fehlt in der Szene.' % name)
        if len(set(matches)) > 1:
            raise AnimError('Gelenk %s ist mehrdeutig: %s' % (name, ', '.join(matches)))
        found[name] = matches[0]
    current = cmds.currentTime(q=True)
    warnings = []
    try:
        cmds.currentTime(rest_frame, edit=True)
        rest = {name: _maya_world(cmds, joint) for name, joint in found.items()}
        for name in bones:
            parent, default = CLOTH_BONES[name]
            _, pos = sl_local_pose(rest[parent], rest[name], rest[parent], rest[name],
                                   basis, scale)
            error = math.sqrt(sum((pos[i] - default[i]) ** 2 for i in range(3)))
            if error > tolerance:
                warnings.append('%s: Ruheposition weicht %.1f mm von SL ab. Gewichte und '
                                'Animation passen dann nicht zusammen.' % (name, error * 1000))
        frames = int(round((end - start)))
        duration = frames / float(fps)
        tracks = {name: JointTrack(name, priority) for name in bones}
        for frame in range(frames + 1):
            cmds.currentTime(start + frame, edit=True)
            t = min(duration, frame / float(fps))
            world = {name: _maya_world(cmds, joint) for name, joint in found.items()}
            for name in bones:
                parent = CLOTH_BONES[name][0]
                rot, pos = sl_local_pose(world[parent], world[name], rest[parent],
                                         rest[name], basis, scale)
                tracks[name].rot_keys.append((t, rot))
                tracks[name].pos_keys.append((t, pos))
    finally:
        cmds.currentTime(current, edit=True)
    anim = Anim([tracks[name] for name in bones], duration, loop=loop,
                ease_in=ease_in, ease_out=ease_out, base_priority=priority)
    with open(path, 'wb') as handle:
        handle.write(write_anim(anim))
    return warnings


def build_test_ribbons(bones=BONE_SETS['hindlimbs'] + BONE_SETS['tail'],
                       width=6.0, length=None, name='mcdClothTest'):
    """Create one thin ribbon per cloth bone, skinned 100 % to that bone.

    Uses the SL skeleton already in the scene. Export the result with your
    usual SL DAE pipeline (skin weights ON, joint positions OFF) and wear it
    for the stage 0 test. Ribbon length defaults to the distance to the child
    joint, or 30 scene units for chain ends. NOT YET VERIFIED IN MAYA.
    """
    import maya.cmds as cmds

    ribbons = []
    for bone in bones:
        joints = (cmds.ls('*:%s' % bone, type='joint') or []) + (cmds.ls(bone, type='joint') or [])
        if not joints:
            raise AnimError('Gelenk %s fehlt in der Szene.' % bone)
        joint = joints[0]
        start = cmds.xform(joint, q=True, ws=True, t=True)
        children = cmds.listRelatives(joint, children=True, type='joint') or []
        if children and length is None:
            end = cmds.xform(children[0], q=True, ws=True, t=True)
        else:
            end = [start[0], start[1] - (length or 30.0), start[2]]
        plane = cmds.polyPlane(name='%s_%s' % (name, bone), w=width, h=1.0, sx=1, sy=4)[0]
        # Stretch the unit plane between start and end, facing the camera axis.
        verts = cmds.ls('%s.vtx[*]' % plane, flatten=True)
        for vtx in verts:
            p = cmds.pointPosition(vtx, local=True)
            u = p[2] + 0.5                     # 0..1 along the plane's height
            side = p[0]
            pos = [start[i] + (end[i] - start[i]) * u for i in range(3)]
            pos[0] += side
            cmds.xform(vtx, ws=True, t=pos)
        cmds.skinCluster(joint, plane, toSelectedBones=True, maximumInfluences=1,
                         name='%s_skin' % plane)
        ribbons.append(plane)
    return ribbons


def _main(argv):
    import os
    if len(argv) >= 2 and argv[0] == '--dump':
        with open(argv[1], 'rb') as handle:
            print(describe(read_anim(handle.read())))
        return 0
    if len(argv) >= 2 and argv[0] == '--sway':
        folder = argv[1]
        if not os.path.isdir(folder):
            os.makedirs(folder)
        tests = {
            'mcd_test_sway_hindlimbs': make_sway_test(BONE_SETS['hindlimbs']),
            'mcd_test_sway_tail': make_sway_test(BONE_SETS['tail']),
            # Rotation only, same motion: compares with the version above.
            'mcd_test_sway_hindlimbs_rot_only': _rotation_only(
                make_sway_test(BONE_SETS['hindlimbs'])),
            # Upper chain bones 10 cm forward (SL +X): checks position axes.
            'mcd_test_hold_hindlimbs_forward': make_hold(
                BONE_SETS['hindlimbs'],
                offsets={b: (0.10, 0.0, 0.0) for b in BONE_SETS['hindlimbs'][::2]}),
            # Upper chain bones +25 deg about SL +Y (left): a hanging ribbon's
            # lower end must swing BACKWARD. Checks rotation direction.
            'mcd_test_hold_hindlimbs_rotate': make_hold(
                BONE_SETS['hindlimbs'],
                rotations={b: quat_from_axis_angle((0.0, 1.0, 0.0), math.radians(25.0))
                           for b in BONE_SETS['hindlimbs'][::2]}),
            # State test set for lsl/mcd_cloth_state.lsl (rest, sway, forward).
            'cloth_stand': make_hold(BONE_SETS['hindlimbs']),
            'cloth_walk': make_sway_test(BONE_SETS['hindlimbs']),
            'cloth_sit': make_hold(
                BONE_SETS['hindlimbs'],
                offsets={b: (0.10, 0.0, 0.0) for b in BONE_SETS['hindlimbs'][::2]}),
        }
        for stem, anim in tests.items():
            path = os.path.join(folder, stem + '.anim')
            with open(path, 'wb') as handle:
                handle.write(write_anim(anim))
            print('%s  (%d Bytes)' % (path, os.path.getsize(path)))
        return 0
    print(__doc__)
    return 1


def _rotation_only(anim):
    for track in anim.tracks:
        track.pos_keys = []
    return anim


if __name__ == '__main__':
    import sys
    sys.exit(_main(sys.argv[1:]))
