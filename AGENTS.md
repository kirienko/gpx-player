# Repository guidance for agents

## Working rules

- Use the applicable Superpowers skills.
- Do not add new code comments unless the implementation cannot work correctly
  without them. Preserve existing comments.

## Architecture

This is a Python library/CLI with Folium/Leaflet HTML playback and Matplotlib video
output. Keep it lightweight: no backend service or JavaScript build pipeline.

| Path | Responsibility |
| --- | --- |
| `gpx_player/openseamap.py` | Map parsing, metrics, Folium rendering, serialization, playback API and CLI |
| `gpx_player/assets/` | Browser playback JavaScript and packaged HTML templates |
| `gpx_player/main.py` | Video CLI and Matplotlib animation |
| `gpx_player/gpx_utils.py` | Trimming, cutting and extension removal |
| `gpx_player/validator.py`, `schema/` | GPX validation and schemas |
| `gpx_player/clean_gpx.py`, `gpx_player/utils.py` | Cleanup and shared helpers |
| `tests/` | Python tests, Node playback harnesses and wheel packaging checks |
| `scripts/`, `example-data/` | Demo generation, synthetic tracks and public examples |

Use the README's **For AI agents** section for invocation details and failure modes.

## Compatibility and playback contracts

- Keep the video console script and module entry point equivalent. Importing
  `main` must not parse arguments or render. MP4 requires `ffmpeg`; GIF does not.
- Map mode requires `--files` and writes `boat_tracks.html`. Do not assume video
  flags exist in map mode. API callers choose their own output paths.
- Preserve `create_playback_map()` returning `folium.Map`, `create_map()` returning
  `(map, tracks, max_speed, map_id)`, and existing playback helpers.
- Trim inclusively without mutating source tracks or dropping metadata. Calculate
  visible bounds/metrics from the selected window and preserve name alignment when
  tracks are skipped. Names map to tracks, not necessarily one per file.
- Require timezone-aware time bounds; test map and video parsers separately.
  Cover missing/duplicate timestamps, segment gaps, stationary points and boundaries.
- Speeds are knots; distances are nautical miles. `max_speed` filters implausible
  speeds rather than capping display values. Keep raw geometry/speeds separate
  from 10-second display smoothing, and preserve genuine stops.
- Scope playback state by Folium `map_id` under `window.gpxPlayerPlayback`.
  Reference layers using `FeatureGroup.get_name()`, not generated DOM scraping.
- Preserve Full (track and marker), Tail (tail and marker), and Off (hide all).
  Tail presets count points: short 30, normal 60, long 120.
- Preserve boat-colored tail outlines and speed-colored cores. Reuse bounded
  Leaflet layer pools; avoid per-frame allocations and repeated whole-track scans.
- Preserve elapsed-time `requestAnimationFrame` playback, interpolation, scrubbing,
  replay, emoji transport controls and customizable slider progress colors.
- Cleanup writes a sibling `_noext` file unless `--overwrite` is requested.

## Security and packaging

- Preserve `_json_for_inline_script()` and `_SafeTooltip` protections. JSON-serialize
  tooltip text and the complete opening tag; escape style attributes before
  serialization. Folium tooltip template literals must not contain dynamic values.
- Cover GPX names and overrides with hostile expressions, backticks, quotes,
  backslashes, `</script>`, markup and Unicode. Assert rendered semantics and
  browser non-execution, not just template source formatting.
- Keep `folium>=0.17.0` in both dependency files while using `folium.template`.
- Load assets through package resources/`PackageLoader`, independent of the working
  directory. Keep `MANIFEST.in` and package data aligned. Preserve top-level
  `schema/` until its loader and packaging tests are deliberately migrated.
- Build wheel tests from temporary source copies with default isolation. Include
  tests/scripts in the copy to exercise exclusions; exclude caches/build artifacts.
  Assert required assets and only `gpx_player`, `schema`, and `.dist-info` roots.
- For packaging changes, install the wheel in a clean environment and verify map
  generation and schema validation from outside the checkout.
- For requested releases, synchronize `pyproject.toml`, `gpx_player/__init__.py`,
  and `CHANGELOG.md`. Tag pushes publish to PyPI; `main` pushes deploy the demo.

## Reviews

Use the [reviewing skill](.claude/skills/review-pr-comments.md).
