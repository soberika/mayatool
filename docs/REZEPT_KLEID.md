# Rezept: So entstand das fertige Thin-Kleid (Legacy und Reborn)

Diese Datei beschreibt **exakt**, wie die in SL bestätigten Ergebnisse berechnet wurden. Ein anderes Tool
oder eine neue Claude-Session soll damit **dasselbe Kleid** reproduzieren können. Danach soll die Logik auf andere
Outfits erweitert werden.

Referenz-Code: `mcd_fit_solver.py`, `mcd_fit_deform.py`, `mcd_fit_apply.py`, `mcd_fit_export.py`, `werkstatt/*.py`.

---

## 0. Die Grundidee in einem Satz

**Erst ganz normal riggen (Dress Auto Rig 0.5.3). Die Gewichte danach NICHT mehr anfassen. Dann nur die Ruheform des
Kleides gezielt verändern, so dass es in den Gehposen nicht mehr in den Body taucht. Zum Schluss alles glätten.**

Warum so:
- **0.5.3** sah optisch am besten aus, ohne Verzerrung, hatte aber viel Clipping.
- Jede Optimierung der **Gewichte pro Vertex** riss in SL das Mesh auf:
  - Beim Kappen auf 4 Einflüsse fallen Einflüsse weg.
  - Die SL-Collision-Volumes sind skaliert.
  - Gewichtsrauschen verstärkt sich in den Posen.
- **Ruheform-Offsets bei festen Gewichten** sind robust. Sie reißen nicht, und eine Dehnung bis p99 ≈ 40 % fällt in SL nicht auf.

---

## 1. Ablauf (was die Kreatorin in Maya tut)

```
1. Kleid mit Dress Auto Rig 0.5.3 auf den Body riggen    → Kopie "<kleid>_autoRig"
2. mcd_fit_export.py: Body + _autoRig-Kopie auswählen   → export.json.gz
3. Rechnen (Abschnitt 3)                                  → mcd_kleid_<name>.json.gz
4. mcd_fit_apply.py: _autoRig-Kopie auswählen, Ergebnis laden → "<kleid>_fit"
5. _fit als DAE exportieren → SL
```

**Was `mcd_fit_apply` macht** (wichtig für jedes eigene Tool):
- Es dupliziert das Kleid ohne History.
- Es setzt die **Pre-Skin-Punkte** neu: Originalform (Intermediate-/Orig-Shape) plus `offsets_object`.
- Es legt einen neuen skinCluster auf **dieselben Joints** an, mit **derselben `geomMatrix`** und **denselben
  `bindPreMatrix`-Werten** wie das Quellkleid.
- Es übernimmt die **unveränderten 0.5.3-Gewichte**, höchstens 4 pro Vertex, normalisiert.
- Die `lockWeights`-Verbindungen des neuen skinClusters werden vorher getrennt, sonst schlägt `setWeights` fehl.

---

## 2. Koordinaten und Skinning

- **Legacy-Szene:** cm, Höhe ist Y, vorne +Z, links +X.
  **Reborn-Szene (Mayastar-Devkit):** cm, Höhe ist Z.
- **Achsen nie annehmen, sondern aus dem Skelett bestimmen:**
  - `up` = mPelvis minus Mittelpunkt der Knöchel
  - `left` = mHipLeft minus mHipRight, orthogonal zu `up`
  - `forward` = left × up
- **Skinning in Zeilenvektoren:** `p = Σ_j w_j · (base · bindPreMatrix_j · worldMatrix_j)`.
  Dabei gilt `base = points_orig · geomMatrix`.
- **Offsets** werden im `base`-Raum addiert, also vor dem Skinning. Eine gewünschte Welt-Verschiebung `d` in der Ruhepose
  rechnet man so um: `offset = d · inv(B)`. `B` ist der 3×3-Teil von `Σ_j w_j · bindPreMatrix_j · worldMatrix_j(rest)`.
  Zum Speichern als `offsets_object` teilt man zusätzlich durch die `geomMatrix`.
- **Body-Abstand („signed distance“):**
  - Für jeden Kleid-Punkt die k = 4 nächsten Body-Vertices nehmen.
  - Den Abstand jeweils entlang der Vertex-Normale messen.
  - Mit 1/Distanz gewichtet mitteln. Negativ heißt: im Body.
  - Die Vertex-Normalen sind die Summe der Dreiecks-Normalen.
- **„smooth_field“** glättet einen Wert pro Vertex entlang der Mesh-Kanten.
  Pro Iteration gilt: `wert = 0.5·wert + 0.5·Mittel(Nachbarn)`.

---

## 3. Die Rechnung für das fertige Kleid („v4 mild, sehr glatt“)

**Startpunkt:** die 0.5.3-Gewichte aus dem Export (`dress.weights`), unverändert.
**Höhen beim Thin-Kleid:**

| Punkt | Höhe |
|---|---|
| Knie (mKneeLeft) | 53,3 cm |
| Hüfte (mHipLeft) | 102,6 cm |
| Becken (mPelvis) | 106,7 cm |

### 3.1 Trainings-Gänge (Laufsteg-AO)
Gangkurve des linken Beins, Phase 0–100, mit Hüftbeugung und Kniebeugung in Grad:
```
(0, 25, 5) (15, 20, 15) (30, 5, 5) (50, -10, 10) (60, -5, 38) (70, 12, 60) (85, 25, 35) (100, 25, 5)
```
- Zwischen den Stützpunkten wird linear interpoliert.
- Das rechte Bein läuft mit Phase + 50.
- `stride` skaliert Hüft- und Kniewinkel.
- `cross` ist die Adduktion: Das Bein kreuzt zur Mitte, wie beim Laufsteg.
- **Rotation pro Bein**, um die Weltachsen der Ruhepose und um den Gelenkpunkt:
  - Hüfte: `left` um −flex, dann `forward` um −s·cross, dann `up` um −s·twist. Dabei ist s = +1 für links und −1 für rechts.
  - Knie: `left` um +knee.
- **Trainingsset, 90 Posen:** stride ∈ {1.0, 1.3, 1.5} × cross ∈ {0, 8, 14} × Phase ∈ {0, 10, …, 90}
- **Testset:** (stride, cross, twist) ∈ {(1.0,0,0), (1.4,10,5), (1.6,12,0), (1.2,16,5)} × Phase ∈ {5, 25, 45, 65, 85}.
  Diese Posen werden **nie** zum Rechnen benutzt, nur zum Messen.

### 3.2 Schritt A – Ausstellen hinten (Wade und Oberschenkel-Rückseite)
`local_flare(direction='back', limit=9.0, margin=0.4, above_knee=35.0, front_margin=8.0, fade=45, passes=10)`
- **Region:** Kleid-Punkte unter (Knie + 35 cm) **und** hinter (Beckenmitte + 8 cm) in `forward`-Richtung.
- **10 Durchgänge.** In jedem Durchgang:
  1. Für jeden Punkt den größten Bedarf über alle Trainingsposen bestimmen: `need = max(0.4 − signed_distance)`.
  2. `extra = clip(need, 0, 9)`, nur in der Region.
  3. `extra` mit `smooth_field` glätten (25 Iterationen).
  4. `amount = clip(amount + extra, 0, 9)`.
  5. Zum Rand hin ausblenden: 45-mal `amount = Region ? smooth_field(amount, 1) : 0`.
  6. Verschiebung = **−forward · amount**, also nach hinten.
- **Die Richtung ist fest nach hinten**, nicht entlang der Normale. So bleibt die Silhouette ruhig.

### 3.3 Schritt B – Ausstellen vorn (Schienbein und Oberschenkel-Vorderseite)
`local_flare(direction='front', limit=5.0, margin=0.4, above_knee=(Hüfte − Knie − 5) ≈ 44,3, front_margin=6.0, fade=45, passes=8)`
- Gleiches Verfahren wie bei A, nur gespiegelt nach **+forward**.
- Es wird auf Schritt A **aufaddiert**.

### 3.4 Schritt C – weiche A-Linie am Saum
`column_hem(start_height=86.0, target_half_width=26.5, smooth=30)`
- Unter 86 cm wird jedes 2-cm-Höhenband seitlich (entlang `left`, weg von der Mitte) so skaliert, dass die halbe Breite
  am Saum 26,5 cm erreicht.
- Eingeblendet wird mit Smoothstep ab 86 cm.
- Nur verbreitern, nie schmaler machen. Vorne und hinten bleiben unberührt.

### 3.5 Schritt D – gerade Rückenlinie
`fill_back_line(top_height=95.0, smooth=15)`
- Seitenprofil in 2-cm-Bändern unter 95 cm nehmen. Die hinterste Linie wird durch ihre **konvexe Hülle** ersetzt.
- Dadurch entstehen keine Beulen vom Ausstellen, sondern eine gerade, schräge Linie.
- Verschoben wird nur nach hinten, mit Smoothstep zur Bandmitte hin.

### 3.6 Schritt E – über Mesh-Teile glätten (Pflicht!)
`harmonize_offsets(radius=2.0, iterations=20)`
- Das Kleid besteht aus **16 getrennten Mesh-Teilen**: Außenstoff, Futter (4283 Vertices), Schlitzblenden.
  Offsets, die pro Teil gerechnet werden, lassen den Schlitz **ausfransen**.
- Deshalb wird die Welt-Verschiebung gemittelt über die Mesh-Kanten **und** über alle Punkte im Umkreis von 2 cm,
  auch wenn sie zu einem anderen Teil gehören. Pro Iteration: `d = 0.5·d + 0.5·Mittel`. Danach zurück in Pre-Skin-Offsets.

→ Ergebnis: **v4 mild**

### 3.7 Schritt F – „sehr glatt“ (die finale Version)
`harmonize_offsets(radius=4.0, iterations=100)` auf das Ergebnis von E.
- Dabei wird **nur die Änderung** geglättet, Falten des Original-Meshes bleiben.
- Das Clipping wird dadurch sogar etwas besser.

→ Ergebnis: **v4 mild sehr glatt** = `mcd_kleid_v4_mild_sehr_glatt.json.gz`, **in SL „perfekt“**

### 3.8 Kontrollwerte (zum Prüfen, ob ein Nachbau stimmt)

Sichtbarer Stoff (ohne Futter), Clipping = signed distance < −2 mm, gezählt über alle Testposen:

| Version | Wade | Oberschenkel | Dehnung p99 (Ruhe) |
|---|---|---|---|
| 0.5.3 | 4904 | 7271 | 0 % |
| v3 | 2966 | 5026 | 34 % |
| v4 mild | 2922 | 4621 | 40 % |

| Glätten | Beine gesamt, Testposen | Unruhe p99 |
|---|---|---|
| v4 mild | 7543 | 0,71 mm |
| glatt (r 3 / 40) | 7259 | 0,65 mm |
| **sehr glatt (r 4 / 100)** | **6817** | **0,47 mm** |

### 3.9 Verworfene Wege (nicht wiederholen)
- **Gewichte optimieren** (NNLS, Stufe 1): in SL über 300 gerissene Kanten.
- **Stoff-Bones** (HindLimb an mPelvis, Stufe 2): Sie helfen der Wade nicht, und das Mesh riss.
- **pelvis_carry** (Rock hängt am Becken): ohne Nutzen.
- **v4 stark:** hinten am Oberschenkel 2–3 cm mehr. Das Bein wird besser, aber es steht sichtbar ab.
- **v5:** Brust 8 mm plus Bein vorn 6,5 cm. Vorn wurde es 5 cm tiefer; die Kreatorin hat es abgelehnt.

---

## 4. Body wechseln: Legacy → Reborn (in Maya bestätigt)

Ablauf:
1. Export B: Reborn-Body plus **dasselbe Original-Kleid**, beliebig geriggt.
2. `mcd_fit_deform.py legacy.json.gz reborn.json.gz out.json.gz`, in der Variante „genau“.
3. In der Reborn-Szene `mcd_fit_apply` auf die geriggte Kleid-Kopie anwenden.
4. Die `_fit`-Kopie **neu mit 0.5.3 riggen**.
5. Neu exportieren und die **Rechnung aus Abschnitt 3 unverändert** gegen Reborn laufen lassen.

Deform-Logik:
1. **Achsen-Abgleich** über passende Joints (Kabsch/SVD). Legacy hat Y oben, Reborn Z oben.
   Das Kleid lag danach auf 0,03 mm genau übereinander.
2. **Feld auf dem Quell-Body:**
   - Für jeden Legacy-Vertex: signed distance zur Reborn-Fläche (k = 6). Die Verschiebung ist `−signed · Reborn-Normale`.
   - Gültig nur, wenn alle drei Bedingungen gelten:
     - nächster Abstand < 9 cm
     - Normalen ähnlich (Skalarprodukt > 0,3)
     - Höhe im Bereich, den der Reborn-Body abdeckt (±2 cm); Kopf und Füße fehlen im Devkit
   - Glätten und Lücken füllen: 15 Iterationen über Nachbarn im Umkreis von 2,5 cm. Werte und Gewichte werden getrennt gemittelt.
   - **Achtung:** Mehr Glättung, z. B. 60 Iterationen, lässt den Po zu flach werden.
3. **Kleid:**
   - Gauß-gewichtetes Mittel des Feldes an den 24 nächsten Body-Punkten, mit σ = 1,5 · nächster Abstand (mindestens 1 cm).
   - Danach über Mesh-Teile glätten: Radius 2 cm, 20 Iterationen.
4. **„genau“:** nachschieben entlang der Reborn-Normalen, bis der Originalabstand (0,2–1 cm) wieder stimmt.
   Bedarf glätten mit 40 Iterationen, Verschiebung mit 30 Iterationen, höchstens 12 Durchgänge.

| Reborn-Ergebnis | Wade | Oberschenkel | in Ruhe im Body |
|---|---|---|---|
| ohne Anpassung (nach Deform + 0.5.3) | 5581 | 7530 | 42 |
| **v4 mild sehr glatt** | **3637** | **3455** | **18** |

In SL bestätigt („PERFEKT“). Reborn ist hinten an Taille und Po bis zu 7 cm voller als Legacy.

---

## 5. Prompt für das eigene Tool

Diesen Text kann die Kreatorin in eine neue Claude-Session kopieren, die an ihrem Tool arbeitet:

```
Ich entwickle ein Maya-Tool (Maya 2024, Python 3, numpy; kein scipy) für Second-Life-Kleidung.
In einem früheren Projekt (Repo mayatool, Datei docs/REZEPT_KLEID.md) haben wir ein enges Kleid
mit Schlitz so hinbekommen, dass es in SL beim Gehen (Laufsteg-AO) kaum noch clippt und
NICHT verzerrt. Lies diese Datei vollständig, bevor du irgendetwas baust.

Halte dich strikt an diese Logik:
1. Startpunkt ist immer ein normales Body-Weight-Rig (wie Dress Auto Rig 0.5.3).
   Diese Gewichte werden danach NICHT pro Vertex verändert. Keine Gewichtsoptimierung, keine
   Stoff-Bones – beides hat in SL das Mesh zerrissen.
2. Verbessert wird ausschließlich die RUHEFORM (Pre-Skin-Offsets) bei festen Gewichten:
   - Posen erzeugen (Gangzyklus mit stride/cross wie im Rezept), Trainings- und Testposen getrennt.
   - Pro Kleid-Punkt messen, wie tief er in den Posen im Body steckt (signed distance).
   - In klar begrenzten Regionen nach außen schieben, mit festen Richtungen (hinten/vorn) oder
     Body-Normalen, Obergrenze in cm, mit Ausblenden zum Rand.
   - Formkorrekturen für eine ruhige Silhouette (A-Linie, gerade Rückenlinie).
   - IMMER zum Schluss über alle Mesh-Teile hinweg räumlich glätten (harmonize, Radius 2 cm, dann
     optional "sehr glatt" Radius 4 cm / 100 Iterationen). Sonst franst der Schlitz aus.
3. Anwenden wie mcd_fit_apply: Kopie, gleiche Joints, gleiche geomMatrix und bindPreMatrix,
   gleiche Gewichte, nur neue Pre-Skin-Punkte. Das Original bleibt unverändert.
4. Prüfen mit Zahlen: Clipping (sichtbarer Stoff, < −2 mm) für Wade/Oberschenkel getrennt,
   Dehnung p99, Unruhe der Änderung. Das Ergebnis muss die Kontrollwerte in Abschnitt 3.8 erreichen.

Vorgehen:
Schritt 1: Baue das Rezept aus Abschnitt 3 für genau dieses Kleid in meinem Tool nach und
           zeige, dass die Kontrollwerte erreicht werden (Export-Daten liegen in C:\mcd\daten).
Schritt 2: Erst wenn das stimmt, verallgemeinern für andere Outfits über Profile, nicht über
           fest eingebaute Sonderfälle:
           - Profil = welche Regionen dürfen sich wie weit bewegen, in welche Richtung,
             mit welchen Posen trainiert wird (Gehen, Sitzen, Arme, ...).
           - Enges Kleid/Rock: wie im Rezept (hinten/vorn ausstellen, A-Linie, Rückenlinie).
           - Hose: kein Ausstellen; Abstand an Schritt, Knie, Po entlang Body-Normalen.
           - Oberteil: Abstand an Brust (Avatar-Physik bewegt PEC/BELLY/BUTT), Achseln, Schultern;
             Arm-Posen trainieren.
           Jedes Profil an einem echten Outfit testen, bevor das nächste kommt.
Schritt 3: Body wechseln (Legacy → Reborn usw.) wie in Abschnitt 4: erst Form übertragen,
           dann neu riggen, dann dieselbe Rechnung gegen den neuen Body.

Arbeite in kleinen, einzeln testbaren Modulen. Erkläre mir jeden Schritt einfach auf Deutsch.
Ändere nie die Originalszene; alles entsteht als Kopie.
```
