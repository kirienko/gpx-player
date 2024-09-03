document.addEventListener('DOMContentLoaded', () => {
    const slider = createSlider();
    const timeLegend = createTimeLegend();
    document.body.appendChild(slider);
    document.body.appendChild(timeLegend);

    // Access the Folium-initialized map using the dynamically generated map_id
    const map = window[map_id]; // Now `map` refers to the Folium map object

    const colors = ['red', 'green', 'blue', 'orange', 'purple', 'brown', 'pink', 'yellow', 'cyan', 'magenta'];
    
    const trackMarkers = gpx_points_data.map((track, index) => {
        const color = colors[index % colors.length];
        const marker = L.circleMarker([track[0].lat, track[0].lon], {
            radius: 4,
            color: color,
            fillColor: color,
            fillOpacity: 0.5
        }).addTo(map);
        return marker;
    });

    let isPlaying = false;
    let playbackInterval;

    function updateSlider() {
        if (slider.value < slider.max) {
            slider.value = parseInt(slider.value) + 1;
            slider.dispatchEvent(new Event('input'));
        } else {
            clearInterval(playbackInterval);
            isPlaying = false;
            playPauseButton.style.backgroundColor = '';
            playPauseButton.innerHTML = '⏯️';
        }
    }

    slider.addEventListener('input', () => {
        const timeIndex = Math.floor(slider.value / 1000 * (gpx_timestamps.length - 1));
        const currentTime = new Date(gpx_timestamps[timeIndex]).getTime();
        timeLegend.timeDisplay.innerHTML = `${new Date(currentTime).toUTCString()}`;

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

function createTimeLegend() {
    const timeLegend = document.createElement('div');
    Object.assign(timeLegend.style, {
        position: 'fixed',
        bottom: '50px',
        right: '10px',
        backgroundColor: ' rgba(0, 0, 0, 0.5)',
        padding: '5px',
        border: '1px solid white',
        borderRadius: '5px',
        zIndex: 1000,
        color: 'white',
    });
    timeLegend.style.display = 'flex';
    timeLegend.style.flexDirection = 'column';
    timeLegend.style.alignItems = 'center';

    const timeDisplay = document.createElement('div');
    timeDisplay.style.marginBottom = '2px';  // Add some space between the text and the button
    timeLegend.appendChild(timeDisplay);

    const playPauseButton = document.createElement('button');
    playPauseButton.innerHTML = '⏯️'; // Play/Pause icon
    playPauseButton.style.marginTop = '5px';
    playPauseButton.addEventListener('click', () => {
        if (isPlaying) {
            clearInterval(playbackInterval);
            playPauseButton.style.backgroundColor = '';
            playPauseButton.innerHTML = '⏯️';
        } else {
            playbackInterval = setInterval(updateSlider, 100);
            playPauseButton.style.backgroundColor = 'gray';
            playPauseButton.innerHTML = '⏸️';
        }
        isPlaying = !isPlaying;
    });
    timeLegend.appendChild(playPauseButton);

    // Attach the timeDisplay to the legend object, so it can be accessed later
    timeLegend.timeDisplay = timeDisplay;

    return timeLegend;
}
