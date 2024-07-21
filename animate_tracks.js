var map;

document.addEventListener('DOMContentLoaded', function() {
    // Create the slider
    var slider = document.createElement('input');
    slider.type = 'range';
    slider.min = 0;
    slider.max = 1000;
    slider.value = 0;
    slider.style.position = 'fixed';
    slider.style.bottom = '20px';
    slider.style.left = '50%';
    slider.style.transform = 'translateX(-50%)';
    slider.style.width = '80%';
    slider.style.zIndex = 1000;

    // Create the time legend
    var timeLegend = document.createElement('div');
    timeLegend.style.position = 'fixed';
    timeLegend.style.top = '10px';
    timeLegend.style.right = '10px';
    timeLegend.style.backgroundColor = 'white';
    timeLegend.style.padding = '10px';
    timeLegend.style.border = '1px solid grey';
    timeLegend.style.zIndex = 1000;

    document.body.appendChild(slider);
    document.body.appendChild(timeLegend);

    slider.addEventListener('input', function () {
        var timeIndex = Math.floor(this.value / 1000 * (gpx_timestamps.length - 1));
        var currentTime = new Date(gpx_timestamps[timeIndex]).getTime();
        timeLegend.innerHTML = `Current Time: ${new Date(currentTime).toUTCString()}`;
    });

    // Initialize with the first timestamp
    slider.dispatchEvent(new Event('input'));
});

function animateTracks(map, interval, all_points) {
    var marker = null;
    var index = 0;
    var timeText = document.createElement('div');
    timeText.style.background = 'white';
    timeText.style.padding = '5px';
    timeText.style.position = 'absolute';
    timeText.style.bottom = '50px';
    timeText.style.left = '50px';
    document.body.appendChild(timeText);

    function updateMarker() {
        if (index < all_points.length) {
            var point = all_points[index];
            if (!marker) {
                marker = L.marker([point.lat, point.lon]).addTo(map);
            } else {
                marker.setLatLng([point.lat, point.lon]);
            }
            timeText.innerHTML = 'Time: ' + point.time + '<br>Speed: ' + point.speed.toFixed(2) + ' knots';
            index++;
        } else {
            clearInterval(animation);
        }
    }
    var animation = setInterval(updateMarker, interval);
}

var gpx_points = gpx_points_data;
animateTracks(map, 1000, gpx_points);

