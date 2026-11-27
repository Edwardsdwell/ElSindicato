const $ = id => document.getElementById(id);
let assets = [];
const images = {};
let assignments = {};
let renderedRoster = '';
try { assignments = JSON.parse(localStorage.getItem('sindicato-unit-sprites') || '{}'); } catch { assignments = {}; }

export async function loadVehicleAssets() {
  const response = await fetch('/multimedia/sprites/vehicles/manifest.json', { cache: 'no-cache' });
  if (!response.ok) throw new Error('No se encontró el manifiesto de imágenes de unidades.');
  const manifest = await response.json();
  assets = (manifest.icons || []).filter(icon => icon.id.startsWith('mini'));
  for (const icon of manifest.icons || []) {
    const image = new Image();
    image.src = `/multimedia/sprites/vehicles/${encodeURIComponent(icon.output)}`;
    images[icon.id] = image;
  }
  return assets;
}

export function assignedImageId(driverId) {
  const id = assignments[String(driverId)];
  return assets.some(icon => icon.id === id) ? id : `mini${driverId}`;
}

export function assignedImagePath(driverId) {
  const icon = assets.find(item => item.id === assignedImageId(driverId));
  return `/multimedia/sprites/vehicles/${encodeURIComponent(icon?.output || `mini${driverId}.png`)}`;
}

export function vehicleSprite(id) { return images[id]; }
export function invalidateRoster() { renderedRoster = ''; }

export function assignUnitImage(driverId, imageId) {
  if (!assets.some(icon => icon.id === imageId)) return false;
  assignments[String(driverId)] = imageId;
  try { localStorage.setItem('sindicato-unit-sprites', JSON.stringify(assignments)); } catch {}
  invalidateRoster();
  return true;
}

export function renderFleet(state) {
  const list = $('fleet');
  $('fleetCount').textContent = `${state.agents.length} / 5`;
  if (!state.agents.length) { list.innerHTML = '<div class="empty">No hay unidades activas en la ruta.</div>'; return; }
  list.innerHTML = state.agents.map(agent => {
    const traffic = ['fluido', 'moderado', 'congestionado'][agent.traffic] || 'fluido';
    return `<button type="button" class="agent" data-driver="${agent.id}" aria-label="Abrir ficha de ${agent.name}">
      <img class="agent-mark" src="${assignedImagePath(agent.id)}" alt="">
      <span class="agent-copy"><span class="agent-name">${agent.name}</span><small class="agent-detail">${status(agent.status)} · ${traffic} · ${agent.pedestrians_nearby} peatones</small></span>
      <span class="agent-money">Bs ${Number(agent.money).toLocaleString('es-BO')}<small class="agent-state">${agent.laps} vueltas</small></span>
      <span class="agent-bars"><i class="bar"><i style="width:${agent.integrity}%"></i></i><i class="bar fuel"><i style="width:${Math.min(100, agent.fuel / 80 * 100)}%"></i></i></span>
    </button>`;
  }).join('');
}

export function renderDriverTabs(drivers, selectedId) {
  const key = drivers.map(driver => `${driver.id}:${driver.name}:${driver.status}:${assignedImageId(driver.id)}`).join('|');
  if (key === renderedRoster) return;
  renderedRoster = key;
  $('driverTabs').innerHTML = drivers.map(driver => `<button class="driver-tab${driver.id === selectedId ? ' active' : ''}" role="tab" aria-selected="${driver.id === selectedId}" data-driver="${driver.id}">
    <img src="${assignedImagePath(driver.id)}" alt=""><span><b>${driver.name.split(' ')[0]}</b><small>Unidad ${String(driver.id).padStart(2, '0')}</small></span></button>`).join('');
}

export function renderDriverDetail(driver) {
  if (!driver) return;
  $('driverDetail').innerHTML = `<div class="driver-focus">
    <div class="driver-portrait-wrap"><img id="driverPreview" class="driver-portrait" src="${assignedImagePath(driver.id)}" alt="Unidad visual de ${driver.name}"></div>
    <div class="driver-focus-copy"><span id="driverIndex" class="driver-index">Conductor ${driver.id} · ${status(driver.status)}</span><h3 id="driverName" class="driver-name">${driver.name}</h3><p id="driverMeta" class="driver-meta">${driver.model} <i>·</i> ${driver.personality} <i>·</i> ${driver.family}</p></div>
    <label class="skin-assign">Imagen asignada<select id="unitImageSelect" aria-label="Asignar imagen de la unidad"></select></label>
    <figure class="driver-art-slot" data-art-slot>
      <img id="driverArtImage" alt="" loading="lazy">
      <div class="driver-art-empty"><span>Retrato del conductor</span><small>Imagen por añadir</small></div>
    </figure>
  </div><div id="driverSpecs" class="driver-specs"></div>
  <div class="driver-actions"><span>Decisiones más frecuentes durante el servicio</span><div id="driverActions"></div></div>
  <div class="driver-stats" id="driverStats"></div>`;
  $('driverDetail').dataset.driver = driver.id;
  $('unitImageSelect').innerHTML = assets.map(icon => `<option value="${icon.id}">Unidad ${icon.id.replace('mini', '')}</option>`).join('');
  $('unitImageSelect').value = assignedImageId(driver.id);
  const artSlot = $('driverArtImage').closest('[data-art-slot]');
  const artImage = $('driverArtImage');
  artImage.addEventListener('load', () => artSlot.classList.toggle('has-art', artImage.naturalWidth > 0), { once: true });
  artImage.addEventListener('error', () => artSlot.classList.remove('has-art'), { once: true });
  artImage.alt = `Retrato de ${driver.name}`;
  artImage.src = `/imgs/arte/conductor-${String(driver.id).padStart(2, '0')}.webp`;
  renderDriverStats(driver);
}

export function renderDriverStats(driver) {
  if (!driver || !$('driverStats')) return;
  const specs = [
    ['Velocidad habitual', `${driver.standard_speed} km/h`], ['Velocidad máxima', `${driver.max_speed} km/h`],
    ['Gasto familiar', `Bs ${driver.family_cost}/día`], ['Agresividad', `${Math.round(driver.aggression * 100)}%`],
    ['Aversión al riesgo', `${Number(driver.risk_aversion).toFixed(1)} / 2`],
  ];
  $('driverSpecs').innerHTML = specs.map(([name, value]) => `<span>${name}<b>${value}</b></span>`).join('');
  $('driverActions').innerHTML = driver.top_actions?.length
    ? driver.top_actions.map(action => `<span class="action-chip">${action.name.replaceAll('_', ' ')} · ${action.count}</span>`).join('')
    : '<span class="driver-empty">Aún sin decisiones registradas</span>';
  const stats = [
    ['Recaudado', `Bs ${Number(driver.income).toLocaleString('es-BO')}`], ['Pasajeros', Number(driver.passengers).toLocaleString('es-BO')],
    ['Vueltas', Number(driver.laps).toLocaleString('es-BO')], ['Integridad', `${driver.integrity}%`], ['Combustible', `${driver.fuel} L`],
    ['Faltas', driver.faults], ['Arrestos', driver.arrests], ['Accidentes', driver.accidents],
    ['Incidentes peatonales', driver.pedestrian_incidents], ['Estrés', `${driver.stress} / 100`], ['Saldo', `Bs ${Number(driver.money).toLocaleString('es-BO')}`],
  ];
  $('driverStats').innerHTML = stats.map(([label, value]) => `<div class="driver-stat"><span>${label}</span><b>${value}</b></div>`).join('');
  $('driverIndex').textContent = `Conductor ${driver.id} · ${status(driver.status)}`;
  $('driverPreview').alt = `Unidad visual de ${driver.name}`;
}

function status(value) {
  return ({ activo: 'En servicio', prision: 'En detención', eliminado: 'Fuera de servicio', abandono: 'Retirado de la línea' })[value] || value;
}

