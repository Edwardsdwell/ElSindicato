import {
  assignedImageId, assignedImagePath, assignUnitImage, invalidateRoster, loadVehicleAssets,
  renderDriverDetail, renderDriverStats, renderDriverTabs, renderFleet, vehicleSprite,
} from './vehicles.js';
import { drawHistoryChart, renderAnalytics, renderDriverHistory } from './charts.js';
import { contextualAudio } from './audio.js?v=20261127-audio-v2';

const $ = id => document.getElementById(id);
function composeViews() {
  const main = document.querySelector('main');
  const views = [
    ['vista-juego', 'Simulación', ['.dispatch-head', '.season-ledger', '#seasonResult', '.metric-ribbon', '#cityView']],
    ['vista-personajes', 'Conductores', ['#driversView']],
    ['vista-telemetria', 'Estadísticas', ['.history-heading', '.history-charts', '#analyticsView']],
  ];
  for (const [id, title, selectors] of views) {
    const section = document.createElement('section'); section.id = id; section.className = 'app-view';
    section.setAttribute('aria-label', title); main.append(section);
    for (const selector of selectors) { const node = main.querySelector(`:scope > ${selector}`); if (node) section.append(node); }
  }
  const logs = document.createElement('section'); logs.id = 'vista-bitacoras'; logs.className = 'app-view editorial-view'; logs.innerHTML = `
    <header class="view-heading"><h1>Bitácoras de ruta</h1><p>El método detrás de las políticas y los resultados de cada corrida.</p></header>
    <section class="asset-gallery" aria-labelledby="assetGalleryTitle">
      <div class="asset-gallery-heading"><h2 id="assetGalleryTitle">Archivo visual de la ruta</h2><p>Coloca tus imágenes en <code>Apartado multimedia/assets/imagenes/</code>.</p></div>
      <div class="asset-gallery-grid">
        <figure class="asset-slot"><div class="asset-frame"><img src="/assets/imagenes/corredor-369.jpeg" alt="Vista del corredor Villa Fátima–Cotahuma" loading="eager"><span class="asset-placeholder">Cargando imagen…</span></div><figcaption><b>Corredor de la línea 369</b><code>Apartado multimedia/assets/imagenes/corredor-369.jpeg</code></figcaption></figure>
        <figure class="asset-slot"><div class="asset-frame"><img src="/assets/imagenes/flota-369.jpg" alt="Flota de minibuses de la línea 369" loading="eager"><span class="asset-placeholder">Cargando imagen…</span></div><figcaption><b>Flota de minibuses</b><code>Apartado multimedia/assets/imagenes/flota-369.jpg</code></figcaption></figure>
        <figure class="asset-slot"><div class="asset-frame"><img src="/assets/imagenes/la-paz-diurna.webp" alt="La Paz durante el servicio diurno" loading="eager"><span class="asset-placeholder">Cargando imagen…</span></div><figcaption><b>La Paz de día</b><code>Apartado multimedia/assets/imagenes/la-paz-diurna.webp</code></figcaption></figure>
      </div>
    </section>
    <nav class="subnav" aria-label="Secciones de la bitácora"><a href="#bitacora-metodo">Construcción</a><a href="#bitacora-preentreno">Preentrenamiento</a><a href="#bitacora-entrenamiento">Entrenamiento</a><a href="#bitacora-experimentos">Experimentos</a></nav>
    <article class="journal-entry" id="bitacora-metodo"><h2>Cómo se construyó</h2><p>El motor combina agentes tabulares SARSA para cinco minibuseros, un agente Q-learning para Tránsito y un grafo vial de OpenStreetMap centrado en La Paz. El servidor local expone el estado y sirve la consola Canvas.</p><p>El código activo vive en <code>juego/src/dies_irae/</code>: configuración, entorno, ciudad, aprendizaje, análisis y pipeline.</p></article>
    <article class="journal-entry" id="bitacora-preentreno"><h2>Preentrenamiento inicial</h2><p>Genera las políticas de partida: SARSA para los cinco minibuses durante 6.000 días y Q-learning para Tránsito durante 2.000 días, con semilla 0. Al terminar se crean <code>mini1.npy</code> a <code>mini5.npy</code> y <code>transito.npy</code> en <code>modelosML/preentrenados/</code>.</p><p>Desde la carpeta principal ejecuta: <code>python "pre entrenamiento" --dias-minis 6000 --dias-transito 2000 --semilla 0</code>.</p></article>
    <article class="journal-entry" id="bitacora-entrenamiento"><h2>Entrenamiento posterior</h2><p>Continúa el aprendizaje desde las políticas preentrenadas durante 1.826 días, con semilla 7 y una exploración baja (ε=0,05). Guarda los modelos finales en <code>outputs/entrenamiento/modelos_finales/</code> y el reporte de la corrida en <code>outputs/entrenamiento/</code>.</p><p>Desde la carpeta principal ejecuta: <code>python "modelosML/entrenamiento/ejecutar.py" --dias 1826 --semilla 7</code>. Necesita que el preentrenamiento ya haya creado los modelos iniciales.</p></article>
    <article class="journal-entry" id="bitacora-experimentos"><h2>Experimentos y corridas</h2><p>Las corridas guardan su configuración y resultados para poder revisar el comportamiento de las políticas.</p><p>Las siguientes corridas guardan sus hashes y configuración en <code>outputs/sindicato/replicabilidad.json</code>.</p><p id="runJournal">Aún no hay una corrida activa con datos que registrar.</p></article>`;
  logs.querySelectorAll('.asset-slot img').forEach(image => {
    const frame = image.closest('.asset-slot');
    const placeholder = frame.querySelector('.asset-placeholder');
    const setLoaded = () => {
      const loaded = image.naturalWidth > 0;
      frame.classList.toggle('has-image', loaded);
      frame.classList.toggle('load-error', !loaded);
      if (!loaded && placeholder) placeholder.textContent = 'No se pudo cargar. Comprueba la ruta y reinicia jugar.py.';
    };
    image.addEventListener('load', setLoaded, { once: true });
    image.addEventListener('error', setLoaded, { once: true });
    if (image.complete) setLoaded();
  });
  logs.insertAdjacentHTML('beforeend', `
    <section id="pretrainingPanel" class="training-dashboard" aria-labelledby="pretrainingTitle" aria-live="polite">
      <header class="training-dashboard-head"><div><span class="kicker">Políticas iniciales · registro local</span><h2 id="pretrainingTitle">Resumen del preentrenamiento</h2><p>Parámetros, evaluación y archivos que alimentan la simulación.</p></div><span id="pretrainingStatus" class="training-status">Consultando modelos…</span></header>
      <div id="pretrainingSummary" class="training-summary"><p class="training-empty">Cargando el registro del preentrenamiento…</p></div>
      <div class="training-visual-grid">
        <article class="training-card"><header><h3>Duración por etapa</h3><p>Días registrados para las tablas iniciales.</p></header><div id="pretrainingPhases" class="training-phases"></div></article>
        <article class="training-card"><header><h3>Flujo de aprendizaje</h3><p>Cómo se obtienen las políticas cargadas por el juego.</p></header><ol class="training-flow"><li><b>1</b><span><strong>Minibuses</strong><small>SARSA · cinco políticas</small></span></li><li><b>2</b><span><strong>Tránsito</strong><small>Q-learning · una política</small></span></li><li><b>3</b><span><strong>Evaluación</strong><small>Corrida sin aprendizaje</small></span></li><li><b>4</b><span><strong>Modelos</strong><small>Tablas .npy listas para usar</small></span></li></ol></article>
      </div>
      <article class="training-card training-results"><header><h3>Evaluación e inventario</h3><p id="pretrainingResultNote">Métricas registradas y estado de las seis tablas.</p></header><div id="pretrainingResults" class="training-results-grid"></div><div class="training-table-wrap"><table class="training-table"><thead><tr><th>Política</th><th>Estados</th><th>Acciones</th><th>Archivo</th><th>Estado</th></tr></thead><tbody id="pretrainingModels"></tbody></table></div></article>
      <article class="training-card"><header><h3>Historial de ejecuciones</h3><p>Últimos registros guardados junto a los modelos.</p></header><ol id="pretrainingHistory" class="training-history"><li>Buscando historial…</li></ol></article>
    </section>`);
  main.append(logs);
  void loadPretrainingPanel();
  const rules = document.createElement('section'); rules.id = 'vista-reglas'; rules.className = 'app-view editorial-view'; rules.innerHTML = '<header class="view-heading"><h1>Reglas del servicio</h1><p>Parámetros activos y efecto de cada decisión en el corredor.</p></header><div id="rulesTable" class="rules-table"><p>Cargando parámetros del motor…</p></div>';
  main.append(rules);
}
composeViews();

function escapeHTML(value) {
  return String(value ?? '—').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}

function formatTrainingDate(value) {
  if (!value) return 'Sin fecha registrada';
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? escapeHTML(value) : new Intl.DateTimeFormat('es-BO', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

function trainingMetric(label, value) {
  return `<div class="training-metric"><span>${escapeHTML(label)}</span><strong>${escapeHTML(value)}</strong></div>`;
}

async function loadPretrainingPanel() {
  const status = $('pretrainingStatus');
  try {
    const response = await fetch('/api/pretraining', { cache: 'no-store' });
    if (!response.ok) throw new Error('No se pudo leer el inventario de modelos.');
    const data = await response.json();
    const metadata = data.metadata || {};
    const tables = data.tables || [];
    const metrics = metadata.metricas || {};
    const complete = data.status === 'completo';
    status.className = `training-status ${complete ? 'is-complete' : data.status === 'incompleto' ? 'is-incomplete' : ''}`;
    status.textContent = data.status === 'sin-registro' ? 'Sin preentreno registrado' : `${data.available_tables} / 6 tablas ${complete ? 'listas' : 'disponibles'}`;

    const date = formatTrainingDate(metadata.fecha);
    const states = Number(metadata.n_estados_mini || tables.find(table => table.file === 'mini1.npy')?.states || 0);
    const actions = Number(metadata.n_acciones_mini || tables.find(table => table.file === 'mini1.npy')?.actions || 0);
    const transitStates = Number(metadata.n_estados_transito || tables.find(table => table.file === 'transito.npy')?.states || 0);
    const totalPairs = tables.reduce((sum, table) => sum + (table.states || 0) * (table.actions || 0), 0);
    $('pretrainingSummary').innerHTML = [
      trainingMetric('Último registro', date),
      trainingMetric('Semilla', metadata.semilla ?? '—'),
      trainingMetric('Método', 'SARSA + Q-learning'),
      trainingMetric('ε · minibuses', metadata.epsilon?.minis_inicial ?? metadata.epsilon?.inicial ?? metadata.epsilon?.minis ?? '—'),
      trainingMetric('ε · Tránsito', metadata.epsilon?.transito ?? '—'),
      trainingMetric('Tasa de aprendizaje α', metadata.alfa ?? '—'),
      trainingMetric('Descuento γ', metadata.gamma ?? '—'),
      trainingMetric('Pares estado–acción', totalPairs.toLocaleString('es-BO')),
    ].join('');

    const miniDays = Number(metadata.dias_minis || 0), transitDays = Number(metadata.dias_transito || 0);
    const maxDays = Math.max(miniDays, transitDays, 1);
    $('pretrainingPhases').innerHTML = [
      ['Minibuses · SARSA', miniDays, '#46866a'],
      ['Tránsito · Q-learning', transitDays, '#bd7b25'],
      ['Evaluación', Number(metadata.dias_evaluacion || 0), '#668ca1'],
    ].map(([label, days, color]) => `<div class="training-phase"><div><span>${escapeHTML(label)}</span><b>${Number(days).toLocaleString('es-BO')} días</b></div><i><span style="width:${Math.min(100, Number(days) / maxDays * 100)}%;background:${color}"></span></i></div>`).join('');

    const resultItems = metrics && Object.keys(metrics).length ? [
      ['Ingreso medio · Bs / minibus / día', metrics.ingreso_medio_minibus_dia],
      ['Faltas por día', metrics.faltas_dia],
      ['Accidentes por día', metrics.accidentes_dia],
      ['Arrestos por día', metrics.arrestos_transito_dia],
      ['Reputación final', metrics.reputacion_final],
      ['Resultado de evaluación', metrics.resultado],
    ] : [
      ['Tablas disponibles', `${data.available_tables} de 6`],
      ['Estados · minibús', states || '—'],
      ['Acciones · minibús', actions || '—'],
      ['Estados · Tránsito', transitStates || '—'],
      ['Evaluación registrada', metadata.dias_evaluacion ? `${metadata.dias_evaluacion} días` : 'Sin métricas guardadas'],
      ['Estado del registro', data.status === 'completo' ? 'Políticas utilizables' : 'Revisar archivos faltantes'],
    ];
    $('pretrainingResults').innerHTML = resultItems.map(([label, value]) => trainingMetric(label, value == null ? '—' : value)).join('');
    $('pretrainingResultNote').textContent = Object.keys(metrics).length
      ? `${metrics.dias_completados || metadata.dias_evaluacion || 0} días observados con aprendizaje desactivado.`
      : 'El registro anterior no guardó resultados de evaluación; se muestran dimensiones y disponibilidad reales de las tablas.';

    const labels = ['Unidad 1', 'Unidad 2', 'Unidad 3', 'Unidad 4', 'Unidad 5', 'Tránsito'];
    $('pretrainingModels').innerHTML = tables.map((table, index) => `<tr><th scope="row">${labels[index] || escapeHTML(table.file)}</th><td>${table.states ?? '—'}</td><td>${table.actions ?? '—'}</td><td><code>${escapeHTML(table.file)}</code></td><td><span class="model-state ${table.available && table.finite ? 'ready' : 'missing'}">${table.available && table.finite ? 'Lista' : 'Falta o inválida'}</span></td></tr>`).join('');

    let history = Array.isArray(metadata.historial) ? metadata.historial : [];
    if (!history.length && metadata.fecha) history = [{ fecha: metadata.fecha, semilla: metadata.semilla, dias_minis: miniDays, dias_transito: transitDays, metricas: metrics }];
    $('pretrainingHistory').innerHTML = history.length
      ? history.slice(-8).reverse().map((run, index) => {
        const summary = run.tipo
          ? `${escapeHTML(run.tipo)} · ${Number(run.dias_evaluacion || 0).toLocaleString('es-BO')} días`
          : `${Number(run.dias_minis || 0).toLocaleString('es-BO')} días SARSA · ${Number(run.dias_transito || 0).toLocaleString('es-BO')} días Q-learning`;
        return `<li><span class="history-index">${String(history.length - index).padStart(2, '0')}</span><span><strong>${formatTrainingDate(run.fecha)} · semilla ${escapeHTML(run.semilla ?? '—')}</strong><small>${summary}${run.metricas?.resultado ? ` · ${escapeHTML(run.metricas.resultado)}` : run.resultado ? ` · ${escapeHTML(run.resultado)}` : ''}</small></span></li>`;
      }).join('')
      : '<li class="training-empty">No hay ejecuciones guardadas todavía.</li>';
  } catch (error) {
    status.className = 'training-status is-incomplete';
    status.textContent = 'No se pudo leer el registro';
    $('pretrainingSummary').innerHTML = `<p class="training-empty">${escapeHTML(error.message)}</p>`;
  }
}

const canvas = $('cityMap'), ctx = canvas.getContext('2d');
const baseCanvas = document.createElement('canvas'), baseCtx = baseCanvas.getContext('2d');
const unitColors = ['#b17a2a','#39796b','#b75e47','#607886','#d9b36a'];
let current = null, routePoints = [], routeLine = [], mapData = null, mapRequested = false;
let displayed = new Map(), displayedTraffic = new Map(), eventQueue = [], lastEventTick = -1;
let selectedDriver = 1, historyRevision = -1, historyDriverId = null, historyRequest = false;
let analyticsRevision = -1, analyticsRequest = false, polling = false;
let hoveredUnit = null, activeViewId = 'vista-juego';

const post = async (path, data) => {
  const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'El servidor no pudo completar la acción.');
  return result;
};

function updateRunFeedback(message = '') {
  const feedback = $('runFeedback');
  feedback.textContent = message;
  feedback.hidden = !message;
}

function syncPortalReadouts(state) {
  $('portalServiceReadout').textContent = !state.ready
    ? state.loading ? 'Preparando ruta' : state.error ? 'Revisa el servicio' : 'En espera'
    : state.running ? 'En servicio' : state.ended ? 'Corrida finalizada' : 'En pausa';
  $('portalFleetReadout').textContent = `${state.ready ? state.agents?.length ?? 0 : 0} / 5`;
  $('portalRepReadout').textContent = state.ready ? Number(state.reputation).toFixed(2) : '—';
  $('portalIntervalsReadout').textContent = String(state.ticks_per_day || 16);
  $('portalRulesReadout').textContent = `${state.ticks_per_day || 16} intervalos`;
}

function updateContextAudio() {
  const menuIsOpen = document.body.classList.contains('portal-open');
  const runningInSimulation = !menuIsOpen && activeViewId === 'vista-juego' && current?.ready && current.running && !current.ended;
  contextualAudio.setMode(runningInSimulation ? 'simulation' : 'menu');
}

async function runControl(action) {
  try {
    const result = await post('/api/control', action);
    updateRunFeedback();
    return result;
  } catch (error) {
    updateRunFeedback(`No se pudo actualizar la simulación. ${error.message}`);
    return null;
  }
}

function fitMap() {
  const w = canvas.clientWidth, h = canvas.clientHeight, pad = 44;
  if (routePoints.length < 2) return null;
  const xs = routePoints.map(point => point.x), ys = routePoints.map(point => point.y);
  let minx = Math.min(...xs), maxx = Math.max(...xs), miny = Math.min(...ys), maxy = Math.max(...ys);
  if (mapData?.bounds) [minx, maxx, miny, maxy] = mapData.bounds;
  const scale = Math.min((w - 2 * pad) / (maxx - minx || 1), (h - 2 * pad) / (maxy - miny || 1));
  return { w, h, minx, maxy, scale, ox: (w - (maxx - minx) * scale) / 2, oy: (h - (maxy - miny) * scale) / 2 };
}
function project(x, y, frame) { return [frame.ox + (x - frame.minx) * frame.scale, frame.h - (frame.oy + (frame.maxy - y) * frame.scale)]; }

function drawMapBase() {
  const w = canvas.clientWidth, h = canvas.clientHeight, dpr = window.devicePixelRatio || 1, frame = fitMap();
  if (!w || !h || !frame) return;
  baseCanvas.width = Math.round(w * dpr); baseCanvas.height = Math.round(h * dpr);
  baseCtx.setTransform(dpr, 0, 0, dpr, 0, 0); baseCtx.clearRect(0, 0, w, h);
  baseCtx.fillStyle = '#e7ecdf'; baseCtx.fillRect(0, 0, w, h);
  if (mapData?.roads) {
    baseCtx.lineWidth = .7; baseCtx.strokeStyle = '#aebaa8'; baseCtx.globalAlpha = .43;
    for (const road of mapData.roads) {
      if (road.length < 2) continue;
      baseCtx.beginPath(); road.forEach((p, i) => { const [x, y] = project(p[0], p[1], frame); i ? baseCtx.lineTo(x, y) : baseCtx.moveTo(x, y); }); baseCtx.stroke();
    }
    baseCtx.globalAlpha = 1;
  }
  const points = routeLine.map(point => project(point.x, point.y, frame));
  baseCtx.beginPath(); points.forEach(([x, y], i) => i ? baseCtx.lineTo(x, y) : baseCtx.moveTo(x, y));
  baseCtx.lineWidth = 11; baseCtx.strokeStyle = '#f6f0df'; baseCtx.lineJoin = 'round'; baseCtx.lineCap = 'round'; baseCtx.stroke();
  baseCtx.lineWidth = 3.4; baseCtx.strokeStyle = '#b87928'; baseCtx.shadowColor = 'transparent'; baseCtx.shadowBlur = 0; baseCtx.stroke();
  routePoints.forEach((point, i) => {
    const [x, y] = project(point.x, point.y, frame); baseCtx.beginPath(); baseCtx.arc(x, y, 2.4, 0, Math.PI * 2); baseCtx.fillStyle = '#c17a22'; baseCtx.fill();
    if (i % 7 === 0) { baseCtx.font = '11px "Trebuchet MS", sans-serif'; baseCtx.fillStyle = '#53634f'; baseCtx.fillText(point.name, x + 8, y - 7); }
  });
}
function resizeMap() {
  const rect = canvas.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(rect.width * dpr); canvas.height = Math.round(rect.height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); drawMapBase();
}
new ResizeObserver(resizeMap).observe(canvas); resizeMap();

async function loadAssets() {
  try {
    await loadVehicleAssets();
    if (current?.ready) {
      renderFleet(current);
      renderDriverPanel(current);
      drawMapBase();
    }
  } catch (error) { console.warn('No se pudieron cargar las imágenes locales:', error); }
}
loadAssets();

function renderEvents(state) {
  const feed = $('eventFeed');
  const heading = '<header><span class="kicker">RADIO DE RUTA</span><h2>Sucesos recientes</h2></header>';
  if (!eventQueue.length) { feed.innerHTML = `${heading}<p>Sin incidentes reportados.</p>`; return; }
  feed.innerHTML = heading + eventQueue.slice(0, 5).map(event =>
    `<div class="event-row"><i>!</i><span>Día ${event.day} · Unidad ${event.mini}: ${String(event.label).replaceAll('_', ' ')}</span></div>`).join('');
}

function renderDriverPanel(state) {
  const drivers = state.drivers || [];
  if (!state.ready || !drivers.length) {
    $('driverDetail').innerHTML = `<div class="driver-empty">${state.loading ? 'Preparando las fichas de las unidades.' : 'Inicia la simulación para consultar a los conductores.'}</div>`;
    $('historyRange').textContent = 'Sin muestras registradas';
    for (const id of ['incomeChart', 'integrityChart', 'stressChart']) $(id).innerHTML = '<div class="chart-empty">El historial aparece al cerrar la jornada.</div>';
    historyDriverId = null; historyRevision = -1; return;
  }
  if (!drivers.some(driver => driver.id === selectedDriver)) selectedDriver = drivers[0].id;
  renderDriverTabs(drivers, selectedDriver);
  $('driverTabs').querySelectorAll('.driver-tab').forEach(tab => {
    const active = Number(tab.dataset.driver) === selectedDriver;
    tab.classList.toggle('active', active); tab.setAttribute('aria-selected', String(active));
  });
  const driver = drivers.find(item => item.id === selectedDriver);
  if ($('driverDetail').dataset.driver !== String(driver.id) || !$('unitImageSelect')?.options.length) renderDriverDetail(driver);
  else renderDriverStats(driver);
  requestHistory(state);
}

function requestHistory(state) {
  if (!state.ready || !state.history_revision || historyRequest) return;
  if (historyDriverId === selectedDriver && historyRevision === state.history_revision) return;
  historyRequest = true;
  fetch(`/api/history?id=${selectedDriver}`, { cache: 'no-store' }).then(response => response.json()).then(data => {
    if (data.driver_id !== selectedDriver) return;
    historyDriverId = data.driver_id; historyRevision = data.revision;
    renderDriverHistory({ income: 'incomeChart', integrity: 'integrityChart', stress: 'stressChart' }, data.points || []);
  }).catch(() => {}).finally(() => { historyRequest = false; });
}

function requestAnalytics(state) {
  if (!state.ready || analyticsRequest || analyticsRevision === state.day) return;
  analyticsRequest = true;
  fetch('/api/analytics', { cache: 'no-store' }).then(response => response.json()).then(data => {
    analyticsRevision = data.revision; renderAnalytics(data);
  }).catch(error => console.warn('No se pudo cargar la telemetría:', error)).finally(() => { analyticsRequest = false; });
}

function applyControlAvailability(state) {
  const ready = !!state.ready;
  $('start').disabled = !!state.loading;
  $('transitMode').disabled = !!state.loading;
  for (const id of ['pause', 'resume', 'stepTick', 'stepDay', 'stepMonth']) $(id).disabled = !ready;
  $('pause').disabled = !ready || !state.running;
  $('resume').disabled = !ready || state.running || state.ended || state.day >= state.target_days;
  $('stepTick').disabled = !ready || state.running;
  $('stepDay').disabled = !ready || state.running;
  $('stepMonth').disabled = !ready || state.running;
  $('reset').disabled = !ready || state.ended || state.saved;
  $('launchTransit').disabled = !ready || state.transit_active || state.ended || state.day >= state.target_days;
}

function setState(state) {
  current = state;
  syncPortalReadouts(state);
  if (!state.ready) {
    $('overlay').classList.remove('hidden'); $('overlay').classList.toggle('busy', !!state.loading);
    $('overlay').querySelector('b').textContent = state.error ? 'No se pudo iniciar' : state.loading ? 'Preparando la ruta' : 'Listo para salir';
    $('overlay').querySelector('small').textContent = state.error || (state.loading ? 'La red vial se prepara en segundo plano.' : 'Las unidades esperan la señal de despacho.');
    applyControlAvailability(state); renderDriverPanel(state); updateContextAudio(); return;
  }
  $('overlay').classList.add('hidden');
  for (const point of state.route) if (!routePoints.some(existing => existing.name === point.name)) routePoints.push(point);
  const present = new Set(state.agents.map(agent => agent.id));
  for (const id of displayed.keys()) if (!present.has(id)) displayed.delete(id);
  for (const agent of state.agents) {
    const item = displayed.get(agent.id) || { x: agent.x, y: agent.y };
    item.tx = agent.x; item.ty = agent.y; item.data = agent; displayed.set(agent.id, item);
  }
  const carIds = new Set(state.traffic_cars.map(car => car.id));
  for (const id of displayedTraffic.keys()) if (!carIds.has(id)) displayedTraffic.delete(id);
  for (const car of state.traffic_cars) {
    const item = displayedTraffic.get(car.id) || { x: car.x, y: car.y };
    item.tx = car.x; item.ty = car.y; displayedTraffic.set(car.id, item);
  }
  if (!mapRequested) {
    mapRequested = true;
    fetch('/api/map', { cache: 'no-store' }).then(response => response.json()).then(map => {
      if (!map.ready) return;
      mapData = map; routeLine = map.route_line; drawMapBase();
      document.querySelector('.map-label span').textContent = `${map.road_count.toLocaleString('es-BO')} tramos viales`;
    }).catch(() => { mapRequested = false; });
  }
  if (state.events?.length && state.tick !== lastEventTick) {
    for (const event of state.events) eventQueue.unshift({ ...event, day: state.day, at: performance.now() });
    eventQueue = eventQueue.slice(0, 8); lastEventTick = state.tick;
  }
  $('runState').textContent = state.running ? 'Unidades en servicio' : state.ended ? 'Simulación finalizada' : state.day >= state.target_days ? 'Jornada completada' : 'Servicio en pausa';
  $('liveDot').classList.toggle('on', state.running);
  $('clock').textContent = `Día ${String(state.day).padStart(4, '0')} · intervalo ${String(state.tick_in_day).padStart(2, '0')}`;
  $('dayMetric').textContent = `${state.day.toLocaleString('es-BO')} / ${state.target_days.toLocaleString('es-BO')}`;
  $('tickMetric').textContent = `Intervalo ${state.tick_in_day} de ${state.ticks_per_day || 16}`;
  $('repMetric').textContent = Number(state.reputation).toFixed(2);
  $('repMetric').style.color = state.reputation >= 4.2 ? 'var(--lime)' : 'var(--orange)';
  $('faultMetric').textContent = Number(state.faults).toLocaleString('es-BO');
  $('transitThresholdLabel').textContent = state.transit_mode === 'manual'
    ? 'Despliegue bajo decisión del operador' : `Umbral automático: ${state.transit_threshold} faltas`;
  $('paxMetric').textContent = Math.max(0, state.passengers_left).toLocaleString('es-BO');
  $('trafficMetric').textContent = ['Fluido', 'Moderado', 'Congestionado'][Math.min(2, state.traffic || 0)];
  $('maxDebt').textContent = `Bs ${Number(state.maxima_deuda || 0).toLocaleString('es-BO')}`;
  $('maxDebtName').textContent = state.maxima_deuda_quien || 'Sin deuda acumulada';
  $('maxGain').textContent = `Bs ${Number(state.maxima_ganancia || 0).toLocaleString('es-BO')}`;
  $('maxGainName').textContent = state.maxima_ganancia_quien || 'Sin ganancia neta';
  renderSeasonResult(state);
  document.querySelectorAll('.traffic-lights i').forEach((light, i) => light.classList.toggle('active', i === (state.traffic || 0)));
  const percent = Math.min(100, 100 * state.day / Math.max(1, state.target_days));
  $('timelineFill').style.width = `${percent}%`; $('progressLabel').textContent = `${percent.toFixed(1)}%`;
  $('timelineLabel').textContent = `Año ${Math.min(5, Math.floor(state.day / 365) + 1)}`;
  $('transitState').textContent = state.transit_active ? 'En ruta' : state.transit_mode === 'manual' ? 'A la espera de despacho' : 'Esperando el umbral';
  $('transitModeNote').textContent = state.transit_active
    ? `Desplegado en la jornada ${state.transit_day ?? state.day}`
    : state.transit_mode === 'manual'
      ? 'Modo manual · decide cuándo desplegar'
      : `Automático a ${state.transit_threshold} faltas · también puedes adelantarlo`;
  $('launchTransit').textContent = state.transit_active ? 'Tránsito desplegado' : 'Desplegar Tránsito ↗';
  $('arrestCount').textContent = state.transit?.arrests || 0;
  const thresholdProgress = state.transit_mode === 'automatic' ? Math.min(100, state.faults * 100 / Math.max(1, state.transit_threshold)) : 0;
  $('transitBar').style.width = state.transit_active ? '100%' : `${thresholdProgress}%`;
  $('modelId').textContent = `Modelos ${state.model_hash?.slice(0, 8) || '—'} · Código ${state.code_hash?.slice(0, 8) || '—'} · Red ${state.street_hash?.slice(0, 8) || '—'}`;
  renderFleet(state); renderEvents(state); applyControlAvailability(state); renderDriverPanel(state); requestAnalytics(state);
  if (state.saved && state.result) $('runState').textContent = state.result.final;
  updateContextAudio();
}

function renderSeasonResult(state) {
  const root = $('seasonResult'), result = state.result;
  if (!result) { root.hidden = true; return; }
  root.hidden = false;
  const winners = (result.ganadores || []).map(id => {
    const driver = state.drivers.find(item => item.id === id);
    return driver ? `<p><b>${driver.name}</b><span>Balance final · Bs ${Number(result.winner_balances?.[id] ?? driver.money).toLocaleString('es-BO')}</span></p>` : '';
  }).join('') || '<p>Sin ganador con las condiciones de esta temporada.</p>';
  const losers = (result.losers || []).map(item => `<p><b>${item.nombre}</b><span>Ronda ${item.ronda} · día ${item.dia} · ${item.motivo} · Bs ${Number(item.balance).toLocaleString('es-BO')}</span></p>`).join('') || '<p>No hubo abandonos ni eliminaciones.</p>';
  root.innerHTML = `<header><span class="kicker">CIERRE DE TEMPORADA</span><h2>${result.final}</h2><p>Balance de quienes llegaron al cierre.</p></header><div class="result-winners"><h3>Ganador y balance</h3>${winners}</div><details class="loser-ledger" open><summary>Perdedores · ronda y motivo de salida</summary>${losers}</details>`;
}

function drawMini(x, y, id) {
  const image = vehicleSprite(assignedImageId(id)) || vehicleSprite('mini1');
  if (hoveredUnit === id || selectedDriver === id) { ctx.beginPath(); ctx.arc(x, y, hoveredUnit === id ? 25 : 21, 0, Math.PI * 2); ctx.strokeStyle = '#9b621c'; ctx.lineWidth = hoveredUnit === id ? 2.5 : 1.5; ctx.stroke(); }
  if (image?.complete && image.naturalWidth) ctx.drawImage(image, x - 28, y - 18, 56, 37);
  else { ctx.fillStyle = unitColors[id - 1]; ctx.beginPath(); ctx.arc(x, y, 6, 0, Math.PI * 2); ctx.fill(); }
}
function drawTransit(x, y) {
  const image = vehicleSprite('transito');
  if (image?.complete && image.naturalWidth) ctx.drawImage(image, x - 28, y - 18, 56, 37);
  else { ctx.fillStyle = '#b75e47'; ctx.beginPath(); ctx.arc(x, y, 7, 0, Math.PI * 2); ctx.fill(); }
}
function animateMap() {
  if (document.body.classList.contains('portal-open') || activeViewId !== 'vista-juego') return;
  requestAnimationFrame(animateMap);
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w || !h) return;
  ctx.clearRect(0, 0, w, h); if (baseCanvas.width) ctx.drawImage(baseCanvas, 0, 0, w, h);
  const frame = fitMap(); if (!frame) return;
  for (const car of displayedTraffic.values()) {
    car.x += (car.tx - car.x) * .24; car.y += (car.ty - car.y) * .24;
    const [x, y] = project(car.x, car.y, frame); ctx.fillStyle = current?.traffic > 1 ? '#b17a2a' : '#607886';
    ctx.beginPath(); ctx.roundRect(x - 2.5, y - 1.4, 5, 2.8, 1); ctx.fill();
  }
  for (const pedestrian of current?.pedestrians || []) {
    const [x, y] = project(pedestrian.x, pedestrian.y, frame); ctx.beginPath(); ctx.arc(x + 10, y + 7, 2.2, 0, Math.PI * 2);
    ctx.fillStyle = '#607886'; ctx.fill(); ctx.fillRect(x + 9, y + 9, 2, 4);
  }
  for (const event of eventQueue) {
    if (performance.now() - event.at > 4500) continue;
    const unit = displayed.get(event.mini); if (!unit) continue;
    const [x, y] = project(unit.x, unit.y, frame); ctx.beginPath(); ctx.arc(x, y, 15, 0, Math.PI * 2);
    ctx.strokeStyle = '#b75e47'; ctx.lineWidth = 2; ctx.stroke();
  }
  for (const [id, unit] of displayed) {
    unit.x += (unit.tx - unit.x) * .22; unit.y += (unit.ty - unit.y) * .22;
    const [x, y] = project(unit.x, unit.y, frame); drawMini(x, y, id);
    ctx.font = '600 12px "Segoe UI", sans-serif'; ctx.fillStyle = '#26372b'; ctx.fillText(`U${id}`, x + 15, y - 11);
  }
  if (current?.transit_active && current.transit) {
    const [x, y] = project(current.transit.x, current.transit.y, frame); drawTransit(x, y);
  }
}
animateMap();

async function poll() {
  if (polling) return; polling = true;
  try { const response = await fetch('/api/state', { cache: 'no-store' }); setState(await response.json()); }
  catch {}
  finally { polling = false; setTimeout(poll, document.body.classList.contains('portal-open') ? 900 : 220); }
}
poll();

function clearRunView() {
  eventQueue = []; displayed.clear(); displayedTraffic.clear(); routePoints = []; routeLine = [];
  mapData = null; mapRequested = false; historyDriverId = null; historyRevision = -1; analyticsRevision = -1; invalidateRoster();
  $('overlay').classList.remove('hidden'); $('overlay').classList.add('busy');
  $('overlay').querySelector('b').textContent = 'Despachando unidades';
}
async function startSimulation() {
  updateRunFeedback();
  $('start').disabled = true;
  try {
    const state = await post('/api/start', { seed: Number($('seed').value), days: Number($('days').value), transit_mode: $('transitMode').value, difficulty: $('difficulty').value });
    clearRunView();
    setState(state);
  } catch (error) {
    updateRunFeedback(`No se pudo iniciar la simulación. ${error.message} Puedes intentarlo de nuevo.`);
  } finally {
    if (!current?.loading) $('start').disabled = false;
  }
}
$('start').addEventListener('click', startSimulation);
$('reset').addEventListener('click', () => $('resetDialog').showModal());
$('resetDialog').addEventListener('close', async () => {
  if ($('resetDialog').returnValue !== 'confirm') return;
  updateRunFeedback();
  try {
    const state = await post('/api/reset', {});
    clearRunView();
    $('overlay').querySelector('b').textContent = 'Reiniciando la simulación';
    setState(state);
  } catch (error) {
    updateRunFeedback(`No se pudo reiniciar la simulación. ${error.message} La corrida sigue disponible.`);
  }
});
$('launchTransit').addEventListener('click', async () => {
  updateRunFeedback();
  try {
    const result = await post('/api/transit', {});
    if (result.error) $('transitModeNote').textContent = result.error;
  } catch (error) { updateRunFeedback(`No se pudo desplegar Tránsito. ${error.message}`); }
});
$('pause').addEventListener('click', () => runControl({ action: 'pause' }));
$('resume').addEventListener('click', () => runControl({ action: 'resume' }));
$('stepTick').addEventListener('click', () => runControl({ action: 'step', ticks: 1 }));
$('stepDay').addEventListener('click', () => runControl({ action: 'step', ticks: 16 }));
$('stepMonth').addEventListener('click', () => runControl({ action: 'step', ticks: 480 }));
$('speed').addEventListener('input', event => {
  $('speedValue').textContent = `${event.target.value} intervalos/s`;
  runControl({ action: 'speed', value: event.target.value });
});
$('driverTabs').addEventListener('click', event => {
  const tab = event.target.closest('[data-driver]'); if (!tab) return;
  selectedDriver = Number(tab.dataset.driver); historyDriverId = null; historyRevision = -1;
  if (current?.ready) renderDriverPanel(current);
});
$('fleet').addEventListener('click', event => {
  const row = event.target.closest('[data-driver]'); if (!row) return;
  selectedDriver = Number(row.dataset.driver); historyDriverId = null; historyRevision = -1;
  if (current?.ready) renderDriverPanel(current);
  showView('vista-personajes', true);
});
$('driverDetail').addEventListener('change', event => {
  if (event.target.id !== 'unitImageSelect') return;
  assignUnitImage(selectedDriver, event.target.value);
  if (current?.ready) {
    renderFleet(current); renderDriverTabs(current.drivers, selectedDriver);
    document.querySelectorAll('.driver-tab').forEach(tab => {
      const active = Number(tab.dataset.driver) === selectedDriver;
      tab.classList.toggle('active', active); tab.setAttribute('aria-selected', String(active));
    });
    const driver = current.drivers.find(item => item.id === selectedDriver);
    renderDriverDetail(driver); drawMapBase();
  }
});
function showView(id, updateHash = false) {
  const node = document.getElementById(id);
  const target = node?.classList.contains('app-view') ? id : 'vista-juego';
  activeViewId = target;
  document.querySelectorAll('.app-view').forEach(view => {
    const active = view.id === target;
    view.hidden = !active;
    if (active) { view.classList.remove('view-enter'); void view.offsetWidth; view.classList.add('view-enter'); }
  });
  document.querySelectorAll('.view-nav a').forEach(item => {
    const active = item.dataset.view === target;
    item.classList.toggle('active', active);
    if (active) item.setAttribute('aria-current', 'page');
    else item.removeAttribute('aria-current');
  });
  if (updateHash && location.hash !== `#${target}`) history.replaceState(null, '', `#${target}`);
  if (target === 'vista-reglas') loadRules();
  if (target === 'vista-bitacoras' && current?.ready) $('runJournal').textContent = `Corrida actual · semilla ${current.seed} · día ${current.day} de ${current.target_days} · ${current.transit_mode === 'manual' ? 'Tránsito manual' : 'Tránsito automático'} · dificultad ${current.difficulty_name || 'Normal'}.`;
  if (target === 'vista-juego') { requestAnimationFrame(resizeMap); requestAnimationFrame(animateMap); }
  updateContextAudio();
}
function scrollToJournalAnchor(id) {
  const destination = document.getElementById(id);
  const view = destination?.closest('.app-view');
  if (!destination || !view || destination === view) return false;
  showView(view.id);
  requestAnimationFrame(() => destination.scrollIntoView({
    behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start',
  }));
  return true;
}
function routeHash() {
  const target = location.hash.slice(1);
  if (target === 'portal') { openPortal(); return; }
  if (portal.open) closePortal({ restoreHash: false });
  if (!scrollToJournalAnchor(target)) showView(target);
}
document.querySelector('#vista-bitacoras .subnav').addEventListener('click', event => {
  const link = event.target.closest('a[href^="#bitacora-"]');
  if (!link) return;
  event.preventDefault();
  history.pushState(null, '', link.hash);
  scrollToJournalAnchor(link.hash.slice(1));
});
const portal = $('routePortal');
const portalTrigger = $('portalToggle');
const soundToggle = $('soundToggle');
const audioStatus = $('audioStatus');
const audioStatusAnchor = $('audioStatusAnchor');
const portalShell = [document.querySelector('.topbar'), $('top')];
let portalClosing = false;
function openPortal() {
  if (portal.open) return;
  portalClosing = false;
  portal.querySelector('.portal-menu')?.classList.remove('chosen');
  portal.querySelectorAll('.portal-panel.is-selected').forEach(panel => panel.classList.remove('is-selected'));
  portal.querySelector('.portal-actions').prepend(soundToggle);
  portal.append(audioStatus);
  portal.inert = false;
  portal.setAttribute('aria-hidden', 'false');
  portal.showModal();
  portalShell.forEach(node => { node.inert = true; });
  document.body.classList.add('portal-open');
  document.body.classList.remove('portal-pending');
  updateContextAudio();
  portalTrigger.setAttribute('aria-expanded', 'true');
  if (location.hash !== '#portal') history.replaceState(null, '', '#portal');
  requestAnimationFrame(() => {
    portal.classList.add('is-open');
    portal.querySelector('[data-portal-view]')?.focus();
  });
}
function closePortal({ restoreHash = true } = {}) {
  if (!portal.open || portalClosing) return;
  portalClosing = true;
  portal.classList.remove('is-open');
  if (restoreHash && location.hash !== `#${activeViewId}`) history.replaceState(null, '', `#${activeViewId}`);
  const closeDelay = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 120;
  window.setTimeout(() => {
    if (portal.open) portal.close();
    portalTrigger.before(soundToggle);
    audioStatusAnchor.after(audioStatus);
    portal.setAttribute('aria-hidden', 'true');
    portal.inert = true;
    portalShell.forEach(node => { node.inert = false; });
    document.body.classList.remove('portal-open');
    updateContextAudio();
    if (activeViewId === 'vista-juego') requestAnimationFrame(animateMap);
    portalTrigger.setAttribute('aria-expanded', 'false');
    portalClosing = false;
    portalTrigger.focus();
  }, closeDelay);
}
portalTrigger.addEventListener('click', openPortal);
$('closePortal').addEventListener('click', closePortal);
portal.addEventListener('click', event => {
  const panel = event.target.closest('[data-portal-view]');
  if (!panel || portal.querySelector('.portal-menu.chosen')) return;
  panel.classList.add('is-selected');
  panel.closest('.portal-menu').classList.add('chosen');
  showView(panel.dataset.portalView, true);
  window.setTimeout(() => {
    closePortal();
    if (pendingJournalAnchor && panel.dataset.portalView === 'vista-bitacoras') {
      const anchor = pendingJournalAnchor; pendingJournalAnchor = null;
      window.setTimeout(() => scrollToJournalAnchor(anchor), 180);
    }
  }, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 150);
});
portal.addEventListener('keydown', event => {
  if (event.key === 'Escape') { event.preventDefault(); closePortal(); return; }
  if (event.key !== 'Tab') return;
  const focusable = [...portal.querySelectorAll('button:not(:disabled)')];
  const first = focusable[0], last = focusable.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});
async function loadRules() {
  const root = $('rulesTable'); if (root.dataset.loaded) return;
  try {
    const response = await fetch('/api/rules'); const data = await response.json();
    const summary = `<div class="rule-facts"><p><b>${data.ticks_per_day}</b><span>intervalos por jornada</span></p><p><b>${data.hours_per_tick}</b><span>horas por intervalo</span></p><p><b>Bs ${Number(data.fare_bs).toFixed(2)}</b><span>tarifa base</span></p><p><b>Bs ${Number(data.annual_fee_bs).toLocaleString('es-BO')}</b><span>cuota anual</span></p><p><b>${Number(data.reputation_minimum).toFixed(1)}</b><span>reputación mínima</span></p><p><b>${data.transit_fault_threshold}</b><span>faltas para Tránsito</span></p></div>`;
    const kinds = { neutro: 'Servicio', egoista: 'Individualista', altruista: 'Cooperativa', filosofica: 'Filosófica', criminal: 'Criminal' };
    const cards = data.actions.map((action, index) => {
      const metrics = [
        ['Velocidad', `${Number(action.speed).toFixed(2)}×`],
        ['Riesgo adicional', `${(Number(action.accident_risk) * 100).toFixed(1)} %`],
        ['Integridad', `${Number(action.integrity_cost).toFixed(1)} pts`],
        ['Cambio de reputación', Number(action.reputation).toFixed(2)],
        ['Atractivo para pasajeros', Number(action.passenger_appeal).toFixed(2)],
        ['Cambio de estatus buscado', Number(action.wanted_change).toFixed(1)],
        ['Recompensa', Number(action.reward).toFixed(1)],
        ['Penalización', Number(action.penalty).toFixed(1)],
        ['Costo', `Bs ${Number(action.cost_bs).toFixed(2)}`],
        ['Cambio de estrés', Number(action.stress).toFixed(1)],
      ];
      const title = String(action.name).replaceAll('_', ' ').replace(/^./, letter => letter.toLocaleUpperCase('es-BO'));
      const kind = kinds[action.kind] || 'Acción';
      return `<article class="rule-card" style="--rule-index:${index}"><header><span class="rule-index">${String(index + 1).padStart(2, '0')}</span><div><h2>${title}</h2><span class="rule-kind">${kind}</span></div></header><dl>${metrics.map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`).join('')}</dl></article>`;
    }).join('');
    root.innerHTML = `<section class="rule-summary" aria-label="Parámetros generales"><h2>Parámetros de la jornada</h2>${summary}</section><section class="rule-actions" aria-label="Acciones del entorno"><header><h2>Acciones y efectos</h2><p>${data.actions.length} decisiones disponibles para las políticas.</p></header><div class="rule-card-grid">${cards}</div></section>`;
    root.dataset.loaded = 'true';
  } catch { root.innerHTML = '<p>No se pudieron cargar los parámetros del motor.</p>'; }
}
document.querySelectorAll('.view-nav a').forEach(link => link.addEventListener('click', event => { event.preventDefault(); showView(link.dataset.view, true); }));
window.addEventListener('hashchange', routeHash);
window.addEventListener('popstate', routeHash);
canvas.addEventListener('pointermove', event => {
  const bounds = canvas.getBoundingClientRect(), frame = fitMap(); if (!frame) return;
  const mx = event.clientX - bounds.left, my = event.clientY - bounds.top;
  let nearest = null, distance = 25;
  for (const [id, unit] of displayed) { const [x, y] = project(unit.x, unit.y, frame); const d = Math.hypot(x - mx, y - my); if (d < distance) { nearest = id; distance = d; } }
  hoveredUnit = nearest; canvas.style.cursor = nearest ? 'pointer' : 'grab';
});
canvas.addEventListener('pointerleave', () => { hoveredUnit = null; canvas.style.cursor = 'grab'; });
canvas.addEventListener('click', () => {
  if (!hoveredUnit) return;
  selectedDriver = hoveredUnit; historyDriverId = null; historyRevision = -1;
  if (current?.ready) renderDriverPanel(current);
  showView('vista-personajes', true);
});
const initialHash = location.hash.slice(1);
const validInitialViews = ['vista-juego', 'vista-personajes', 'vista-telemetria', 'vista-bitacoras', 'vista-reglas'];
const initialAnchor = document.getElementById(initialHash);
let pendingJournalAnchor = initialAnchor && initialAnchor.closest('.app-view')?.id === 'vista-bitacoras' ? initialHash : null;
showView(validInitialViews.includes(initialHash) ? initialHash : pendingJournalAnchor ? 'vista-bitacoras' : 'vista-juego');
openPortal();







