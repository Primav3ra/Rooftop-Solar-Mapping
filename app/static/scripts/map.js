export function createMapController() {
  const basemaps = {
    street: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }),
    satellite: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19,
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics',
    }),
    hybrid: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19,
      attribution: 'Tiles &copy; Esri',
    }),
  };

  const labelsLayer = L.tileLayer('https://stamen-tiles-{s}.a.ssl.fastly.net/toner-labels/{z}/{x}/{y}{r}.png', {
    maxZoom: 19,
    opacity: 0.7,
  });

  const map = L.map('map', { zoomControl: true }).setView([28.62, 77.09], 14);
  basemaps.street.addTo(map);

  let marker = null;
  let aoiRect = null;
  let buildingLayer = null;

  function setBasemap(name) {
    Object.values(basemaps).forEach((layer) => {
      if (map.hasLayer(layer)) map.removeLayer(layer);
    });
    if (map.hasLayer(labelsLayer)) map.removeLayer(labelsLayer);
    basemaps[name].addTo(map);
    if (name === 'hybrid') labelsLayer.addTo(map);

    document.querySelectorAll('.map-toggle button').forEach((button) => button.classList.remove('active'));
    const id = `btn${name.charAt(0).toUpperCase() + name.slice(1)}`;
    document.getElementById(id)?.classList.add('active');
  }

  function drawAOI(lat, lon, halfSizeDeg) {
    if (marker) marker.remove();
    if (aoiRect) aoiRect.remove();
    marker = L.marker([lat, lon]).addTo(map);
    aoiRect = L.rectangle(
      [[lat - halfSizeDeg, lon - halfSizeDeg], [lat + halfSizeDeg, lon + halfSizeDeg]],
      { color: '#2b8a3e', weight: 2, fill: false }
    ).addTo(map);
  }

  function renderBuildingLayer(geojson, energyFormatter, areaFormatter, irrFormatter, co2Formatter) {
    if (buildingLayer) buildingLayer.remove();
    if (!geojson?.features?.length) return;

    buildingLayer = L.geoJSON(geojson, {
      style: () => ({
        fillColor: '#1a4c80',
        fillOpacity: 0.45,
        color: '#7dd3fc',
        weight: 2.4,
        dashArray: '7 5',
        lineCap: 'round',
        lineJoin: 'round',
      }),
      onEachFeature: (feature, layer) => {
        const p = feature.properties || {};
        const eff = Number(document.getElementById('efficiency')?.value || 0.18);
        const kwp = p.roof_area_m2 ? `${(p.roof_area_m2 * eff).toFixed(1)} kWp` : 'n/a';

        layer.bindPopup(`
          <div class="building-popup">
            <b>Rooftop footprint</b>
            <div class="pop-row"><span>PV (period)</span><span class="pop-val">${energyFormatter(p.period_yield_kwh, '')}</span></div>
            <div class="pop-row"><span>Capacity</span><span class="pop-val">${kwp}</span></div>
            <div class="pop-row"><span>CO\u2082 offset</span><span class="pop-val">${co2Formatter(p.period_yield_kwh)}</span></div>
            <div class="pop-row"><span>Roof area</span><span class="pop-val">${areaFormatter(p.roof_area_m2)}</span></div>
            <div class="pop-row"><span>Net GHI</span><span class="pop-val">${irrFormatter(p.net_irradiance_kwh_m2_period, false)}</span></div>
            <div class="pop-row"><span>Shadow</span><span class="pop-val">${p.mean_shadow_fraction != null ? `${(p.mean_shadow_fraction * 100).toFixed(1)}%` : 'n/a'}</span></div>
            <div class="pop-row"><span>Confidence</span><span class="pop-val">${p.confidence != null ? `${(p.confidence * 100).toFixed(0)}%` : 'n/a'}</span></div>
          </div>
        `).openPopup();
      },
    }).addTo(map);

    map.fitBounds(buildingLayer.getBounds(), { padding: [40, 40] });
  }

  function onMapClick(handler) {
    map.on('click', handler);
  }

  function invalidate() {
    map.invalidateSize();
  }

  return {
    map,
    setBasemap,
    drawAOI,
    renderBuildingLayer,
    onMapClick,
    invalidate,
  };
}