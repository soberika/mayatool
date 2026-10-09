# Kleidung und Bewegung als ein Designproblem

Konzeptpapier für die Weiterentwicklung von *mcd. Dress Auto Rig* (aktuell 0.4).
Noch kein Code. Stand: Oktober 2026.

> Leitfrage: **Welche Kleidung könnten wir erschaffen, wenn wir ihre Geometrie,
> ihre Gewichtsverteilung und ihre Bewegungen als ein gemeinsames Designproblem
> behandeln?**

Kurze Antwort vorweg: Kleidung, deren auffälligstes Verhalten nicht trotz,
sondern wegen der Bewegung entsteht. Ein Schlitz, der sich in einer bestimmten
Gangphase öffnet und sich danach wieder schließt. Eine Säulensilhouette, die beim
Gehen erhalten bleibt, weil Gang und Rock aufeinander abgestimmt sind. Straps,
die einen Moment lang „arbeiten“. Second Life kann so etwas zur Laufzeit nicht
simulieren. Wir können es aber **vorab gemeinsam lösen und in Gewichte, Geometrie
und Animationsspuren einbacken**, die SL abspielen kann.

---

## 0. Was Second Life zur Laufzeit wirklich kann

Diese Grenzen gelten für alle Konzepte. Geprüft am offiziellen Viewer-Quellcode
von Linden Lab (`github.com/secondlife/viewer`, Stand Oktober 2026), an den
Release Notes und am SL-Wiki, soweit es erreichbar war:

| Fakt | Quelle |
|---|---|
| Skelett: 133 Bones + 26 Collision Volumes | `indra/newview/character/avatar_skeleton.xml` |
| Max. 110 Gelenke pro geriggtem Mesh-Objekt | `indra/llcharacter/lljoint.h` (`LL_MAX_JOINTS_PER_MESH_OBJECT = 110`), Wiki „Limits“ |
| Max. 4 Gewichte pro Vertex | Viewer-Release-Notes 7.1.14 / 7.2.0, Wiki „Mesh Asset Format“ |
| `mTail1–6`, `mGroin`, `mHindLimbsRoot` (+ 2×4 HindLimb-Bones) hängen an `mPelvis`; `mWingsRoot` (+ Wing-Bones) hängt an `mChest` | `avatar_skeleton.xml` |
| Animation: max. 60 s; Größe max. 250 000 Byte nach Konvertierung | `llbvhconsts.h` (`MAX_ANIM_DURATION = 60`), Wiki „Limit“ |
| `.anim` enthält pro Gelenk eine eigene Priorität sowie Rotations- **und Positionskeys** (Position auf ±5 m geklemmt, 16-Bit-quantisiert) | `llkeyframemotion.cpp`, `lljoint.h` (`LL_MAX_PELVIS_OFFSET = 5`), Wiki „Internal Animation Format“ |
| BVH-Upload: Positionskanäle sind laut Quellkommentar **nur für `mPelvis`** vorgesehen. Für Positionsspuren anderer Bones brauchen wir den direkten `.anim`-Export. | `llbvhloader.cpp` |
| Standard-Upload: globale Priorität 0–4, keine UI für Prioritäten pro Bone | Wiki „Animation Priority“ |
| Avatar-Physik bewegt per *volume morph* nur `LEFT_PEC`, `RIGHT_PEC`, `BELLY`, `BUTT`. Die Parameter kommen aus dem Physics-Wearable des Trägers. | `avatar_lad.xml`, `llphysicsmotion.cpp` |
| Animesh-Attachment: hat **ein eigenes Skelett**, dessen Wurzel dem Attachment-Punkt folgt, und spielt **eigene** Animationen. Es folgt nicht den Beinen des Trägers. | `llcontrolavatar.cpp` |
| Animesh-Attachments pro Avatar: 1 (Basic/Plus), 2 (Premium), 3 (Premium Plus) | Wiki „Limits“ |
| Das Dreieckslimit für Animesh legt die Region fest; der Viewer fragt es ab | `llvovolume.cpp` (`getAnimatedObjectMaxTris`) |

**Was es nicht gibt (und was wir deshalb nicht verwenden):**
- keine Laufzeit-Stoffsimulation für Mesh-Kleidung (Flexi gibt es nur für Prims, nicht für Mesh);
- keine Blendshapes oder Pose-Space-Korrekturen für hochgeladenes Mesh;
- keine skriptbaren Deformer;
- keine zusätzlichen Bones.

**Was es gibt:**
- lineares Skinning (LBS) auf festen Bones;
- Keyframe-Animationen, die sich pro Bone nach Priorität überlagern, mit Ease-In/Out;
- Skripte, die Animationen starten (für Attachments des Trägers ohne Rückfrage) und Faces ein- oder ausblenden;
- Collision-Volume-Verformung durch Shape-Slider und Avatar-Physik;
- Animesh.

**Die eine Laufzeitgrenze, die alle Konzepte prägt:** Zwei getrennt gestartete
Animationen oder eine Animation und ein Skriptbefehl sind auf fremden Viewern
**nicht bildgenau synchron**. Was zeitlich zusammenpassen muss, gehört **in
dieselbe Animationsdatei**.

> Noch offen: Dass Positionskeys auf Nicht-Pelvis-Bones aus einer direkt
> hochgeladenen `.anim` abgespielt werden, ergibt sich aus dem Code. Für unseren
> Fall testen wir es trotzdem als ersten Schritt im Prototyp (Abschnitt 4, Stufe 0),
> bevor wir darauf aufbauen.

---

## 1. Sechs Tool-Konzepte

Jedes Konzept trennt vier Ebenen:
- **Tool**: was nur in Maya passiert;
- **Export**: was als Geometrie, Gewichte oder Animation hinausgeht;
- **Laufzeit**: was SL ausführt;
- **Kompromisse**: welche Einschränkungen, Konflikte und sichtbaren Folgen entstehen.

### K1 – Multi-Pose-Fit: feste Gewichte *und* Ruhegeometrie aus korrigierten Zielposen

**Neue Möglichkeit.** Die Kreatorin korrigiert das Kleid in 5–8 Schlüsselposen von Hand: Sie zieht Vertices aus dem Körper und formt die Falte am Knie so, wie sie aussehen soll. Das Tool sucht dann **eine** feste Gewichtsverteilung und eine **leicht veränderte Ruheform**, die alle Korrekturen zusammen möglichst gut wiedergeben. Der Unterschied zum üblichen Vorgehen: Normalerweise übernimmt man Gewichte vom Körper und malt dann nach, wobei jede Korrektur eine andere Pose verschlechtern kann. Hier ist der Zielkonflikt zwischen den Posen Teil der Rechnung. Die Ruheform darf sich um wenige Millimeter vom Design entfernen, wenn das die Posen deutlich verbessert.

**Kleidungsstück.** Enges Etuikleid mit Schlitz links, getestet in Gehen, Sitzen auf der Kante und Knie-über-Knie. Die Rückseite unter dem Gesäß bekommt in Ruhe ein paar Millimeter Luft, die man in der A-Pose kaum sieht. Dafür taucht sie beim Sitzen nicht mehr in den Oberschenkel ein.

**Mechanismus.** Minimiert wird
Σ_Pose Σ_Vertex ‖ Σ_j w_ij · M_j(p) · (v_i + d_i) − t_i(p) ‖²
plus eine Glättung der Gewichte entlang der Mesh-Kanten, die Schlitzkanten **nicht** verbindet (wie in 0.4), eine Strafe für Eindringen in den Körper, eine Begrenzung |d_i| ≤ δ und eine Strafe für Silhouettenänderung in Ruhe. Nebenbedingungen: w ≥ 0, Σw = 1, höchstens 4 Einflüsse.

Gelöst wird abwechselnd. Bei festem d werden die Gewichte pro Vertex als kleines QP berechnet. Bei festen Gewichten ergibt sich d linear. Kandidaten-Bones sind die 0.4-Rolle plus deren Nachbarn und die Collision Volumes. Optional rechnet das Tool über 2–3 Shape-Varianten mit skalierten Collision Volumes, damit die Shape-Slider das Ergebnis nicht zerstören.

**Eingaben und Ablauf.**
1. Ergebnis von 0.4 als Startwert.
2. Posenbibliothek auswählen.
3. In jeder Pose eine Korrektur sculpten (Maya Sculpt oder Blendshape-Ziel als reiner Datenträger).
4. Solver ausführen.
5. Fehler-Heatmap pro Pose ansehen und Gewichtung der Posen anpassen.

**Output.** Ein normal geriggtes Mesh mit geänderter Ruhegeometrie und neuen Gewichten. Keine Animation.

| Ebene | Inhalt |
|---|---|
| Tool | Posen, Sculpts, Solver, Heatmaps |
| Export | Mesh + Gewichte (DAE wie bisher) |
| Laufzeit | normales LBS |
| Kompromisse | LBS kann widersprüchliche Korrekturen nur mitteln. Wo Gehen und Sitzen Gegensätzliches verlangen, gewinnt keine Pose ganz. Die Ruheform weicht sichtbar, wenn auch wenig, vom Entwurf ab. |

**Wichtigster Fehlschlag.** Überanpassung: Die Trainingsposen sehen besser aus, ungesehene Posen schlechter als vorher. Das gilt besonders für Rotationen um die Längsachse (Candy-Wrapper am Oberschenkel).

**Kleiner Versuch.** Nur der Rockteil, 5 Trainings- und 3 Testposen. Wir messen Clipping und Kantenverzerrung gegen 0.4. Erfolg heißt: Die Testposen werden nicht schlechter und die Trainingsposen deutlich besser.

---

### K2 – Phantom-Stoffbones → Bento-Bake

**Neue Möglichkeit.** In Maya bekommt der Rock beliebig viele *virtuelle* Stoff-Bones oder eine nCloth-Simulation. Das Tool **zerlegt** diese Bewegung anschließend auf ein kleines, festes Budget **echter, ungenutzter Bento-Bones** an `mPelvis`: `mHindLimb1–4 L/R`, `mHindLimbsRoot`, `mTail1–6`, `mGroin`, bei Bedarf zusätzlich Wing-Bones am Oberkörper. Exportiert wird das Ergebnis als **Gewichte plus Rotations- und Positionsspuren** dieser Bones.

Was das von bekannten Verfahren unterscheidet:
- Die Zerlegung einer Simulation in starre Bones mit linearem Skinning ist bekannt (Smooth Skinning Decomposition, Le & Deng 2012, in Spielen verbreitet).
- Röcke auf Tail- oder HindLimb-Bones zu riggen gibt es in SL auch schon.
- Neu ist die Kombination: Die Zerlegung arbeitet unter **SL-Bedingungen**. Höchstens 4 Einflüsse werden **gemeinsam** mit den Körperbones vergeben, das Bone-Budget ist fest, die Ruhegeometrie ist fest. Und weil Bento-Bones animierbare Positionen haben, kann **jede starre Transformation** pro Frame dargestellt werden, also auch Pivots, die weit vom Standard-Gelenkort entfernt liegen.

**Kleidungsstück.** Bleistiftrock mit vorderem Schlitz. Zwei HindLimb-Ketten steuern die beiden Schlitzkanten, die Tail-Kette den hinteren Saum. Beim Gehen schwingt der Saum leicht nach, statt starr am Oberschenkel zu kleben.

**Mechanismus.**
1. Simulation oder Keyframes der Phantom-Bones über einen Clip.
2. Residuum bilden: Simulation minus K1- oder 0.4-Körperskinning.
3. SSDR-artige Zerlegung des Residuums auf N ≤ 12 starre Bones, mit zeitlicher Glättung und Gewichtsbudget.
4. Weltmatrizen in lokale Keys relativ zur Elternkette umrechnen und in `.anim` schreiben.

Die Cloth-Bones sind **gegen die Standardpositionen des Skeletts gebunden**, ohne Joint-Offset-Upload. Ohne laufende Animation zeigt der Rock deshalb einfach seine Ruheform.

**Eingaben und Ablauf.** Kleid und Animation; Phantom-Bones oder nCloth einstellen; Bone-Set wählen (Tail, HindLimb, Wings); Budget wählen; zerlegen; Fehler und Animation prüfen.

**Output.** Mesh mit Gewichten (Körper- und Cloth-Bones) plus `.anim`, das **nur** die Cloth-Bones keyt.

| Ebene | Inhalt |
|---|---|
| Tool | Simulation, Zerlegung, Bone-Budget |
| Export | Mesh + Gewichte, `.anim` mit Rotations- und Positionskeys |
| Laufzeit | LBS + Keyframe-Abspielen; keine Physik |
| Kompromisse | Belegt Bones, die Tails, Flügel oder Vierbeiner-Avatare und deren AOs ebenfalls nutzen. Zwei Kleidungsstücke mit demselben Bone-Set vertragen sich nicht. Animiert ein anderes Objekt die Bones mit höherer Priorität, verzieht sich der Rock. Ohne Kopplung an den Gang läuft die Saumbewegung **nicht** synchron zu den Beinen des AO. |

**Wichtigster Fehlschlag.** Der Desync. Eine nachschwingende Saumkurve, die nicht zur Beinphase passt, wirkt schlimmer als ein starrer Rock.

**Kleiner Versuch.** nCloth-Rock über einen Gehzyklus, zerlegt mit 4 / 8 / 12 Bones. Wir vergleichen Fehlerkurven und Renderings und prüfen den Uploadtest in SL mit einem einzelnen Positionskey-Bone.

---

### K3 – Choreografierter Gang: Kleid und Animation gemeinsam optimieren

**Neue Möglichkeit.** Wir passen nicht das Kleid an einen beliebigen Gang an, sondern lösen **Gang, Gewichte und Saumspuren gemeinsam**. Das Kleid bekommt eine *Signature Walk*, in der der Schlitz gezielt arbeitet: Er öffnet sich kurz vor dem Fersenaufsatz des vorderen Beins und schließt sich in der Standphase. Gleichzeitig bleibt die Säulensilhouette in Front- und Seitenansicht erhalten.

**Kleidungsstück.** Bodenlanges Säulenkleid mit hohem Schlitz rechts und zwei Straps über dem Schlitz.
- Beim Gehen setzt der Fuß leicht über die Mittellinie, wie beim Catwalk.
- Das Becken rollt eine Spur stärker.
- Der Schlitz öffnet sich einmal pro Doppelschritt auf der rechten Seite.
- Die Straps spannen sich in diesem Moment sichtbar über das Bein.
- Links bleibt die Linie geschlossen.

**Mechanismus.**
- **Basisgang**: eigene Keyframes oder lizenziertes Mocap.
- **Wenige Stilparameter θ** statt freier Keys, etwa 4–8: Schrittlänge, Fußkreuzung, Beckenrolle und -gier, Kniehub, Phasenverschiebung Becken/Bein, Oberkörper-Gegenrotation.
- **Zielfunktion** J(θ, w, Cloth-Spuren):
  - Schlitzöffnung zur Wunschphase (Abstand der Schlitzkanten bzw. sichtbare Beinfläche aus Kamerasicht);
  - Silhouettenfehler gegen eine Zielmaske aus 3 orthografischen Ansichten;
  - Eindringtiefe in den Körper;
  - Natürlichkeit: Abweichung vom Basisgang, Gelenkgrenzen, Fußgleiten bezogen auf die von SL vorgegebene Laufgeschwindigkeit, Ruck/Jerk.
- **Optimierung** ableitungsfrei (z. B. CMA-ES) über θ. Jede Auswertung ist schnell, weil LBS in NumPy ohne Maya-Deformer gerechnet wird. In der inneren Schleife werden K1-Gewichte und K2-Cloth-Spuren bei festem θ nachgezogen.
- **Kernpunkt**: Körperbones und Cloth-Bones stehen **in derselben `.anim`**. Damit sind sie bildgenau phasengleich. Das ist der einzige Weg, auf dem SL eine an den Gang gekoppelte Stoffbewegung zuverlässig abspielt.

**Eingaben und Ablauf.**
1. Kleid und Basisgang laden.
2. Die Kreatorin markiert Schlitzkanten und Straps und legt **Designabsichten** fest: „Schlitz rechts auf bei 40–55 % der Phase, Silhouette vorne ±1 cm“.
3. Parametergrenzen setzen.
4. Optimieren.
5. 3–5 Varianten nebeneinander vergleichen (Turntable + Phasenstreifen) und auswählen.
6. Von Hand nachkeyen ist erlaubt. Danach rechnet das Tool nur die Cloth-Spuren neu.

**Output.** Rigged Mesh (Körper- + Cloth-Bones); eine geloopte Walk-`.anim` mit Körper- und Cloth-Bones; optional Stand- und Turn-Varianten; ein kleines Dress-Skript, das die Walk-Animation startet und stoppt (bzw. Notecard-Einträge für gängige AOs).

| Ebene | Inhalt |
|---|---|
| Tool | Stilparameter, Zielfunktion, Optimierer, Variantenvergleich |
| Export | Mesh + Gewichte; `.anim` mit Bein-, Becken- **und** Cloth-Bone-Spuren; Skript oder AO-Eintrag |
| Laufzeit | Keyframes + LBS, Start über Skript oder AO |
| Kompromisse | Die Walk **ersetzt** die AO-Walk der Trägerin. Bei gleicher Priorität gewinnt die zuletzt gestartete Animation, im Zweifel braucht es eine höhere Priorität (Konflikt mit AOs). Übergänge Stand ↔ Walk laufen nur über Ease-In/Out, also lineare Blends ohne physikalisches Nachschwingen. Die Schrittlänge muss zur SL-Laufgeschwindigkeit passen, sonst rutschen die Füße. Sitzen, Tanzen und Fremdposen sind nicht co-designt und fallen auf K1-Qualität zurück. |

**Wichtigster Fehlschlag.** Die Bewegung wirkt choreografiert-künstlich: zu deutlich und zu regelmäßig. Oder sie wird im Alltag gar nicht gesehen, weil die AO sie überschreibt.

**Kleiner Versuch.** Ein Gehzyklus, 4 Stilparameter, eine Zielgröße: Schlitzöffnung zur Phase. Wir vergleichen den unoptimierten und den optimierten Gang mit identischem Kleid. Blindvergleich durch dich und zwei weitere Personen: „Welche Variante zeigt den Schlitz bewusster, ohne unnatürlich zu gehen?“

---

### K4 – Silhouetten-Zustände: Kleid mit Modi und Übergängen

**Neue Möglichkeit.** Ein Kleid hat diskrete Zustände, zum Beispiel *geschlossene Säule*, *Schlitz geöffnet und Panel zurückgeschlagen*, *Schleppe gerafft*, und **sichtbare Übergänge** dazwischen. Das ist mehr als ein Alpha-Wechsel per HUD: Ein Panel klappt über Cloth-Bones um, und erst wenn es geometrisch deckungsgleich mit der Alternativgeometrie ist, schaltet das Skript die Faces um.

**Kleidungsstück.** Wickelrock, dessen vorderes Panel per HUD auf- und zugeschlagen wird. Im offenen Zustand ist es mit einem Strap an der Hüfte „festgesteckt“.

**Mechanismus.**
- Zustandsposen der Cloth-Bones werden als kurze, geloopte **Halte-Animationen** gespeichert. Sie keyen nur die Cloth-Bones, mit hoher Priorität.
- Übergangsanimationen dauern etwa 0,6–1,2 s.
- Geometrie, die durch Bones nicht erreichbar ist (umgeschlagene Innenseite, Strap im festgesteckten Zustand), liegt als **eigene Faces** vor. SL erlaubt bis zu 8 Faces pro Mesh-Objekt.
- Das Skript startet die Übergangsanimation und schaltet die Alpha-Faces erst nach dem Übergang um.
- **Das Tool erzwingt eine Übergabe ohne sichtbaren Unterschied:** Am Umschaltpunkt fallen alte und neue Geometrie zusammen. Ein Timing-Fehler zwischen Skript und Animation fällt dann nicht auf.

**Eingaben und Ablauf.** Zustände modellieren, Übergänge keyen, Übergabezeitpunkte markieren. Das Tool prüft die Deckungsgleichheit und meldet sichtbare Sprünge.

**Output.** Mesh mit Face-Aufteilung, Halte- und Übergangsanimationen, Zustandsskript plus HUD.

| Ebene | Inhalt |
|---|---|
| Tool | Zustandsgraph, Übergabeprüfung |
| Export | Mesh mit Face-Struktur, mehrere `.anim`, LSL-Skript |
| Laufzeit | Animationen + `llSetAlpha`/`llSetLinkAlpha` |
| Kompromisse | Die Laufzeitsynchronisation ist ungenau, deshalb nur „robuste“ Übergaben. Halte-Animationen belegen die Cloth-Bones dauerhaft, was mit K3 und mit Tails kollidiert. Unsichtbare Faces kosten trotzdem Dreiecke und Komplexität. |

**Wichtigster Fehlschlag.** Auf fremden Viewern sieht man kurz beide oder keine Geometrie.

**Kleiner Versuch.** Ein Panel, zwei Zustände. Zwei Avatare beobachten den Wechsel 20-mal und zählen sichtbare Sprünge.

---

### K5 – Dehnungsgetriebener Entwurf: das Tool schlägt Schlitze, Falten und Einsätze vor

**Neue Möglichkeit.** Statt nur zu fragen, wie man ein Kleid besser riggt, fragt das Tool, **welche Konstruktion** unter LBS und dem gewünschten Bewegungsumfang gut aussieht. Es misst über eine Bewegungsbibliothek die Dehnung und Stauchung pro Fläche sowie Eindringzonen. Daraus leitet es Konstruktionsvorschläge ab:
- Schlitzlage und -höhe;
- verdeckte Faltenzüge (Kellerfalte mit Untertritt);
- Godets und Einsätze;
- Stellen, an denen ein Strap Material „hält“.

Nachgefragt wird also das Schnittmuster, nicht die Gewichtung.

**Kleidungsstück.** Etuikleid. Das Tool zeigt, dass ein Schlitz 4 cm weiter hinten und 6 cm höher die Kniedehnung beim Sitzen halbiert. Alternativ schlägt es eine Kellerfalte hinten vor, deren Innenlage nur in Bewegung sichtbar wird.

**Mechanismus.** Statistik über Posen und Clips: Dehnungsfeld, Eindringfeld, Sichtbarkeitsfeld aus Kameras. Für Kandidaten-Schnitte gibt es eine schnelle Neuberechnung: Mesh an Kandidatenkante auftrennen, K1-Gewichte neu lösen, bewerten. Ergebnis ist ein Ranking mit Vorher/Nachher-Overlay.

**Eingaben und Ablauf.** Kleid, Bewegungsbibliothek, Zonen, an denen der Entwurf **nicht** geändert werden darf. Die Kreatorin wählt Vorschläge aus und modelliert sie selbst sauber nach. Das Tool schneidet nur grob zur Bewertung.

**Output.** Indirekt: ein verbessertes Mesh aus dem eigenen Modelling-Schritt, danach K1-Gewichte.

| Ebene | Inhalt |
|---|---|
| Tool | Analyse und Vorschläge |
| Export | normales Mesh + Gewichte |
| Laufzeit | LBS |
| Kompromisse | Vorschläge können modisch falsch sein. Verdeckte Untertritte können je nach Pose doch sichtbar werden. Mehr Kanten und Faces kosten Dreiecke. |

**Wichtigster Fehlschlag.** Das Tool optimiert gegen Messgrößen, die nicht das ausdrücken, was gut aussieht.

**Kleiner Versuch.** Drei Schlitzpositionen am gleichen Kleid, je mit K1 gelöst. Wir vergleichen das Ranking des Tools mit deinem eigenen Ranking.

---

### K6 – Hybrid-Baukasten: Animesh-Schleppe, starre Ornamente, Physik-Volumes

**Neue Möglichkeit.** Wir ordnen Kleidungsteile nach **Synchronitätsbedarf** einer passenden Technik zu und lassen das Tool den Übergang zwischen den Teilen planen:

1. **Körpernah, muss exakt folgen** → geskinnt (K1).
2. **Körperfern, phasengekoppelt** → Cloth-Bones in derselben Animation (K2/K3).
3. **Körperfern, darf frei laufen** (Schleppe, Fächer, Cape-Ende hinter dem Körper) → **Animesh-Attachment** mit eigenem Skelett und eigener Loop. Es folgt starr dem Attachment-Punkt, zum Beispiel dem Becken.
4. **Weiche, physikalisch wirkende Mitbewegung** an Gesäß, Bauch und Brust → Gewichtsanteile auf `BUTT`/`BELLY`/`*_PEC`. Die Avatar-Physik bewegt diese Volumes tatsächlich, Stärke und Charakter bestimmt aber das Physics-Wearable der Trägerin.

**Kleidungsstück.** Abendkleid mit langer, separater Schleppe als Animesh, die in einer langsamen Loop auf dem Boden „atmet“. Dazu ein Peplum, das über `BUTT` bei aktivierter Physik leicht mitfedert, und ein Strap-Gurt, der starr am Becken geskinnt ist.

**Mechanismus.** Zerlegungsassistent: Das Kleid wird in Zonen geteilt. Pro Zone wählt das Tool die Technik und prüft die **Nahtstelle**: Wo Animesh-Teil und geskinnter Teil aneinanderstoßen, muss die Naht beim Desync verdeckt bleiben, etwa durch Überlappung, Rüsche oder Gürtel. Für die Physik-Zone simuliert das Tool die Volume-Auslenkung über einen Bereich typischer Physik-Einstellungen und begrenzt die Gewichte so, dass auch hohe Werte keinen Riss erzeugen.

**Output.** Mehrere Objekte: rigged Mesh, Animesh-Objekt mit eigenen Animationen und Skript, Hinweise zu den Physik-Layern.

| Ebene | Inhalt |
|---|---|
| Tool | Zonenplanung, Nahtprüfung, Physik-Bereichstest |
| Export | Mehrere Meshes, Animesh-Animationen, Skript |
| Laufzeit | Animesh spielt eigene Animationen, Avatar-Physik wirkt auf die Collision Volumes |
| Kompromisse | Animesh folgt **nicht** den Beinen und ist **nicht** phasengleich mit dem Gang. Animesh-Attachments sind pro Konto auf 1–3 begrenzt und erhöhen die Komplexität. Die Physik-Stärke kontrolliert die Trägerin, nicht wir. |

**Wichtigster Fehlschlag.** Die Nahtstelle zwischen Animesh- und Körperteil reißt oder überlappt sichtbar.

**Kleiner Versuch.** Animesh-Schleppe an `Pelvis` bei Gehen, Drehen und Hinsetzen. Wir dokumentieren, wo die Schleppe durch Beine oder Boden geht und ob eine Überlappungsnaht das kaschiert.

---

## 2. Auswahl

| Konzept | Kreatives Potenzial | Machbarkeit (SL + Maya) | Nutzen für eine einzelne Kreatorin |
|---|---|---|---|
| K1 Multi-Pose-Fit | mittel | hoch | hoch (ersetzt Nachmalen) |
| K2 Cloth-Bone-Bake | hoch | mittel–hoch | mittel (Bone-Konflikte) |
| **K3 Choreografierter Gang** | **sehr hoch** | **mittel** | **hoch, wenn als Paket verkauft** |
| K4 Zustände | hoch | mittel | mittel (Skript- und HUD-Aufwand) |
| K5 Dehnungsentwurf | mittel–hoch | hoch | mittel |
| K6 Hybrid | mittel | mittel | niedrig–mittel |

**Kern: K3, ergänzt um K2 (die Stoffspuren) und K1 (der Boden für alle Posen,
die nicht co-designt sind).** K3 ohne K2 hätte keinen Stoff, der eigenständig
mitarbeitet. K3 ohne K1 sähe außerhalb der Signature Walk schlechter aus als 0.4.
K4–K6 kommen später: K4 nutzt dieselben Cloth-Bones und dieselbe Übergabelogik
und lässt sich leicht anschließen.

### Die stärkste Idee infrage gestellt

1. **„Die Trägerin trägt sowieso ihre eigene AO.“** Das ist der härteste Einwand.
   Eine Signature Walk wird nur gesehen, wenn sie aktiv ist.
   → *Verbesserung:* **Zwei Modi** liefern.
   - **Signature-Modus**: volle Kopplung, Körper- und Cloth-Spuren in einer Datei.
   - **Overlay-Modus**: eine Animation, die **nur Cloth-Bones** keyt und die Fremd-AO unberührt lässt. Ihre Saumbewegung wird bewusst **phasenrobust** optimiert: kleine Amplitude, langsamer als der Schritt, ohne klare Beinkorrelation. So wirkt sie zu jedem Gang plausibel. Das Tool bewertet sie gegen *mehrere* fremde Gänge statt gegen einen.
2. **„Optimierter Gang = Roboter-Catwalk.“**
   → Nur 4–8 Stilparameter als Abweichung von einem guten Basisgang. Natürlichkeit ist ein harter Term. Die Kreatorin wählt aus Varianten, statt eine Lösung zu bekommen. Ein Regler für die Ausprägung (0–100 %) blendet zwischen Basis und Optimum.
3. **„Die Walk deckt nur einen Teil der Zeit ab.“** Stehen, Sitzen, Tanz und Möbelposen sind nicht co-designt.
   → K1 trainiert genau diese Posen. Die Ruheform der Cloth-Bones ist so entworfen, dass „keine Animation aktiv“ ein guter Zustand ist und nicht ein eingefrorener Zwischenzustand. Optional kommt ein kleines **Pose-Pack** (Stand, Turn, Sit) mit denselben Cloth-Spuren dazu.
4. **„Bone-Konflikte.“**
   → Das Bone-Set ist pro Produkt wählbar: HindLimb oder Tail für Röcke, Wings für Oberteile. Das Tool erzeugt eine **Kompatibilitätsnotiz** für die Produktseite („nicht zusammen mit Bento-Tails tragen“). Ein Fallback-Mesh ohne Cloth-Bones (reines K1) liegt jedem Produkt bei.
5. **„Übergänge.“** Start und Stopp der Walk sind lineare Blends.
   → Das Tool optimiert die **Ease-In/Out-Längen** und die Ruhe-Kompatibilität des ersten und letzten Frames mit, sodass der Blend ohne Durchdringung verläuft. Ein echtes Nachschwingen beim Anhalten gibt es nicht. Eine AO kann eine kurze „Settle“-Animation starten, die aber nur ungefähr im richtigen Moment beginnt.

**Verbesserte Kernidee:** *Garment + Motion Pack Solver*. Ein Kleid wird zusammen
mit einer kleinen Bewegungsfamilie gelöst: Signature Walk, Overlay-Loop,
Stand/Turn/Sit-Posen und ein Fallback. Gemeinsam gelöst werden
Ruhegeometrie (begrenzt), Gewichte über Körper- und Cloth-Bones, Cloth-Spuren
und die Stilparameter des Gangs. Die Designabsichten (Schlitzphase, Silhouettenband,
Straps) sind **messbare Ziele**, keine Hoffnungen.

---

## 3. Unterschied zu bekannten Verfahren (ehrlich eingeordnet)

- **Gewichte aus Beispielposen** zu optimieren ist in der Forschung bekannt (example-based skinning, SSDR).
  - *Unser Unterschied:* begrenzte Änderung der Ruheform, Fitted-Mesh-Shape-Varianten und SL-Grenzen (4 Einflüsse, feste Bones) in einem Lauf.
- **Bento-Bones für Röcke** werden in SL schon kommerziell genutzt.
  - *Unser Unterschied:* Die Spuren werden aus Simulation oder Absicht **berechnet** und **in dieselbe Datei wie die Körperbewegung** gebacken. Dazu kommt ein phasenrobuster Overlay-Modus.
- **Gangstile zu optimieren** ist aus Animation und Robotik bekannt.
  - *Unser Unterschied:* Die Zielfunktion ist eine **Kleidungsabsicht** (Schlitzphase, Silhouette, Strap-Spannung), bewertet am tatsächlich exportierbaren LBS-Ergebnis.

---

## 4. Prototyp-Plan (klein, in Maya)

**Testobjekt.** Bodenlanges Säulenkleid mit hohem Schlitz rechts und zwei Straps, auf einem festen Ziel-Body. Zusätzlich 2 Shape-Varianten, simuliert über skalierte Collision Volumes.

**Stufe 0 – Messgerüst und Machbarkeitstest (vor jedem Solver).**
- Uploadtest: `.anim` mit Positions- und Rotationskeys auf `mHindLimb1Left` und `mTail1`, möglichst auf dem Beta-Grid. Wir prüfen, ob die Bones sich bewegen und ob Ease-In/Out sauber zurückblendet.
- Messwerkzeuge in Maya als reine Auswertung, ohne Deformer-Abhängigkeit (Details unten).

**Stufe 1 – K1** auf den Körperbones. Startwert ist das Ergebnis von 0.4. 6 Trainingsposen.

**Stufe 2 – K2** mit 8 Cloth-Bones: `mHindLimb1–4 L/R` für die Schlitz- und Vorderpanels, oder `mTail1–4` für den hinteren Saum. Grundlage ist ein nCloth-Gehzyklus mit Körperkollision. Die Kreatorin korrigiert 2–3 Frames.

**Stufe 3 – K3**: 4 Stilparameter (Fußkreuzung, Beckenrolle, Kniehub, Schrittlänge), 3 Ziele (Schlitzphase, Silhouette, Eindringtiefe) plus ein Natürlichkeitsterm. Daraus entstehen 3 Varianten zur Auswahl. Zusätzlich ein Overlay-Loop, bewertet gegen 2 fremde Gänge.

### Vergleich mit dem bisherigen Rig (0.4)

Gleiches Kleid, gleicher Body, **identische Posen und Clips**. Verglichen werden drei Varianten:

| Variante | Inhalt |
|---|---|
| A | 0.4 |
| B | K1 |
| C | K1 + K2 + K3 |

**Posen und Clips.**
- **Trainingsposen** (für die Optimierung genutzt): Neutral, Gehen Kontakt L, Gehen Passing, breiter Stand, Kniebeuge 60°, Sitzen auf der Kante.
- **Ungesehene Extremposen** (nie in der Optimierung):
  - tiefes Sitzen mit 100° Hüftbeugung;
  - Bein über Bein;
  - Knie hoch auf 90°;
  - weiter Ausfallschritt;
  - Knien;
  - Hüftdrehung 30° mit Schritt;
  - Treppenstufe.
- **Clips**:
  - die Signature Walk;
  - **zwei fremde Gänge**, nicht genutzt;
  - Stand → Walk → Stand mit realen Ease-Zeiten;
  - Drehung auf der Stelle.
- **Shape-Varianten**: Basis plus 2 skalierte Collision-Volume-Sätze.

**Messgrößen.**

| Kriterium | Messung |
|---|---|
| Clipping | Anteil der Kleid-Vertices mit signiertem Abstand zum Körper < −1 mm; maximale Eindringtiefe; betroffene Fläche. Pro Pose und Frame, getrennt nach Training und Test. |
| Silhouettentreue | Binärmasken aus Front, Seite und Rücken (orthografisch), IoU und Konturabstand (Chamfer, mm) gegen die Zielsilhouette (Entwurf bzw. korrigierte Referenz). |
| Verzerrung | Kantendehnung und Flächenverhältnis pro Dreieck gegenüber der Ruheform (95. Perzentil + Maximum); Volumenverlust an Knie und Hüfte (Candy-Wrapper); Karotextur-Render zur Sichtkontrolle. |
| Bewegungsübergänge | Vertex-Beschleunigung und Ruck pro Frame; maximaler Sprung pro Frame bei Ease-In/Out und Loop-Naht; Durchdringung während des Blends. |
| Designabsicht | Schlitzöffnung über der Gangphase (Kurve vs. Wunschfenster); Strap-Spannung als Abstand der Strap-Enden. |
| Wahrnehmung | Blindvergleich nebeneinander (Turntable + Gehvideo) durch dich und 2 weitere Personen, Fragen zu Natürlichkeit, Silhouette und „wirkt der Schlitz gewollt?“. |

**Bewertung ohne Übertreibung.**
- Gewonnen hat eine Variante nur, wenn sie in den **Testposen** nicht schlechter ist als 0.4 und in mindestens zwei Kriterien deutlich besser.
- Ergebnisse werden pro Pose berichtet, nicht nur als Mittelwert. Die schlechteste Pose wird immer gezeigt.
- Wir erwarten Restclipping in Extremposen und sagen das auf der Produktseite auch so.

**Erfolgs- und Abbruchkriterien.**
- Stufe 0 scheitert, weil Positionskeys auf Nicht-Pelvis-Bones nicht abgespielt werden → K2/K3 nur mit Rotationen weiterführen (geringere Ausdruckskraft) und das dokumentieren.
- K3-Varianten werden im Blindtest als unnatürlich bewertet → Stilparameter enger fassen oder nur den Overlay-Modus ausliefern.

---

## 5. Nächste Schritte

1. Stufe 0 umsetzen: Testanimation exportieren, Uploadtest, Messgerüst in Maya.
2. Danach Stufe 1 (K1) als Erweiterung von 0.4. Der vorhandene Gewichtscode bleibt der Startwert und die Vergleichsbasis.

## Quellen

- Second Life Viewer, Quellcode: <https://github.com/secondlife/viewer>
  - `indra/llcharacter/lljoint.h`
  - `indra/llcharacter/llbvhconsts.h`
  - `indra/llcharacter/llbvhloader.cpp`
  - `indra/llcharacter/llkeyframemotion.cpp`
  - `indra/newview/character/avatar_skeleton.xml`
  - `indra/newview/character/avatar_lad.xml`
  - `indra/newview/llphysicsmotion.cpp`
  - `indra/newview/llcontrolavatar.cpp`
  - `indra/newview/llvovolume.cpp`
- Release Notes 7.2.0: <https://releasenotes.secondlife.com/viewer/7.2.0.16729091892.html>
- Release Notes 7.1.14: <https://releasenotes.secondlife.com/viewer/7.1.14.15361077240.html>
- SL Wiki:
  - Limits: <https://wiki.secondlife.com/wiki/Limits>
  - Internal Animation Format: <https://wiki.secondlife.com/wiki/Internal_Animation_Format>
  - Animation Priority: <https://wiki.secondlife.com/wiki/Animation_Priority>
  - Mesh/Rigging Fitted Mesh: <https://wiki.secondlife.com/wiki/Mesh/Rigging_Fitted_Mesh>
  - Animesh User Guide: <https://wiki.secondlife.com/wiki/Animesh_User_Guide>
- Le, B. H., Deng, Z.: *Smooth Skinning Decomposition with Rigid Bones*, ACM TOG (SIGGRAPH Asia) 2012.
