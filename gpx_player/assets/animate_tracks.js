(function () {
    "use strict";

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

        const slider = createSlider(state);
        const timeLegend = createTimeLegend(state, slider);
        const boatLegend = document.getElementById(state.boatLegendId);
        const trackMarkers = initializeTrackMarkers(map, state);

        state.initialized = true;
        state.isPlaying = false;
        state.playbackInterval = null;
        state.slider = slider;
        state.timeLegend = timeLegend;
        state.boatLegend = boatLegend;
        state.trackMarkers = trackMarkers;

        document.body.appendChild(slider);
        document.body.appendChild(timeLegend);

        slider.addEventListener('input', () => {
            updateSliderVisual(state);
            updateTrackMarkers(state);
            updateTimeDisplay(state);
            updateBoatLegend(state);
        });

        slider.dispatchEvent(new Event('input'));
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

    function initializeTrackMarkers(map, state) {
        return state.points.map((track, index) => {
            const color = state.colors[index % state.colors.length];
            const marker = L.circleMarker([track[0].lat, track[0].lon], {
                radius: 4,
                color: color,
                fillColor: color,
                fillOpacity: 0.5
            }).addTo(map);
            return marker;
        });
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

    function updateTrackMarkers(state) {
        const currentTime = currentSliderTime(state);

        state.trackMarkers.forEach((marker, trackIndex) => {
            const track = state.points[trackIndex];
            let closestPoint = track[0];
            for (let i = 1; i < track.length; i++) {
                const pointTime = new Date(track[i].time).getTime();
                if (pointTime <= currentTime) {
                    closestPoint = track[i];
                } else {
                    break;
                }
            }
            marker.setLatLng([closestPoint.lat, closestPoint.lon]);
        });
    }

    function updateTimeDisplay(state) {
        const currentTime = currentSliderTime(state);
        state.timeDisplay.textContent = new Date(currentTime).toUTCString().replace('GMT', 'UTC');
    }

    function updateBoatLegend(state) {
        const legend = state.boatLegend;
        if (!legend) {
            return;
        }
        const currentTime = currentSliderTime(state);
        legend.querySelectorAll('.boat-entry').forEach((entry) => {
            const idx = parseInt(entry.getAttribute('data-index'), 10);
            const track = state.points[idx];
            const speeds = state.speeds[idx];
            const dists = state.distances[idx];
            const avgs = state.avgSpeeds[idx];
            let pointIndex = 0;
            for (let i = 1; i < track.length; i++) {
                const pointTime = new Date(track[i].time).getTime();
                if (pointTime <= currentTime) {
                    pointIndex = i;
                } else {
                    break;
                }
            }
            entry.querySelector('.distance').textContent = `${dists[pointIndex].toFixed(1)} nm`;
            entry.querySelector('.speed').textContent = `${speeds[pointIndex].toFixed(1)} kt`;
            entry.querySelector('.avg-speed').textContent = `${avgs[pointIndex].toFixed(1)} kt`;
        });
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
