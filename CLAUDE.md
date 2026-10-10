# CLAUDE.md – Kontext für neue Sessions

Lies zuerst `README.md` (Stand, Ablauf, v3-Rezept, nächster Schritt) und bei Bedarf `docs/gehen_ausstellen.md`.

## Wer und was

- Die Kreatorin baut Mesh-Kleidung für **Second Life** in **Maya** und benutzt **Dress Auto Rig 0.5.3**.
  0.5.3 ist nicht im Repo; die Datei `mcd_dress_auto_rig (3).py` ist die alte Version 0.4.
- Ziel: Ein enges, geschlitztes Kleid (Testobjekt: **Thin-Version**) soll beim **Gehen** nicht clippen und dabei
  nicht verzerrt aussehen. **Sitzen ist egal.**
- **Erreicht:** „Laufsteg v3“, von der Kreatorin in SL als perfekt bestätigt. Die 0.5.3-Gewichte bleiben unverändert,
  nur die Ruheform wird angepasst.
- **Nächstes Thema:** Einen eigenen Frauen-Gang (BVH/`.anim`) in SL hochladen und das Kleid auf genau diesen Gang
  trainieren. Siehe README, Abschnitt 6.

## Kommunikation

- **Deutsch**, einfach und Schritt für Schritt („für Dummies“): Klick für Klick sagen, was in Maya bzw. SL zu tun ist.
- So einfach wie möglich, am besten **ein Klick** in Maya.
- Ergebnisse ehrlich mit Zahlen berichten und nichts versprechen, was SL nicht kann.
- Die Kreatorin schickt Screenshots und Videos aus Maya und SL. Fehlermeldungen in Dialogen sollen sie zum Abschicken
  auffordern („Bitte diese Meldung schicken“).
- Die Kreatorin hat bisher entschieden:
  - **Kein eigener Walk als Ersatz für die AO.** Konzept K3 wurde abgelehnt.
  - Ausnahme: Den neuen Frauen-Gang will sie jetzt selbst und trägt ihn im AO als Walk ein.
  - **Dehnung und Formänderung sind erlaubt**, solange es wie das Original bzw. die Design-Referenz aussieht.

## Harte Regeln

- **Das Repo ist öffentlich.** Nie committen:
  - Body- oder Devkit-Geometrie
  - Exporte und Ergebnisse (`*.json.gz`)
  - Bilder oder Punktwolken des Bodys

  `.gitignore` deckt die meisten Fälle ab. Vor jedem Commit `git status` prüfen.
- **Keine Pull Requests**, außer die Kreatorin bittet ausdrücklich darum. Nur auf den Branch der aktuellen Session pushen.
- Commit `78024d1` hat noch Vorschaubilder in der Historie. Umschreiben nur mit ihrer Zustimmung.

## Technik, die man wissen muss

- **Maya-Szene:**
  - Einheit cm, **Y oben**, vorn **+Z**, links **+X**.
  - Der Bind ist in SL-Metern mit Z oben, das wird über die `geomMatrix` und die `bindPreMatrix` gelöst.
  - Neutrale Pose: Beine 5°, Arme 25°.
- **Skinning-Formel** (Zeilenvektoren): p = Σ w_j · (p_orig · geomMatrix · bindPreMatrix_j · worldMatrix_j).
- **Body:** Legacy, Gewichte nachträglich normalisiert. Den Orig-Zustand rekonstruiert `mcd_fit_solver._recover_orig`.
- **Export:** Den Body mit dem **kompletten SL-Skelett** laden, auch die Nicht-Menschen-Bones. Arbeitsdatei bisher:
  `export2.json.gz`. Die Kreatorin lädt sie hoch; sie liegt nicht im Repo.
- **Maya cacht Module:** Bei einer neuen Version von `mcd_fit_apply.py` zum Verschicken einen neuen Dateinamen wählen
  (z. B. `_v2`, liegt in `.gitignore`) und die Version im Fenstertitel erhöhen.
- **SL-Grenzen** (aus dem Viewer-Quellcode; das SL-Wiki ist aus der Sandbox gesperrt):
  - 133 Bones und 26 Collision Volumes
  - höchstens 110 Joints pro Mesh, höchstens 4 Gewichte pro Vertex
  - `.anim`: höchstens 60 s und 250 KB, Positionen auf ±5 m geklemmt, Priorität pro Joint
  - BVH-Positionen gelten nur für das Becken
  - Tail-, HindLimb- und Groin-Bones hängen an mPelvis

## Was funktioniert / was nicht (nicht wiederholen)

- ✔ **Ruheform-Offsets bei festen 0.5.3-Gewichten**:
  - `local_flare` hinten und vorn
  - `column_hem`
  - `fill_back_line`
  - zum Schluss **immer** `harmonize_offsets`, weil getrennte Mesh-Teile sonst den Schlitz ausfransen
- ✔ Offset-Richtung = **Body-Normalen**, Offsets akkumulieren.
- ✘ **Gewichte pro Vertex optimieren:** in SL reißt das Mesh. Ursachen: Beim Kappen auf 4 Gewichte fallen Einflüsse
  weg, und die Collision Volumes sind skaliert. Betrifft Stufe 1 und Stufe 2.
- ✘ **Stoff-Bones** (HindLimb, an mPelvis): helfen der Wade nicht. Siehe `docs/stufe2_ergebnis.md`.
  `pelvis_carry` hat ebenfalls keinen Nutzen.
- **Laufsteg-AO** kreuzt die Schritte. Deshalb mit `gait_pose(phase, stride, cross)` trainieren:
  stride bis 1.5, cross bis 14.
- **Messen:**
  - Clipping: signed distance < −2 mm
  - Wade und Oberschenkel getrennt auswerten
  - Risse: Kanten, die 3–5 mm länger als bei 0.5.3 werden
  - Dehnung: p99
  - Trainings- und Testposen getrennt halten

## Arbeitsweise

- Tests: `python -m unittest discover tests`. Alle müssen grün sein, bevor gepusht wird.
- Rechnen findet außerhalb von Maya statt (numpy). Maya-Code ist API 2.0 und Python 3. Ohne Maya ist er nicht
  testbar, also sorgfältig lesen.
- Ergebnisdateien heißen `mcd_kleid_<variante>.json.gz` und werden der Kreatorin geschickt, nicht committet.
- Neue Erkenntnisse kommen in `docs/` (deutsch). README und diese Datei aktuell halten.
