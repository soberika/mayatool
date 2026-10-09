# mcd. Maya-Tools für Second-Life-Kleidung

| Datei | Zweck | Stand |
|---|---|---|
| `mcd_dress_auto_rig (3).py` | Dress Auto Rig 0.4: Körpergewichte übertragen + Rockgewichte | in Benutzung |
| `mcd_sl_anim.py` | `.anim`-Export für Stoff-Bones (Tail, HindLimb, Groin, Wings); Testbänder und Bake in Maya | Stufe 0, in SL noch ungetestet |
| `mcd_fit_metrics.py` | Messgerüst: Clipping, Verzerrung, Silhouette, Sprünge pro Frame | Stufe 0, in Maya noch ungetestet |
| `lsl/mcd_cloth_state.lsl` | Zustandsskript (Stehen/Gehen/Sitzen …) für Overlay-Animationen, lässt die AO unberührt | Stufe 0, in SL noch ungetestet |
| `testdaten/stufe0/` | fertige Testanimationen und Teststäbe (`mcd_test_baender.dae`) | |

## Dokumente

- `docs/konzept_kleidung_und_bewegung.md`: Konzept, Grenzen von SL, Auswahl, Prototyp-Plan
- `docs/anleitung_einfach.md`: Stufe 0 Schritt für Schritt (ohne Maya)
- `docs/stufe0_testprotokoll.md`: Tests in SL mit Entscheidungstabelle (ausführlich)

## Tests außerhalb von Maya

```
python -m unittest discover tests
```
