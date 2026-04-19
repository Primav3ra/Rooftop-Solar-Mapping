import { fetchBaseline, fetchPresets, fetchYield } from './api.js';
import { runIntroSequence } from './intro.js';
import { createMapController } from './map.js';
import { BUILDING_CAP, BuildingLru, buildingKeyFromGeojson, fmtArea, fmtCo2, fmtEnergy, fmtIrr } from './state.js';

const state = {
  energyUnit: 'kWh',
  lastCardData: null,
  lastCardType: null,
  activeBuildingKey: null,
  buildingLru: new BuildingLru(BUILDING_CAP),
};

const dom = {
  lat: document.getElementById('lat'),
  lon: document.getElementById('lon'),
  halfSize: document.getElementById('halfSize'),
  presence: document.getElementById('presence'),
  minHeight: document.getElementById('minHeight'),
  status: document.getElementById('status'),
  out: document.getElementById('out'),
  summaryBox: document.getElementById('summaryBox'),
  summaryTitle: document.getElementById('summaryTitle'),
  summaryStats: document.getElementById('summaryStats'),
  unitKwh: document.getElementById('unitKwh'),
  unitMwh: document.getElementById('unitMwh'),
  runBaselineBtn: document.getElementById('runBaselineBtn'),
  runYieldBtn: document.getElementById('runYieldBtn'),
  mode: document.getElementById('mode'),
  rowYearly: document.getElementById('rowYearly'),
  rowQuarterly: document.getElementById('rowQuarterly'),
  rowDaily: document.getElementById('rowDaily'),
  baselineYear: document.getElementById('baselineYear'),
  quarterYear: document.getElementById('quarterYear'),
  quarterSelect: document.getElementById('quarterSelect'),
  startDate: document.getElementById('startDate'),
  endDate: document.getElementById('endDate'),
  efficiency: document.getElementById('efficiency'),
  pr: document.getElementById('pr'),
  confidence: document.getElementById('confidence'),
  toast: document.getElementById('toast'),
  historySection: document.getElementById('buildingHistorySection'),
  historyCount: document.getElementById('buildingCount'),
  historyChips: document.getElementById('buildingChips'),
  btnStreet: document.getElementById('btnStreet'),
  btnSatellite: document.getElementById('btnSatellite'),
  btnHybrid: document.getElementById('btnHybrid'),
};

const mapCtrl = createMapController();

function showToast(message, timeout = 4300) {
  dom.toast.textContent = message;
  dom.toast.classList.add('show');
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => dom.toast.classList.remove('show'), timeout);
}

function formatEnergy(value, suffix = '/yr') {
  return fmtEnergy(value, state.energyUnit, suffix);
}

function basePayload() {
  return {
    lat: Number(dom.lat.value),
    lon: Number(dom.lon.value),
    half_size_deg: Number(dom.halfSize.value),
    roof_year: 2022,
    presence_threshold: Number(dom.presence.value),
    min_height_m: Number(dom.minHeight.value),
  };
}

function baselineTemporalPayload() {
  const mode = dom.mode.value;
  const payload = { baseline_mode: mode };

  if (mode === 'yearly') {
    payload.year = Number.parseInt(dom.baselineYear.value, 10) || null;
  } else if (mode === 'quarterly') {
    payload.year = Number.parseInt(dom.quarterYear.value, 10) || null;
    payload.quarter = Number.parseInt(dom.quarterSelect.value, 10);
  } else {
    payload.start_date = dom.startDate.value || null;
    payload.end_date_exclusive = dom.endDate.value || null;
  }

  return payload;
}

function showSummary(data) {
  dom.summaryBox.hidden = false;
  dom.summaryTitle.textContent = 'AOI Summary';

  const rb = data.roof_baseline || {};
  const rt = data.rooftop || {};
  const efficiency = Number(dom.efficiency.value) || 0.18;
  const performanceRatio = Number(dom.pr.value) || 0.8;
  const estimatedYield = rb.pre_penalty_total_kwh_year
    ? rb.pre_penalty_total_kwh_year * efficiency * performanceRatio
    : null;

  const mode = rb.baseline_time_mode || data.baseline_time_mode || '';
  const rows = [
    ['Rooftop area', fmtArea(rt.rooftop_candidate_area_m2)],
    ['AOI area', fmtArea((rt.aoi_area_km2 || 0) * 1e6)],
    [
      'Regional GHI (annualized)',
      fmtIrr(rb.regional_irradiance_kwh_m2_year),
      mode === 'yearly' ? 'ERA5, one calendar year' : 'Scaled to annualized equivalent from selected window',
    ],
  ];

  if (rb.period_ghi_kwh_m2 != null) {
    rows.push(['GHI (window total)', fmtIrr(rb.period_ghi_kwh_m2, false), 'kWh/m\u00b2 over selected dates']);
    rows.push(['Pre-penalty (window)', formatEnergy(rb.pre_penalty_total_kwh_period, ''), 'All rooftops for selected window']);
  }

  rows.push(
    ['Pre-penalty (annualized)', formatEnergy(rb.pre_penalty_total_kwh_year)],
    ['Estimated yield (all rooftops)', formatEnergy(estimatedYield), `At ${(efficiency * 100).toFixed(0)}% efficiency x ${(performanceRatio * 100).toFixed(0)}% PR`],
    ['Estimated CO\u2082 offset', fmtCo2(estimatedYield), 'India grid factor 0.82 kg/kWh'],
    ['Irradiance source', rb.irradiance_source || '-'],
  );

  dom.summaryStats.innerHTML = rows
    .map(([label, value, note]) => `
      <div class="stat">
        <span class="stat-label">${label}${note ? `<span class="stat-note">${note}</span>` : ''}</span>
        <span class="stat-value">${value}</span>
      </div>
    `)
    .join('');
}

function showBuildingCard(data) {
  dom.summaryBox.hidden = false;
  dom.summaryTitle.textContent = 'Selected Building';

  const eff = data.panel_efficiency || 0.18;
  const performanceRatio = data.performance_ratio || 0.8;
  const kwp = data.roof_area_m2 ? `${(data.roof_area_m2 * eff).toFixed(1)} kWp` : '-';
  const py = data.period_yield_kwh;

  const rows = [
    ['PV output (period)', formatEnergy(py, ''), 'Same window as baseline', true],
    ['Estimated capacity', kwp, `At ${(eff * 100).toFixed(0)}% panel efficiency`],
    ['CO\u2082 offset (period)', fmtCo2(py), 'India grid 0.82 kg CO\u2082/kWh'],
    ['Roof area', fmtArea(data.roof_area_m2)],
    ['Net GHI on roof (period)', fmtIrr(data.net_irradiance_kwh_m2_period, false), 'After shadow over selected window'],
    ['Shadow fraction', data.mean_shadow_fraction != null ? `${(data.mean_shadow_fraction * 100).toFixed(1)}%` : '-'],
    ['Regional GHI (period)', fmtIrr(data.regional_ghi_kwh_m2_period, false), 'ERA5 at AOI centroid'],
    ['Time window', data.start_date && data.end_date_exclusive ? `${data.start_date} to ${data.end_date_exclusive}` : '-', data.baseline_time_mode || ''],
    ['Panel efficiency', `${(eff * 100).toFixed(0)}%`],
    ['Performance ratio', `${(performanceRatio * 100).toFixed(0)}%`],
    ['Building confidence', data.building_confidence != null ? `${(data.building_confidence * 100).toFixed(0)}%` : '-'],
  ];

  dom.summaryStats.innerHTML = rows
    .map(([label, value, note, highlight]) => `
      <div class="stat">
        <span class="stat-label">${label}${note ? `<span class="stat-note">${note}</span>` : ''}</span>
        <span class="stat-value${highlight ? ' highlight' : ''}">${value}</span>
      </div>
    `)
    .join('');
}

function renderHistory() {
  const items = state.buildingLru.list();
  if (!items.length) {
    dom.historySection.hidden = true;
    return;
  }

  dom.historySection.hidden = false;
  dom.historyCount.textContent = `(${items.length}/${BUILDING_CAP})`;
  dom.historyChips.innerHTML = items
    .map(({ key, entry }) => {
      const active = key === state.activeBuildingKey ? ' active' : '';
      const safeLabel = String(entry.label || key)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/"/g, '&quot;');
      return `<button type="button" class="chip${active}" data-key="${encodeURIComponent(key)}" title="${safeLabel}">${safeLabel}</button>`;
    })
    .join('');

  dom.historyChips.querySelectorAll('.chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const encoded = chip.getAttribute('data-key');
      const key = encoded ? decodeURIComponent(encoded) : '';
      if (!key) return;
      const payload = state.buildingLru.get(key);
      if (!payload) return;

      state.activeBuildingKey = key;
      state.lastCardData = payload.data;
      state.lastCardType = 'building';

      showBuildingCard(payload.data);
      if (payload.geojson) {
        mapCtrl.renderBuildingLayer(payload.geojson, formatEnergy, fmtArea, fmtIrr, fmtCo2);
      }

      renderHistory();
      dom.status.textContent = 'Showing saved rooftop result.';
    });
  });
}

function refreshCard() {
  if (!state.lastCardData) return;
  if (state.lastCardType === 'building') showBuildingCard(state.lastCardData);
  else showSummary(state.lastCardData);
}

async function handleBaselineRun() {
  dom.status.textContent = 'Running baseline...';
  const payload = { ...basePayload(), ...baselineTemporalPayload() };

  try {
    const data = await fetchBaseline(payload);
    dom.out.textContent = JSON.stringify(data, null, 2);
    dom.status.textContent = 'Baseline completed.';

    state.lastCardData = data;
    state.lastCardType = 'summary';
    showSummary(data);
  } catch (error) {
    dom.status.textContent = `Error: ${error.message}`;
  }
}

async function handleYieldRun() {
  dom.status.textContent = 'Finding building at selected point...';

  const clickLat = Number(dom.lat.value);
  const clickLon = Number(dom.lon.value);

  const payload = {
    ...basePayload(),
    ...baselineTemporalPayload(),
    panel_efficiency: Number(dom.efficiency.value),
    performance_ratio: Number(dom.pr.value),
    building_confidence: Number(dom.confidence.value),
  };

  try {
    const data = await fetchYield(payload);

    if (data.status === 'no_building_at_point') {
      dom.status.textContent = data.message;
      dom.out.textContent = JSON.stringify(data, null, 2);
      return;
    }

    dom.out.textContent = JSON.stringify({
      status: data.status,
      period_yield_kwh: data.period_yield_kwh,
      roof_area_m2: data.roof_area_m2,
      net_irradiance_kwh_m2_period: data.net_irradiance_kwh_m2_period,
      mean_shadow_fraction: data.mean_shadow_fraction,
      regional_ghi_kwh_m2_period: data.regional_ghi_kwh_m2_period,
      start_date: data.start_date,
      end_date_exclusive: data.end_date_exclusive,
      baseline_time_mode: data.baseline_time_mode,
      building_confidence: data.building_confidence,
    }, null, 2);

    data._clickLat = clickLat;
    data._clickLon = clickLon;

    const key = buildingKeyFromGeojson(data.geojson);
    const entry = {
      data: JSON.parse(JSON.stringify(data)),
      geojson: data.geojson ? JSON.parse(JSON.stringify(data.geojson)) : null,
      label: `${clickLat.toFixed(4)}, ${clickLon.toFixed(4)}`,
    };

    const { isDuplicate, evictedKey } = state.buildingLru.add(key, entry);
    state.activeBuildingKey = key;

    if (isDuplicate) {
      showToast(`Same rooftop selected - saved entry refreshed (still one of ${BUILDING_CAP}).`);
    } else if (evictedKey) {
      showToast(`Maximum ${BUILDING_CAP} saved rooftops reached. Oldest entry removed.`, 5200);
    }

    dom.status.textContent = `Done. Yield: ${formatEnergy(data.period_yield_kwh, '')} | Shadow: ${data.mean_shadow_fraction != null ? `${(data.mean_shadow_fraction * 100).toFixed(1)}%` : 'n/a'}`;

    state.lastCardData = data;
    state.lastCardType = 'building';

    showBuildingCard(data);
    if (data.geojson) {
      mapCtrl.renderBuildingLayer(data.geojson, formatEnergy, fmtArea, fmtIrr, fmtCo2);
    }
    renderHistory();
  } catch (error) {
    dom.status.textContent = `Error: ${error.message}`;
  }
}

function handleModeChange() {
  const mode = dom.mode.value;
  dom.rowYearly.hidden = mode !== 'yearly';
  dom.rowQuarterly.hidden = mode !== 'quarterly';
  dom.rowDaily.hidden = mode !== 'daily';
}

async function loadPresetsAndApply() {
  try {
    const presets = await fetchPresets();
    const bounds = presets?.baseline?.year_bounds;
    if (!bounds) return;

    dom.baselineYear.value = bounds.default;
    dom.quarterYear.value = bounds.default;

    dom.baselineYear.min = bounds.min;
    dom.baselineYear.max = bounds.max;
    dom.quarterYear.min = bounds.min;
    dom.quarterYear.max = bounds.max;
  } catch {
    // Keep static defaults when presets are unavailable.
  }
}

function bindEvents() {
  dom.unitKwh.addEventListener('click', () => {
    state.energyUnit = 'kWh';
    dom.unitKwh.classList.add('active');
    dom.unitMwh.classList.remove('active');
    refreshCard();
  });

  dom.unitMwh.addEventListener('click', () => {
    state.energyUnit = 'MWh';
    dom.unitMwh.classList.add('active');
    dom.unitKwh.classList.remove('active');
    refreshCard();
  });

  dom.mode.addEventListener('change', handleModeChange);
  dom.runBaselineBtn.addEventListener('click', handleBaselineRun);
  dom.runYieldBtn.addEventListener('click', handleYieldRun);

  mapCtrl.onMapClick((event) => {
    const lat = event.latlng.lat;
    const lon = event.latlng.lng;
    dom.lat.value = lat.toFixed(6);
    dom.lon.value = lon.toFixed(6);
    mapCtrl.drawAOI(lat, lon, Number(dom.halfSize.value || 0.01));
  });

  dom.halfSize.addEventListener('change', () => {
    if (!dom.lat.value || !dom.lon.value) return;
    mapCtrl.drawAOI(Number(dom.lat.value), Number(dom.lon.value), Number(dom.halfSize.value || 0.01));
  });

  dom.btnStreet.addEventListener('click', () => mapCtrl.setBasemap('street'));
  dom.btnSatellite.addEventListener('click', () => mapCtrl.setBasemap('satellite'));
  dom.btnHybrid.addEventListener('click', () => mapCtrl.setBasemap('hybrid'));
}

function start() {
  bindEvents();
  handleModeChange();
  loadPresetsAndApply();

  runIntroSequence(() => {
    setTimeout(() => mapCtrl.invalidate(), 220);
    setTimeout(() => mapCtrl.invalidate(), 740);
  });
}

start();