// Global variables to track play/pause state and the interval ID
let isPlaying = false;
let playbackInterval;
const colors = ['red', 'green', 'blue', 'orange', 'purple', 'brown', 'pink', 'yellow', 'cyan', 'magenta'];

document.addEventListener('DOMContentLoaded', () => {
    const slider = createSlider();
    const timeLegend = createTimeLegend(slider);
    const boatLegend = createBoatLegend();

    document.body.appendChild(slider);
    document.body.appendChild(timeLegend);
    document.body.appendChild(boatLegend);

    // Access the Folium-initialized map using the dynamically generated map_id
    const map = window[map_id];

    const trackMarkers = initializeTrackMarkers(map);

    slider.addEventListener('input', () => {
        updateTrackMarkers(slider, trackMarkers);
        updateTimeDisplay(slider, timeLegend);
        updateBoatLegend(slider, boatLegend);
    });

    // Initialize with the first timestamp
    slider.dispatchEvent(new Event('input'));
});

function createSlider() {
    const slider = document.createElement('input');
    slider.type = 'range';
    slider.min = 0;
    slider.max = 1000;
    slider.value = 0;
    Object.assign(slider.style, {
        position: 'fixed',
        bottom: '20px',
        left: '50%',
        transform: 'translateX(-50%)',
        width: '80%',
        zIndex: 1000,
    });
    return slider;
}

function createTimeLegend(slider) {
    const timeLegend = document.createElement('div');
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
    timeDisplay.style.marginBottom = '2px';
    timeLegend.appendChild(timeDisplay);

    const playPauseButton = document.createElement('button');
    playPauseButton.innerHTML = '⏯️'; // Play/Pause icon
    playPauseButton.style.marginTop = '5px';
    playPauseButton.addEventListener('click', () => togglePlayPause(slider, playPauseButton));

    timeLegend.appendChild(playPauseButton);

    timeLegend.timeDisplay = timeDisplay;

    return timeLegend;
}

function createBoatLegend() {
    const legend = document.getElementById('boat-legend');
    return legend;
}

function initializeTrackMarkers(map) {
    return gpx_points_data.map((track, index) => {
        const color = colors[index % colors.length];
        const marker = L.circleMarker([track[0].lat, track[0].lon], {
            radius: 4,
            color: color,
            fillColor: color,
            fillOpacity: 0.5
        }).addTo(map);
        return marker;
    });
}

function updateTrackMarkers(slider, trackMarkers) {
    const timeIndex = Math.floor(slider.value / 1000 * (gpx_timestamps.length - 1));
    const currentTime = new Date(gpx_timestamps[timeIndex]).getTime();

    trackMarkers.forEach((marker, trackIndex) => {
        const track = gpx_points_data[trackIndex];
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

function updateTimeDisplay(slider, timeLegend) {
    const timeIndex = Math.floor(slider.value / 1000 * (gpx_timestamps.length - 1));
    const currentTime = new Date(gpx_timestamps[timeIndex]).getTime();
    timeLegend.timeDisplay.innerHTML =
        `${new Date(currentTime).toUTCString().replace('GMT', 'UTC')}`;
}

function updateBoatLegend(slider, legend) {
    const timeIndex = Math.floor(slider.value / 1000 * (gpx_timestamps.length - 1));
    const currentTime = new Date(gpx_timestamps[timeIndex]).getTime();
    legend.querySelectorAll('.boat-entry').forEach((entry) => {
        const idx = parseInt(entry.getAttribute('data-index'));
        const track = gpx_points_data[idx];
        const speeds = gpx_speeds_data[idx];
        const dists = gpx_distances_data[idx];
        const avgs = gpx_avg_speeds_data[idx];
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

function updateSlider(slider) {
    if (parseInt(slider.value) < parseInt(slider.max)) {
        slider.value = parseInt(slider.value) + 1;
        slider.dispatchEvent(new Event('input'));
    } else {
        // Slider has reached the maximum value
        clearInterval(playbackInterval);
        isPlaying = false;
        resetPlayPauseButton();
    }
}

function togglePlayPause(slider, playPauseButton) {
    if (isPlaying) {
        clearInterval(playbackInterval);
        resetPlayPauseButton();
        isPlaying = false;  // Ensure isPlaying is set to false when paused
    } else {
        playbackInterval = setInterval(() => updateSlider(slider), 100);
        playPauseButton.style.backgroundColor = 'gray';
        playPauseButton.innerHTML = '⏸️';
        isPlaying = true;  // Set isPlaying to true when playback starts
    }
}

function resetPlayPauseButton() {
    const playPauseButton = document.querySelector('button');
    playPauseButton.style.backgroundColor = '';
    playPauseButton.innerHTML = '⏯️';
}

