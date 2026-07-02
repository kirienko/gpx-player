# Smooth Map Playback Design

## Summary

Map playback should move boat markers smoothly between existing GPX points instead
of snapping from point to point. The solution is client-side only: generated maps
continue to embed the same point payload, and JavaScript computes interpolated
positions in the browser.

The playback clock should use elapsed GPX time rather than equal sample indexes.
This gives more natural playback for irregularly sampled tracks and creates a
clean base for future playback speeds.

## Goals

- Smooth marker movement between adjacent GPX points.
- Keep all interpolation work in JavaScript on the client.
- Avoid adding backend processing, database changes, or generated intermediate
  points.
- Preserve existing Full / Tail / Off visibility behavior.
- Preserve point-based tail-length presets.
- Prepare the playback loop for future playback-rate controls.
- Keep generated HTML payload size effectively unchanged.

## Non-Goals

- No public Python API changes are required for the first implementation.
- No server-side track densification.
- No interpolation of persisted GPX points.
- No first-pass playback-speed UI, although the internal state should support it.
- No first-pass interpolation of legend statistics unless needed by the marker
  implementation.

## Current Behavior

The current map playback uses a discrete slider loop. While playing, JavaScript
increments the slider value on a fixed interval. The slider value is mapped to a
timestamp index, then each boat is moved to the latest GPX point at or before that
timestamp.

That means marker position and heading can jump when adjacent GPX points are far
apart. The playback cadence is also not tied to elapsed race time; it is tied to
slider/sample progression.

## Proposed Architecture

Replace the interval-driven playback loop with a `requestAnimationFrame` loop.
The loop owns a playback clock:

- `currentTimeMs`: current GPX playback time in milliseconds.
- `minTimeMs` and `maxTimeMs`: bounds of the playback timeline.
- `playbackRate`: speed multiplier, initially `1`.
- `lastFrameTimeMs`: browser frame timestamp from the previous frame.
- `currentSegmentIndexes`: per-track cursor for the active GPX segment.

The render frame computes real browser time elapsed since the previous frame,
multiplies it by `playbackRate`, advances `currentTimeMs`, updates the slider
visual, and renders markers/tails for the new time.

## Data Flow

For each visible track:

1. Find the active segment surrounding `currentTimeMs`.
2. Use the existing per-track timestamp arrays and segment cursor for normal
   forward playback.
3. Fall back to binary search when playback jumps, scrubs backward, or otherwise
   moves outside the current segment.
4. Interpolate marker latitude and longitude between the segment endpoints.
5. Rotate the triangle marker toward the active movement segment.
6. Update tail geometry only for tracks in Tail mode.

This keeps normal playback work bounded by the number of tracks, not by the
number of points.

## Interpolation

Given two GPX points `A` and `B`:

```text
ratio = (currentTimeMs - A.timeMs) / (B.timeMs - A.timeMs)
lat = A.lat + (B.lat - A.lat) * ratio
lon = A.lon + (B.lon - A.lon) * ratio
heading = direction from A to B
```

The ratio should be clamped to `[0, 1]`. Duplicate points and zero-duration
segments should be skipped when selecting a movement segment for heading.

If a track has no usable movement segment, render the triangle at the nearest
known point with the existing default heading of `0deg`.

## Track Visibility Modes

The existing modes remain:

- Full: full speed-colored track is visible, marker is visible, tail hidden.
- Tail: full track hidden, marker visible, tail visible.
- Off: full track hidden, tail hidden, marker hidden.

Smooth marker interpolation applies only when the marker is visible.

## Tail Behavior

Tail length remains point-based. In Tail mode, the tail should include the last
configured number of real GPX points up to the active segment, plus the current
interpolated marker position as the live endpoint.

This keeps the tail bounded by the existing preset and prevents the marker from
visually detaching from the tail while moving between two GPX points.

## Slider Behavior

The slider should represent elapsed playback progress:

```text
slider.value = progress from minTimeMs to maxTimeMs, scaled to slider range
```

When the user scrubs the slider, JavaScript should compute `currentTimeMs` from
the slider value, refresh per-track segment cursors with binary search, and render
one frame immediately.

## Future Playback Speeds

The first implementation should include `state.playbackRate = 1` internally even
without exposing a UI control. Future speed controls can then adjust only that
value:

```text
currentTimeMs += frameDeltaMs * playbackRate
```

This supports rates such as `0.5x`, `1x`, `2x`, or `5x` without reworking the
playback loop.

## Performance

- Use `requestAnimationFrame` so rendering follows the browser's frame scheduler.
- Do not pre-render or precompute interpolated points.
- Do not add extra generated HTML payload for smoothing.
- Use per-track segment cursors during normal forward playback.
- Use binary search only for scrubbing, backward jumps, and cursor misses.
- Skip marker/tail updates for tracks in Off mode.
- Keep tail redraw bounded by the configured point preset plus one live endpoint.

The expected steady-state cost per frame is proportional to the number of visible
tracks and the active tail preset, not the total number of GPX points.

## Portability

The implementation should stay browser-native and Folium-compatible:

- No Leaflet plugins.
- No generated image assets.
- No backend assumptions.
- No dependency on Folium layer-control DOM structure.
- All state remains scoped under the existing per-map playback state.

## Edge Cases

- Before a track starts: show its first point if the marker is visible.
- After a track ends: show its final point if the marker is visible.
- Duplicate coordinates: skip them for heading, but keep position stable.
- Duplicate or invalid timestamps: avoid division by zero and fall back to the
  nearest valid point.
- Long GPS gaps: interpolate linearly for the first implementation. A future
  configurable gap threshold can change this to pause, fade, or snap if needed.

## Testing

Add or update JavaScript-stub tests for:

- Playback time advancing through `requestAnimationFrame`.
- Marker latitude/longitude interpolating between two GPX points.
- Heading following the active segment.
- Duplicate point handling.
- Slider scrubbing backward and forward.
- Full / Tail / Off visibility behavior.
- Tail mode including the interpolated live endpoint.
- Future playback-rate state affecting time advancement.

Keep Python render tests focused on generated payload compatibility and asset
presence. No backend data-shape changes should be required.
