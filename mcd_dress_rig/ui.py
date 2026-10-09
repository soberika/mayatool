# -*- coding: utf-8 -*-
"""Maya UI for mcd. Dress Rig (M1)."""
from __future__ import division

import traceback

from . import pipeline
from . import scene
from .scene import RigError

WINDOW = 'mcdDressRigWindow'
SLIDERS = (
    ('center_width', 'Mitte weich (x Beinabstand)', 0.5, 3.0),
    ('center_hold', 'Mitte am Becken', 0.0, 1.0),
    ('leg_follow', 'Beinbindung', 0.0, 1.0),
    ('knee_follow', 'Knie folgen', 0.0, 1.0),
    ('outer_follow', 'Aussenseite folgt Bein', 0.0, 1.0),
    ('contact_strength', 'Am Bein anliegend folgt', 0.0, 1.0),
    ('sweep_scale', 'Bewegungsbereich (Schritte)', 0.0, 1.0),
    ('front_follow', 'Vorne folgt Beinen', 0.0, 0.6),
    ('back_hold', 'Hinten am Becken', 0.0, 0.6),
)


class DressRigWindow(object):
    def __init__(self, version):
        import maya.cmds as cmds
        self.cmds = cmds
        self.version = version
        self.c = {}
        self.strip = {}   # part transform -> list of strips (vertex index sets), one per 'merken'
        self._build()

    # ----------------------------------------------------------------- UI
    def _build(self):
        cmds = self.cmds
        if cmds.window(WINDOW, exists=True):
            cmds.deleteUI(WINDOW)
        cmds.window(WINDOW, title='mcd. Dress Rig %s' % self.version, widthHeight=(560, 760))
        cmds.scrollLayout(childResizable=True)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        cmds.text(label='Base Skinning fuer Kleider (M1)', font='boldLabelFont', height=24)
        cmds.text(label='Kleid in der Pose riggen, in der es zum Body passt (z. B. A-Pose).\n'
                        'Das Tool bewegt das Rig nicht und erzeugt nur neue Kopien.', align='left')
        self.c['body'] = cmds.textFieldButtonGrp(label='Body', buttonLabel='Body laden', editable=False,
                                                 columnWidth3=(80, 330, 110),
                                                 buttonCommand=lambda *_: self._safe(self._load_body))
        self.c['body_info'] = cmds.text(label='Geskinnten Body auswaehlen und laden.', align='left')
        self.c['base'] = cmds.textFieldButtonGrp(label='Basis', buttonLabel='Basis laden', editable=False,
                                                 columnWidth3=(80, 330, 110),
                                                 buttonCommand=lambda *_: self._safe(self._load_base))
        cmds.text(label='Basis = Kleid ohne Dicke (innere Teile). Wird nicht veraendert.', align='left')
        cmds.text(label='Kleidteile (werden als Kopien gerigged):', align='left')
        self.c['parts'] = cmds.textScrollList(numberOfRows=6, allowMultiSelection=True)
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1)
        cmds.button(label='Auswahl hinzufuegen', command=lambda *_: self._safe(self._add_parts))
        cmds.button(label='Liste leeren', command=lambda *_: cmds.textScrollList(self.c['parts'], edit=True, removeAll=True))
        cmds.setParent('..')
        self.c['profile'] = cmds.optionMenu(label='Kleidungsprofil', changeCommand=lambda *_: self._apply_profile())
        for name in pipeline.PROFILES:
            cmds.menuItem(label=name)
        cmds.frameLayout(label='Erweitert', collapsable=True, collapse=True, marginWidth=6)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        for key, label, low, high in SLIDERS:
            self.c[key] = cmds.floatSliderGrp(label=label, field=True, minValue=low, maxValue=high,
                                              value=pipeline.DEFAULTS[key], precision=2,
                                              columnWidth3=(150, 55, 260))
        self.c['start_offset'] = cmds.floatFieldGrp(label='Rockbeginn ueber Becken (cm)', value1=0.0,
                                                    precision=2, columnWidth2=(200, 80))
        self.c['transition'] = cmds.floatFieldGrp(label='Uebergang (cm)', value1=0.0, precision=2,
                                                  columnWidth2=(200, 80))
        self.c['layer_distance'] = cmds.floatFieldGrp(label='Lagen zusammenhalten bis (cm, 0 = aus)',
                                                      value1=0.0, precision=2, columnWidth2=(200, 80))
        self.c['leg_contact'] = cmds.floatFieldGrp(label='Am Bein anliegend bis (cm, 0 = aus)', value1=0.0,
                                                   precision=2, columnWidth2=(200, 80))
        self.c['widen'] = cmds.floatFieldGrp(label='Rock aufweiten (cm, 0 = aus)', value1=0.0,
                                             precision=2, columnWidth2=(200, 80))
        cmds.text(label='Streifen gerade halten (z. B. hintere Mittelbahn): Vertices/Faces am KLEIDTEIL '
                        'waehlen, alle Lagen.', align='left')
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1)
        cmds.button(label='Streifen aus Auswahl merken', command=lambda *_: self._safe(self._store_strip))
        cmds.button(label='Streifen leeren', command=lambda *_: self._safe(self._clear_strip))
        cmds.setParent('..')
        self.c['strip_info'] = cmds.text(label='Kein Streifen gemerkt.', align='left')
        self.c['auto_strips'] = cmds.checkBox(label='Schlitz-Streifen automatisch erkennen (gerade halten)',
                                              value=True)
        self.c['strip_mode'] = cmds.optionMenu(label='Streifen folgt')
        cmds.menuItem(label='als Ganzes (Mittelwert, z. B. Schlitzkante)')
        cmds.menuItem(label='dem Becken (ganz ruhig, z. B. hintere Mitte)')
        cmds.menuItem(label='dem Bein (dreht gerade mit dem Oberschenkel)')
        cmds.optionMenu(self.c['strip_mode'], edit=True, select=3)
        self.c['strip_leg'] = cmds.floatSliderGrp(label='Streifen: Anteil Bein', field=True, minValue=0.0,
                                                  maxValue=1.0, value=0.8, precision=2,
                                                  columnWidth3=(150, 55, 260))
        self.c['strip_hold'] = cmds.floatSliderGrp(label='Streifen gerade (Staerke)', field=True, minValue=0.0,
                                                   maxValue=1.0, value=1.0, precision=2,
                                                   columnWidth3=(150, 55, 260))
        self.c['strip_rings'] = cmds.intSliderGrp(label='Streifen Uebergang (Ringe)', field=True, minValue=0,
                                                  maxValue=10, value=3, columnWidth3=(150, 55, 260))
        self.c['widen_back'] = cmds.floatFieldGrp(label='Extra hinten Mitte (cm)', value1=0.0,
                                                  precision=2, columnWidth2=(200, 80))
        self.c['smooth_passes'] = cmds.intSliderGrp(label='Glaetten (Durchlaeufe)', field=True, minValue=0,
                                                    maxValue=10, value=pipeline.DEFAULTS['smooth_passes'],
                                                    columnWidth3=(150, 55, 260))
        self.c['upper_smooth'] = cmds.intSliderGrp(label='Oberteil glaetten (Durchlaeufe)', field=True, minValue=0,
                                                   maxValue=10, value=0, columnWidth3=(150, 55, 260))
        self.c['sweep_sit'] = cmds.checkBox(label='Sitzen beruecksichtigen (Oberschenkel)', value=True)
        self.c['sweep_side'] = cmds.checkBox(label='Bein seitlich beruecksichtigen (Schlitz, 40 Grad)', value=False)
        self.c['keep_all'] = cmds.checkBox(label='Alle Body-Influences in den Skin uebernehmen', value=False)
        self.c['hide'] = cmds.checkBox(label='Original nach Erfolg ausblenden', value=False)
        cmds.setParent('..')
        cmds.setParent('..')
        cmds.button(label='Kleid analysieren (Schlitz / Streifen anzeigen)',
                    command=lambda *_: self._safe(self._analyze))
        cmds.button(label='BASE RIG ERSTELLEN', height=40, backgroundColor=(0.22, 0.43, 0.36),
                    command=lambda *_: self._safe(self._run))
        cmds.text(label='Bericht:', align='left')
        self.c['report'] = cmds.scrollField(editable=False, wordWrap=False, height=260,
                                            font='fixedWidthFont', text='Body, Basis und Kleidteile laden.')
        cmds.showWindow(WINDOW)
        self._apply_profile()

    def _say(self, text):
        self.cmds.scrollField(self.c['report'], edit=True, text=text)

    def _safe(self, function):
        try:
            function()
        except RigError as error:
            self._say('FEHLER:\n%s' % error)
            self.cmds.warning('mcd. Dress Rig: %s' % str(error).splitlines()[0])
        except Exception as error:
            traceback.print_exc()
            self._say('UNERWARTETER FEHLER (Details im Script Editor):\n%s' % error)
            self.cmds.warning('mcd. Dress Rig: %s' % error)

    # ------------------------------------------------------------- inputs
    def _selected_mesh(self):
        picked = self.cmds.ls(selection=True, long=True, objectsOnly=True) or []
        if len(picked) != 1:
            raise RigError('Bitte genau ein Mesh auswaehlen.')
        return scene.mesh_nodes(picked[0])[0]

    def _load_body(self):
        transform = self._selected_mesh()
        body, info = pipeline.body_setup(transform)
        self.cmds.textFieldButtonGrp(self.c['body'], edit=True, text=transform)
        if info['problems']:
            self.cmds.text(self.c['body_info'], edit=True, label='Problem: ' + '; '.join(info['problems']))
            raise RigError('\n'.join(info['problems']))
        frame = info['frame']
        self.cmds.floatFieldGrp(self.c['start_offset'], edit=True, value1=round(0.15 * frame['leg_length'], 2))
        self.cmds.floatFieldGrp(self.c['transition'], edit=True, value1=round(0.35 * frame['leg_length'], 2))
        self.cmds.floatFieldGrp(self.c['layer_distance'], edit=True, value1=round(0.08 * frame['leg_length'], 2))
        self.cmds.floatFieldGrp(self.c['leg_contact'], edit=True, value1=round(0.06 * frame['leg_length'], 2))
        cv = 'alle Collision Volumes gefunden' if not info['missing_cv'] else \
            'ohne CV: ' + ', '.join(info['missing_cv'])
        self.cmds.text(self.c['body_info'], edit=True,
                       label='%s, %d Influences, Beinlaenge %.1f; %s' % (body.skin, len(body.influences),
                                                                        frame['leg_length'], cv))
        # Profiles with a fixed leg distance etc. win over the skeleton-derived values.
        self._apply_profile()
        self._say('Body geladen. Rockbeginn und Uebergang wurden aus dem Skeleton gesetzt.')

    def _load_base(self):
        transform = self._selected_mesh()
        self.cmds.textFieldButtonGrp(self.c['base'], edit=True, text=transform)

    def _analyze(self):
        cmds = self.cmds
        body = cmds.textFieldButtonGrp(self.c['body'], query=True, text=True)
        base = cmds.textFieldButtonGrp(self.c['base'], query=True, text=True)
        if not body or not base:
            raise RigError('Erst Body und Basis laden.')
        text, mesh, strips = pipeline.analyze(body, base, self._params())
        ids = sorted(set(v for strip in strips for v in strip['vertices']))
        if ids:
            cmds.select(['%s.vtx[%d]' % (mesh.shape, v) for v in ids], replace=True)
            text += '\n\nDie erkannten Streifen sind an der Basis ausgewaehlt.'
        self._say(text)

    def _store_strip(self):
        cmds = self.cmds
        picked = cmds.ls(selection=True, long=True) or []
        verts = cmds.ls(cmds.polyListComponentConversion(picked, toVertex=True) or [], flatten=True, long=True)
        if not verts:
            raise RigError('Bitte Vertices oder Faces des Streifens am Kleidteil auswaehlen.')
        found = {}
        for item in verts:
            node, _, index = item.partition('.vtx[')
            transform = scene.mesh_nodes(node)[0]
            found.setdefault(transform, set()).add(int(index.rstrip(']')))
        parts = cmds.textScrollList(self.c['parts'], query=True, allItems=True) or []
        unknown = [scene.short(t) for t in found if t not in parts]
        if unknown:
            raise RigError('Streifen liegt nicht auf einem Kleidteil der Liste: %s. Erst das Kleidteil '
                           'hinzufuegen, dann den Streifen dort auswaehlen.' % ', '.join(unknown))
        for transform, ids in found.items():
            self.strip.setdefault(transform, []).append(ids)
        self._show_strip()

    def _clear_strip(self):
        self.strip = {}
        self._show_strip()

    def _show_strip(self):
        text = ', '.join('%s: %d Streifen (%s Vertices)' % (scene.short(t), len(groups),
                                                            ' + '.join(str(len(g)) for g in groups))
                         for t, groups in self.strip.items())
        self.cmds.text(self.c['strip_info'], edit=True, label='Streifen: ' + text if text else 'Kein Streifen gemerkt.')

    def _add_parts(self):
        picked = self.cmds.ls(selection=True, long=True, objectsOnly=True) or []
        if not picked:
            raise RigError('Kleidteile auswaehlen.')
        current = self.cmds.textScrollList(self.c['parts'], query=True, allItems=True) or []
        for node in picked:
            transform, shape = scene.mesh_nodes(node)
            if scene.has_skin(shape):
                raise RigError('%s ist schon geriggt. Bitte das ungeriggte ORIGINAL hinzufuegen.'
                               % scene.short(transform))
            if transform not in current:
                self.cmds.textScrollList(self.c['parts'], edit=True, append=transform)
                current.append(transform)

    def _apply_profile(self):
        name = self.cmds.optionMenu(self.c['profile'], query=True, value=True)
        values = pipeline.PROFILES[name]
        for key, _, _, _ in SLIDERS:
            if key in values:
                self.cmds.floatSliderGrp(self.c[key], edit=True, value=values[key])
            self.cmds.floatSliderGrp(self.c[key], edit=True, enable=values.get('skirt', True))
        for key in ('leg_contact', 'layer_distance', 'widen', 'widen_back'):
            if key in values:
                self.cmds.floatFieldGrp(self.c[key], edit=True, value1=values[key])
        for key in ('smooth_passes', 'upper_smooth'):
            if key in values:
                self.cmds.intSliderGrp(self.c[key], edit=True, value=values[key])
        for key in ('sweep_sit', 'sweep_side'):
            if key in values:
                self.cmds.checkBox(self.c[key], edit=True, value=values[key])

    def _params(self):
        cmds = self.cmds
        name = cmds.optionMenu(self.c['profile'], query=True, value=True)
        params = {'skirt': pipeline.PROFILES[name].get('skirt', True)}
        for key, _, _, _ in SLIDERS:
            params[key] = cmds.floatSliderGrp(self.c[key], query=True, value=True)
        params['start_offset'] = cmds.floatFieldGrp(self.c['start_offset'], query=True, value1=True)
        params['transition'] = cmds.floatFieldGrp(self.c['transition'], query=True, value1=True)
        params['layer_distance'] = cmds.floatFieldGrp(self.c['layer_distance'], query=True, value1=True)
        params['leg_contact'] = cmds.floatFieldGrp(self.c['leg_contact'], query=True, value1=True)
        params['strip'] = {t: [sorted(g) for g in groups] for t, groups in self.strip.items()}
        params['strip_hold'] = cmds.floatSliderGrp(self.c['strip_hold'], query=True, value=True)
        params['strip_mode'] = {2: 'pelvis', 3: 'leg'}.get(
            cmds.optionMenu(self.c['strip_mode'], query=True, select=True), 'average')
        params['strip_leg'] = cmds.floatSliderGrp(self.c['strip_leg'], query=True, value=True)
        params['auto_strips'] = cmds.checkBox(self.c['auto_strips'], query=True, value=True)
        params['strip_rings'] = cmds.intSliderGrp(self.c['strip_rings'], query=True, value=True)
        params['upper_smooth'] = cmds.intSliderGrp(self.c['upper_smooth'], query=True, value=True)
        params['widen'] = cmds.floatFieldGrp(self.c['widen'], query=True, value1=True)
        params['widen_back'] = cmds.floatFieldGrp(self.c['widen_back'], query=True, value1=True)
        params['smooth_passes'] = cmds.intSliderGrp(self.c['smooth_passes'], query=True, value=True)
        params['keep_all_influences'] = cmds.checkBox(self.c['keep_all'], query=True, value=True)
        params['sweep_sit'] = cmds.checkBox(self.c['sweep_sit'], query=True, value=True)
        params['sweep_side'] = cmds.checkBox(self.c['sweep_side'], query=True, value=True)
        params['hide_original'] = cmds.checkBox(self.c['hide'], query=True, value=True)
        return params

    def _run(self):
        cmds = self.cmds
        body = cmds.textFieldButtonGrp(self.c['body'], query=True, text=True)
        base = cmds.textFieldButtonGrp(self.c['base'], query=True, text=True)
        parts = cmds.textScrollList(self.c['parts'], query=True, allItems=True) or []
        missing = [label for label, value in (('Body', body), ('Basis', base), ('Kleidteile', parts)) if not value]
        if missing:
            raise RigError('Es fehlt: %s.' % ', '.join(missing))
        if not cmds.undoInfo(query=True, state=True):
            raise RigError('Maya-Undo ist ausgeschaltet. Bitte einschalten (Sicherheitsnetz).')
        cmds.progressWindow(title='mcd. Dress Rig', progress=0, maxValue=100, status='Start', isInterruptable=True)

        def progress(text, value):
            if cmds.progressWindow(query=True, isCancelled=True):
                raise RigError('Abgebrochen. Bereits erzeugte Kopien wurden entfernt.')
            cmds.progressWindow(edit=True, progress=value, status=text)
        try:
            report, outputs = pipeline.run(body, base, parts, self._params(), progress)
        finally:
            cmds.progressWindow(endProgress=True)
        text = report.text()
        print(text)
        self._say(text)
        if outputs:
            cmds.select(outputs, replace=True)
