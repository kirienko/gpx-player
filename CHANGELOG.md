# Changelog
All notable changes to **gpx-player** will be documented in this file.

## 0.1.0 – 2025-06-01
* First public release on PyPI.
* CLI `gpx-player` to create animated videos/GIFs from GPX files.
* CLI `gpx-validate` to schema-check GPX files.
* OpenSeaMap HTML playback with colour-coded speed, timeline slider and markers.

## 0.1.1 – 2025-07-20
* `remove_extensions_tags` function with optional in-place overwrite
* `clean_gpx.py` script to validate and clean GPX files

## 0.1.2 – 2025-07-20
* new dynamic distance/speed/avg.speed legend for the map mode
* minor UI fix: the time is UTC, not GMT

## 0.2.0 — 2025-08-20
* Restructure into a proper package (`gpx_player/`).
* Switch CLI entry points to package modules and enable package discovery: `gpx-player` and `gpx-validate`.
* Update README examples to use the new CLI and `python -m gpx_player.*`.
* **Potentially breaking:** update imports (`from validator` → `from gpx_player.validator`) and prefer installed CLIs over top-level scripts.