# Übergabe – alles Wichtige auf einen Blick (Stand 11.10.2026)

**Für eine neue Session:** Lies diese Datei zuerst, sie reicht als Einstieg. Details stehen in `README.md` und in `docs/`.

## 1. Wer, was, Regeln

- **Kreatorin** von SL-Mesh-Kleidung. Arbeitet mit Maya 2024 (Python 3, numpy vorhanden, kein scipy).
  Kommunikation: **Deutsch**, einfach, Schritt für Schritt, möglichst Ein-Klick-Werkzeuge.
- **Repo `soberika/mayatool` ist öffentlich.** Nie committen:
  - Body- oder Devkit-Geometrie
  - Exporte und Ergebnisse (`*.json.gz`)
  - Bilder des Bodys
  - SL-Animationen, solange ihre Lizenz ungeklärt ist

  `.gitignore` deckt das meiste ab. Vor jedem Commit `git status` prüfen.
- **Keine PR ohne ausdrückliche Bitte.** Nur auf den Branch der Session pushen.
- **Daten** liegen privat bei der Kreatorin (OneDrive-Ordner `mcd_mayatool_daten`) und werden bei Bedarf hochgeladen.
- Commit `78024d1` enthält noch Vorschaubilder in der Historie. Bereinigen nur mit Zustimmung.

## 2. Was erreicht ist (in SL bestätigt)

| Ergebnis | Body | Datei | Status |
|---|---|---|---|
| Thin-Kleid **v4 mild** (sehr glatt) | Legacy Female | `mcd_kleid_v4_mild_sehr_glatt.json.gz` | **Favorit**, „perfekt“ |
| Thin-Kleid Deform Legacy → Reborn | eBody Reborn | `mcd_kleid_reborn_deform.json.gz` (genau), `_weich` | beide „geil“ |
| Thin-Kleid **v4 mild** auf Reborn | eBody Reborn | `mcd_kleid_reborn_v4_mild_sehr_glatt.json.gz` | „PERFEKT“ |

**Kernrezept:** Die Gewichte aus **Dress Auto Rig 0.5.3** bleiben **unverändert**. Nur die **Ruheform** wird angepasst:
- Saum hinten und vorn ausstellen
- weiche A-Linie
- gerade Rückenlinie
- über alle Mesh-Teile glätten

Code dafür: `README.md`, Abschnitt 3. Für v4 mild gilt der hintere Flare mit `above_knee=35`, `limit=9`, der vordere mit `limit=5`. Danach `harmonize_offsets(…, 2.0, 20)`. Die Fassung „sehr glatt“ hängt noch `harmonize_offsets(…, 4.0, 100)` an.
Werkstatt-Skripte mit den genauen Aufrufen: `werkstatt/` (`v4.py`, `smooth.py`, `reborn_v4.py`, `deform*.py`).

| Messung (Test-Gänge, sichtbarer Stoff) | Wade | Oberschenkel |
|---|---|---|
| Legacy 0.5.3 → v4 mild | 4904 → 2922 | 7271 → 4621 |
| Reborn ohne → v4 mild sehr glatt | 5581 → 3637 | 7530 → 3455 |

## 3. Werkzeuge (alle im Repo)

| Datei | Was | Wo läuft es |
|---|---|---|
| `mcd_fit_export.py` | Body + Kleid exportieren (`.json.gz`) | Maya, in den Viewport ziehen |
| `mcd_fit_apply.py` (0.2) | Ergebnis anwenden → Kopie `…_fit` | Maya |
| `mcd_fit_solver.py` | Posen, Gangzyklen, Clipping, Formwerkzeuge | außerhalb Maya (numpy + scipy) |
| `mcd_fit_deform.py` | Kleid von Body A auf Body B übertragen | außerhalb Maya |
| `mcd_fit_data.py` | Export lesen und prüfen | außerhalb Maya |
| `mcd_sl_anim.py` | `.anim` schreiben und lesen | beides |
| `lsl/mcd_cloth_state.lsl` | Zustandsskript (für Kleider derzeit nicht nötig) | SL |
| `mcd_dress_auto_rig (3).py` | Auto Rig **0.4** (alt). **0.5.3 ist nicht im Repo** und liegt bei der Kreatorin. | Maya |
| `tests/` | `python -m unittest discover tests` (39 Tests) | |

**Ablauf für ein Kleid:**
1. In Maya mit 0.5.3 riggen.
2. `mcd_fit_export` (Body + `_autoRig`-Kopie auswählen).
3. Export hochladen; Claude rechnet das Rezept.
4. `mcd_fit_apply` → `…_fit` → DAE → SL.

**Body wechseln:**
1. Zweiter Export mit dem Ziel-Body und demselben Kleid.
2. `python mcd_fit_deform.py quelle.json.gz ziel.json.gz out.json.gz [--soft]`
3. In der Ziel-Szene anwenden.
4. Mit 0.5.3 neu riggen und neu exportieren.
5. Rezept gegen den neuen Body rechnen.

**Maya-Fallen:**
- Maya cacht Module. Bei neuer Version Maya neu starten oder die Datei umbenennen.
- Beim Auto Rig ist das Feld „Becken“ leer, weil `mPelvis` und `PELVIS` beide passen. Dann `mPelvis` von Hand wählen.

## 4. Regeln aus der Erfahrung (nicht wiederholen)

1. **Keine Gewichtsoptimierung pro Vertex.** In SL reißt das Mesh: Beim Kappen auf 4 fallen Einflüsse weg, und die
   Collision Volumes sind skaliert. Das galt für Stufe 1 und Stufe 2.
2. **Stoff-Bones (HindLimb, an mPelvis) helfen der Wade nicht.** `pelvis_carry` bringt nichts.
3. **Formänderung ist robust.** Dehnung bis p99 ≈ 40 % fällt in SL nicht auf.
4. **Immer über Mesh-Teile glätten** (`harmonize_offsets`), sonst franst der Schlitz aus.
   Die Offset-Richtung kommt von den Body-Normalen.
5. **Laufsteg-AO** kreuzt die Schritte. Darauf trainieren mit `gait_pose(phase, stride≤1.5, cross≤14)`.
6. **Brust-Anpassung (v5) und mehr Raum vorn** wurden verworfen, weil das Bein vorn sichtbar dicker wurde.
7. **Messen:**
   - Clipping: signed distance < −2 mm, nur sichtbarer Stoff. Futter erkennt man in `shell_labels` am Label 2.
   - Wade und Oberschenkel getrennt auswerten.
   - Training- und Testposen getrennt halten.
   - Risse: Kanten, die mehr als 3–5 mm länger werden.
8. **Deform:**
   - Feld auf dem Quell-Body, nur wo der Ziel-Body vorhanden ist; Kopf und Füße fehlen in Devkits.
   - Glättung nicht zu stark (15 Iterationen bei Radius 2,5 cm), sonst verliert der Po die Form.
   - „genau“ schiebt danach bis auf den Originalabstand nach.

**SL-Grenzen** (Viewer-Quellcode):
- 133 Bones und 26 Collision Volumes
- höchstens 110 Joints pro Mesh, höchstens 4 Gewichte pro Vertex
- `.anim`: höchstens 60 s und 250 KB
- BVH-Positionen gelten nur für das Becken
- Avatar-Physik wirkt auf PEC, BELLY und BUTT

## 5. Devkit-Fakten (aus den Exporten)

| | Legacy Female 2.5.3 | eBody Reborn 2.44 (A-Pose, Mayastar) |
|---|---|---|
| Up-Achse der Szene | Y-Werte (meta sagt z) | **Z** |
| Body-Mesh | `Mesh_Legacy_f_Pinup_Pushup`, 41536 V | `A_Pose_` (in `eBody_Parts_A_Pose`), 33033 V |
| Skelett | gleiche SL-Proportionen; Becken auf 106,7 cm Höhe | identisch, nur die Achsen sind getauscht |
| Joints im Export | 160 | 88 |
| Body-Unterschied | – | hinten an Taille und Po bis zu ca. 7 cm voller |

## 6. Plan: MCD Creator (Maya-Suite)

Die Kreatorin hat eine Spezifikation für ein Komplettwerkzeug geschrieben:

> DEV KIT → **MCD RIG PREP** → MCD-READY DEV KIT → MD Prep, Garment Import, Rigging, Body-Deformation, Posen- und
> Animationstest, Clipping-Analyse, Optimierung, Validator, SL-Export.
> Das Referenz-Rig bleibt unberührt; gearbeitet wird am **MCD Working Rig**. Bones werden nie blind gelöscht.
> Devkit-Profile kommen als JSON (`profiles/legacy_female.json` …). Der MD-Maßstab wird berechnet, nicht angenommen.
> **Jedes Modul wird einzeln gebaut und getestet.** Die nächste Phase beginnt erst nach ihrem OK.

| Phase | Inhalt | Stand / Bezug |
|---|---|---|
| **1** | **Rig Inspector**, nur lesend: Maya-Version, Einheiten, Joint-Wurzeln, Hierarchie, Joint-Zahl, skinClusters, Meshes, Einflüsse (genutzt oder leer), bindPose/dagPose, Body-Meshes, Joints mit und ohne Einfluss auf den Body, Auffälligkeiten | **nächster Schritt**, Plan unten |
| 2 | Rig Prep: Working Rig und Working Body | |
| 3 | Bindepose prüfen und reparieren | |
| 4–5 | MD Prep, MD-Export, Kleid zurück | |
| 6 | Garment-Analyse | Mesh-Teile und Futter-Erkennung vorhanden |
| 7 | Erst-Rig | Auto Rig 0.4/0.5.3 |
| 8 | SL-Posen-Bibliothek | **SL-Standardposen (BVH) aus dem SL-Wiki**, von der Kreatorin bereitgestellt; dazu Gang/Laufsteg/Sitzen aus dem Solver |
| 9 | Clipping-Analyse | im Solver fertig, muss nach Maya |
| 10 | Body-Verformungs-Rigging | Rezept „Form statt Gewichte“ |
| 11 | Animationstest | `.anim`-Leser vorhanden, BVH-Leser fehlt |
| 12 | Optimierung Training/Validierung | Prinzip erprobt; Regel 1 beachten |
| 13 | Validator | |
| 14 | SL-Export | |
| 15 | ein Fenster für alles | |
| + | Body-Deform | `mcd_fit_deform.py`, bestätigt |

**Phase 1 – vereinbarter Plan:**
- **Datei:** `mcd_creator/mcd_rig_inspector.py`. Per Drag-and-drop in Maya; der Bericht erscheint im Fenster und im Script Editor.
- **Speichern:** Knopf „Save Report“ legt `.txt` und `.json` ab. Die `.json` lädt die Kreatorin hoch.
- **Nur lesen:** keine Nodes anlegen, keine Auswahl ändern, keine Pose oder Zeit ändern.
- **Inhalt:** die 13 Punkte der Spezifikation. Joints gruppiert in SL-Grundskelett (26), Collision Volumes (26),
  Bento-Gruppen und Joints außerhalb von SL.
- **Body-Erkennung:** über die Höhe im Vergleich zum Skelett und die Einflüsse auf Becken, Beine und Rumpf, nicht über den Namen.
- **Warnungen:**
  - mehrere Skelette oder doppelte Namen
  - fehlende Grundbones
  - Einflüsse, die keine Joints sind
  - `bindPreMatrix` passt nicht zur aktuellen Pose (Collision Volumes und Bones getrennt gezählt)
  - mehrere oder fehlende Bindeposen
  - Keyframes oder Constraints am Skelett, mit aktuellem Frame
  - Gruppen über der Wurzel, die verschoben, gedreht oder skaliert sind
  - Vertices mit mehr als 4 Einflüssen
  - blendShapes vor dem Skin
  - referenzierte Nodes
- **Sprache:** Bericht auf Englisch. Die Auswertung bleibt getrennt von Maya und wird mit Tests geprüft.
- **Test:** Die Kreatorin lässt den Inspector auf Legacy **und** Reborn laufen und schickt beide `.json`. Daraus entstehen Rig Prep und die Profile.

## 7. Dateien für den Neustart

Paket `mcd_paket_uebergabe.zip`. Die Kreatorin legt es in OneDrive ab.
- `1_maya_tools/`: Export, Apply, Auto Rig 0.4
- `2_ergebnisse/`: alle Kleid-Ergebnisse für Legacy und Reborn
- `3_exporte/` (**privat**):
  - `export_legacy_thin.json.gz`
  - `export_reborn_thin_0.4rig.json.gz` (Deform-Quelle)
  - `export_reborn_thin_rig.json.gz` (Kleid genau, neu geriggt)
- `4_second_life/`: das LSL-Skript

**In einer neuen Session hochladen, je nach Aufgabe:**
- Phase 1: nichts, nur später die Inspector-Berichte
- Neuberechnung: den passenden Export
