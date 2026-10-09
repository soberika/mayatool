# Stufe 2 – Stoffebene, erstes Ergebnis (Thin-Kleid)

Export mit komplettem Skelett. Die HindLimb-, Tail- und Groin-Bones stehen exakt auf den
SL-Standardpositionen (geprüft).

**Stoff-Bones:** `mHindLimb1Left/Right` (Gesäß/Oberschenkel hinten) und `mHindLimb2Left/Right`
(Saum hinten, unterhalb des Knies).

**Gelöst wird gemeinsam:**
- Gewichte auf Körper- **und** Stoff-Bones, höchstens 4 pro Vertex;
- die Ruheform aus Stufe 1, bis 6 mm weiter;
- je Zustand eine Verschiebung der Stoff-Bones.

**Gefundene Stoffposen (Maya-Weltachsen, cm):**

| Zustand | obere Bones (HindLimb1) | untere Bones (HindLimb2) |
|---|---|---|
| Stehen | 0 | 0 |
| Gehen | 1 cm nach hinten | 3 cm nach hinten |
| Sitzen | 2 cm nach hinten, 1 cm nach oben | 2 cm nach hinten |

Etwa 5 500 Vertices haben Stoffgewicht, höchstens 34 % pro Vertex.

## Clipping (Anteil Vertices > 2 mm im Body; „U“ = nur Unterschenkelbereich)

| Pose | Satz | 0.5.3 | Stufe 1 | Stufe 2 |
|---|---|---|---|---|
| Gehen 70 % (Schwungphase) | Training | 0,9 % (U 7,0 %) | 0,7 % (U 6,0 %) | 0,4 % (U 3,8 %) |
| Gehen 20 % | Training | 1,1 % (U 8,8 %) | 0,9 % (U 8,0 %) | 0,7 % (U 6,5 %) |
| Gehen 15 % | Test | 1,0 % (U 7,6 %) | 0,6 % (U 5,8 %) | 0,5 % (U 4,2 %) |
| Gehen 75 % groß | Test | 1,0 % (U 7,4 %) | 0,7 % (U 6,5 %) | 0,4 % (U 3,9 %) |
| Gehen 65 % groß | Test | 1,2 % (U 8,0 %) | 0,8 % (U 7,2 %) | 0,8 % (U 7,2 %) |
| Schritt L 40 | Test | 1,3 % (U 2,5 %) | 0,4 % (U 0,5 %) | 0,7 % (U 1,6 %) |
| Sitzen | Training | 5,9 % | 3,2 % | 2,4 % |
| Bein über Bein | Test | 5,7 % | 3,6 % | 3,2 % |
| Bein über Bein R | Test | 5,6 % | 3,2 % | 2,6 % |
| Ruhe | – | 0,0 % | 0,0 % | 0,0 % (tiefste Stelle 0,5 cm) |
| Beine stark gekreuzt | Test | 2,8 % | 2,1 % | 1,9 % |

## Ehrliche Einordnung

- **Deutlicher Gewinn** in der Schwungphase beim Gehen und beim Sitzen, auch in Testposen.
- **Kein Gewinn bei „Gehen 65 % groß“** (sehr großer Schritt, Test).
- **Leichter Rückschritt bei „Schritt L 40“:** 0,4 → 0,7 %. Dafür ist das Ergebnis dort immer noch besser als 0.5.3.
- **Stehen ohne Animation** ist unverändert gut, weil die Stoffpose „Stehen“ der Ruhelage entspricht.
- **Nur Verschiebungen, noch keine Rotationen** der Stoff-Bones. Größere Saum-Effekte, etwa ein bewusst ausschwingender Schlitz, kommen mit Rotationen dazu.
- **Gemessen ist nur am erzeugten Gangzyklus.** Fremde AO-Gänge folgen beim Test in SL.

---

## Nachtrag: In SL getestet – Saum gerissen. Ursache und Korrektur

**Rückmeldung aus SL:** Es clippt weiterhin, und der Saum ist unten kaputt (zackige, aufgerissene Kanten).

**Ursache (Fehler im Solver, nicht in SL):**
1. **4-Einfluss-Grenze.** Kam ein Stoff-Bone dazu, musste ein anderer Einfluss raus. Bei benachbarten Vertices war das mal der eine, mal der andere Bein-Bone bzw. das Collision Volume.
2. **Rauschen.** Die Gewichte wurden pro Vertex unabhängig gelöst. Bein-Collision-Volumes sind stark skaliert, deshalb ergeben kleine Gewichtsunterschiede große Verschiebungen.
3. **Falsches Prüfmaß.** Ich hatte nur das 95. Perzentil der Dehnung geprüft. Auf einer 1-mm-Kante lagen aber bis zu 1,6 cm zwischen den Nachbarn.

**Neues Prüfmaß:** Kanten, die in einer Pose mindestens 3 mm länger sind als mit 0.5.3 („Risse“).

| Variante | Sitzen: Clipping / Risse | Bein über Bein | Gehen 70 % | Schritt L 40 |
|---|---|---|---|---|
| 0.5.3 | 5,9 % / 0 | 5,7 % / 0 | 0,9 % / 0 | 1,3 % / 0 |
| Stufe 1 (getestete Version) | 3,2 % / 324 | 3,6 % / 319 | 0,7 % / 106 | 0,4 % / 154 |
| **0.5.3-Gewichte + glatte Form bis 6 mm** | **4,1 % / 1** | **4,1 % / 1** | **0,7 % / 1** | **0,4 % / 1** |
| 0.5.3-Gewichte + Form bis 10 mm | 3,5 % / 79 | 3,4 % / 77 | 0,6 % / 133 | 0,3 % / 125 |

**Folgerungen:**
- Fast der ganze Gewinn von Stufe 1 kam von der glatten Formänderung. Die Gewichtsänderungen bringen beim Sitzen nur etwas mehr, reißen aber den Stoff auf.
- **Saubere Empfehlung:** 0.5.3-Gewichte unverändert, Ruheform glatt bis 6 mm weiter (`mcd_kleid_form6mm.json.gz`).
- **Stufe 2 bringt bei diesem Kleid nichts.** Weder die Variante mit freien Slots noch die mit glattem Stoffanteil liefert einen sauberen Gewinn. Starre, beckenfeste Verschiebungen bringen ohne Pro-Vertex-Freiheit kaum etwas, und mit dieser Freiheit reißt das Mesh.
- **Wadenclipping beim Gehen (ca. 6–7 % im Unterschenkelbereich) bleibt ungelöst.** Realistische Optionen:
  - Entwurf ändern: hinterer Gehschlitz oder etwas mehr Saumweite hinten. Das ist Konzept K5.
  - Stoff-Bones, die mit der Wade mitgehen, statt beckenfester. Dafür bräuchte es Rotationen und andere Bone-Ketten.
- Der Code für Stufe 2 bleibt als Experiment im Repo (`mcd_cloth_layer.py`). Das Ergebnis wird nicht empfohlen.
