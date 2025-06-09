let windLayer;
let windEnabled = false;

function initWindToggle(map) {
    const control = L.control({ position: 'topright' });
    control.onAdd = function () {
        const btn = L.DomUtil.create('button', 'wind-toggle');
        btn.innerHTML = '⚡';
        btn.title = 'Toggle wind';
        btn.onclick = () => {
            windEnabled = !windEnabled;
            btn.style.background = windEnabled ? 'gray' : '';
            if (!windEnabled && windLayer) {
                map.removeLayer(windLayer);
                windLayer = undefined;
            }
        };
        return btn;
    };
    control.addTo(map);
}

async function updateWindLayer(timestamp, map) {
    if (!windEnabled) return;
    try {
        const resp = await fetch(`/wind?time=${encodeURIComponent(timestamp)}`);
        if (!resp.ok) return;
        const data = await resp.json();
        if (windLayer) map.removeLayer(windLayer);
        windLayer = L.velocityLayer({ data, maxVelocity: 25, velocityScale: 0.005 }).addTo(map);
    } catch (e) {
        console.error('wind error', e);
    }
}
