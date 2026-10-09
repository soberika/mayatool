# Stufe 0 – Testprotokoll in Second Life

Ziel: Bevor wir Solver bauen, prüfen wir, ob SL das abspielt, worauf die
zustandsgesteuerte Stoffebene aufbaut (siehe `konzept_kleidung_und_bewegung.md`).
Jede Frage hat eine erwartete Beobachtung und eine Konsequenz.

Alles hier ist **noch nicht in SL getestet**. Die Dateien folgen dem
Viewer-Quellcode, entscheiden muss aber das, was in SL tatsächlich zu sehen ist.

---

## Was du brauchst

| Datei | Zweck |
|---|---|
| `testdaten/stufe0/*.anim` | fertige Testanimationen (direkt hochladbar, der Viewer akzeptiert `.anim`) |
| `mcd_sl_anim.py` | erzeugt diese Dateien neu (`python mcd_sl_anim.py --sway <ordner>`) und baut in Maya Testbänder |
| `lsl/mcd_cloth_state.lsl` | Zustandsskript mit Zeitprotokoll (mit lslint geprüft: 0 Fehler, 0 Warnungen) |
| `mcd_fit_metrics.py` | Messgerüst in Maya für den späteren Vergleich mit 0.4 |

**Die Testanimationen**

Alle Dateien keyen **nur** HindLimb- bzw. Tail-Bones mit Priorität 1. Die AO bleibt also unberührt.

| Datei | Inhalt | Was man sehen soll |
|---|---|---|
| `mcd_test_sway_hindlimbs` | Schwingen + Vorwärtsverschiebung, 2 s Loop | Bänder schwingen **und** wandern um bis zu 4 cm nach vorn |
| `mcd_test_sway_hindlimbs_rot_only` | gleiche Bewegung, nur Rotation | Bänder schwingen nur auf der Stelle |
| `mcd_test_sway_tail` | Welle über `mTail1–3` | Schwanzband wellt |
| `mcd_test_hold_hindlimbs_forward` | obere Bones 10 cm nach vorn (SL +X) | beide Bänder stehen 10 cm weiter **vorn** |
| `mcd_test_hold_hindlimbs_rotate` | obere Bones +25° um SL +Y | das **untere Ende** schwingt nach **hinten** |
| `cloth_stand` / `cloth_walk` / `cloth_sit` | Ruhe / Schwingen / 10 cm vor | für den Zustandstest |

**Hinweise**
- Am besten testest du auf dem Beta-Grid (Aditi), sofern du dort Zugang hast. Dort kosten Uploads keine L$.
- Das Skript nimmt als Testanimation die erste, deren Name mit `mcd_test` beginnt. Lege deshalb **immer nur eine** `mcd_test…`-Animation ins Objekt.

---

## Vorbereitung: Testbänder (einmalig)

Ohne Geometrie auf diesen Bones sieht man nichts. Deshalb:

1. In Maya die Szene mit eurem SL-Skelett öffnen. Die Bones müssen in **SL-Standardposition** stehen und ihre SL-Namen tragen, etwa `mHindLimb1Left`.
2. Im Script Editor (Python) ausführen:
   ```python
   import mcd_sl_anim as sa
   sa.build_test_ribbons()
   ```
   Das erzeugt je Bone ein schmales Band, zu 100 % an diesen Bone gebunden.
   **Achtung:** Diese Funktion ist in Maya noch ungetestet. Gibt es eine Fehlermeldung, schick sie mir.
3. Mit eurer üblichen DAE-Pipeline exportieren und hochladen: Skin Weights **an**, Joint Positions **aus**.
4. Die Bänder hängen in SL-Standardposition hinter und unter dem Becken. Das ist für den Test gewollt.
5. Bänder anziehen. In ihren Inhalt (Bearbeiten → Inhalt) legst du das Skript und die jeweils nötigen Animationen.

---

## Die Tests

Trag die Ergebnisse direkt in die Tabelle am Ende ein. Screenshots oder kurze Videos helfen sehr.

### T1 – Upload
Lade alle `.anim` über *Hochladen → Animation* hoch.
- **Erwartet:** Alle werden angenommen. Die Vorschau zeigt den Dummy-Avatar ohne die Bänder, also ist dort keine Bewegung zu sehen. Das ist in Ordnung.
- **Wenn abgelehnt:** Genaue Fehlermeldung notieren. Hilfreich ist auch `SecondLife.log` (Abschnitt mit „BVH“ oder „animation“).

### T2 – Werden Positionskeys auf Nicht-Pelvis-Bones abgespielt?
1. `mcd_test_sway_hindlimbs` ins Objekt legen und `/7 test` eingeben. Das Skript schaltet die Animation alle 4 s ein und aus.
2. Dasselbe mit `mcd_test_sway_hindlimbs_rot_only`.

- **Erwartet:** Die erste Variante wandert zusätzlich nach vorn, die zweite schwingt nur.
- **Kein Unterschied:** Positionen werden nicht abgespielt → Plan B (nur Rotationen, siehe Entscheidungstabelle).

### T3 – Achsen und Drehrichtung
`mcd_test_hold_hindlimbs_forward` und danach `mcd_test_hold_hindlimbs_rotate`, jeweils mit `/7 test`.
- **Erwartet:**
  - Forward: Die Bänder springen bzw. blenden **10 cm nach vorn** in Blickrichtung des Avatars.
  - Rotate: Das untere Ende schwingt **nach hinten**.
- **Abweichung:** Notieren, wohin es tatsächlich geht. Dann korrigiere ich die Achsen- oder Vorzeichenumrechnung.

### T4 – Rückkehr nach dem Stoppen
Bei den Tests T2 und T3 darauf achten, was beim **Ausschalten** passiert.
- **Erwartet:** Innerhalb von etwa 0,5 s (Ease-Out) gleiten die Bänder in die Ausgangslage zurück.
- **Risiko:** Laut Quellcode sind animierte Positionen absolut. Es ist möglich, dass Bones nach dem Stoppen **in der letzten Position stehen bleiben**. Dann bitte notieren, ob ein Relog oder das Ausziehen und Wiederanziehen der Bänder sie zurücksetzt.
- **Folge, falls sie hängen bleiben:** Die Stoffebene braucht dauerhaft eine laufende Ruheanimation (`cloth_stand`). Das Skript ist bereits so gebaut, dass im Zustand „Stehen“ immer `cloth_stand` läuft.

### T5 – Die AO bleibt unberührt
Deine normale AO läuft (Stehen, Gehen). Dazu `cloth_walk` per Skript abspielen (T6) oder `mcd_test_sway_hindlimbs` per `/7 test`.
- **Erwartet:** Arme, Beine, Kopf und **Hände** (auch Bento-Hände) bewegen sich exakt wie ohne Overlay.
- **Besonders prüfen:** die **Handhaltung**. Laut Quellcode kann eine Animation die System-Handpose überschreiben, wenn ihre Priorität mindestens so hoch ist wie die der aktuellen Handpose. Unsere Priorität 1 sollte darunter liegen.

### T6 – Zustandserkennung und Verzögerung
1. `cloth_stand`, `cloth_walk`, `cloth_sit` ins Objekt legen, keine `mcd_test`-Datei.
2. Debug ist an. Bei jedem Wechsel schreibt das Skript Zeit, alten und neuen Zustand und die Overlay-Animation in den Chat.
3. Stehen → Gehen → Stehen → auf einen Stuhl setzen → aufstehen → auf den Boden setzen (falls die AO das kann). Jeden Wechsel 3-mal.
4. Mit `/7 rate 0.1` wiederholen.

- **Erwartet:**
  - Gehen: Die Bänder schwingen.
  - Sitzen: Sie stehen 10 cm vor.
  - Stehen: Ruhe.
  - Die Zustandsnamen im Chat passen zu dem, was die AO zeigt.
- **Messen:** Wie lange dauert es zwischen Beginn der Körperbewegung und sichtbarer Reaktion der Bänder? Am besten per Bildschirmvideo, Frames zählen.

### T7 – Zweiter Beobachter
Ein Alt-Account oder eine Freundin schaut bei T6 zu. Am besten nehmt ihr beide gleichzeitig auf.
- **Fragen:** Sieht der zweite Viewer dasselbe? Wie groß ist dort die Verzögerung?

### T8 – Shape-Slider
Während `cloth_sit` läuft: Körpergröße und Hüftbreite in der Shape stark ändern.
- **Fragen:** Bleiben die Bänder an einer plausiblen Stelle relativ zum Becken? Oder verschiebt sich das deutlich, weil die animierten Positionen absolut sind?

### T9 (optional) – Konflikt mit einem Bento-Tail
Falls verfügbar: einen Bento-Schwanz mit eigener Animation tragen und `mcd_test_sway_tail` spielen.
- **Erwartet:** Konflikt. Bei gleicher Priorität gewinnt die zuletzt gestartete Animation.
- **Notieren:** wie sichtbar der Konflikt ist (für den Kompatibilitätshinweis auf der Produktseite).

---

## Entscheidungstabelle

| Ergebnis | Folge für Stufe 1–2 |
|---|---|
| T1 abgelehnt | Fehlermeldung an mich, Format korrigieren, erneut testen |
| T2: Positionen laufen | volle Stoffebene: Rotation **und** Verschiebung pro Zustand |
| T2: nur Rotationen | Stoffebene nur mit Rotationen. Bones über Joint-Positionen im Mesh-Upload günstiger platzieren? Muss ich gesondert prüfen, weil das alle getragenen Meshes betrifft. Ausdruck geringer. |
| T3 falsche Richtung | Achsen und Vorzeichen in `mcd_sl_anim.py` korrigieren, T3 wiederholen |
| T4: Bones bleiben hängen | `cloth_stand` läuft dauerhaft. Zusätzlich prüfen, was nach dem Ausziehen passiert, damit nicht ohne Kleid etwas hängen bleibt. |
| T5: AO gestört / Handpose ändert sich | Priorität auf 0 senken bzw. Handpose-Wert anpassen und neu testen |
| T6/T7: Verzögerung > ca. 0,5 s oder unzuverlässig | weniger automatische Zustände: nur Sitzen automatisch, Rest per Menü |
| T8: deutlicher Versatz bei extremen Shapes | Zustandsformen über 2–3 Shape-Varianten optimieren (Teil des Solvers) und Grenzen auf der Produktseite nennen |

---

## Ergebnisse (Oktober 2026, Rückmeldung der Kreatorin)

| Test | Ergebnis |
|---|---|
| T1 Upload | Teststäbe (`mcd_test_baender.dae`) und `.anim`-Dateien wurden angenommen. Das Skript lief nach einem Kopierfehler beim Einfügen. |
| T2 Positionen | **Funktioniert.** Im Sitzen wandern die Stäbe nach vorn, also werden Positionskeys auf HindLimb-Bones abgespielt. |
| T3 Achsen | Kippen sichtbar. Die genaue Richtung (unteres Ende nach hinten?) ist noch nicht eindeutig bestätigt. Prüfen wir beim ersten Bake aus Maya. |
| T4 Rückkehr | **Funktioniert.** Nach dem Aufstehen kehren die Stäbe zurück, nichts bleibt hängen. |
| T5 AO / Hände | **Unverändert.** |
| T6 Zustände | **Funktioniert.** Reagiert „ziemlich schnell“, ohne Zahl gemessen. |
| T7 Zweiter Viewer | nicht getestet |
| T8 Shape | nicht getestet |
| T9 Tail | nicht getestet |

**Nebenbefund:** Wenn das Skript aktiv wird, zeigt der Viewer einen Kreis um den Avatar. Vermutlich ist das die Anzeige für Skriptaktivität. In der Produktversion bleibt die Chat-Ausgabe aus (`/7 debug`).

**Folge laut Entscheidungstabelle:** Die volle Stoffebene ist machbar, mit Rotation **und** Verschiebung pro Zustand und ohne dauerhaft laufende Ruheanimation.
Noch offen und nachzuholen:
- T7, ob ein zweiter Beobachter dasselbe sieht;
- T8, Verhalten bei extremen Shapes.

---

## Parallel in Maya: Messgerüst ausprobieren

Das Messgerüst brauchen wir erst für Stufe 1. Ein früher Lauf zeigt aber, ob es in eurer Maya-Version funktioniert.

```python
import mcd_fit_metrics as fm
fm.report_maya(body='body', variants={'A': 'kleid_autoRig'},
               frames={'train': [1, 10, 20], 'test': [30, 40]},
               csv_path='C:/temp/stufe0_messung.csv')
```

Das Ergebnis sind zwei CSV-Dateien: eine Zeile pro Variante und Frame, plus eine Zusammenfassung mit Mittelwert und schlechtestem Frame.

- **Silhouetten-Werte** erscheinen nur, wenn du ein Referenz-Mesh angibst (`reference='kleid_ziel'`).
- **Clipping-Toleranz:** Standard ist 0,1 Szeneneinheiten, bei Zentimetern also 1 mm.
- **Laufzeit:** Die Silhouetten werden in reinem Python gerastert. Bei großen Meshes kann das einige Sekunden pro Frame dauern.
