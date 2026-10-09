# Kleidung und Bewegung als ein Designproblem

Konzeptpapier für die Weiterentwicklung von *mcd. Dress Auto Rig* (aktuell 0.4).
Noch kein Code. Stand: Oktober 2026.

> Leitfrage: **Welche Kleidung könnten wir erschaffen, wenn wir ihre Geometrie,
> ihre Gewichtsverteilung und ihre Bewegungen als ein gemeinsames Designproblem
> behandeln?**

Kurze Antwort vorweg: Kleidung, die je nach Situation eine **andere, gewollte
Form** annimmt, ohne der Trägerin ihre eigene AO wegzunehmen. Im Stehen ist der
Schlitz geschlossen und die Linie ruhig. Beim Gehen öffnet er sich und gibt dem
Bein Raum. Beim Sitzen gleitet der Rock zur Seite, statt im Oberschenkel zu
verschwinden. Second Life kann Stoff zur Laufzeit nicht simulieren. Wir können
diese Formen aber **vorab gemeinsam mit den Gewichten lösen** und als
Animationsspuren auf ungenutzten Bento-Bones ausliefern, die **neben** jeder AO laufen.

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

### K3 – Choreografierter Gang: Kleid und Animation gemeinsam optimieren *(verworfen, siehe Abschnitt 2)*

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

**Feste Vorgabe nach Rücksprache:** Die AO der Trägerin bleibt unangetastet. Das
Kleid ersetzt keinen Gang, keine Stand- und keine Sitzanimation. Damit fällt
**K3 (choreografierter Gang) als Kern weg**: Eine eigene Walk würde im Alltag
gegen die AO verlieren oder sie verdrängen. Beides wollen wir nicht.

| Konzept | Kreatives Potenzial | Machbarkeit (SL + Maya) | Nutzen für eine einzelne Kreatorin |
|---|---|---|---|
| K1 Multi-Pose-Fit | mittel | hoch | hoch (ersetzt Nachmalen) |
| **K2 Cloth-Bone-Bake** | **hoch** | **mittel–hoch** | **hoch, wenn AO-neutral** |
| K3 Choreografierter Gang | sehr hoch | mittel | **gering: kollidiert mit der eigenen AO** (verworfen) |
| K4 Zustände | hoch | mittel | mittel (Skript- und HUD-Aufwand) |
| K5 Dehnungsentwurf | mittel–hoch | hoch | mittel |
| K6 Hybrid | mittel | mittel | niedrig–mittel |

**Kern: K2 + K1, umgebaut zu einer zustandsgesteuerten Stoffebene.**

### Die Kernidee: Kleid mit eigener Stoffebene, die *neben* jeder AO läuft

Die Beine bewegt weiterhin die AO der Trägerin. Das Kleid weiß aber in jedem
Moment, **in welchem Zustand** der Avatar ist: Stehen, Gehen, Rennen, Sitzen,
Sitzen am Boden, Drehen, Hocken. LSL liefert das über `llGetAnimation()` bzw.
`llGetAgentInfo()`, unabhängig davon, welche AO-Animation gerade läuft. Für jeden
Zustand hat das Kleid eine eigene **Stoffpose** auf den Cloth-Bones, optional mit
einer kleinen, phasenrobusten Loop. Ein Skript im Kleid spielt beim Zustandswechsel
die passende Overlay-Animation. Diese Animation keyt **ausschließlich Cloth-Bones**
(HindLimb-, Tail-, ggf. Wing-Bones), die eine normale Humanoid-AO nicht anfasst.
Damit bleibt die AO vollständig erhalten.

**Was das für das Design öffnet:** Das Kleid darf **pro Zustand eine andere,
gewollte Form** haben. Diese Formen werden gemeinsam mit **einem** Gewichtssatz
gelöst:

- **Stehen:** Der Schlitz liegt geschlossen und die Säulenlinie ist sauber. Das ist die Katalogansicht.
- **Gehen:** Die Panels um den Schlitz rücken ein paar Zentimeter nach außen und vorn. Das Bein bekommt Spielraum und der Schlitz öffnet sich, während die Silhouette von der Seite gerade bleibt.
- **Sitzen:** Der Rücken des Rocks gleitet unter dem Gesäß nach hinten, der Schlitz klappt zur Seite und fällt über den Oberschenkel. Genau hier clippen enge Kleider heute am stärksten.
- **Am Boden sitzen / Hocken:** Der Saum legt sich flacher und weiter auf, statt durch die Waden zu gehen.
- **Rennen:** Der Saum hebt sich leicht und gibt das Knie frei.

Das ist mehr als „bessere Gewichte“: Die Formvarianten sind Teil des Entwurfs.
Und das Tool optimiert sie **nicht gegen eine einzige Animation**, sondern gegen
eine **Bibliothek fremder Animationen pro Zustand**, also gegen das, was die
Kundinnen tatsächlich tragen.

### Mechanismus

**Unbekannte.**
- Gewichte w über Körper-Bones **und** Cloth-Bones (≤ 4 pro Vertex);
- begrenzte Ruhe-Offsets d (aus K1);
- pro Zustand s eine starre Transformation C_s,k je Cloth-Bone k (z. B. 5 Zustände × 8 Bones);
- optional eine kleine Loop-Amplitude A_s.

**Daten.** Pro Zustand eine Posen- und Clip-Bibliothek L_s aus verschiedenen AOs und Möbeln. Sie wird **in Training und Test geteilt**, die Testanimationen sieht der Solver nie. Dazu Sculpt-Korrekturen der Kreatorin für ausgewählte Frames (wie K1) und Zielsilhouetten pro Zustand.

**Ziel.**
Σ_s Σ_{p∈L_s} [ Eindringen + Verzerrung + Silhouettenfehler_s + Abstand zu Korrekturen ]
plus Glättung (Schlitzkanten bleiben getrennt), plus |d| ≤ δ, plus ein **Übergangsterm**.
Der Übergangsterm misst den linearen Blend zwischen C_s und C_s' (so überblendet
SL per Ease-In/Out) über repräsentative Wechselposen und bestraft Durchdringung
während des Wechsels.

**Lösung.** Abwechselnd:
1. Gewichte pro Vertex (kleines QP);
2. C_s pro Zustand (wenige starre Transformationen, Gauß-Newton über die Bibliothek);
3. d linear.

Startwert ist das Ergebnis von 0.4. Eine Robustheitsvariante optimiert zusätzlich den **schlechtesten** Fall pro Zustand statt nur den Mittelwert.

**Optional, die Loop.** Innerhalb eines Zustands eine kleine Saumbewegung (K2-Zerlegung aus einer nCloth-Simulation). Sie ist **phasenrobust**: langsamer als der Schritt, kleine Amplitude, bewertet gegen *alle* Gänge der Bibliothek. Sie darf die Beinbewegung nicht nachahmen wollen, denn die kennt sie nicht.

### Die vier Ebenen

| Ebene | Inhalt |
|---|---|
| **Tool (nur Maya)** | Zustands- und Posenbibliothek, Sculpt-Korrekturen, gemeinsamer Solver, Robustheitstest gegen fremde AOs, Übergangsprüfung, Kompatibilitätsbericht |
| **Export** | Ein rigged Mesh (Körper- + Cloth-Bones, gebunden an die Standardpositionen, **ohne** Joint-Offsets); pro Zustand eine kurze `.anim`, die **nur Cloth-Bones** keyt (Rotation + Position, geloopt, mit optimierten Ease-Zeiten); ein LSL-Skript (Zustandserkennung → Overlay starten/stoppen); ein Fallback-Mesh ohne Cloth-Bones (reines K1) |
| **Laufzeit (SL)** | LBS; das Skript fragt den Zustand ab und startet die passende Overlay-Animation (Attachments des Trägers bekommen die Animationsberechtigung ohne Rückfrage); SL überblendet per Ease-In/Out; die AO läuft unverändert weiter |
| **Kompromisse** | siehe unten |

### Die Kernidee infrage gestellt

1. **Zustandserkennung kommt verzögert.** Das Skript pollt, und die Animation startet auf fremden Viewern versetzt. Der Rock reagiert also einen Moment nach dem Körper.
   → Übergänge lang und weich halten (Ease 0,3–0,6 s). Zustandsformen so lösen, dass auch die **Kombination „alter Stoffzustand + neue Körperpose“** nicht stark clippt. Das Tool prüft genau diese Kreuzkombinationen. Eine sichtbare Verzögerung bleibt, im Idealfall wirkt sie wie Stoffträgheit.
2. **Sitzen ist nicht gleich Sitzen.** Barhocker, Sofa, Bein über Bein und Paarposen liefern alle „Sitting“.
   → Die Sitzform wird gegen eine breite Sitzbibliothek robust optimiert. Optional gibt es 2–3 Sitzvarianten, die die Trägerin per Menü wählt („aufrecht“, „Bein über Bein“, „lounge“). Extreme Möbelposen bleiben ein Restrisiko, das wir offen benennen.
3. **Bone-Konflikte.** Bento-Tails, Flügel, Vierbeiner-Avatare und deren AOs nutzen dieselben Bones.
   → Bone-Set pro Produkt wählbar (HindLimb oder Tail für Röcke, Wings für Oberteile). Kompatibilitätshinweis auf der Produktseite. Fallback-Mesh ohne Cloth-Bones liegt bei. Das Tool prüft und meldet, wenn zwei eigene Produkte dasselbe Set belegen.
4. **Ohne laufendes Skript** (Skripte in der Region aus, Overlay gestoppt) gehen die Cloth-Bones in die Standardpose zurück.
   → Die Ruheform des Kleides ist genau die Stehform. Ohne Overlay sieht man also das geschlossene Kleid in normaler K1-Qualität, nicht eine kaputte Zwischenform.
5. **Warum nicht einfach mehr Körpergewichte?** Ein fester Gewichtssatz muss Stehen und Sitzen gleichzeitig bedienen und mittelt deshalb. Die Zustandsebene gibt jedem Zustand eigene Freiheitsgrade, ohne die AO anzufassen. Genau das kann reines Skinning nicht.

### Einordnung (was daran bekannt ist)

- Röcke auf Bento-Bones und Skripte, die auf den Avatarzustand reagieren, gibt es in SL einzeln schon.
- Neu ist die Kombination:
  - die Zustandsformen werden **gemeinsam mit den Gewichten** gelöst;
  - der Solver arbeitet **robust gegen fremde AO-Bibliotheken** statt gegen eine Referenzanimation;
  - die Übergänge werden so geprüft, wie SL sie tatsächlich überblendet;
  - das Ergebnis ist explizit AO-neutral.

### Was später dazukommen kann

- **K4 (Modi per HUD)** nutzt dieselben Cloth-Bones und dasselbe Skript. Neben den automatischen Zuständen kommen dann bewusst gewählte Modi hinzu („Schlitz offen tragen“).
- **K5 (Dehnungsentwurf)** nutzt dieselbe Bibliothek, um vor dem Riggen zu sagen, wo ein Schlitz oder eine Falte sitzen sollte.

---

## 3. Prototyp-Plan (klein, in Maya)

**Testobjekt.** Bodenlanges Säulenkleid mit hohem Schlitz rechts und zwei Straps, auf einem festen Ziel-Body. Zusätzlich 2 Shape-Varianten, simuliert über skalierte Collision Volumes. Cloth-Bones: `mHindLimb1–4 L/R` (Schlitz- und Vorderpanels); `mTail1–4` als Alternative für den hinteren Saum.

**Stufe 0 – Machbarkeit und Messgerüst.**
- Uploadtest: `.anim` mit Positions- und Rotationskeys **nur** auf `mHindLimb1Left` und `mTail1`, zusammen mit einer laufenden fremden AO.
  - Bewegen sich die Bones?
  - Bleibt die AO völlig unberührt?
  - Blendet Ease-In/Out sauber?
- Skripttest: Wie schnell wird ein Zustandswechsel (Stehen → Gehen → Sitzen) erkannt? Wie groß ist die sichtbare Verzögerung auf einem zweiten Viewer?
- Messwerkzeuge in Maya, rein auswertend.

**Stufe 1 – K1** auf den Körperbones. Startwert ist das Ergebnis von 0.4.

**Stufe 2 – Zustandsebene** mit zunächst **3 Zuständen** (Stehen, Gehen, Sitzen) und 8 Cloth-Bones, gemeinsam mit den Gewichten gelöst. Noch ohne Loop.

**Stufe 3 (optional)** – phasenrobuste Geh-Loop aus einer nCloth-Zerlegung.

### Bibliothek und Testaufteilung

- Pro Zustand Animationen aus **mindestens 4 verschiedenen AOs bzw. Posenquellen**.
- **Training:** 2–3 Quellen pro Zustand.
- **Test (nie gesehen):** 1–2 andere Quellen pro Zustand, dazu ungesehene Extremposen:
  - tiefes Sitzen mit 100° Hüftbeugung;
  - Bein über Bein;
  - Knie hoch auf 90°;
  - weiter Ausfallschritt;
  - Knien;
  - Hüftdrehung 30° mit Schritt;
  - Treppenstufe.
- **Übergänge:** Stehen ↔ Gehen ↔ Sitzen, je einmal mit „Stoff verzögert“ (alter Stoffzustand auf neuer Körperpose über 0,5 s).

### Vergleich mit dem bisherigen Rig (0.4)

Gleiches Kleid, gleicher Body, **identische Posen und Clips**. Verglichen werden drei Varianten:

| Variante | Inhalt |
|---|---|
| A | 0.4 |
| B | K1 |
| C | K1 + Zustandsebene |

**Messgrößen.**

| Kriterium | Messung |
|---|---|
| Clipping | Anteil der Kleid-Vertices mit signiertem Abstand zum Körper < −1 mm; maximale Eindringtiefe; betroffene Fläche. Pro Pose und Frame, getrennt nach Training und Test. |
| Silhouettentreue | Binärmasken aus Front, Seite und Rücken (orthografisch), IoU und Konturabstand (Chamfer, mm) gegen die Zielsilhouette des jeweiligen Zustands. |
| Verzerrung | Kantendehnung und Flächenverhältnis pro Dreieck gegenüber der Ruheform (95. Perzentil + Maximum); Volumenverlust an Knie und Hüfte; Karotextur-Render. |
| Bewegungsübergänge | Vertex-Beschleunigung und Ruck pro Frame; maximaler Sprung pro Frame beim Zustandswechsel; Durchdringung während des Blends **und** in der Verzögerungsphase. |
| Designabsicht | Schlitzöffnung pro Zustand (geschlossen im Stehen, offen im Gehen, seitlich im Sitzen) gegen die Vorgabe. |
| Wahrnehmung | Blindvergleich nebeneinander (Turntable + Clips **mit fremden AOs**) durch dich und 2 weitere Personen: Natürlichkeit, Silhouette, „wirkt die Reaktion des Stoffs gewollt oder verspätet?“ |

**Bewertung ohne Übertreibung.**
- Gewonnen hat eine Variante nur, wenn sie bei den **ungesehenen AOs und Extremposen** nicht schlechter ist als 0.4 und in mindestens zwei Kriterien deutlich besser.
- Ergebnisse werden pro Pose berichtet, nicht nur als Mittelwert. Die schlechteste Pose wird immer gezeigt.
- Restclipping in Extremposen und die Verzögerung bei Zustandswechseln benennen wir offen.

**Abbruchkriterien.**
- Positionskeys auf Nicht-Pelvis-Bones werden nicht abgespielt → nur Rotationen, Ausdruckskraft geringer, dokumentieren.
- Die Verzögerung beim Zustandswechsel wirkt im Blindtest eher wie ein Fehler als wie Stoffträgheit → weniger Zustände, längere Blends oder nur die Sitzform automatisch, den Rest per Menü (Übergang zu K4).

---

## 4. Nächste Schritte

1. Stufe 0 umsetzen: Testanimation nur auf Cloth-Bones exportieren, Uploadtest mit laufender fremder AO, Skripttest für die Zustandserkennung, Messgerüst in Maya.
2. Danach Stufe 1 (K1) als Erweiterung von 0.4. Der vorhandene Gewichtscode bleibt Startwert und Vergleichsbasis.

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
- LSL: `llGetAnimation`, `llGetAgentInfo`, `llStartAnimation` (SL-Wiki, LSL-Portal)
- Le, B. H., Deng, Z.: *Smooth Skinning Decomposition with Rigid Bones*, ACM TOG (SIGGRAPH Asia) 2012.
