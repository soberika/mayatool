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
