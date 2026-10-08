# Zwischenstand: Kleid-Rigging für das SL-Skelett

Stand 2026-10-08. Dies ist ein Forschungs-Zwischenschritt, kein fertiges Werkzeug.

## 1. Was bisher existiert: `mcd_dress_auto_rig (3).py` (v0.4)

Ein Maya-Tool (Python 3 / API 2.0) mit UI. Es erzeugt eine geskinnte Kopie des Kleides und verwendet dabei nur die vorhandenen Body-Joints.

- **Oberteil / Arme:** Die Gewichte werden mit `copySkinWeights` über den nächstgelegenen Punkt vom Body übernommen.
- **Rock:** Ein analytisches, symmetrisches Gewichtsfeld im Becken-Frame. Es bindet Becken, linken und rechten Oberschenkel und das Knie der dominanten Seite. Dazu kommen ein Übergang über die Höhe, Glättung entlang der Mesh-Kanten (keine Verschweißung über Schlitze hinweg) und eine Grenze von max. 4 Einflüssen.
- **Regler:** Beinbindung, Mitte am Becken, Knie folgen, Breite des Mittelbereichs, Glättung, max. Joints.
- **Weitere Funktionen:** eine optionale Rock-Maske und ein Rockbeginn aus der Vertex-Auswahl, die SL-Kollisionsvolumen sind als Ausnahme bei der Bindepose-Prüfung bekannt, die Gewichte werden undo-fähig geschrieben und anschließend verifiziert.
- **Grenzen:** Es gibt nur eine einzige Gewichtslösung ohne Beispielposen. Die Ruheform wird nicht verändert, und es gibt keine Kollision und keine Simulation.

## 2. Neu: Fit aus mehreren korrigierten Zielposen

Dateien:

- `dress_pose_fit.py`: der Kern. Er nutzt nur numpy und ist damit später auch in mayapy lauffähig. Er greift nicht auf Maya zu.
- `experiments/sl_dress_study.py`: die Vergleichsstudie. Ausgabe nach `experiments/results/` (`report.md`, `metrics.json`, Plots).
- `tests/test_dress_pose_fit.py`: Solver-Tests. Bekannte LBS-Gewichte und Ruheform-Verschiebungen werden wiedergefunden.

### Modell

Gegeben sind P Posen mit den Skinning-Matrizen `S_j^p` und für jede Pose eine korrigierte Form `y_i^p`. Gesucht sind **ein** Satz Gewichte `w_ij` und ein kleiner Ruheform-Offset `d_i`, sodass gilt:

```
v_i^p = Σ_j w_ij · S_j^p · (x_i + d_i)  ≈  y_i^p     für alle p
```

Dabei gelten die SL-Regeln: `w ≥ 0`, `Σw = 1`, höchstens 4 Joints pro Vertex. Gewichte und Offset sind fest, das Ergebnis ist also ein ganz normales LBS-Mesh, das SL darstellen kann.

- **Bindepose als Pflicht-Trainingspose:** Ihr Ziel ist das unveränderte Kleid. Dadurch bleibt `d` nur dort ungleich null, wo die Posen es wirklich verlangen. Zusätzlich gibt es eine Laplace-Glättung und eine harte Obergrenze (3 cm).
- **Alternierende Lösung:**
  - Gewichte: pro Vertex ein quadratisches Problem auf dem Simplex, gelöst mit batched FISTA. Zuerst ohne Support-Beschränkung, dann werden die 4 stärksten Joints behalten und es wird nachoptimiert. Ein Glättungsterm zieht zum Mittel der Nachbarn, ein Prior zu den v0.4-Gewichten.
  - Ruheform: ein globales, dünn besetztes Least-Squares-Problem, gelöst matrixfrei mit CG.
- Das Oberteil oberhalb der Taille bleibt gesperrt und behält die Body-Copy-Gewichte.

### Virtuelle Stoff-Bones

- Freie Helper-Bones pro Trainingspose nach dem SSDR-Prinzip (Le & Deng 2012). Die Bone-Treiber kommen aus einer Ridge-Regression von den Hüft- und Knie-Rotationen auf die Bone-Transformation, angelehnt an Beispiel-basierte Helper-Bone-Rigs (Mukai 2015/16). Den Ridge-Parameter wähle ich per Leave-one-out.
- **SL kann solche Treiber zur Laufzeit nicht auswerten.** Möglich wäre nur, ungenutzte Bento-Bones umzuwidmen, die dann jede Animation bzw. der AO mitbewegen müsste. Darum habe ich die Bones auf zwei Arten getestet:
  - **E** als nicht SL-taugliche Obergrenze,
  - **F** als „Lehrer“: Das Helper-Rig erzeugt 48 zusätzliche Zwischenposen, die als schwach gewichtete Zusatzdaten in den SL-Fit gehen (Destillation).

## 3. Ergebnisse der Studie

**Wichtige Einschränkung:** Echte, von Hand korrigierte Posen gibt es im Repo noch nicht. Die Zielformen erzeugt deshalb ein skriptbasierter **Proxy**. Er arbeitet mit einem Rotationsfeld (Rotationsvektor-Blend der Hüften und anteilig der Knie), mit Durchhang des angehobenen Stoffs, mit nicht dehnbaren Längsbahnen (Follow-the-Leader) und mit Bein-Kollisionskapseln. Die Ziele sind geprüft: längentreu, durchdringungsfrei, und in der Bindepose identisch zur Ruheform. Der Proxy ist absichtlich *kein* LBS. Die Schlussfolgerungen müssen aber mit echten Maya-Sculpts bestätigt werden.

Aufbau: SL-ähnliches Skelett (mPelvis, mTorso, Hüften, Knie, Knöchel; Meter, Y-up), zwei A-Linien-Kleider (knielang und maxi) mit je 1632 Vertices.

- **Trainingsposen** (6 + Bindepose): Gehen L/R, breiter Stand, Sitzen 60°, Knie hoch, Bein seitlich.
- **Ungesehene Posen im Trainingsbereich** (4): halber Schritt, halbes Sitzen in breiter Stellung, Spiegelposen.
- **Ungesehene Extremposen** (7): Sitzen 90°, hoher Kick 110°, Grätsche 50°, Ausfallschritt, Beine überschlagen, Sprint, Knien.

Mittlerer Vertex-Fehler zur Zielform in cm (Mittelwert über die Posen der jeweiligen Gruppe):

| Methode | knielang Training | knielang ungesehen | knielang **Extrem** | maxi Training | maxi ungesehen | maxi **Extrem** |
|---|---:|---:|---:|---:|---:|---:|
| A v0.4 Standard (aktuelles Rig) | 2.87 | 2.55 | 4.65 | 4.32 | 3.87 | 7.39 |
| B v0.4, Regler auf Training optimiert | 2.33 | 1.99 | 4.68 | 3.22 | 2.63 | 7.45 |
| C Fit: nur Gewichte | 1.70 | 1.66 | 3.81 | 2.42 | 2.37 | 6.47 |
| **D Fit: Gewichte + Ruheform** | **1.57** | **1.58** | **3.68** | **2.13** | **2.27** | **6.26** |
| D5 wie D, ohne Knöchel-Joints | 1.57 | 1.57 | 3.67 | 2.11 | 2.24 | 6.28 |
| E virtuelle Stoff-Bones (nicht SL) | 0.76 | 1.39 | 4.28 | 0.95 | 1.93 | 6.44 |
| F D + Stoff-Bone-Destillation | 1.75 | 1.67 | 3.86 | 2.41 | 2.32 | 6.50 |
| O Orakel: D auf *allen* Posen trainiert (LBS-Grenze) | 1.71 | 1.58 | 3.00 | 2.57 | 2.47 | 4.95 |

Ruheform-Änderung bei D: knielang max. 1,2 cm (Ø 0,35 cm), maxi max. 2,3 cm (Ø 0,6 cm). Alle SL-Varianten halten max. 4 Einflüsse ein.

Die vollständigen Tabellen (p95, Max, Durchdringung, Dehnung, jede Pose einzeln) und die Plots stehen in `experiments/results/report.md`.

### Interpretation

1. **Der Fit aus Zielposen schlägt das aktuelle Rig deutlich.** Gegenüber v0.4 Standard liegt der Fehler bei ungesehenen Posen im Trainingsbereich etwa 40 % niedriger, bei den Extremposen 15–21 %. Gegenüber v0.4 mit optimierten Reglern bleibt bei den Extremposen ein Vorteil von 16–21 %.
2. **Bloßes Nachregeln von v0.4 hilft bei Extremposen nicht.** B ist im Training besser als A, bei den Extremposen aber gleich schlecht oder schlechter. Die vier Regler reichen nicht aus, um das Verhalten zu verallgemeinern.
3. **Die Ruheform-Offsets bringen wenig, aber verlässlich:** etwa 5–12 % weniger Fehler im Training und 3–4 % bei Extremposen, bei max. 1–2 cm Formänderung. Den größeren Teil leistet der Gewichts-Fit.
4. **Bei Extremposen liegt der Großteil des Restfehlers an LBS selbst.** Selbst das Orakel, das die Extremposen kennt, kommt nur auf 3,0 bzw. 5,0 cm. D liegt 0,7 bzw. 1,3 cm darüber; das ist die echte Lücke in der Generalisierung. Mit festen Gewichten am SL-Skelett ist Sitzen, Kick und Knien grundsätzlich nur begrenzt darstellbar.
5. **Virtuelle Stoff-Bones** passen die Trainingsposen 2–2,5× besser an. Bei ungesehenen Posen im Trainingsbereich sind sie noch etwas besser, bei Extremposen dagegen schlechter als D: Die linearen Treiber extrapolieren schlecht, besonders bei hohem Kick und beim Knien. Als Lehrer für SL-Gewichte (F) bringen sie hier **keinen** Gewinn. Ihr Nutzen beschränkt sich damit auf:
   - umgewidmete Bento-Bones mit eigener Animation, was den AO bzw. die Animationen betrifft,
   - ein Werkzeug zum Erzeugen von Korrekturformen.
6. **Die Knöchel-Joints sind überflüssig.** D5 ist so gut wie D, auch beim Maxikleid. Die fünf Joints, die v0.4 schon nutzt, reichen aus.
7. **Offenes Problem: Durchdringung.** Kein LBS-Ansatz verhindert, dass Beine bei Extremposen durch den Stoff gehen. Bei den Extremposen dringen 4–7 % der Vertices ein, bis zu etwa 7 cm tief. Der Fehler-Fit verbessert daran kaum etwas.

## 4. Vorschlag für die nächsten Schritte

1. **Maya-Brücke:**
   - Export: Kleid, Joint-Matrizen und korrigierte Shapes pro Pose ins Format von `save_training_set`.
   - Import: Gewichte und Ruheform-Offset auf eine neue `_poseFit`-Kopie schreiben, mit derselben Verifikation wie v0.4.
2. **Mit echten, von Hand korrigierten Posen nachmessen.** Das sind 6–8 Posen, die Extremposen bleiben als Test zurückgehalten.
3. **Durchdringung direkt in den Fit nehmen.** Ein Strafterm für Punkte innerhalb von Bein-Kapseln, ausgewertet auch in künstlich erzeugten Zwischen- und Extremposen, für die kein Sculpt nötig ist.
4. **Gewichtung der Posen festlegen.** Welche Posen sind in SL wirklich wichtig (Gehen, Stehen, Sitzen)? Extremposen lassen sich nur mit Kompromissen bedienen.
5. Bento-Helper-Bones nur weiterverfolgen, wenn ein eigener AO bzw. eigene Animationen im Spiel sind.
