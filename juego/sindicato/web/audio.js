const button = document.getElementById('soundToggle');
const buttonLabel = document.getElementById('soundLabel');
const status = document.getElementById('audioStatus');
const audioFiles = {
  simulation: new URL('/assets/musica/soundtrack.mp3?v=20261127-audio', document.baseURI).href,
  menu: new URL('/assets/musica/menus.mp3?v=20261127-audio', document.baseURI).href,
};

const PLAYBACK_RATE = 1.18;
const DRY_MIX = 0.82;
const WET_MIX = 0.18;
const TRACK_GAIN = 0.62;
const FADE_SECONDS = 0.28;

let audioContext = null;
let masterGain = null;
let audioUnlocked = false;
let enabled = loadPreference();
let requestedMode = 'menu';
let activeMode = null;
let switchVersion = 0;
let announcementVersion = 0;
let failureLatched = false;
let failureReported = false;
let unlockPromise = null;
const tracks = new Map();

function loadPreference() {
  try { return localStorage.getItem('dies-irae-audio-muted') !== 'true'; }
  catch { return true; }
}

function savePreference() {
  try { localStorage.setItem('dies-irae-audio-muted', String(!enabled)); } catch {}
}

function announce(message, visible = false) {
  if (!status) return;
  status.textContent = message;
  status.classList.toggle('visually-hidden', !visible);
  const version = ++announcementVersion;
  if (visible) window.setTimeout(() => {
    if (version === announcementVersion) status.classList.add('visually-hidden');
  }, 3200);
}

function reportFailure(message, visible = true) {
  failureLatched = true;
  if (failureReported) return;
  failureReported = true;
  announce(message, visible);
  console.warn(`[Audio] ${message}`);
}

function renderButton() {
  if (!button || !buttonLabel) return;
  const audible = enabled && audioUnlocked && activeMode !== null;
  const label = audible ? 'Silenciar audio' : 'Activar audio';
  buttonLabel.textContent = label;
  button.setAttribute('aria-label', label);
  button.setAttribute('aria-pressed', String(audible));
  button.classList.toggle('is-active', audible);
}

function makeImpulse(context, seconds = 1.6, decay = 2.8) {
  const frames = Math.floor(context.sampleRate * seconds);
  const impulse = context.createBuffer(2, frames, context.sampleRate);
  for (let channel = 0; channel < impulse.numberOfChannels; channel += 1) {
    const samples = impulse.getChannelData(channel);
    for (let frame = 0; frame < frames; frame += 1) {
      const tail = 1 - frame / frames;
      samples[frame] = (Math.random() * 2 - 1) * tail ** decay;
    }
  }
  return impulse;
}

function createTrack(mode) {
  const media = new Audio();
  media.src = audioFiles[mode];
  media.preload = 'none';
  media.loop = true;
  media.playbackRate = PLAYBACK_RATE;
  if ('preservesPitch' in media) media.preservesPitch = false;

  const source = audioContext.createMediaElementSource(media);
  const dry = audioContext.createGain();
  const wet = audioContext.createGain();
  const reverb = audioContext.createConvolver();
  const channel = audioContext.createGain();
  reverb.buffer = makeImpulse(audioContext);
  dry.gain.value = DRY_MIX;
  wet.gain.value = WET_MIX;
  channel.gain.value = 0;

  source.connect(dry);
  dry.connect(channel);
  source.connect(reverb);
  reverb.connect(wet);
  wet.connect(channel);
  channel.connect(masterGain);

  const track = { media, channel };
  media.addEventListener('error', () => {
    const code = media.error?.code;
    reportFailure(`No se pudo cargar la pista ${mode === 'menu' ? 'del menú' : 'de la simulación'}${code ? ` (error ${code})` : ''}. Comprueba que el servidor y el archivo estén disponibles.`);
  });
  tracks.set(mode, track);
  return track;
}

function prepareAudio() {
  if (audioContext) return true;
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) {
    reportFailure('Este navegador no admite el procesamiento de audio.');
    button.disabled = true;
    renderButton();
    return false;
  }
  try {
    const context = new AudioContextClass();
    audioContext = context;
    context.addEventListener('statechange', () => {
      audioUnlocked = context.state === 'running';
      renderButton();
    });
    masterGain = audioContext.createGain();
    masterGain.gain.value = 0;
    masterGain.connect(audioContext.destination);
    createTrack('menu');
    createTrack('simulation');
    return true;
  } catch {
    audioContext?.close();
    audioContext = null;
    masterGain = null;
    reportFailure('No se pudo preparar el procesamiento de audio.');
    renderButton();
    return false;
  }
}

function setGain(gainNode, value, now = audioContext.currentTime) {
  gainNode.gain.cancelScheduledValues(now);
  gainNode.gain.setValueAtTime(gainNode.gain.value, now);
  gainNode.gain.setTargetAtTime(value, now, 0.075);
}

function activateTrack(mode, version) {
  if (version !== switchVersion || !enabled || !audioUnlocked) return false;
  const now = audioContext.currentTime;
  for (const [key, track] of tracks) setGain(track.channel, key === mode ? TRACK_GAIN : 0, now);
  setGain(masterGain, 0.78, now);
  const previous = activeMode;
  activeMode = mode;
  if (previous && previous !== activeMode) {
    window.setTimeout(() => {
      const oldTrack = tracks.get(previous);
      if (activeMode !== previous && oldTrack) oldTrack.media.pause();
    }, FADE_SECONDS * 1000 + 180);
  }
  announce(requestedMode === 'simulation' ? 'Música de simulación activa.' : 'Música de menú activa.');
  renderButton();
  return true;
}

async function switchTrack(mode) {
  requestedMode = mode === 'simulation' ? 'simulation' : 'menu';
  if (!enabled || failureLatched || !audioUnlocked || !audioContext || audioContext.state !== 'running') return;

  const next = tracks.get(requestedMode) || createTrack(requestedMode);
  if (activeMode === requestedMode && !next.media.paused) return;
  const version = ++switchVersion;

  try {
    await next.media.play();
  } catch {
    reportFailure('No se pudo cargar la música. Comprueba que el servidor y las pistas estén actualizados.');
    return;
  }
  if (!activateTrack(requestedMode, version)) next.media.pause();
}

function unlockAudio({ retry = false } = {}) {
  if (!enabled || (!retry && failureLatched)) return Promise.resolve(false);
  if (unlockPromise) return unlockPromise;
  if (!prepareAudio()) return Promise.resolve(false);
  if (retry) { failureLatched = false; failureReported = false; }

  const mode = requestedMode;
  const version = ++switchVersion;
  const next = tracks.get(mode) || createTrack(mode);
  // resume() y play() se invocan sincrónicamente dentro del gesto del usuario.
  let resumePromise, playbackPromise;
  try {
    resumePromise = audioContext.resume();
    playbackPromise = next.media.play();
  } catch {
    reportFailure('No se pudo cargar la música. Comprueba que el servidor y las pistas estén actualizados.');
    renderButton();
    return Promise.resolve(false);
  }
  unlockPromise = Promise.all([resumePromise, playbackPromise]).then(async () => {
    audioUnlocked = audioContext.state === 'running';
    if (!audioUnlocked) throw new Error('El navegador mantuvo el audio suspendido.');
    renderButton();
    if (requestedMode !== mode) return await switchTrack(requestedMode);
    failureLatched = false;
    failureReported = false;
    return activateTrack(mode, version);
  }).catch(() => {
    audioUnlocked = audioContext?.state === 'running';
    for (const track of tracks.values()) track.media.pause();
    activeMode = null;
    renderButton();
    reportFailure('No se pudo cargar la música. Comprueba que el servidor y las pistas estén actualizados.');
    return false;
  }).finally(() => { unlockPromise = null; });
  return unlockPromise;
}

function silenceAudio() {
  if (!audioContext || !masterGain) return;
  setGain(masterGain, 0);
  switchVersion += 1;
  window.setTimeout(() => {
    if (enabled) return;
    for (const track of tracks.values()) track.media.pause();
    activeMode = null;
  }, FADE_SECONDS * 1000 + 180);
}

function onPageGesture(event) {
  if (!enabled || audioUnlocked || failureLatched || event.target.closest?.('#soundToggle')) return;
  void unlockAudio();
}

button?.addEventListener('click', async () => {
  if (!enabled || !audioUnlocked || failureLatched) {
    enabled = true;
    savePreference();
    renderButton();
    await unlockAudio({ retry: true });
    return;
  }

  enabled = !enabled;
  savePreference();
  renderButton();
  if (enabled) {
    await unlockAudio();
  } else {
    silenceAudio();
    announce('Audio silenciado.');
  }
});

document.addEventListener('pointerdown', onPageGesture, { capture: true });
document.addEventListener('keydown', onPageGesture, { capture: true });
renderButton();

export const contextualAudio = { setMode: switchTrack };
