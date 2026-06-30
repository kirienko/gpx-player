(function () {
    "use strict";

    const TRACK_MODES = ["full", "tail", "off"];

    function registry() {
        window.gpxPlayerPlayback = window.gpxPlayerPlayback || {};
        return window.gpxPlayerPlayback;
    }

    function initAllPlaybackMaps() {
        const playbackMaps = registry();
        Object.keys(playbackMaps).forEach((mapId) => {
            initPlaybackMap(mapId, playbackMaps[mapId]);
        });
    }

    function initPlaybackMap(mapId, state) {
        if (!state || state.initialized) {
            return;
        }

        const map = window[mapId];
        if (!map || !window.L) {
            return;
        }

        state.initialized = true;
        state.map = map;
        state.isPlaying = false;
        state.playbackInterval = null;
        state.trackTimeValues = initializeTrackTimeValues(state);
        state.currentPointIndexes = state.points.map(() => 0);
        state.trackModes = state.points.map(() => "full");
        state.fullTrackLayers = initializeFullTrackLayers(state);
        state.trackHeadings = initializeTrackHeadings(state);

        const slider = createSlider(state);
        const timeLegend = createTimeLegend(state, slider);
        const boatLegend = document.getElementById(state.boatLegendId);
        const trackMarkers = initializeTrackMarkers(map, state);
        const tailLayers = initializeTailLayers(state);
        const visibilityControl = createTrackVisibilityControl(state);

        state.slider = slider;
        state.timeLegend = timeLegend;
        state.boatLegend = boatLegend;
        state.trackMarkers = trackMarkers;
        state.tailLayers = tailLayers;
        state.visibilityControl = visibilityControl;

        document.body.appendChild(slider);
        document.body.appendChild(timeLegend);
        visibilityControl.addTo(map);

        slider.addEventListener('input', () => {
            updateSliderVisual(state);
            updateCurrentPointIndexes(state);
            updateTrackMarkers(state);
            updateTailLayers(state);
            updateTimeDisplay(state);
            updateBoatLegend(state);
        });

        slider.dispatchEvent(new Event('input'));
        state.trackModes.forEach((_mode, trackIndex) => applyTrackMode(state, trackIndex));
    }

    function createSlider(state) {
        const slider = document.createElement('input');
        slider.type = 'range';
        slider.min = 0;
        slider.max = 1000;
        slider.value = 0;
        slider.id = state.sliderId;
        slider.className = 'gpx-player-time-slider';
        slider.setAttribute('aria-label', 'Playback time');
        slider.title = 'Playback time';
        Object.assign(slider.style, {
            position: 'fixed',
            bottom: '20px',
            left: '50%',
            transform: 'translateX(-50%)',
            width: '80%',
            zIndex: 1000,
        });
        applySliderTheme(state, slider);
        updateSliderProgress(slider);
        return slider;
    }

    function cssEscape(value) {
        if (window.CSS && typeof window.CSS.escape === 'function') {
            return window.CSS.escape(value);
        }
        return String(value).replace(/([^\w-])/g, '\\$1');
    }

    function applySliderTheme(state, slider) {
        const styleId = `${state.sliderId}-theme`;
        if (!document.getElementById(styleId)) {
            const sliderSelector = `#${cssEscape(state.sliderId)}`;
            const style = document.createElement('style');
            style.id = styleId;
            style.textContent = `
${sliderSelector} {
    -webkit-appearance: none;
    appearance: none;
    background: transparent;
    cursor: pointer;
    height: 24px;
}
${sliderSelector}:focus {
    outline: 2px solid #ffffff;
    outline-offset: 4px;
}
${sliderSelector}:focus-visible {
    box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.45);
}
${sliderSelector}::-webkit-slider-runnable-track {
    height: 6px;
    border-radius: 999px;
    background: linear-gradient(
        to right,
        var(--gpx-slider-active-color) 0%,
        var(--gpx-slider-active-color) var(--gpx-slider-progress),
        var(--gpx-slider-inactive-color) var(--gpx-slider-progress),
        var(--gpx-slider-inactive-color) 100%
    );
}
${sliderSelector}::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 24px;
    height: 24px;
    margin-top: -9px;
    border: 1px solid #bdbdbd;
    border-radius: 50%;
    background: #ffffff;
}
${sliderSelector}::-moz-range-track {
    height: 6px;
    border: none;
    border-radius: 999px;
    background: var(--gpx-slider-inactive-color);
}
${sliderSelector}::-moz-range-progress {
    height: 6px;
    border-radius: 999px;
    background: var(--gpx-slider-active-color);
}
${sliderSelector}::-moz-range-thumb {
    width: 24px;
    height: 24px;
    border: 1px solid #bdbdbd;
    border-radius: 50%;
    background: #ffffff;
}
`;
            document.head.appendChild(style);
        }

        slider.style.setProperty('--gpx-slider-active-color', state.sliderActiveColor || '#6e6e6e');
        slider.style.setProperty('--gpx-slider-inactive-color', state.sliderInactiveColor || '#d0d0d0');
    }

    function updateSliderProgress(slider) {
        const min = parseInt(slider.min, 10) || 0;
        const max = parseInt(slider.max, 10) || 0;
        const value = parseInt(slider.value, 10) || 0;
        const progress = max > min ? ((value - min) / (max - min)) * 100 : 0;
        slider.style.setProperty('--gpx-slider-progress', `${progress}%`);
    }

    function updateSliderVisual(state) {
        if (!state.slider) {
            return;
        }
        updateSliderProgress(state.slider);
    }

    function createTimeLegend(state, slider) {
        const timeLegend = document.createElement('div');
        timeLegend.id = state.timeLegendId;
        timeLegend.className = 'gpx-player-time-control';
        Object.assign(timeLegend.style, {
            position: 'fixed',
            bottom: '50px',
            right: '10px',
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            padding: '5px',
            border: '1px solid white',
            borderRadius: '5px',
            zIndex: 1000,
            color: 'white',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
        });

        const timeDisplay = document.createElement('div');
        timeDisplay.className = 'gpx-player-time-display';
        timeDisplay.style.marginBottom = '2px';
        timeLegend.appendChild(timeDisplay);

        const playPauseButton = document.createElement('button');
        playPauseButton.id = state.playPauseButtonId;
        playPauseButton.className = 'gpx-player-play-pause';
        playPauseButton.type = 'button';
        playPauseButton.textContent = '⏯️';
        playPauseButton.setAttribute('aria-label', 'Play GPX animation');
        playPauseButton.title = 'Play GPX animation';
        playPauseButton.style.marginTop = '5px';
        playPauseButton.addEventListener('click', () => togglePlayPause(state, playPauseButton));

        timeLegend.appendChild(playPauseButton);
        state.timeDisplay = timeDisplay;
        state.playPauseButton = playPauseButton;

        return timeLegend;
    }

    function initializeTrackTimeValues(state) {
        return state.points.map((track) => track.map((point) => new Date(point.time).getTime()));
    }

    function initializeFullTrackLayers(state) {
        const names = state.fullTrackLayerNames || [];
        return state.points.map((_track, index) => {
            const name = names[index];
            const layer = name ? window[name] : null;
            return isLeafletLayer(layer) ? layer : null;
        });
    }

    function isLeafletLayer(candidate) {
        return candidate && typeof candidate.addTo === 'function';
    }

    function initializeTrackMarkers(map, state) {
        return state.points.map((track, index) => {
            const color = state.colors[index % state.colors.length];
            const marker = L.marker([track[0].lat, track[0].lon], {
                icon: createTrackMarkerIcon(color, state.trackHeadings[index] || 0),
                interactive: false,
                keyboard: false
            }).addTo(map);
            marker._gpxPlayerColor = color;
            return marker;
        });
    }

    function createTrackMarkerIcon(color, heading) {
        return L.divIcon({
            className: 'gpx-player-direction-marker-icon',
            html: `<div class="gpx-player-direction-marker" style="
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-bottom: 13px solid ${color};
                transform: rotate(${heading}deg);
                transform-origin: 50% 60%;
            "></div>`,
            iconSize: [14, 14],
            iconAnchor: [7, 7],
        });
    }

    function initializeTrackHeadings(state) {
        return state.points.map((track) => trackHeadingAtIndex(track, 0, 0));
    }

    function initializeTailLayers(state) {
        return state.points.map((_track, index) => {
            const color = state.colors[index % state.colors.length];
            return L.polyline([], {
                color: color,
                weight: 3,
                opacity: 0.9,
                interactive: false
            });
        });
    }

    function createTrackVisibilityControl(state) {
        const control = L.control({position: 'topright'});
        control.onAdd = () => {
            const container = L.DomUtil.create('div', 'leaflet-control gpx-player-track-visibility');
            container.id = `gpx-player-track-visibility-${state.mapId}`;
            Object.assign(container.style, {
                backgroundColor: 'rgba(0, 0, 0, 0.5)',
                border: '1px solid white',
                borderRadius: '5px',
                color: 'white',
                fontSize: '10px',
                padding: '2px 3px',
                width: '128px',
                maxWidth: 'calc(100vw - 20px)',
                boxSizing: 'border-box',
            });
            L.DomEvent.disableClickPropagation(container);
            if (L.DomEvent.disableScrollPropagation) {
                L.DomEvent.disableScrollPropagation(container);
            }

            const title = document.createElement('div');
            title.textContent = 'Tracks';
            Object.assign(title.style, {
                fontWeight: '600',
                marginBottom: '2px',
            });
            container.appendChild(title);

            state.trackModeControls = [];
            state.trackNames.forEach((name, trackIndex) => {
                const row = document.createElement('div');
                row.className = 'gpx-player-track-visibility-row';
                Object.assign(row.style, {
                    display: 'grid',
                    gridTemplateColumns: 'minmax(0, 1fr) auto',
                    gap: '3px',
                    alignItems: 'center',
                    marginTop: trackIndex === 0 ? '0' : '2px',
                });

                const label = document.createElement('span');
                Object.assign(label.style, {
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                });
                const dot = document.createElement('span');
                dot.textContent = '●';
                dot.style.color = state.colors[trackIndex % state.colors.length];
                label.appendChild(dot);
                label.appendChild(document.createTextNode(` ${name}`));
                row.appendChild(label);

                const selectWrap = document.createElement('span');
                Object.assign(selectWrap.style, {
                    position: 'relative',
                    display: 'inline-block',
                    width: '38px',
                });

                const select = document.createElement('select');
                select.className = 'gpx-player-track-mode-select';
                select.setAttribute('aria-label', `${name}: track visibility`);
                select.title = `${name}: track visibility`;
                Object.assign(select.style, {
                    appearance: 'none',
                    WebkitAppearance: 'none',
                    MozAppearance: 'none',
                    border: '1px solid white',
                    borderRadius: '3px',
                    background: 'rgba(0, 0, 0, 0.2)',
                    color: 'white',
                    cursor: 'pointer',
                    fontSize: '10px',
                    lineHeight: '1.2',
                    width: '38px',
                    padding: '1px 8px 1px 2px',
                    boxSizing: 'border-box',
                });
                TRACK_MODES.forEach((mode) => {
                    const option = document.createElement('option');
                    option.value = mode;
                    option.textContent = mode === 'full' ? 'Full' : mode === 'tail' ? 'Tail' : 'Off';
                    option.style.color = '#222';
                    option.style.background = 'white';
                    select.appendChild(option);
                });
                L.DomEvent.on(select, 'change', () => setTrackMode(state, trackIndex, select.value));
                state.trackModeControls[trackIndex] = select;

                const arrow = document.createElement('span');
                arrow.textContent = '▾';
                Object.assign(arrow.style, {
                    position: 'absolute',
                    right: '3px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: 'white',
                    fontSize: '8px',
                    lineHeight: '1',
                    pointerEvents: 'none',
                });

                selectWrap.appendChild(select);
                selectWrap.appendChild(arrow);
                row.appendChild(selectWrap);
                container.appendChild(row);
                updateTrackModeControl(state, trackIndex);
            });

            return container;
        };
        return control;
    }

    function sliderTimeIndex(state) {
        const slider = state.slider;
        if (!state.timestamps.length) {
            return 0;
        }
        return Math.floor(slider.value / 1000 * (state.timestamps.length - 1));
    }

    function currentSliderTime(state) {
        const timeIndex = sliderTimeIndex(state);
        return new Date(state.timestamps[timeIndex]).getTime();
    }

    function pointIndexAtTime(times, currentTime) {
        if (!times.length || currentTime < times[0]) {
            return 0;
        }
        let low = 0;
        let high = times.length - 1;
        while (low <= high) {
            const mid = Math.floor((low + high) / 2);
            if (times[mid] <= currentTime) {
                low = mid + 1;
            } else {
                high = mid - 1;
            }
        }
        return Math.max(0, high);
    }

    function updateCurrentPointIndexes(state) {
        const currentTime = currentSliderTime(state);
        state.currentTime = currentTime;
        state.currentPointIndexes = state.trackTimeValues.map((times) => pointIndexAtTime(times, currentTime));
    }

    function updateTrackMarkers(state) {
        const map = state.map;
        state.trackMarkers.forEach((marker, trackIndex) => {
            const track = state.points[trackIndex];
            const pointIndex = state.currentPointIndexes[trackIndex] || 0;
            const closestPoint = track[pointIndex] || track[0];
            const heading = trackHeadingAtIndex(track, pointIndex, state.trackHeadings[trackIndex] || 0);
            state.trackHeadings[trackIndex] = heading;
            marker.setLatLng([closestPoint.lat, closestPoint.lon]);
            updateTrackMarkerHeading(marker, heading);
            if (state.trackModes[trackIndex] === 'off') {
                if (map.hasLayer(marker)) {
                    map.removeLayer(marker);
                }
            } else if (!map.hasLayer(marker)) {
                marker.addTo(map);
            }
        });
    }

    function trackHeadingAtIndex(track, pointIndex, fallbackHeading) {
        const point = track[pointIndex] || track[0];
        if (!point) {
            return fallbackHeading || 0;
        }
        for (let i = pointIndex - 1; i >= 0; i--) {
            if (hasMovement(track[i], point)) {
                return headingBetween(track[i], point);
            }
        }
        for (let i = pointIndex + 1; i < track.length; i++) {
            if (hasMovement(point, track[i])) {
                return headingBetween(point, track[i]);
            }
        }
        return fallbackHeading || 0;
    }

    function hasMovement(fromPoint, toPoint) {
        if (!fromPoint || !toPoint) {
            return false;
        }
        return fromPoint.lat !== toPoint.lat || fromPoint.lon !== toPoint.lon;
    }

    function headingBetween(fromPoint, toPoint) {
        const dx = toPoint.lon - fromPoint.lon;
        const dy = toPoint.lat - fromPoint.lat;
        const heading = Math.atan2(dx, dy) * 180 / Math.PI;
        return (heading + 360) % 360;
    }

    function updateTrackMarkerHeading(marker, heading) {
        const element = marker.getElement && marker.getElement();
        const arrow = element && element.querySelector && element.querySelector('.gpx-player-direction-marker');
        if (arrow) {
            arrow.style.transform = `rotate(${heading}deg)`;
        } else if (marker.setIcon) {
            marker.setIcon(createTrackMarkerIcon(marker._gpxPlayerColor || 'red', heading));
        }
    }

    function tailLatLngs(state, trackIndex) {
        const track = state.points[trackIndex];
        const pointIndex = state.currentPointIndexes[trackIndex] || 0;
        const tailPointCount = Math.max(1, parseInt(state.tailPointCount, 10) || 60);
        const startIndex = Math.max(0, pointIndex - tailPointCount + 1);
        return track.slice(startIndex, pointIndex + 1).map((point) => [point.lat, point.lon]);
    }

    function updateTailLayers(state) {
        const map = state.map;
        state.tailLayers.forEach((tailLayer, trackIndex) => {
            if (state.trackModes[trackIndex] !== 'tail') {
                return;
            }
            tailLayer.setLatLngs(tailLatLngs(state, trackIndex));
            if (!map.hasLayer(tailLayer)) {
                tailLayer.addTo(map);
            }
        });
    }

    function updateTimeDisplay(state) {
        const currentTime = state.currentTime || currentSliderTime(state);
        state.timeDisplay.textContent = new Date(currentTime).toUTCString().replace('GMT', 'UTC');
    }

    function updateBoatLegend(state) {
        const legend = state.boatLegend;
        if (!legend) {
            return;
        }
        legend.querySelectorAll('.boat-entry').forEach((entry) => {
            const idx = parseInt(entry.getAttribute('data-index'), 10);
            const speeds = state.speeds[idx];
            const dists = state.distances[idx];
            const avgs = state.avgSpeeds[idx];
            const pointIndex = state.currentPointIndexes[idx] || 0;
            entry.querySelector('.distance').textContent = `${dists[pointIndex].toFixed(1)} nm`;
            entry.querySelector('.speed').textContent = `${speeds[pointIndex].toFixed(1)} kt`;
            entry.querySelector('.avg-speed').textContent = `${avgs[pointIndex].toFixed(1)} kt`;
        });
    }

    function setTrackMode(state, trackIndex, mode) {
        if (!TRACK_MODES.includes(mode)) {
            return;
        }
        state.trackModes[trackIndex] = mode;
        applyTrackMode(state, trackIndex);
        updateTrackModeControl(state, trackIndex);
    }

    function applyTrackMode(state, trackIndex) {
        const map = state.map;
        const mode = state.trackModes[trackIndex];
        const fullLayer = state.fullTrackLayers[trackIndex];
        const tailLayer = state.tailLayers[trackIndex];
        const marker = state.trackMarkers[trackIndex];

        if (mode === 'full') {
            if (fullLayer && !map.hasLayer(fullLayer)) {
                fullLayer.addTo(map);
            }
            if (tailLayer) {
                tailLayer.setLatLngs([]);
                if (map.hasLayer(tailLayer)) {
                    map.removeLayer(tailLayer);
                }
            }
            if (marker && !map.hasLayer(marker)) {
                marker.addTo(map);
            }
            return;
        }

        if (fullLayer && map.hasLayer(fullLayer)) {
            map.removeLayer(fullLayer);
        }

        if (mode === 'tail') {
            if (marker && !map.hasLayer(marker)) {
                marker.addTo(map);
            }
            if (tailLayer) {
                tailLayer.setLatLngs(tailLatLngs(state, trackIndex));
                if (!map.hasLayer(tailLayer)) {
                    tailLayer.addTo(map);
                }
            }
            return;
        }

        if (tailLayer) {
            tailLayer.setLatLngs([]);
            if (map.hasLayer(tailLayer)) {
                map.removeLayer(tailLayer);
            }
        }
        if (marker && map.hasLayer(marker)) {
            map.removeLayer(marker);
        }
    }

    function updateTrackModeControl(state, trackIndex) {
        const control = state.trackModeControls && state.trackModeControls[trackIndex];
        if (!control) {
            return;
        }
        control.value = state.trackModes[trackIndex];
    }

    function updateSlider(state) {
        const slider = state.slider;
        if (parseInt(slider.value, 10) < parseInt(slider.max, 10)) {
            slider.value = parseInt(slider.value, 10) + 1;
            slider.dispatchEvent(new Event('input'));
        } else {
            clearInterval(state.playbackInterval);
            state.isPlaying = false;
            resetPlayPauseButton(state);
        }
    }

    function togglePlayPause(state, playPauseButton) {
        if (state.isPlaying) {
            clearInterval(state.playbackInterval);
            resetPlayPauseButton(state);
            state.isPlaying = false;
        } else {
            state.playbackInterval = setInterval(() => updateSlider(state), 100);
            playPauseButton.style.backgroundColor = 'gray';
            playPauseButton.textContent = '⏸️';
            playPauseButton.setAttribute('aria-label', 'Pause GPX animation');
            playPauseButton.title = 'Pause GPX animation';
            state.isPlaying = true;
        }
    }

    function resetPlayPauseButton(state) {
        const playPauseButton = state.playPauseButton;
        if (!playPauseButton) {
            return;
        }
        playPauseButton.style.backgroundColor = '';
        playPauseButton.textContent = '⏯️';
        playPauseButton.setAttribute('aria-label', 'Play GPX animation');
        playPauseButton.title = 'Play GPX animation';
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAllPlaybackMaps);
    } else {
        initAllPlaybackMaps();
    }
})();
