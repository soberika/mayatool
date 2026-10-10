# mcd. Maya-Tools für Second-Life-Kleidung

Werkzeuge, mit denen ein enges, geschlitztes Mesh-Kleid (Testobjekt: **Thin-Version**) in Second Life
beim **Gehen** kaum noch clippt, ohne dass es verzerrt aussieht. Sitzen ist bewusst zweitrangig.

> **Stand Oktober 2026: Laufsteg v3 ist das bestätigte Ergebnis** („v3 war perfekt“ – SL-Test mit Laufsteg-AO).
> Diese README ist die Übergabe, damit in einem neuen Branch weitergearbeitet werden kann.

---

## 1. Kurzfassung: Was funktioniert

**Rezept:** Die Gewichte aus Dress Auto Rig **0.5.3** bleiben **unverändert**. Nur die **Ruheform** des Kleides wird
leicht verändert: hinten und vorn am Saum etwas ausgestellt, eine weiche A-Linie, eine gerade Rückenlinie, und das
Ganze über die getrennten Mesh-Teile geglättet. Das ist v3.

| Messung auf Test-Gängen (Laufsteg, gekreuzt, große Schritte) | 0.5.3 | v3 |
|---|---|---|
| Wade (Unterschenkel-Clipping, Punkte) | 7325 | **4991** |
| Oberschenkel | 12574 | **8825** |
| sichtbares Clipping gesamt | 12175 | **7992 (−34 %)** |

In SL fällt die Dehnung nicht auf. Die Form entspricht weiter dem Original bzw. der Design-Referenz.

### Ablauf (für ein Kleid)

1. **Riggen** in Maya mit Dress Auto Rig **0.5.3** (wie gewohnt). Es entsteht die Kopie `..._autoRig`.
   Body mit **komplettem SL-Skelett** laden, auch die Nicht-Menschen-Bones.
2. **Export:** `mcd_fit_export.py` in den Viewport ziehen. Body und Kleid auswählen, einmal klicken.
   Es entsteht eine `.json.gz`. Der Export findet die `_autoRig`-Kopie selbst. Höheres Mesh = Body; falls
   vertauscht, auf „Tauschen“ klicken.
3. **Solver** (außerhalb von Maya, bisher mit Claude im Chat): Export hochladen → Ergebnisdatei
   `mcd_kleid_<name>.json.gz` kommt zurück. Rezept siehe Abschnitt 3.
4. **Anwenden:** `mcd_fit_apply.py` in den Viewport ziehen (Fenstertitel muss die aktuelle Version zeigen).
   Die `_autoRig`-Kopie auswählen → **ERGEBNIS LADEN** → Datei wählen. Es entsteht `..._fit`, das Original
   bleibt unverändert.
5. `..._fit` wie gewohnt als DAE exportieren und in SL hochladen.

> **Maya-Cache-Falle:** Maya merkt sich ein einmal geladenes Modul. Wird eine neue Version der Datei gezogen,
> läuft eventuell noch die alte. Abhilfe: Datei umbenennen (z. B. `mcd_fit_apply_v2.py`) oder Maya neu starten.
> Die Versionsnummer steht im Fenstertitel.

---

## 2. Dateien

| Datei | Zweck | Stand |
|---|---|---|
| `mcd_fit_export.py` | Ein-Klick-Export Body + Kleid (Skelett, Gewichte, Bind, Ruheform) | in Maya benutzt ✔ |
| `mcd_fit_solver.py` | Kern: Skelett-FK, Posen/Gangzyklen, Clipping-Messung, Formwerkzeuge (Flare, A-Linie, Rückenlinie, Harmonisieren) | v3 damit gerechnet ✔ |
| `mcd_fit_apply.py` | legt das Ergebnis als Kopie `..._fit` an (gleicher Bind, neue Ruheform, Gewichte) | Version 0.2, in Maya benutzt ✔ |
| `mcd_fit_data.py` | liest/prüft den Export außerhalb von Maya, rechnet das Skinning nach | ✔ |
| `mcd_fit_metrics.py` | Messgerüst in Maya (Clipping, Dehnung, Silhouette, Sprünge pro Frame) | in Maya ungetestet |
| `mcd_sl_anim.py` | `.anim` schreiben/lesen (`read_anim`, `--dump`), Testanimationen, Teststäbe als DAE, Bake aus Maya | `.anim` in SL getestet ✔ |
| `lsl/mcd_cloth_state.lsl` | Zustandsskript (Stehen/Gehen/Sitzen …) für Overlay-Animationen, AO bleibt unberührt | in SL getestet ✔, für v3 **nicht nötig** |
| `mcd_cloth_layer.py` | Stufe 2: Stoff-Bones (HindLimb) am Saum | **verworfen**, nur als Referenz |
| `mcd_dress_auto_rig (3).py` | Dress Auto Rig 0.4 (alt). **Benutzt wird 0.5.3, das nicht im Repo liegt.** | |
| `testdaten/stufe0/` | Testanimationen und Teststäbe (`mcd_test_baender.dae`) | |
| `tests/` | `python -m unittest discover tests` (36 Tests, alle grün) | |

**Nicht im Repo (absichtlich, Repo ist öffentlich):** Body-/Devkit-Geometrie, Exporte (`*.json.gz`),
Ergebnisdateien, Vorschaubilder davon. Siehe `.gitignore`. Die Ergebnisdatei **`mcd_kleid_laufsteg_v3.json.gz`**
liegt nur lokal bei der Kreatorin. Für eine Neuberechnung braucht es den Export (`export2.json.gz`, mit komplettem Skelett).

### Dokumente

- `docs/konzept_kleidung_und_bewegung.md`: Konzept, SL-Grenzen, sechs Konzepte, Auswahl
- `docs/anleitung_einfach.md`: Stufe 0 Schritt für Schritt
- `docs/stufe0_testprotokoll.md`: SL-Tests mit `.anim` und Teststäben
- `docs/stufe1_ergebnis.md`: Gewichte + 6 mm gegen 0.5.3
- `docs/stufe2_ergebnis.md`: Stoff-Bones, warum es in SL riss (Post-mortem)
- `docs/gehen_ausstellen.md`: **der Weg zu v3**: Analyse Gehen, Flare, A-Linie, Harmonisieren, Laufsteg-Gänge

---

## 3. Rezept Laufsteg v3 (zum Nachrechnen)

```python
import mcd_fit_data as fd, mcd_fit_solver as fs
data = fd.load('export2.json.gz')                     # Export mit komplettem Skelett
rig, body, dress = fs.prepare(data)
base = dress.weights                                  # 0.5.3-Gewichte, unverändert
up = rig.axes['up']
hip_y, knee_y = rig.position('mHipLeft') @ up, rig.position('mKneeLeft') @ up
train = [fs.gait_pose(p, s, c)                       # Phase, Schrittweite, Kreuzen (Laufsteg)
         for s in (1.0, 1.3, 1.5) for c in (0, 8, 14) for p in range(0, 100, 10)]
off = fs.local_flare(rig, body, dress, base, train, limit=9.0, above_knee=20.0,
                     front_margin=8.0, fade=45, passes=10)[0]                     # hinten bis 9 cm
off = fs.local_flare(rig, body, dress, base, train, limit=3.5,
                     above_knee=hip_y - knee_y - 5.0, front_margin=6.0, fade=45,
                     passes=8, base_offsets=off, direction='front')[0]            # vorn bis 3,5 cm
off = fs.column_hem(rig, dress, base, 86.0, 26.5, base_offsets=off, smooth=30)  # weiche A-Linie am Saum
off = fs.fill_back_line(rig, dress, base, 95.0, base_offsets=off)               # gerade Rückenlinie
off = fs.harmonize_offsets(rig, dress, base, off, 2.0, 20)                      # Mesh-Teile glätten (Schlitz!)
fs.save_result('mcd_kleid_laufsteg_v3.json.gz', data, dress, base, off, {}, {})
```

Maße in cm (Maya-Szene: cm, Y oben, vorn +Z, links +X). 

---

## 4. Erkenntnisse – Regeln für die Weiterarbeit

1. **Gewichte nicht pro Vertex verändern.** Jede Gewichtsoptimierung (Stufe 1 und 2) ergab in SL Risse:
   Beim Kappen auf 4 Einflüsse fallen Gewichte weg, und die Collision Volumes sind skaliert. 0.5.3-Gewichte sind stabil.
2. **Form statt Gewichte.** Ruheform-Offsets bei festen Gewichten sind robust und reißen nicht.
3. **Über Mesh-Teile hinweg glätten.** Das Kleid besteht aus getrennten Teilen. Offsets pro Teil lassen den
   Schlitz ausfransen. Deshalb immer zum Schluss `harmonize_offsets` (räumlich, nicht über die Topologie).
4. **Offset-Richtung = Body-Normalen** und Offsets akkumulieren. Mit den Kleid-Normalen schwingt es.
5. **Stoff-Bones (HindLimb/Tail an mPelvis) helfen der Wade nicht.** Sie hängen am Becken, die Wade aber am
   Unterschenkel. Dazu kommen Risse, siehe `docs/stufe2_ergebnis.md`. `pelvis_carry` ebenfalls ohne Nutzen.
6. **Laufsteg-AO braucht mehr Raum** als normales Gehen, weil sich die Schritte kreuzen. Mit `cross` in `gait_pose` trainieren.
7. **Messen:** Clipping = signed distance < −2 mm (kNN-Normalen); Wade und Oberschenkel getrennt; **Risse** = Kanten,
   die 3–5 mm länger als bei 0.5.3 werden; Dehnung p99; Versatz zwischen Mesh-Teilen. Training- und Testposen trennen.

**SL-Grenzen** (aus dem Viewer-Quellcode): 133 Bones + 26 Collision Volumes; max. 110 Joints pro Mesh; max. 4 Gewichte
pro Vertex. `.anim`: max. 60 s und 250 KB, Priorität pro Joint. BVH-Positionen nur am Becken. Avatar-Physik wirkt nur auf
Brust/Bauch/Po.

---

## 5. Offene Punkte

- **Spitzen am Schlitz** stammen schon aus dem 0.5.3-Rig: Die Kanten dort werden 10–19× gedehnt. Lösung gehört eher in den Auto-Rig.
- **Oberschenkel bei gekreuzten Beinen im Stand** clippt noch etwas.
- **Synthetische Gänge** (`GAIT`-Kurve) sind nur eine Annäherung an die echte AO → siehe nächster Schritt.
- Commit `78024d1` enthält noch Vorschaubilder (Bein-Punktwolken) in der Git-Historie. Bereinigen nur mit Zustimmung
  der Kreatorin, weil dafür die Historie umgeschrieben wird.

---

## 6. Nächster Schritt: eigene Frauen-Laufanimation

**Ziel:** Einen eigenen Frauen-Gang in SL hochladen und das Kleid **genau auf diesen Gang** trainieren,
statt auf erzeugte Gänge. Dann passt die Form zu dem, was in SL tatsächlich läuft.

Plan:
1. **Gang beschaffen/erstellen:** BVH, z. B. aus Mocap, einer Bibliothek mit passender Lizenz oder selbst in Maya
   animiert am SL-Skelett. Schleife 1–2 s, Hüftbewegung nur über mPelvis (BVH-Positionen gelten nur für das Becken).
2. **Hochladen in SL:** Viewer → *Hochladen → Animation (BVH)*; Priorität, Loop und Ease-in/out einstellen.
   Firestorm kann auch `.anim` direkt hochladen. `mcd_sl_anim.py` schreibt `.anim` und prüft sie mit `validate`.
3. **Im AO als Walk eintragen.** Hinweis: Am Anfang galt „eigener Walk stört“ (Konzept K3 abgelehnt). Jetzt ist es die
   bewusste Entscheidung der Kreatorin, der eigene Gang ersetzt nur den Walk im AO.
4. **Solver auf den Gang trainieren** – das fehlt noch im Code:
   - BVH-Leser (bzw. `read_anim` für `.anim`) → pro Frame die Joint-Rotationen.
   - Umrechnung von SL-Achsen (Z oben) auf die Maya-Szene (Y oben, cm), dann in `rig.pose(...)` statt `gait_pose`.
   - Rezept aus Abschnitt 3 mit diesen Frames als `train` laufen lassen, Test mit zurückgehaltenen Frames.
5. Ergebnis wie gehabt mit `mcd_fit_apply.py` anwenden und in SL mit genau diesem Gang prüfen.

### Neuen Branch starten

```
git fetch origin claude/adoring-hawking-3n8uvx
git checkout -b <neuer-branch> origin/claude/adoring-hawking-3n8uvx
```

`CLAUDE.md` enthält den Kontext für Claude (Regeln, Technik, Entscheidungen). Für eine neue Session reicht der Hinweis: „Lies README.md, weiter mit Abschnitt 6.“ Dazu den Export
(`export2.json.gz`) und die Gang-Datei (BVH/`.anim`) hochladen.
