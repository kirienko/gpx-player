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
