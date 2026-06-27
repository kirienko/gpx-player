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

## 0.2.1 — 2025-08-21
* Fix schemas for GPX validator.

## 0.3.0 — 2026-04-19
* **Map mode**: add `--start` / `--end` flags to `gpx_player.openseamap` for
  rendering only a time window of a GPX track. Points outside the window are
  excluded from the map, speed calculations, distance totals, map bounds and
  the animation slider (#15).
* `create_map()` gains optional `start_time` / `end_time` keyword arguments;
  default behaviour is unchanged when they are omitted.
* Tracks whose filtered window contains no points are skipped with a warning
  instead of crashing; the all-empty case is guarded so `max_speed` and
  `fit_bounds` do not fail on empty inputs.
* New utility `gpx_player.gpx_utils.trim_track()` (and `trim_tracks()` wrapper)
  for in-memory time-window trimming of already-parsed tracks, preserving
  track metadata and point extension fields without mutating the input (#14).

## 0.4.0 — 2026-06-26
* **Map mode**: bundle playback JavaScript and HTML templates as package
  assets, so installed wheels can generate playable OpenSeaMap HTML from any
  current working directory.
* Add public `add_playback_controls()` and `create_playback_map()` helpers for
  downstream Python applications that want static playable maps without
  vendoring assets.
* Escape title/name output and serialize playback data safely for inline
  scripts, preventing user-provided strings from breaking out of generated
  HTML/JavaScript.
* Scope playback UI state by Folium map id under `window.gpxPlayerPlayback`,
  avoid generic button selectors, and add accessible labels for the play/pause
  button and time slider.
* Keep `create_map()` and existing map CLI behavior working while routing the
  CLI through the packaged playback helper.
