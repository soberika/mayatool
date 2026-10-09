# Stufe 1 – erstes Ergebnis (Thin-Kleid, Oktober 2026)

**Vergleichsbasis:** Das Kleid, wie es mit Dress Auto Rig **0.5.3** geriggt wurde.
Laut Kreatorin ist das der optisch beste Stand: keine Verzerrung, aber viel Clipping.

**Body:** Legacy, aus dem Export. Die Geometrie liegt **nicht** im Repo (Devkit-Lizenz).

**Posen:** Erzeugt am exportierten Skelett, ohne Posieren in Maya.

| Satz | Posen |
|---|---|
| Training (der Solver lernt daran) | Schritt L/R 25°, Beine gekreuzt stehend, Sitzen, Bein über Bein leicht |
| Test (nie gesehen) | Schritt L/R 40°, Ausfallschritt, Bein über Bein L und R, Beine stark gekreuzt |

**Messung:**
- **Clipping:** Anteil der Kleid-Vertices, die mehr als 2 mm im Body stecken, und die tiefste Stelle.
- **Dehnung:** 95. Perzentil der Kantenlängenänderung gegenüber der Ruheform.

## Variante „nur Gewichte“ (Ruheform unverändert)

| Pose | Satz | Clipping 0.5.3 → neu | tiefste Stelle | Dehnung (95 %) |
|---|---|---|---|---|
| Sitzen | Training | 5,9 % → 4,8 % | 4,6 → 3,5 cm | 0,36 → 0,40 |
| Bein über Bein leicht | Training | 5,9 % → 4,6 % | 4,6 → 3,8 cm | 0,36 → 0,41 |
| Bein über Bein | Test | 5,7 % → 4,9 % | 4,6 → 4,3 cm | 0,38 → 0,43 |
| Bein über Bein R | Test | 5,6 % → 5,0 % | 4,4 → 4,3 cm | 0,36 → 0,40 |
| Schritt L 40 | Test | 1,3 % → 1,4 % | 3,1 → 2,9 cm | 0,35 → 0,36 |
| Beine stark gekreuzt | Test | 2,8 % → 2,9 % | 4,9 → 4,9 cm | 0,16 → 0,17 |

## Variante „Gewichte + 6 mm“ (Ruheform an Hüfte und Rockkanten bis 6 mm weiter)

| Pose | Satz | Clipping 0.5.3 → neu | tiefste Stelle | Dehnung (95 %) |
|---|---|---|---|---|
| Ruhe | – | 0,0 % → 0,0 % | 0,3 → 0,0 cm | 0,00 → 0,07 |
| Sitzen | Training | 5,9 % → 3,2 % | 4,6 → 3,2 cm | 0,36 → 0,41 |
| Bein über Bein leicht | Training | 5,9 % → 3,1 % | 4,6 → 3,5 cm | 0,36 → 0,42 |
| Bein über Bein | Test | 5,7 % → 3,5 % | 4,6 → 4,1 cm | 0,38 → 0,43 |
| Bein über Bein R | Test | 5,6 % → 3,2 % | 4,4 → 4,1 cm | 0,36 → 0,40 |
| Schritt L 40 | Test | 1,3 % → 0,4 % | 3,1 → 2,6 cm | 0,35 → 0,37 |
| Ausfallschritt L | Test | 1,7 % → 0,8 % | 3,7 → 3,3 cm | 0,46 → 0,49 |
| Beine stark gekreuzt | Test | 2,8 % → 2,1 % | 4,9 → 5,3 cm | 0,16 → 0,20 |

## Einordnung

- **Gewichte allein bringen wenig.** Das hatte das Konzept so erwartet: Lineares Skinning kann widersprüchliche Posen nur mitteln.
- **Mit 6 mm Spielraum** halbiert sich das Clipping beim Sitzen und bei Bein über Bein, **auch in den Testposen**. Das Clipping an den Schienbeinen verschwindet fast ganz.
- **Der Preis:**
  - Das Kleid ist an Hüfte und Bauch in Ruhe bis 6 mm weiter, also etwa 4–7 % mehr Umfang dort.
  - In den Posen wird der Stoff etwas stärker gedehnt.
- **Nicht gelöst** ist die Gesäß-/Oberschenkelfalte beim Sitzen (bis 3–4 cm). Dort klappt die Oberschenkelrotation den Stoff in den Body. Das kann ein fester Gewichtssatz kaum verhindern. Hier setzt die **Stoffebene aus Stufe 2** an: Im Zustand „Sitzen“ schieben Stoff-Bones diese Partie gezielt nach außen.
- **Eine Testpose wird schlechter:** „Beine stark gekreuzt“, tiefste Stelle 4,9 → 5,3 cm. Das berichten wir offen.

## Nächste Schritte

1. Die Kreatorin legt beide Varianten mit `mcd_fit_apply.py` in Maya an und vergleicht sie selbst in echten Posen.
2. Danach Stufe 2: eine Stoffpose „Sitzen“ auf HindLimb-Bones für die Gesäß-/Oberschenkelpartie, gemeinsam mit den Gewichten gelöst.
