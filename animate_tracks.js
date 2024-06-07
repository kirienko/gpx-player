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
            timeText.innerHTML = 'Time: ' + point.time;
            index++;
        } else {
            clearInterval(animation);
        }
    }
    var animation = setInterval(updateMarker, interval);
}

var gpx_points = gpx_points_data; // This variable will be set in the HTML by the Python script
animateTracks(map, 1000, gpx_points);
