# Stufe 0 – Schritt für Schritt

**Worum es geht:** Wir wollen herausfinden, ob Second Life ein paar ungenutzte
Bones des Avatars (die „Hinterbein“- und „Schwanz“-Bones) so bewegen kann, wie
wir es später für Röcke brauchen. Unsichtbare Bones kann man nicht sehen. Deshalb
hängen wir **rosa Stäbe** daran, die **Testbänder**. Bewegen sich die Stäbe, bewegen
sich die Bones.

Du brauchst **kein Maya**. Alles liegt fertig in der ZIP-Datei
`stufe0_paket.zip`.

**Inhalt der ZIP**

| Datei | Was ist das? |
|---|---|
| `mcd_test_baender.dae` | die rosa Teststäbe (ein Mesh) |
| `cloth_stand.anim` | Animation „Stäbe hängen ruhig“ |
| `cloth_walk.anim` | Animation „Stäbe schwingen“ |
| `cloth_sit.anim` | Animation „Stäbe 10 cm nach vorn“ |
| `mcd_test_hold_hindlimbs_rotate.anim` | Animation „Stäbe kippen“ (Richtungstest) |
| `mcd_cloth_state.lsl` | das Skript (Text zum Kopieren) |

Uploads kosten im Hauptgrid ein paar L$. Wenn du Zugang zum Beta-Grid (Aditi)
hast, kannst du dort kostenlos testen. Das ist aber nicht nötig.

---

## Teil A – Hochladen (ca. 10 Minuten)

### A1. Die Stäbe hochladen
1. ZIP entpacken.
2. In SL: **Bauen → Hochladen → Modell…** und `mcd_test_baender.dae` wählen.
3. Im Fenster auf den Reiter **Upload-Optionen** gehen:
   - Haken bei **Skin-Gewichte einschließen**: **an**
   - Haken bei **Gelenkpositionen einschließen**: **aus**
4. **Gewichte und Gebühr berechnen** klicken, dann **Hochladen**.
5. Gibt es eine Fehlermeldung, mach einen Screenshot davon und hör hier auf. Schick ihn mir.

### A2. Die vier Animationen hochladen
Für jede der vier `.anim`-Dateien:
1. **Bauen → Hochladen → Animation…** und die Datei wählen.
2. **Wichtig:** Der Name muss **genau** so bleiben wie der Dateiname ohne `.anim`, also `cloth_stand`, `cloth_walk`, `cloth_sit`, `mcd_test_hold_hindlimbs_rotate`. Das Skript sucht genau diese Namen.
3. **Hochladen** klicken.

Im Vorschaufenster bewegt sich nichts. Das ist richtig: Die Vorschaupuppe hat keine Stäbe.

---

## Teil B – Stäbe anziehen und Skript einbauen (ca. 5 Minuten)

1. Im Inventar die hochgeladenen Stäbe suchen (Ordner *Objekte*) → Rechtsklick → **Hinzufügen**.
   Du siehst rosa Stäbe hinter deinem Becken: zwei, die nach unten hängen, und einen, der nach hinten zeigt. Das ist so gewollt.
2. Rechtsklick auf die Stäbe → **Bearbeiten** → Reiter **Inhalt**.
3. Die drei Animationen `cloth_stand`, `cloth_walk` und `cloth_sit` aus dem Inventar in den Inhalt ziehen. Die vierte **noch nicht**.
4. Im Reiter Inhalt auf **Neues Skript** klicken und es mit Doppelklick öffnen.
5. Den ganzen Text darin löschen. Dann `mcd_cloth_state.lsl` mit einem Texteditor öffnen, alles kopieren und einfügen. **Speichern**.
6. Bearbeiten-Fenster schließen. Im Chat sollte jetzt stehen:
   `mcd. Cloth State bereit. Befehle: /7 on|off|debug|test|rate <s>|status`

---

## Teil C – Testen (ca. 10 Minuten)

Deine **eigene AO bleibt an**. Nimm am besten alles als kurzes Bildschirmvideo auf.

### Test 1 – Reagieren die Stäbe auf Stehen, Gehen, Sitzen?
1. **Still stehen:** Die Stäbe hängen ruhig.
2. **Ein paar Schritte gehen:** Die beiden hängenden Stäbe sollen **hin und her schwingen**.
3. **Wieder stehen bleiben:** Sie sollen zur Ruhe kommen.
4. **Auf einen Stuhl setzen:** Die beiden hängenden Stäbe sollen etwa **10 cm nach vorn** wandern.
5. **Aufstehen:** Sie sollen wieder zurückgehen.

Jeden Schritt 2- bis 3-mal machen. Im Chat erscheint bei jedem Wechsel eine
Zeile wie `[12.3] stand -> walk (Walking), Overlay: cloth_walk`. Diese Zeilen
bitte kopieren.

### Test 2 – In welche Richtung kippen die Stäbe?
1. Im Chat `/7 off` eingeben. Das schaltet Test 1 ab.
2. Bearbeiten → Inhalt: jetzt die vierte Animation `mcd_test_hold_hindlimbs_rotate` hineinziehen.
3. Im Chat `/7 test` eingeben. Ab jetzt kippen die Stäbe alle 4 Sekunden und kommen dann zurück.
4. Von der **Seite** anschauen: Schwingt das **untere Ende** der hängenden Stäbe **nach hinten** (vom Bauch weg) oder **nach vorn**?
5. Zum Beenden wieder `/7 test`, danach `/7 on`.

### Test 3 – Bleibt deine AO normal?
Achte während Test 1 und 2 darauf:
- Bewegen sich Beine, Arme und Kopf genau wie sonst?
- Bleibt die **Handhaltung** wie sonst?

---

## Was du mir schicken sollst

Kurze Antworten reichen, zum Beispiel „ja / nein / anders: …“:

1. Ließ sich alles hochladen? (Wenn nein: Screenshot der Fehlermeldung)
2. Test 1: Schwingen die Stäbe beim Gehen?
3. Test 1: Wandern sie beim Sitzen nach vorn?
4. Test 1: Gehen sie danach **zurück** an ihren Platz, oder bleiben sie hängen?
5. Test 1: Wie lange reagieren sie verspätet? (gefühlt: sofort / ½ Sekunde / 1 Sekunde / mehr)
6. Test 2: Unteres Ende nach **hinten** oder nach **vorn**?
7. Test 3: Hat sich an deiner AO oder an den Händen etwas verändert?
8. Die kopierten Chatzeilen und, falls vorhanden, das Video.

Mit diesen Antworten weiß ich, ob unser Plan in SL funktioniert und was ich anpassen muss.

Die ausführliche Fassung mit allen Tests steht in `docs/stufe0_testprotokoll.md`.
Für den ersten Durchgang reicht diese Anleitung.
