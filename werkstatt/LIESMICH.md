# Werkstatt-Skripte

Mit diesen Skripten sind die Ergebnisse entstanden. Gerechnet wurde außerhalb von Maya, die Pfade zeigen auf `/tmp/claude-0/fit/`.
Für eine neue Rechnung reicht es, die Pfade auf den hochgeladenen Export umzustellen.

- `catwalk.py` → Laufsteg v3
- `v4.py` → v4 mild/stark (Variante `v4b` = mild)
- `smooth.py` → v4 mild glatt / sehr glatt
- `deform.py` + `deform2.py` → Prototyp Legacy → Reborn (sauber als `mcd_fit_deform.py`)
- `reborn_v4.py` → v4 mild gegen Reborn
- `harm.py`, `aline.py` → Glätten über Mesh-Teile, A-Linie
- `resid.py`, `legfront.py` → Analyse, wo noch Clipping bleibt
- `v5s.py` → v5 (Brust + Bein vorn), verworfen

`out/shell_labels.npy` sind die Mesh-Teile des Kleides, nicht im Repo. Erzeugen:
`scipy.sparse.csgraph.connected_components` über `dress.edges`. Beim Thin-Kleid ist Label 2 das Futter (4283 Vertices) und Label 15 der Außenstoff.
