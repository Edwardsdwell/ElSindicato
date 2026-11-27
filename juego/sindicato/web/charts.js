const $ = id => document.getElementById(id);
const clusterColors = ['#b17a2a', '#39796b', '#607886', '#b75e47', '#d9b36a'];

export function drawHistoryChart(target, points, key, options = {}) {
  const box = $(target);
  if (!points?.length) { box.innerHTML = '<div class="chart-empty">El historial aparece al cerrar la jornada.</div>'; return; }
  const W = 380, H = 150, L = 40, R = 12, T = 12, B = 28, PW = W - L - R, PH = H - T - B;
  const values = points.map(point => Number(point[key]) || 0);
  let max = options.max || Math.max(1, ...values);
  if (!options.max) max = Math.ceil(max / (options.step || 50)) * (options.step || 50);
  const coords = values.map((value, i) => [L + (points.length === 1 ? PW / 2 : i * PW / (points.length - 1)), T + PH - Math.max(0, value) / max * PH]);
  const path = coords.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  const grid = [0, .5, 1].map(fraction => {
    const y = T + PH * (1 - fraction), value = max * fraction;
    return `<line x1="${L}" y1="${y}" x2="${W - R}" y2="${y}"/><text x="${L - 7}" y="${y + 3}" text-anchor="end">${options.format ? options.format(value) : Math.round(value)}</text>`;
  }).join('');
  const dots = coords.length <= 24 ? coords.map(([x, y]) => `<circle cx="${x}" cy="${y}" r="2.7"/>`).join('') : '';
  const first = points[0].day, last = points.at(-1).day;
  let marker = '';
  if (options.markerDay != null && options.markerDay >= first && options.markerDay <= last) {
    const x = L + (last === first ? 0 : (options.markerDay - first) / (last - first) * PW);
    marker = `<line class="transit-marker" x1="${x}" y1="${T}" x2="${x}" y2="${T + PH}"/><text class="marker-label" x="${x + 4}" y="${T + 10}">Tránsito</text>`;
  }
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${options.label || key}; jornadas ${first} a ${last}"><g class="chart-grid">${grid}</g>${marker}<path class="chart-line" d="${path}"/>${dots}<text class="chart-xlabel" x="${L}" y="${H - 5}">Día ${first}</text><text class="chart-xlabel" x="${W - R}" y="${H - 5}" text-anchor="end">Día ${last}</text></svg>`;
}

export function renderDriverHistory(targets, points) {
  const range = $('historyRange');
  range.textContent = points.length ? `${points.length} jornadas · día ${points[0].day} a ${points.at(-1).day}` : 'Sin jornadas cerradas';
  drawHistoryChart(targets.income, points, 'daily_income', { step: 50, label: 'Ingreso diario en bolivianos' });
  drawHistoryChart(targets.integrity, points, 'integrity', { max: 100, label: 'Integridad mecánica en porcentaje' });
  drawHistoryChart(targets.stress, points, 'stress', { max: 100, label: 'Estrés del conductor en escala de cero a cien' });
}

function drawScatter(target, points, xKey, yKey, options = {}) {
  const box = $(target);
  if (!points?.length) { box.innerHTML = '<div class="chart-empty">Sin observaciones suficientes.</div>'; return; }
  const W = 520, H = 225, L = 48, R = 28, T = 14, B = 34, PW = W - L - R, PH = H - T - B;
  const xMax = options.xMax ?? Math.max(1, ...points.map(point => Number(point[xKey]) || 0)) * 1.1;
  const yMax = options.yMax ?? Math.max(.1, ...points.map(point => Number(point[yKey]) || 0)) * 1.15;
  const grid = [0, .5, 1].map(fraction => {
    const x = L + fraction * PW, y = T + fraction * PH;
    return `<line x1="${x}" y1="${T}" x2="${x}" y2="${T + PH}"/><line x1="${L}" y1="${y}" x2="${L + PW}" y2="${y}"/><text x="${x}" y="${H - 9}" text-anchor="middle">${(xMax * fraction).toFixed(options.xDigits ?? 0)}</text><text x="${L - 8}" y="${T + PH - fraction * PH + 3}" text-anchor="end">${(yMax * fraction).toFixed(options.yDigits ?? 1)}</text>`;
  }).join('');
  const dots = points.map(point => {
    const x = L + Math.min(xMax, Number(point[xKey]) || 0) / xMax * PW;
    const y = T + PH - Math.min(yMax, Number(point[yKey]) || 0) / yMax * PH;
    const color = clusterColors[((point.cluster || point.id) - 1) % clusterColors.length];
    const radius = options.stressRadius ? 4 + Math.min(5, (point.stress || 0) / 22) : 6;
    return `<g><circle class="scatter-point" cx="${x}" cy="${y}" r="${radius}" fill="${color}"/><text class="point-label" x="${x + 8}" y="${y - 7}">M${point.id}</text><title>Unidad ${point.id} · ${point.name}; ${options.xLabel}: ${point[xKey]}; ${options.yLabel}: ${point[yKey]}${point.stress != null ? `; estrés ${point.stress}` : ''}</title></g>`;
  }).join('');
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${options.title}"><g class="scatter-grid">${grid}</g>${dots}<text class="axis-label" x="${L + PW / 2}" y="${H}" text-anchor="middle">${options.xLabel}</text><text class="axis-label" transform="translate(12 ${T + PH / 2}) rotate(-90)" text-anchor="middle">${options.yLabel}</text></svg>`;
}

function renderLuckRows(drivers) {
  const maxEvents = Math.max(1, ...drivers.map(driver => driver.events_per_100_ticks));
  $('luckChart').innerHTML = drivers.map(driver => `<div class="comparison-line">
    <span class="comparison-name"><i style="background:${clusterColors[driver.id - 1]}"></i>M${driver.id}</span>
    <span class="comparison-bar"><i style="width:${100 * driver.events_per_100_ticks / maxEvents}%"></i></span><b>${driver.events_per_100_ticks.toFixed(1)}</b>
    <span class="comparison-bar luck"><i style="width:${100 * driver.luck}%"></i></span><b>${Math.round(driver.luck * 100)}%</b>
  </div>`).join('');
}

function renderEgoRows(drivers) {
  const maxGain = Math.max(1, ...drivers.map(driver => driver.ego_gain));
  const maxRep = Math.max(.01, ...drivers.map(driver => Math.abs(driver.ego_rep_delta)));
  const maxIntegrity = Math.max(1, ...drivers.map(driver => driver.ego_integrity_cost));
  $('egoChart').innerHTML = drivers.map(driver => `<div class="ego-line">
    <span class="comparison-name"><i style="background:${clusterColors[driver.id - 1]}"></i>M${driver.id}</span>
    <div class="ego-metrics">
      <span class="ego-cell"><small>Ganancia base</small><b>+${driver.ego_gain.toFixed(0)}</b><i><em class="gain" style="width:${100 * driver.ego_gain / maxGain}%"></em></i></span>
      <span class="ego-cell"><small>Δ reputación</small><b>${driver.ego_rep_delta.toFixed(2)}</b><i><em class="rep" style="width:${100 * Math.abs(driver.ego_rep_delta) / maxRep}%"></em></i></span>
      <span class="ego-cell"><small>Integridad</small><b>−${driver.ego_integrity_cost.toFixed(0)}</b><i><em class="damage" style="width:${100 * driver.ego_integrity_cost / maxIntegrity}%"></em></i></span>
    </div>
  </div>`).join('');
}

function renderClusters(data) {
  drawScatter('clusterPlot', data.drivers, 'stress', 'criminal_share_pct', {
    title: 'Estrés y proporción de acciones criminales observadas', xLabel: 'Estrés · 0–100', yLabel: 'Acciones criminales · %',
    xMax: 100, yMax: Math.max(1, ...data.drivers.map(point => point.criminal_share_pct)) * 1.2, yDigits: 1,
  });
  $('clusterList').innerHTML = (data.clusters || []).map(group => {
    const members = data.drivers.filter(driver => driver.cluster === group.id);
    const averageStress = members.length ? members.reduce((sum, driver) => sum + driver.stress, 0) / members.length : 0;
    const averageCrime = members.length ? members.reduce((sum, driver) => sum + driver.criminal_share_pct, 0) / members.length : 0;
    return `<article class="cluster-card" style="--cluster-color:${clusterColors[(group.id - 1) % clusterColors.length]}">
      <h4>Grupo ${group.id}</h4><p>${group.traits.join(' · ')}</p><p class="cluster-members">${group.members.join(', ')}</p>
      <small>Estrés medio ${averageStress.toFixed(0)} · acciones criminales ${averageCrime.toFixed(1)}%</small></article>`;
  }).join('');
}

export function renderAnalytics(data) {
  if (!data?.ready) { $('analyticsEmpty').hidden = false; return; }
  $('analyticsEmpty').hidden = true;
  drawScatter('pressureChart', data.drivers, 'aggression', 'crimes_per_100_ticks', {
    title: 'Agresividad y crímenes observados por cien ticks activos', xLabel: 'Agresividad · 0–1', yLabel: 'Crímenes / 100 ticks',
    xMax: 1, xDigits: 1, yDigits: 2, stressRadius: true,
  });
  $('pressureNote').textContent = `${data.drivers.length} conductores · tamaño de marca = estrés`;
  renderLuckRows(data.drivers); renderEgoRows(data.drivers); renderClusters(data);
  const reputationDays = (data.days || []).map(point => ({ ...point, day: point.day ?? point.dia }));
  drawHistoryChart('reputationChart', reputationDays, 'rep', { max: 5, label: 'Reputación sindical por jornada', markerDay: data.transit_day });
  $('transitDayLabel').textContent = data.transit_day == null ? `Tránsito aún no activado · umbral ${data.transit_threshold} faltas` : `Tránsito se activó el día ${data.transit_day}`;
}
