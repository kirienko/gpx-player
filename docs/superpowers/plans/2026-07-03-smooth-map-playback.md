# Smooth Map Playback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace point-to-point marker jumps in map playback with client-side interpolated marker motion while preserving the existing payload and visibility controls.

**Architecture:** Keep the Python-generated playback payload unchanged and move the timing model inside `gpx_player/assets/animate_tracks.js`. Replace the interval/sample-index loop with an elapsed-time playback clock, per-track segment cursors, and `requestAnimationFrame` rendering. Marker positions and headings are computed from existing GPX points in the browser; tails remain point-based with one interpolated live endpoint.

**Tech Stack:** Browser JavaScript, Leaflet markers/polylines, Folium-rendered inline assets, Node-based JavaScript behavior tests embedded in `tests/test_openseamap.py`, pytest.

## Global Constraints

- Client-side only: no backend processing, database changes, generated intermediate points, or Python public API changes.
- No extra generated payload for smoothing; reuse existing `points`, `timestamps`, `minTime`, and `maxTime`.
- Use browser-native `requestAnimationFrame`; do not add Leaflet plugins or JS dependencies.
- Preserve Full / Tail / Off visibility behavior.
- Preserve point-based tail-length presets.
- Keep all playback state scoped to each Folium `map_id`.
- Keep legend statistics based on the latest real GPX point for this first implementation.
- Include internal `state.playbackRate = 1` support, but do not add playback-speed UI.

---

## File Structure

- Modify: `gpx_player/assets/animate_tracks.js`
  - Owns playback initialization, slider input, marker interpolation, tail geometry, visibility modes, and play/pause scheduling.
  - Add small pure helpers near the existing time helpers:
    - `initializePlaybackClock(state)`
    - `clamp(value, min, max)`
    - `timeFromSlider(state)`
    - `setSliderToTime(state, timeMs)`
    - `findPointIndexAtTime(times, currentTimeMs)`
    - `findSegmentIndexAtTime(times, currentTimeMs, previousIndex)`
    - `trackPositionAtTime(track, times, currentTimeMs, segmentIndex, fallbackHeading)`
    - `renderPlaybackFrame(state)`
    - `playbackFrame(state, frameTimeMs)`
    - `startPlayback(state)`
    - `stopPlayback(state)`
- Modify: `tests/test_openseamap.py`
  - Keep existing render tests.
  - Update the two existing Node-stub playback tests to match elapsed-time slider behavior and interpolated marker positions.
  - Add one focused Node-stub playback-clock test for `requestAnimationFrame` and `playbackRate`.
  - Reuse the existing inline Node harness style; no new test dependencies.
- No README change for the first implementation because there is no public API or visible control change.

---

### Task 1: Elapsed-Time Clock And Segment Cursors

**Files:**
- Modify: `gpx_player/assets/animate_tracks.js:28-66`
- Modify: `gpx_player/assets/animate_tracks.js:402-436`
- Test: `tests/test_openseamap.py`

**Interfaces:**
- Consumes: existing state fields `points`, `timestamps`, `minTime`, `maxTime`, `slider`, and `trackTimeValues`.
- Produces:
  - `state.minTimeMs: number`
  - `state.maxTimeMs: number`
  - `state.currentTimeMs: number`
  - `state.playbackRate: number`
  - `state.lastFrameTimeMs: number | null`
  - `state.playbackAnimationFrame: number | null`
  - `state.currentSegmentIndexes: number[]`
  - `timeFromSlider(state): number`
  - `setSliderToTime(state, timeMs): void`
  - `findPointIndexAtTime(times, currentTimeMs): number`
  - `findSegmentIndexAtTime(times, currentTimeMs, previousIndex): number`
  - `refreshPlaybackForCurrentTime(state): void`

- [ ] **Step 1: Add the failing test for elapsed-time slider mapping and cursor refresh**

Add this test after `test_add_playback_controls_rejects_bytes_track_layer_names()` in `tests/test_openseamap.py`:

```python
def test_playback_js_uses_elapsed_time_slider_and_segment_cursors():
    if not shutil.which("node"):
        pytest.skip("node is required for playback JS behavior test")

    asset_path = Path(__file__).resolve().parents[1] / "gpx_player" / "assets" / "animate_tracks.js"
    playback_js = asset_path.read_text(encoding="utf-8")
    script = f"""
const assert = require('assert');
const layers = new Set();
const map = {{
  addLayer(layer) {{ layers.add(layer); }},
  removeLayer(layer) {{ layers.delete(layer); }},
  hasLayer(layer) {{ return layers.has(layer); }}
}};
function makeElement(tag) {{
  return {{
    tagName: tag,
    style: {{ setProperty(name, value) {{ this[name] = value; }} }},
    children: [],
    listeners: {{}},
    appendChild(child) {{ this.children.push(child); return child; }},
    setAttribute(name, value) {{ this[name] = value; }},
    addEventListener(type, handler) {{ this.listeners[type] = handler; }},
    dispatchEvent(event) {{ if (this.listeners[event.type]) this.listeners[event.type](event); }},
  }};
}}
global.Event = function Event(type) {{ this.type = type; }};
global.window = global;
global.map_test = map;
global.requestAnimationFrame = function requestAnimationFrame() {{ return 1; }};
global.cancelAnimationFrame = function cancelAnimationFrame() {{}};
global.document = {{
  readyState: 'complete',
  body: makeElement('body'),
  head: makeElement('head'),
  createElement: makeElement,
  createTextNode(text) {{ return {{ textContent: text }}; }},
  getElementById() {{ return null; }},
}};
global.L = {{
  divIcon(options) {{ return options; }},
  marker(latlng, options) {{
    const arrow = {{ style: {{}} }};
    return {{
      latlng,
      icon: options.icon,
      options,
      addTo(targetMap) {{ targetMap.addLayer(this); return this; }},
      setLatLng(nextLatLng) {{ this.latlng = nextLatLng; }},
      setIcon(nextIcon) {{ this.icon = nextIcon; }},
      getElement() {{
        return {{
          querySelector(selector) {{
            return selector === '.gpx-player-direction-marker' ? arrow : null;
          }}
        }};
      }},
      arrow,
    }};
  }},
  polyline(latlngs) {{
    return {{
      latlngs,
      addTo(targetMap) {{ targetMap.addLayer(this); return this; }},
      setLatLngs(nextLatLngs) {{ this.latlngs = nextLatLngs; }},
    }};
  }},
  control() {{
    return {{ addTo(targetMap) {{ this.container = this.onAdd(targetMap); return this; }} }};
  }},
  DomUtil: {{ create(_tag, className) {{ const element = makeElement(_tag); element.className = className; return element; }} }},
  DomEvent: {{
    disableClickPropagation() {{}},
    disableScrollPropagation() {{}},
    on(element, type, handler) {{ element.addEventListener(type, handler); }},
  }},
}};
window.gpxPlayerPlayback = {{
  map_test: {{
    mapId: 'map_test',
    colors: ['red'],
    points: [[
      {{ lat: 1, lon: 1, time: '2024-06-15T12:00:00Z' }},
      {{ lat: 2, lon: 1, time: '2024-06-15T12:01:00Z' }},
      {{ lat: 2, lon: 2, time: '2024-06-15T12:03:00Z' }},
    ]],
    speeds: [[0, 1, 2]],
    distances: [[0, 1, 2]],
    avgSpeeds: [[0, 1, 2]],
    trackNames: ['Alpha'],
    timestamps: [
      '2024-06-15T12:00:00Z',
      '2024-06-15T12:01:00Z',
      '2024-06-15T12:03:00Z',
    ],
    minTime: '2024-06-15T12:00:00Z',
    maxTime: '2024-06-15T12:03:00Z',
    timeRange: 180,
    title: 'Test',
    sliderId: 'slider',
    timeLegendId: 'time',
    playPauseButtonId: 'play',
    boatLegendId: 'legend',
    sliderActiveColor: '#111',
    sliderInactiveColor: '#ddd',
    tailPointCount: 2,
    fullTrackLayerNames: [null],
  }}
}};
{playback_js}
const state = window.gpxPlayerPlayback.map_test;
const slider = state.slider;
assert.strictEqual(state.minTimeMs, Date.parse('2024-06-15T12:00:00Z'));
assert.strictEqual(state.maxTimeMs, Date.parse('2024-06-15T12:03:00Z'));
assert.strictEqual(state.currentTimeMs, state.minTimeMs);
assert.strictEqual(state.playbackRate, 1);
assert.deepStrictEqual(state.currentSegmentIndexes, [0]);
slider.value = 500;
slider.dispatchEvent(new Event('input'));
assert.strictEqual(state.currentTimeMs, Date.parse('2024-06-15T12:01:30Z'));
assert.deepStrictEqual(state.currentPointIndexes, [1]);
assert.deepStrictEqual(state.currentSegmentIndexes, [1]);
slider.value = 250;
slider.dispatchEvent(new Event('input'));
assert.strictEqual(state.currentTimeMs, Date.parse('2024-06-15T12:00:45Z'));
assert.deepStrictEqual(state.currentPointIndexes, [0]);
assert.deepStrictEqual(state.currentSegmentIndexes, [0]);
assert.strictEqual(state.slider.style['--gpx-slider-progress'], '25%');
"""
    result = subprocess.run(
        ["node", "-e", script],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```bash
env MPLCONFIGDIR=/tmp pytest tests/test_openseamap.py::test_playback_js_uses_elapsed_time_slider_and_segment_cursors -q
```

Expected: FAIL because `state.minTimeMs`, `state.playbackRate`, and `state.currentSegmentIndexes` are not initialized yet, and slider `500` maps by timestamp index rather than elapsed time.

- [ ] **Step 3: Initialize playback-clock state**

In `gpx_player/assets/animate_tracks.js`, replace the initialization block in `initPlaybackMap`:

```javascript
state.isPlaying = false;
state.playbackInterval = null;
state.trackTimeValues = initializeTrackTimeValues(state);
state.currentPointIndexes = state.points.map(() => 0);
state.trackModes = state.points.map(() => "full");
state.fullTrackLayers = initializeFullTrackLayers(state);
state.trackHeadings = initializeTrackHeadings(state);
```

with:

```javascript
state.isPlaying = false;
state.playbackAnimationFrame = null;
state.lastFrameTimeMs = null;
state.playbackRate = 1;
state.trackTimeValues = initializeTrackTimeValues(state);
initializePlaybackClock(state);
state.currentPointIndexes = state.points.map(() => 0);
state.currentSegmentIndexes = state.points.map(() => 0);
state.trackModes = state.points.map(() => "full");
state.fullTrackLayers = initializeFullTrackLayers(state);
state.trackHeadings = initializeTrackHeadings(state);
```

- [ ] **Step 4: Replace slider input with elapsed-time refresh**

Replace the current slider input listener:

```javascript
slider.addEventListener('input', () => {
    updateSliderVisual(state);
    updateCurrentPointIndexes(state);
    updateTrackMarkers(state);
    updateTailLayers(state);
    updateTimeDisplay(state);
    updateBoatLegend(state);
});
```

with:

```javascript
slider.addEventListener('input', () => {
    state.currentTimeMs = timeFromSlider(state);
    refreshPlaybackForCurrentTime(state);
});
```

- [ ] **Step 5: Add elapsed-time helper functions**

Replace `sliderTimeIndex`, `currentSliderTime`, `pointIndexAtTime`, and `updateCurrentPointIndexes` with this block:

```javascript
function initializePlaybackClock(state) {
    const timestampValues = (state.timestamps || [])
        .map((timestamp) => new Date(timestamp).getTime())
        .filter((timestamp) => Number.isFinite(timestamp));
    const payloadMinTime = new Date(state.minTime).getTime();
    const payloadMaxTime = new Date(state.maxTime).getTime();
    state.minTimeMs = Number.isFinite(payloadMinTime)
        ? payloadMinTime
        : Math.min(...timestampValues);
    state.maxTimeMs = Number.isFinite(payloadMaxTime)
        ? payloadMaxTime
        : Math.max(...timestampValues);
    if (!Number.isFinite(state.minTimeMs)) {
        state.minTimeMs = 0;
    }
    if (!Number.isFinite(state.maxTimeMs) || state.maxTimeMs < state.minTimeMs) {
        state.maxTimeMs = state.minTimeMs;
    }
    state.currentTimeMs = state.minTimeMs;
}

function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

function timeFromSlider(state) {
    const slider = state.slider;
    const minValue = parseInt(slider.min, 10) || 0;
    const maxValue = parseInt(slider.max, 10) || 0;
    const sliderValue = parseInt(slider.value, 10) || 0;
    const sliderRange = Math.max(1, maxValue - minValue);
    const ratio = clamp((sliderValue - minValue) / sliderRange, 0, 1);
    return state.minTimeMs + ratio * (state.maxTimeMs - state.minTimeMs);
}

function setSliderToTime(state, timeMs) {
    const slider = state.slider;
    const minValue = parseInt(slider.min, 10) || 0;
    const maxValue = parseInt(slider.max, 10) || 0;
    const timeRange = state.maxTimeMs - state.minTimeMs;
    const ratio = timeRange > 0 ? (timeMs - state.minTimeMs) / timeRange : 0;
    slider.value = String(Math.round(minValue + clamp(ratio, 0, 1) * (maxValue - minValue)));
    updateSliderVisual(state);
}

function findPointIndexAtTime(times, currentTimeMs) {
    if (!times.length || currentTimeMs < times[0]) {
        return 0;
    }
    let low = 0;
    let high = times.length - 1;
    while (low <= high) {
        const mid = Math.floor((low + high) / 2);
        if (times[mid] <= currentTimeMs) {
            low = mid + 1;
        } else {
            high = mid - 1;
        }
    }
    return Math.max(0, high);
}

function findSegmentIndexAtTime(times, currentTimeMs, previousIndex) {
    if (times.length < 2) {
        return 0;
    }
    const lastSegmentIndex = times.length - 2;
    let index = clamp(previousIndex || 0, 0, lastSegmentIndex);
    if (currentTimeMs >= times[index] && currentTimeMs <= times[index + 1]) {
        return index;
    }
    if (currentTimeMs >= times[index + 1]) {
        while (index < lastSegmentIndex && currentTimeMs > times[index + 1]) {
            index += 1;
        }
        return index;
    }
    let low = 0;
    let high = lastSegmentIndex;
    while (low <= high) {
        const mid = Math.floor((low + high) / 2);
        if (currentTimeMs < times[mid]) {
            high = mid - 1;
        } else if (currentTimeMs > times[mid + 1]) {
            low = mid + 1;
        } else {
            return mid;
        }
    }
    return clamp(high, 0, lastSegmentIndex);
}

function refreshPlaybackForCurrentTime(state) {
    state.currentTimeMs = clamp(state.currentTimeMs, state.minTimeMs, state.maxTimeMs);
    state.currentPointIndexes = state.trackTimeValues.map((times) => (
        findPointIndexAtTime(times, state.currentTimeMs)
    ));
    state.currentSegmentIndexes = state.trackTimeValues.map((times, trackIndex) => (
        findSegmentIndexAtTime(times, state.currentTimeMs, state.currentSegmentIndexes[trackIndex])
    ));
    setSliderToTime(state, state.currentTimeMs);
    renderPlaybackFrame(state);
}
```

- [ ] **Step 6: Add `renderPlaybackFrame` with the existing render order**

Add this helper after `refreshPlaybackForCurrentTime`:

```javascript
function renderPlaybackFrame(state) {
    updateTrackMarkers(state);
    updateTailLayers(state);
    updateTimeDisplay(state);
    updateBoatLegend(state);
}
```

- [ ] **Step 7: Update time display to read the playback clock**

Replace `updateTimeDisplay` with:

```javascript
function updateTimeDisplay(state) {
    state.timeDisplay.textContent = new Date(state.currentTimeMs).toUTCString().replace('GMT', 'UTC');
}
```

- [ ] **Step 8: Run the focused test**

Run:

```bash
env MPLCONFIGDIR=/tmp pytest tests/test_openseamap.py::test_playback_js_uses_elapsed_time_slider_and_segment_cursors -q
```

Expected: PASS.

- [ ] **Step 9: Run syntax check**

Run:

```bash
node --check gpx_player/assets/animate_tracks.js
```

Expected: no output and exit code 0.

- [ ] **Step 10: Commit Task 1**

Run:

```bash
git add gpx_player/assets/animate_tracks.js tests/test_openseamap.py
git commit -m "Add elapsed-time playback clock"
```

---

### Task 2: Interpolated Marker Position And Heading

**Files:**
- Modify: `gpx_player/assets/animate_tracks.js:438-498`
- Test: `tests/test_openseamap.py`

**Interfaces:**
- Consumes from Task 1:
  - `state.currentTimeMs`
  - `state.currentPointIndexes`
  - `state.currentSegmentIndexes`
  - `state.trackTimeValues`
- Produces:
  - `trackPositionAtTime(track, times, currentTimeMs, segmentIndex, fallbackHeading): { lat: number, lon: number, heading: number }`
  - `movementHeadingForSegment(track, segmentIndex, fallbackHeading): number`
  - `updateTrackMarkers(state): void` using interpolated positions when markers are visible.

- [ ] **Step 1: Update the existing invalid-layer/tail test expectations to assert interpolation**

In `test_playback_js_ignores_invalid_full_track_layer_and_limits_tail_updates`, keep the setup but change the assertions after the initial render to:

```javascript
slider.value = 750;
slider.dispatchEvent(new Event('input'));
assert.strictEqual(tailLayer.setLatLngCalls, 1);
assert.deepStrictEqual(state.trackMarkers[0].latlng, [2, 1.5]);
assert.strictEqual(state.trackMarkers[0].arrow.style.transform, 'rotate(90deg)');
```

Then add this scrub assertion before switching to Tail mode:

```javascript
slider.value = 250;
slider.dispatchEvent(new Event('input'));
assert.deepStrictEqual(state.trackMarkers[0].latlng, [1.5, 1]);
assert.strictEqual(state.trackMarkers[0].arrow.style.transform, 'rotate(0deg)');
```

The complete middle of the test should read:

```javascript
assert.strictEqual(tailLayer.setLatLngCalls, 1);
assert.strictEqual(state.trackMarkers[0].arrow.style.transform, 'rotate(0deg)');
slider.value = 750;
slider.dispatchEvent(new Event('input'));
assert.strictEqual(tailLayer.setLatLngCalls, 1);
assert.deepStrictEqual(state.trackMarkers[0].latlng, [2, 1.5]);
assert.strictEqual(state.trackMarkers[0].arrow.style.transform, 'rotate(90deg)');
slider.value = 250;
slider.dispatchEvent(new Event('input'));
assert.deepStrictEqual(state.trackMarkers[0].latlng, [1.5, 1]);
assert.strictEqual(state.trackMarkers[0].arrow.style.transform, 'rotate(0deg)');
state.trackModeControls[0].value = 'tail';
state.trackModeControls[0].dispatchEvent(new Event('change'));
```

- [ ] **Step 2: Run the updated test and verify it fails**

Run:

```bash
env MPLCONFIGDIR=/tmp pytest tests/test_openseamap.py::test_playback_js_ignores_invalid_full_track_layer_and_limits_tail_updates -q
```

Expected: FAIL because marker `latlng` is still snapped to a real GPX point for each slider input.

- [ ] **Step 3: Replace point-snap marker updates with interpolated marker updates**

Replace `updateTrackMarkers` with:

```javascript
function updateTrackMarkers(state) {
    const map = state.map;
    state.trackMarkers.forEach((marker, trackIndex) => {
        if (state.trackModes[trackIndex] === 'off') {
            if (map.hasLayer(marker)) {
                map.removeLayer(marker);
            }
            return;
        }

        const track = state.points[trackIndex];
        const times = state.trackTimeValues[trackIndex];
        const segmentIndex = state.currentSegmentIndexes[trackIndex] || 0;
        const position = trackPositionAtTime(
            track,
            times,
            state.currentTimeMs,
            segmentIndex,
            state.trackHeadings[trackIndex] || 0
        );
        state.trackHeadings[trackIndex] = position.heading;
        marker.setLatLng([position.lat, position.lon]);
        updateTrackMarkerHeading(marker, position.heading);
        if (!map.hasLayer(marker)) {
            marker.addTo(map);
        }
    });
}
```

- [ ] **Step 4: Add interpolation helpers**

Add these helpers before `trackHeadingAtIndex`:

```javascript
function trackPositionAtTime(track, times, currentTimeMs, segmentIndex, fallbackHeading) {
    if (!track.length) {
        return {lat: 0, lon: 0, heading: fallbackHeading || 0};
    }
    if (track.length === 1 || times.length < 2 || currentTimeMs <= times[0]) {
        const firstPoint = track[0];
        return {
            lat: firstPoint.lat,
            lon: firstPoint.lon,
            heading: movementHeadingForSegment(track, 0, fallbackHeading || 0),
        };
    }
    const lastPoint = track[track.length - 1];
    if (currentTimeMs >= times[times.length - 1]) {
        return {
            lat: lastPoint.lat,
            lon: lastPoint.lon,
            heading: movementHeadingForSegment(track, track.length - 2, fallbackHeading || 0),
        };
    }

    const startIndex = clamp(segmentIndex, 0, track.length - 2);
    const endIndex = startIndex + 1;
    const startTime = times[startIndex];
    const endTime = times[endIndex];
    const startPoint = track[startIndex];
    const endPoint = track[endIndex];
    if (!Number.isFinite(startTime) || !Number.isFinite(endTime) || endTime <= startTime) {
        return {
            lat: startPoint.lat,
            lon: startPoint.lon,
            heading: movementHeadingForSegment(track, startIndex, fallbackHeading || 0),
        };
    }

    const ratio = clamp((currentTimeMs - startTime) / (endTime - startTime), 0, 1);
    return {
        lat: startPoint.lat + (endPoint.lat - startPoint.lat) * ratio,
        lon: startPoint.lon + (endPoint.lon - startPoint.lon) * ratio,
        heading: movementHeadingForSegment(track, startIndex, fallbackHeading || 0),
    };
}

function movementHeadingForSegment(track, segmentIndex, fallbackHeading) {
    if (!track.length) {
        return fallbackHeading || 0;
    }
    const startIndex = clamp(segmentIndex, 0, Math.max(0, track.length - 1));
    if (startIndex < track.length - 1 && hasMovement(track[startIndex], track[startIndex + 1])) {
        return headingBetween(track[startIndex], track[startIndex + 1]);
    }
    for (let i = startIndex; i > 0; i--) {
        if (hasMovement(track[i - 1], track[i])) {
            return headingBetween(track[i - 1], track[i]);
        }
    }
    for (let i = startIndex + 1; i < track.length - 1; i++) {
        if (hasMovement(track[i], track[i + 1])) {
            return headingBetween(track[i], track[i + 1]);
        }
    }
    return fallbackHeading || 0;
}
```

Keep `trackHeadingAtIndex` for initial marker heading and existing duplicate-point tests.

- [ ] **Step 5: Run the focused marker interpolation test**

Run:

```bash
env MPLCONFIGDIR=/tmp pytest tests/test_openseamap.py::test_playback_js_ignores_invalid_full_track_layer_and_limits_tail_updates -q
```

Expected: PASS.

- [ ] **Step 6: Run duplicate heading and full-layer toggle regression test**

Run:

```bash
env MPLCONFIGDIR=/tmp pytest tests/test_openseamap.py::test_playback_js_marker_heading_handles_duplicate_points_and_full_layer_toggle -q
```

Expected: PASS. The duplicate-position segment at slider `750` should keep the previous valid north heading, and the final point should rotate east.

- [ ] **Step 7: Run syntax check**

Run:

```bash
node --check gpx_player/assets/animate_tracks.js
```

Expected: no output and exit code 0.

- [ ] **Step 8: Commit Task 2**

Run:

```bash
git add gpx_player/assets/animate_tracks.js tests/test_openseamap.py
git commit -m "Interpolate playback marker positions"
```

---

### Task 3: RequestAnimationFrame Playback Loop And Playback Rate State

**Files:**
- Modify: `gpx_player/assets/animate_tracks.js:611-636`
- Test: `tests/test_openseamap.py`

**Interfaces:**
- Consumes from Task 1:
  - `state.currentTimeMs`
  - `state.minTimeMs`
  - `state.maxTimeMs`
  - `state.playbackRate`
  - `refreshPlaybackForCurrentTime(state)`
- Produces:
  - `startPlayback(state): void`
  - `stopPlayback(state): void`
  - `playbackFrame(state, frameTimeMs): void`
  - play/pause button behavior equivalent to current UI, but scheduled with `requestAnimationFrame`.

- [ ] **Step 1: Add a failing RAF/playback-rate test**

Add this test after `test_playback_js_uses_elapsed_time_slider_and_segment_cursors()`:

```python
def test_playback_js_request_animation_frame_advances_elapsed_time_with_rate():
    if not shutil.which("node"):
        pytest.skip("node is required for playback JS behavior test")

    asset_path = Path(__file__).resolve().parents[1] / "gpx_player" / "assets" / "animate_tracks.js"
    playback_js = asset_path.read_text(encoding="utf-8")
    script = f"""
const assert = require('assert');
const layers = new Set();
const frameCallbacks = [];
const cancelledFrames = [];
const map = {{
  addLayer(layer) {{ layers.add(layer); }},
  removeLayer(layer) {{ layers.delete(layer); }},
  hasLayer(layer) {{ return layers.has(layer); }}
}};
function makeElement(tag) {{
  return {{
    tagName: tag,
    style: {{ setProperty(name, value) {{ this[name] = value; }} }},
    children: [],
    listeners: {{}},
    appendChild(child) {{ this.children.push(child); return child; }},
    setAttribute(name, value) {{ this[name] = value; }},
    addEventListener(type, handler) {{ this.listeners[type] = handler; }},
    dispatchEvent(event) {{ if (this.listeners[event.type]) this.listeners[event.type](event); }},
  }};
}}
global.Event = function Event(type) {{ this.type = type; }};
global.window = global;
global.map_test = map;
global.requestAnimationFrame = function requestAnimationFrame(callback) {{
  frameCallbacks.push(callback);
  return frameCallbacks.length;
}};
global.cancelAnimationFrame = function cancelAnimationFrame(frameId) {{
  cancelledFrames.push(frameId);
}};
global.document = {{
  readyState: 'complete',
  body: makeElement('body'),
  head: makeElement('head'),
  createElement: makeElement,
  createTextNode(text) {{ return {{ textContent: text }}; }},
  getElementById() {{ return null; }},
}};
global.L = {{
  divIcon(options) {{ return options; }},
  marker(latlng, options) {{
    const arrow = {{ style: {{}} }};
    return {{
      latlng,
      icon: options.icon,
      options,
      addTo(targetMap) {{ targetMap.addLayer(this); return this; }},
      setLatLng(nextLatLng) {{ this.latlng = nextLatLng; }},
      setIcon(nextIcon) {{ this.icon = nextIcon; }},
      getElement() {{ return {{ querySelector(selector) {{ return selector === '.gpx-player-direction-marker' ? arrow : null; }} }}; }},
      arrow,
    }};
  }},
  polyline(latlngs) {{
    return {{
      latlngs,
      addTo(targetMap) {{ targetMap.addLayer(this); return this; }},
      setLatLngs(nextLatLngs) {{ this.latlngs = nextLatLngs; }},
    }};
  }},
  control() {{
    return {{ addTo(targetMap) {{ this.container = this.onAdd(targetMap); return this; }} }};
  }},
  DomUtil: {{ create(_tag, className) {{ const element = makeElement(_tag); element.className = className; return element; }} }},
  DomEvent: {{
    disableClickPropagation() {{}},
    disableScrollPropagation() {{}},
    on(element, type, handler) {{ element.addEventListener(type, handler); }},
  }},
}};
window.gpxPlayerPlayback = {{
  map_test: {{
    mapId: 'map_test',
    colors: ['red'],
    points: [[
      {{ lat: 1, lon: 1, time: '2024-06-15T12:00:00Z' }},
      {{ lat: 2, lon: 1, time: '2024-06-15T12:01:00Z' }},
    ]],
    speeds: [[0, 1]],
    distances: [[0, 1]],
    avgSpeeds: [[0, 1]],
    trackNames: ['Alpha'],
    timestamps: ['2024-06-15T12:00:00Z', '2024-06-15T12:01:00Z'],
    minTime: '2024-06-15T12:00:00Z',
    maxTime: '2024-06-15T12:01:00Z',
    timeRange: 60,
    title: 'Test',
    sliderId: 'slider',
    timeLegendId: 'time',
    playPauseButtonId: 'play',
    boatLegendId: 'legend',
    sliderActiveColor: '#111',
    sliderInactiveColor: '#ddd',
    tailPointCount: 2,
    fullTrackLayerNames: [null],
  }}
}};
{playback_js}
const state = window.gpxPlayerPlayback.map_test;
state.playbackRate = 2;
state.playPauseButton.dispatchEvent(new Event('click'));
assert.strictEqual(state.isPlaying, true);
assert.strictEqual(frameCallbacks.length, 1);
frameCallbacks.shift()(1000);
assert.strictEqual(state.currentTimeMs, Date.parse('2024-06-15T12:00:00Z'));
frameCallbacks.shift()(2000);
assert.strictEqual(state.currentTimeMs, Date.parse('2024-06-15T12:00:02Z'));
assert.strictEqual(state.slider.value, '33');
assert.deepStrictEqual(state.trackMarkers[0].latlng, [1 + 2 / 60, 1]);
state.playPauseButton.dispatchEvent(new Event('click'));
assert.strictEqual(state.isPlaying, false);
assert.ok(cancelledFrames.length >= 1);
"""
    result = subprocess.run(
        ["node", "-e", script],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
```

- [ ] **Step 2: Run the new RAF test and verify it fails**

Run:

```bash
env MPLCONFIGDIR=/tmp pytest tests/test_openseamap.py::test_playback_js_request_animation_frame_advances_elapsed_time_with_rate -q
```

Expected: FAIL because current playback still uses `setInterval`, `playbackInterval`, and slider increments.

- [ ] **Step 3: Replace interval playback functions with RAF functions**

Delete `updateSlider`. Replace `togglePlayPause` with:

```javascript
function togglePlayPause(state, playPauseButton) {
    if (state.isPlaying) {
        stopPlayback(state);
    } else {
        startPlayback(state);
        playPauseButton.style.backgroundColor = 'gray';
        playPauseButton.textContent = '⏸️';
        playPauseButton.setAttribute('aria-label', 'Pause GPX animation');
        playPauseButton.title = 'Pause GPX animation';
    }
}
```

Add these helpers before `togglePlayPause`:

```javascript
function startPlayback(state) {
    if (state.isPlaying) {
        return;
    }
    state.isPlaying = true;
    state.lastFrameTimeMs = null;
    state.playbackAnimationFrame = window.requestAnimationFrame((frameTimeMs) => (
        playbackFrame(state, frameTimeMs)
    ));
}

function stopPlayback(state) {
    if (state.playbackAnimationFrame !== null) {
        window.cancelAnimationFrame(state.playbackAnimationFrame);
        state.playbackAnimationFrame = null;
    }
    state.lastFrameTimeMs = null;
    state.isPlaying = false;
    resetPlayPauseButton(state);
}

function playbackFrame(state, frameTimeMs) {
    if (!state.isPlaying) {
        return;
    }
    if (state.lastFrameTimeMs === null) {
        state.lastFrameTimeMs = frameTimeMs;
    } else {
        const frameDeltaMs = Math.max(0, frameTimeMs - state.lastFrameTimeMs);
        state.lastFrameTimeMs = frameTimeMs;
        state.currentTimeMs = clamp(
            state.currentTimeMs + frameDeltaMs * state.playbackRate,
            state.minTimeMs,
            state.maxTimeMs
        );
        refreshPlaybackForCurrentTime(state);
    }

    if (state.currentTimeMs >= state.maxTimeMs) {
        stopPlayback(state);
        return;
    }

    state.playbackAnimationFrame = window.requestAnimationFrame((nextFrameTimeMs) => (
        playbackFrame(state, nextFrameTimeMs)
    ));
}
```

- [ ] **Step 4: Run the RAF test**

Run:

```bash
env MPLCONFIGDIR=/tmp pytest tests/test_openseamap.py::test_playback_js_request_animation_frame_advances_elapsed_time_with_rate -q
```

Expected: PASS.

- [ ] **Step 5: Update render assertions away from interval playback**

In `test_create_playback_map_renders_from_arbitrary_cwd`, add:

```python
assert "requestAnimationFrame" in rendered
assert "playbackRate" in rendered
assert "setInterval" not in rendered
```

- [ ] **Step 6: Run render test**

Run:

```bash
env MPLCONFIGDIR=/tmp pytest tests/test_openseamap.py::test_create_playback_map_renders_from_arbitrary_cwd -q
```

Expected: PASS.

- [ ] **Step 7: Run syntax check**

Run:

```bash
node --check gpx_player/assets/animate_tracks.js
```

Expected: no output and exit code 0.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add gpx_player/assets/animate_tracks.js tests/test_openseamap.py
git commit -m "Use animation frames for playback"
```

---

### Task 4: Point-Based Tail With Interpolated Live Endpoint

**Files:**
- Modify: `gpx_player/assets/animate_tracks.js:500-519`
- Modify: `gpx_player/assets/animate_tracks.js:552-601`
- Test: `tests/test_openseamap.py`

**Interfaces:**
- Consumes from Task 2:
  - `trackPositionAtTime(track, times, currentTimeMs, segmentIndex, fallbackHeading)`
  - `state.currentPointIndexes`
  - `state.currentSegmentIndexes`
- Produces:
  - `tailLatLngs(state, trackIndex): [number, number][]` with the current interpolated marker position as the final point.

- [ ] **Step 1: Update tail test expectations**

In `test_playback_js_ignores_invalid_full_track_layer_and_limits_tail_updates`, after switching to Tail mode at slider value `250`, assert the live endpoint:

```javascript
state.trackModeControls[0].value = 'tail';
state.trackModeControls[0].dispatchEvent(new Event('change'));
assert.strictEqual(tailLayer.setLatLngCalls, 2);
assert.deepStrictEqual(tailLayer.latlngs, [[1, 1], [1.5, 1]]);
slider.value = 1000;
slider.dispatchEvent(new Event('input'));
assert.strictEqual(tailLayer.setLatLngCalls, 3);
assert.strictEqual(state.trackMarkers[0].arrow.style.transform, 'rotate(90deg)');
assert.deepStrictEqual(tailLayer.latlngs, [[2, 1], [2, 2]]);
```

- [ ] **Step 2: Run the focused tail test and verify it fails**

Run:

```bash
env MPLCONFIGDIR=/tmp pytest tests/test_openseamap.py::test_playback_js_ignores_invalid_full_track_layer_and_limits_tail_updates -q
```

Expected: FAIL because `tailLatLngs` still returns only real GPX points.

- [ ] **Step 3: Update `tailLatLngs` to append the live endpoint**

Replace `tailLatLngs` with:

```javascript
function tailLatLngs(state, trackIndex) {
    const track = state.points[trackIndex];
    const times = state.trackTimeValues[trackIndex];
    const pointIndex = state.currentPointIndexes[trackIndex] || 0;
    const segmentIndex = state.currentSegmentIndexes[trackIndex] || 0;
    const tailPointCount = Math.max(1, parseInt(state.tailPointCount, 10) || 60);
    const startIndex = Math.max(0, pointIndex - tailPointCount + 1);
    const latlngs = track.slice(startIndex, pointIndex + 1).map((point) => [point.lat, point.lon]);
    const livePosition = trackPositionAtTime(
        track,
        times,
        state.currentTimeMs,
        segmentIndex,
        state.trackHeadings[trackIndex] || 0
    );
    const liveLatLng = [livePosition.lat, livePosition.lon];
    const lastLatLng = latlngs[latlngs.length - 1];
    if (!lastLatLng || lastLatLng[0] !== liveLatLng[0] || lastLatLng[1] !== liveLatLng[1]) {
        latlngs.push(liveLatLng);
    }
    return latlngs;
}
```

- [ ] **Step 4: Ensure mode transitions render current tail state**

In `applyTrackMode`, keep the existing calls to `tailLayer.setLatLngs(tailLatLngs(state, trackIndex))` when mode is `tail`. Do not call `setLatLngs` for Full or Off except to clear the layer.

- [ ] **Step 5: Run the focused tail test**

Run:

```bash
env MPLCONFIGDIR=/tmp pytest tests/test_openseamap.py::test_playback_js_ignores_invalid_full_track_layer_and_limits_tail_updates -q
```

Expected: PASS.

- [ ] **Step 6: Run duplicate/full-layer regression test**

Run:

```bash
env MPLCONFIGDIR=/tmp pytest tests/test_openseamap.py::test_playback_js_marker_heading_handles_duplicate_points_and_full_layer_toggle -q
```

Expected: PASS.

- [ ] **Step 7: Run syntax check**

Run:

```bash
node --check gpx_player/assets/animate_tracks.js
```

Expected: no output and exit code 0.

- [ ] **Step 8: Commit Task 4**

Run:

```bash
git add gpx_player/assets/animate_tracks.js tests/test_openseamap.py
git commit -m "Extend playback tails to live marker position"
```

---

### Task 5: Full Regression And Compatibility Sweep

**Files:**
- Modify: `tests/test_openseamap.py`
- Modify: `gpx_player/assets/animate_tracks.js`

**Interfaces:**
- Consumes all tasks above.
- Produces a tested implementation with no public Python API change and no added payload fields.

- [ ] **Step 1: Search for stale interval/index playback references**

Run:

```bash
rg -n "playbackInterval|setInterval|sliderTimeIndex|currentSliderTime|updateSlider\\(" gpx_player/assets/animate_tracks.js tests/test_openseamap.py
```

Expected: no matches.

- [ ] **Step 2: Verify no generated payload changes were introduced**

Run:

```bash
rg -n "playbackRate|currentTimeMs|currentSegmentIndexes|minTimeMs|maxTimeMs" gpx_player/openseamap.py
```

Expected: no matches, because those are JS runtime state fields only.

- [ ] **Step 3: Run JS syntax check**

Run:

```bash
node --check gpx_player/assets/animate_tracks.js
```

Expected: no output and exit code 0.

- [ ] **Step 4: Run focused OpenSeaMap tests**

Run:

```bash
env MPLCONFIGDIR=/tmp pytest tests/test_openseamap.py
```

Expected: all tests in `tests/test_openseamap.py` pass.

- [ ] **Step 5: Run full test suite**

Run:

```bash
env MPLCONFIGDIR=/tmp pytest
```

Expected: full suite passes.

- [ ] **Step 6: Run compile check**

Run:

```bash
python -m compileall -q gpx_player tests
```

Expected: no output and exit code 0.

- [ ] **Step 7: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 8: Review final diff for portability and payload size**

Run:

```bash
git diff --stat HEAD~4..HEAD
git diff HEAD~4..HEAD -- gpx_player/assets/animate_tracks.js gpx_player/openseamap.py tests/test_openseamap.py
```

Expected:

- `gpx_player/assets/animate_tracks.js` contains `requestAnimationFrame`, `playbackRate`, interpolation helpers, and no `setInterval`.
- `gpx_player/openseamap.py` has no changes for this feature.
- `tests/test_openseamap.py` contains Node-stub coverage for elapsed-time slider mapping, interpolation, RAF playback rate, tails, duplicate points, and visibility modes.

- [ ] **Step 9: Commit final cleanup if needed**

If Step 8 shows only uncommitted test expectation or cleanup edits, run:

```bash
git add gpx_player/assets/animate_tracks.js tests/test_openseamap.py
git commit -m "Verify smooth playback integration"
```

If there are no uncommitted edits after Step 8, do not create an empty commit.

---

## Self-Review Notes

- Spec coverage: Tasks 1-4 cover elapsed-time clock, client-side interpolation, future `playbackRate`, marker heading, point-based tail with live endpoint, and visibility behavior. Task 5 covers portability, no Python payload changes, and regression verification.
- Placeholder scan: no implementation step relies on unspecified behavior; each test and code change has concrete snippets and commands.
- Type consistency: runtime state names are consistent across tasks: `currentTimeMs`, `minTimeMs`, `maxTimeMs`, `playbackRate`, `lastFrameTimeMs`, `playbackAnimationFrame`, `currentPointIndexes`, and `currentSegmentIndexes`.
