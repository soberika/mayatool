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
