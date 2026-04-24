export function createMapController() {
  if (typeof maplibregl === 'undefined') {
    throw new Error('MapLibre GL JS is not loaded');
  }

  const TILE_SOURCES = {
    street: {
      // MapLibre does NOT expand {a-c} templates; list subdomains explicitly.
      tiles: [
        'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'https://b.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'https://c.tile.openstreetmap.org/{z}/{x}/{y}.png',
      ],
      attribution: '&copy; OpenStreetMap contributors',
      maxzoom: 19,
    },
    satellite: {
      tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics',
      maxzoom: 19,
    },
    hybrid: {
      tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
      attribution: 'Tiles &copy; Esri',
      maxzoom: 19,
      labels: {
        // Explicit subdomains; omit {r} (not supported in MapLibre raster sources).
        tiles: [
          'https://stamen-tiles-a.a.ssl.fastly.net/toner-labels/{z}/{x}/{y}.png',
          'https://stamen-tiles-b.a.ssl.fastly.net/toner-labels/{z}/{x}/{y}.png',
          'https://stamen-tiles-c.a.ssl.fastly.net/toner-labels/{z}/{x}/{y}.png',
        ],
        maxzoom: 19,
      },
    },
  };

  const baseStyle = (kind) => {
    const cfg = TILE_SOURCES[kind] || TILE_SOURCES.street;
    const sources = {
      basemap: { type: 'raster', tiles: cfg.tiles, tileSize: 256, attribution: cfg.attribution, maxzoom: cfg.maxzoom },
    };
    const layers = [
      { id: 'basemap', type: 'raster', source: 'basemap' },
    ];
    if (cfg.labels) {
      sources.labels = { type: 'raster', tiles: cfg.labels.tiles, tileSize: 256, maxzoom: cfg.labels.maxzoom };
      layers.push({ id: 'labels', type: 'raster', source: 'labels', paint: { 'raster-opacity': 0.72 } });
    }
    return { version: 8, sources, layers };
  };

  const map = new maplibregl.Map({
    container: 'map',
    style: baseStyle('street'),
    center: [77.09, 28.62],
    zoom: 14,
    attributionControl: true,
  });

  map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-left');

  let clickHandler = null;
  let activeBasemap = 'street';
  let overlays = [];

  function ensureSource(id, src) {
    if (map.getSource(id)) return;
    map.addSource(id, src);
  }

  function ensureLayer(layer) {
    if (map.getLayer(layer.id)) return;
    map.addLayer(layer);
  }

  function setBasemap(name) {
    activeBasemap = name;
    map.setStyle(baseStyle(name));
    map.once('styledata', () => {
      // Re-add overlays after style reset
      overlays.forEach((o) => {
        addRasterOverlay(o.id, o.urlTemplate, o.opacity, o.beforeId, true);
      });
      if (map._aoiGeojson) drawAOI(map._aoiGeojson.lat, map._aoiGeojson.lon, map._aoiGeojson.halfSizeDeg);
      if (map._buildingGeojson) renderBuildingLayer(map._buildingGeojson, map._buildingFormatters);
      if (clickHandler) map.on('click', clickHandler);
    });

    document.querySelectorAll('.map-toggle button').forEach((button) => button.classList.remove('active'));
    const id = `btn${name.charAt(0).toUpperCase() + name.slice(1)}`;
    document.getElementById(id)?.classList.add('active');
  }

  function drawAOI(lat, lon, halfSizeDeg) {
    const rect = {
      type: 'Feature',
      properties: {},
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [lon - halfSizeDeg, lat - halfSizeDeg],
          [lon + halfSizeDeg, lat - halfSizeDeg],
          [lon + halfSizeDeg, lat + halfSizeDeg],
          [lon - halfSizeDeg, lat + halfSizeDeg],
          [lon - halfSizeDeg, lat - halfSizeDeg],
        ]],
      },
    };
    const point = {
      type: 'Feature',
      properties: {},
      geometry: { type: 'Point', coordinates: [lon, lat] },
    };

    map._aoiGeojson = { lat, lon, halfSizeDeg };

    const fc = { type: 'FeatureCollection', features: [rect] };
    ensureSource('aoi', { type: 'geojson', data: fc });
    ensureLayer({ id: 'aoi-line', type: 'line', source: 'aoi', paint: { 'line-color': '#2b8a3e', 'line-width': 2 } });

    ensureSource('aoi-point', { type: 'geojson', data: { type: 'FeatureCollection', features: [point] } });
    ensureLayer({
      id: 'aoi-point-layer',
      type: 'circle',
      source: 'aoi-point',
      paint: { 'circle-radius': 5, 'circle-color': '#2b8a3e', 'circle-stroke-width': 2, 'circle-stroke-color': '#e2e8f0' },
    });

    map.getSource('aoi')?.setData(fc);
    map.getSource('aoi-point')?.setData({ type: 'FeatureCollection', features: [point] });
  }

  function boundsFromGeojson(geojson) {
    let minX = Infinity; let minY = Infinity; let maxX = -Infinity; let maxY = -Infinity;
    const coords = geojson?.features?.[0]?.geometry?.coordinates;
    if (!coords) return null;
    const walk = (c) => {
      if (typeof c[0] === 'number' && typeof c[1] === 'number') {
        minX = Math.min(minX, c[0]); minY = Math.min(minY, c[1]);
        maxX = Math.max(maxX, c[0]); maxY = Math.max(maxY, c[1]);
        return;
      }
      c.forEach(walk);
    };
    walk(coords);
    if (!Number.isFinite(minX)) return null;
    return [[minX, minY], [maxX, maxY]];
  }

  function renderBuildingLayer(geojson, formatters) {
    if (!geojson?.features?.length) return;
    map._buildingGeojson = geojson;
    map._buildingFormatters = formatters;

    ensureSource('building', { type: 'geojson', data: geojson });
    ensureLayer({
      id: 'building-fill',
      type: 'fill',
      source: 'building',
      paint: { 'fill-color': '#1a4c80', 'fill-opacity': 0.45 },
    });
    ensureLayer({
      id: 'building-line',
      type: 'line',
      source: 'building',
      paint: { 'line-color': '#7dd3fc', 'line-width': 2.4, 'line-dasharray': [7, 5] },
    });

    map.getSource('building')?.setData(geojson);

    const b = boundsFromGeojson(geojson);
    if (b) map.fitBounds(b, { padding: 40, duration: 650 });

    // Popup on click
    map.off('click', 'building-fill', map._buildingClick);
    map._buildingClick = (e) => {
      const feature = e.features?.[0];
      const p = feature?.properties || {};
      const eff = Number(document.getElementById('efficiency')?.value || 0.18);
      const kwp = p.roof_area_m2 ? `${(Number(p.roof_area_m2) * eff).toFixed(1)} kWp` : 'n/a';

      const html = `
        <div class="building-popup">
          <b>Rooftop footprint</b>
          <div class="pop-row"><span>PV (period)</span><span class="pop-val">${formatters.energyFormatter(Number(p.period_yield_kwh), '')}</span></div>
          <div class="pop-row"><span>Capacity</span><span class="pop-val">${kwp}</span></div>
          <div class="pop-row"><span>CO\u2082 offset</span><span class="pop-val">${formatters.co2Formatter(Number(p.period_yield_kwh))}</span></div>
          <div class="pop-row"><span>Roof area</span><span class="pop-val">${formatters.areaFormatter(Number(p.roof_area_m2))}</span></div>
          <div class="pop-row"><span>Net GHI</span><span class="pop-val">${formatters.irrFormatter(Number(p.net_irradiance_kwh_m2_period), false)}</span></div>
          <div class="pop-row"><span>Shadow</span><span class="pop-val">${p.mean_shadow_fraction != null ? `${(Number(p.mean_shadow_fraction) * 100).toFixed(1)}%` : 'n/a'}</span></div>
          <div class="pop-row"><span>Confidence</span><span class="pop-val">${p.confidence != null ? `${(Number(p.confidence) * 100).toFixed(0)}%` : 'n/a'}</span></div>
        </div>
      `;

      new maplibregl.Popup({ closeButton: true, closeOnClick: true })
        .setLngLat(e.lngLat)
        .setHTML(html)
        .addTo(map);
    };
    map.on('click', 'building-fill', map._buildingClick);

    map.on('mouseenter', 'building-fill', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'building-fill', () => { map.getCanvas().style.cursor = ''; });
  }

  function renderBuildingLayerCompat(geojson, energyFormatter, areaFormatter, irrFormatter, co2Formatter) {
    renderBuildingLayer(geojson, { energyFormatter, areaFormatter, irrFormatter, co2Formatter });
  }

  function onMapClick(handler) {
    clickHandler = (e) => handler({ latlng: { lat: e.lngLat.lat, lng: e.lngLat.lng } });
    map.on('click', clickHandler);
  }

  function invalidate() {
    map.resize();
  }

  function addRasterOverlay(id, urlTemplate, opacity = 0.7, beforeId = null, silent = false) {
    const sourceId = `ov-src-${id}`;
    const layerId = `ov-${id}`;

    // Update tracking list (LRU not needed; tiny list).
    overlays = overlays.filter((o) => o.id !== id);
    overlays.push({ id, urlTemplate, opacity, beforeId });

    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, { type: 'raster', tiles: [urlTemplate], tileSize: 256, maxzoom: 19 });
    }
    if (!map.getLayer(layerId)) {
      const layer = { id: layerId, type: 'raster', source: sourceId, paint: { 'raster-opacity': opacity } };
      if (beforeId && map.getLayer(beforeId)) map.addLayer(layer, beforeId);
      else map.addLayer(layer);
    } else {
      map.setPaintProperty(layerId, 'raster-opacity', opacity);
    }

    if (!silent) {
      // no-op: reserved for future toasts
    }
  }

  function removeRasterOverlay(id) {
    const sourceId = `ov-src-${id}`;
    const layerId = `ov-${id}`;
    overlays = overlays.filter((o) => o.id !== id);
    if (map.getLayer(layerId)) map.removeLayer(layerId);
    if (map.getSource(sourceId)) map.removeSource(sourceId);
  }

  function setOverlayOpacity(opacity) {
    overlays = overlays.map((o) => ({ ...o, opacity }));
    overlays.forEach((o) => {
      const layerId = `ov-${o.id}`;
      if (map.getLayer(layerId)) map.setPaintProperty(layerId, 'raster-opacity', opacity);
    });
  }

  return {
    map,
    setBasemap,
    drawAOI,
    renderBuildingLayer: renderBuildingLayerCompat,
    onMapClick,
    invalidate,
    addRasterOverlay,
    removeRasterOverlay,
    setOverlayOpacity,
  };
}