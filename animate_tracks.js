document.addEventListener('DOMContentLoaded', () => {
    const slider = createSlider();
    const timeLegend = createTimeLegend();
    document.body.appendChild(slider);
    document.body.appendChild(timeLegend);

    slider.addEventListener('input', () => {
        const timeIndex = Math.floor(slider.value / 1000 * (gpx_timestamps.length - 1));
        const currentTime = new Date(gpx_timestamps[timeIndex]).getTime();
        timeLegend.innerHTML = `Current Time: ${new Date(currentTime).toUTCString()}`;
    });

    // Initialize with the first timestamp
    slider.dispatchEvent(new Event('input'));

    const map = initializeMap();
    animateTracks(map, 1000, gpx_points_data);
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
        top: '10px',
        right: '10px',
        backgroundColor: 'white',
        padding: '10px',
        border: '1px solid grey',
        zIndex: 1000,
    });
    return timeLegend;
}

function initializeMap() {
    const map = L.map('map').setView([0, 0], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    return map;
}

function animateTracks(map, interval, allPoints) {
    let marker = null;
    let index = 0;
    const timeText = createTimeText();
    document.body.appendChild(timeText);

    function updateMarker() {
        if (index < allPoints.length) {
            const point = allPoints[index];
            if (!marker) {
                marker = L.marker([point.lat, point.lon]).addTo(map);
            } else {
                marker.setLatLng([point.lat, point.lon]);
            }
            timeText.innerHTML = `Time: ${point.time}<br>Speed: ${point.speed.toFixed(2)} knots`;
            index++;
        } else {
            clearInterval(animation);
        }
    }

    const animation = setInterval(updateMarker, interval);
}

function createTimeText() {
    const timeText = document.createElement('div');
    Object.assign(timeText.style, {
        background: 'white',
        padding: '5px',
        position: 'absolute',
        bottom: '50px',
        left: '50px',
    });
    return timeText;
}
