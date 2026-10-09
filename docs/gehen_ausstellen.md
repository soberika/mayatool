# Gehen: Warum Stoff-Bones hier nicht helfen, und was stattdessen hilft

## Analyse (Thin-Kleid, erzeugter Gangzyklus)

**Wie weit die Wade schwingt:** Die Wadenmitte bewegt sich pro Schritt relativ zum Becken um **48,7 cm** vor und zurück (−18 cm bis +31 cm).

**Wohin das Clipping zeigt:** Wo der Unterschenkel durch den Stoff geht, braucht der Stoff je nach Gangphase eine andere Richtung:
- in den meisten Phasen (10–30 %, 60–80 %) **nach hinten**;
- bei **50 % nach vorn** (79 % der betroffenen Vertices).

**Was eine Stoffebene in SL kann:** Die nutzbaren Zusatz-Bones (HindLimb, Tail, Groin) hängen fest am Becken, ihre Eltern lassen sich nicht ändern. Die eigene AO steuert die Beine. Eine Overlay-Animation weiß deshalb nicht, in welcher Gangphase welches Bein ist. Sie kann pro Zustand („Gehen“) nur eine **feste** Verschiebung relativ zum Becken setzen.

**Folge:**
1. Stoff, der an einem Stoff-Bone hängt, folgt der Wade nicht mehr. Bei 48 cm Schwung geht dann das Schienbein vorn durch, sobald das Bein nach vorn schwingt.
2. Lässt man den Stoff überwiegend an den Beinen hängen und gibt nur einen kleinen Stoff-Bone-Anteil dazu, bewegt dieser Anteil die betroffenen Stellen um höchstens Anteil × Verschiebung, hier etwa 0,3 × 3 cm = 1 cm. Und das immer in dieselbe Richtung, auch in der Phase, die „nach vorn“ braucht.
3. Mehr Freiheit pro Vertex (verschiedene Anteile bei Nachbarn) reißt das Mesh auf. Das wurde in SL beobachtet und nachgemessen.

**Bewertung:** Mit der eigenen AO, festen Bento-Eltern und höchstens 4 Einflüssen ist eine beckenfeste Stoffebene für die **Wade beim Gehen eines engen, langen Rocks** nicht wirksam.

**Grundsätzlich unmöglich ist es nicht.** Es ginge, wenn:
- Gang und Stoffspur in **einer** Animation lägen (eigener Walk statt AO, verworfen), oder
- der betroffene Stoff der Wade nicht folgen muss (weite oder ausgestellte Röcke, Schleppen).

## Was stattdessen hilft: lokales Ausstellen der Ruheform

`mcd_fit_solver.local_flare`:
- Die **0.5.3-Gewichte bleiben unverändert**, deshalb gibt es keine Risse durch Gewichte.
- Nur der Rock **unterhalb Knie + 15 cm** und **hinter der Seitenlinie** wird glatt nach hinten versetzt, so weit die Waden es in den Gangposen brauchen. Am Rand läuft das weich aus.
- Weil der Versatz in der Ruheform liegt, dreht er mit dem Bein mit und steht in jeder Gangphase hinter der Wade.

| Variante | Unterschenkel-Clipping (11 Gangphasen, Vertices gesamt) | Außensilhouette |
|---|---|---|
| 0.5.3 | 2095 | – |
| bis 1,5 cm | 1509 (−28 %) | unverändert (Rückenlinie ±0,2 cm) |
| bis 2,5 cm | 1141 (−46 %) | unverändert (Rückenlinie ±0,2 cm) |

**Pro Gangphase (2,5 cm):**
- 65 %: 228 → 56
- 75 %: 220 → 54
- 10 %: 198 → 30
- 20 %: 373 → 324 (kaum besser)
- 50 %: 43 → 83 (schlechter; diese Phase bräuchte „nach vorn“)

**Ruheform:** Nur Kanten unter 1 mm Länge ändern sich relativ stark, absolut höchstens 1,2 mm.

## Rückmeldung SL (2,5 cm): besser, aber noch nicht genug. Stärkere Stufen

Trainiert jetzt auch auf großen Schritten (Faktor 1,25), Bereich bis Knie + 20 cm.

| Variante | Wade normal | Wade große Schritte | Rückenlinie außen | Dehnung in Ruhe |
|---|---|---|---|---|
| 2,5 cm | −46 % | −12 % | bis 2,0 cm (nur ganz unten am Saum) | fast keine |
| **4 cm** | **−65 %** | **−31 %** | bis 3,5 cm | Streifen an der Seitenkante ca. 20–30 % gedehnt (p99 11 %) |
| 5,5 cm | −73 % | −51 % | bis 4,5 cm | wie 4 cm, etwas stärker (p99 15 %) |

Die Breite von hinten bleibt bei allen Varianten unverändert.

## Rückmeldung SL (5,5 cm): Dehnung fällt nicht auf, darf weiter gehen

Trainiert auf Schrittweiten ×1,0 / ×1,25 / ×1,4. Neu ist eine kleine Zugabe **vorn** unterhalb des Knies für die Phase, in der das Schienbein nach vorn drückt.

| Variante | Wade ×1,0 | ×1,25 | ×1,4 | Rückenlinie | Vorderlinie | Breite | Dehnung p99 |
|---|---|---|---|---|---|---|---|
| 5,5 cm (getestet) | −66 % | −46 % | −23 % | +4,5 cm | 0 | 0 | 15 % |
| hinten 7,5 | −64 % | −59 % | −40 % | +6,1 cm | 0 | 0 | 21 % |
| **hinten 7,5 / vorn 2** | **−73 %** | **−66 %** | **−46 %** | +6,1 cm | +0,7 cm | 0 | 22 % |
| hinten 9 / vorn 2,5 | −74 % | −71 % | −58 % | +6,9 cm | +0,8 cm | 0 | 26 % |

## Referenzbild: Säulenrock statt nach unten enger Saum

Das Design-Referenzbild zeigt einen Rock, der von der Hüfte **gerade** fällt, unten eher etwas weiter. Gemessen ist das Thin-Kleid in der Grundpose:
- Es wird unterhalb von etwa 20 cm Höhe enger, von 39 auf 36,6 cm Breite.
- Die Rückenlinie hatte durch das Ausstellen eine Beule unterhalb des Knies.

**Neue Werkzeuge** in `mcd_fit_solver`:
- `column_hem`: Der Rock wird unterhalb einer Höhe seitlich glatt bis zur Zielbreite geweitet.
- `fill_back_line`: Die Rückenlinie wird durch ihre konvexe Hülle ersetzt. Dadurch entstehen gerade Segmente statt Beule.
- `straight_back`: parametrische gerade Rückenlinie. Am Thin-Kleid wirkungslos, weil die Wade die Innenfläche trifft, nicht die äußere Rückenlinie.

**Wadenclipping** (Vertices über 13 Gangphasen):

| Variante | Schritte ×1,0 | ×1,25 | ×1,4 |
|---|---|---|---|
| 0.5.3 | 2113 | 2900 | 3151 |
| 7,5 hinten / 2 vorn | 567 | 1025 | 1642 |
| **+ Säule 45 cm + gerade Rückenlinie** | **233** | **511** | **944** |

Dehnung in Ruhe p99 28 %. Die Silhouette folgt jetzt der Säulenform des Referenzbildes.

## Referenzbild vermessen: Es ist eine weiche A-Linie, keine Säule

Gemessen wurden die Breitenprofile der Vorder- und Rückansicht im Referenzbild (Pixel, Stoff per Farbe getrennt). Bezugswert ist die Breite am Oberschenkel, knapp unter den Händen.

| Höhe (Oberschenkel 0,25 → Saum 0,85) | 0,25 | 0,50 | 0,70 | 0,85 |
|---|---|---|---|---|
| Referenz vorn | 1,00 | 1,08 | 1,17 | 1,25 |
| Referenz hinten | 1,00 | 1,09 | 1,16 | 1,21 |
| 0.5.3 | 1,00 | ≈0,99 | ≈0,95 | ≈0,95 (wird enger) |
| Säule (letzte Variante) | 1,00 | ≈1,00 | ≈1,02 | 1,04 |
| **A-Linie Saum 53 cm ab 86 cm** | 1,00 | ≈1,05 | ≈1,11 | 1,16 |

Das Referenzbild ist ein 2D-Rendering mit Perspektive. Die Werte sind deshalb Näherungen von etwa ±3 %.

**Wadenclipping** (Vertices über 13 Gangphasen, Schritte ×1,0 / ×1,25 / ×1,4):

| Variante | ×1,0 | ×1,25 | ×1,4 |
|---|---|---|---|
| 0.5.3 | 2113 | 2900 | 3151 |
| Säule | 233 | 511 | 944 |
| **A-Linie** | **30** | **328** | **716** |

Dehnung in Ruhe: p99 36 %.

**Was SL-Kreatoren zu langen Röcken schreiben** (Forenrecherche):
- Clipping zwischen den Beinen gilt als bekanntes Problem.
- Die Mittelzonen vorn und hinten zwischen den Beinen werden stark gedehnt. Empfohlen werden dort mehr Geometrie und weich abgestufte Gewichte (Mitte 0,5/0,5, nach außen abgestuft).
- Manche Kreatoren riggen den Rock stärker auf das Becken.
- Als Notlösungen werden eine Alpha-Ebene oder eine passende Unterhose bzw. ein Unterrock genannt.

## SL-Video der A-Linie: Rücken gut, Schlitz ausgefranst. Ursache und Korrektur

**Beobachtung im SL-Video:**
- Der Rücken fällt als ruhige, leicht ausgestellte Säule, nah an der Referenz.
- Am Schlitz hängen dünne Streifen und Zacken herunter.
- Bei gekreuzten Beinen kommt der Oberschenkel durch das vordere Stoffteil.

**Ursache der Streifen:** Das Kleid besteht aus mehreren getrennten Mesh-Teilen:

| Teil | Vertices |
|---|---|
| Hauptteil | 34 426 |
| Unterlage | 4 283 |
| Schlitzstreifen | 527 und 495 |

Die Formänderung wurde nur entlang von Mesh-Kanten geglättet, also pro Teil. Übereinanderliegende Teile wichen dadurch bis zu **6,2 cm** voneinander ab.

**Korrektur:** `harmonize_offsets` mittelt die Verschiebung über Kanten **und** räumliche Nachbarn im Radius 2 cm.

| | Teil-Versatz Ruhe (max) | Teil-Abstand beim Gehen (max) | Wade ×1,0 / ×1,25 / ×1,4 |
|---|---|---|---|
| A-Linie vorher | 6,2 cm | 6,1 cm | 30 / 328 / 716 |
| **A-Linie harmonisiert** | **0,5 cm** | **0,4 cm** | 45 / 363 / 748 |

**Lehre für das Tool:** Jede Formänderung muss über getrennte Mesh-Teile hinweg geglättet werden. Mesh-Kanten allein reichen nicht.

**Noch offen:** Bei gekreuzten Beinen im Stand drückt der Oberschenkel durch das vordere Stoffteil am Schlitz. Das ist ein eigener Bereich: vorn, oberhalb des Knies.
