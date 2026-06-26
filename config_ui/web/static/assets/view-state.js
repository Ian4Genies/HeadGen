/** Per-profile UI view state — scroll, selections, filters (not config data). */

const configFileStates = new Map();
const traceStates = new Map();

export function configStateKey(profile, fileId) {
  return `${profile}:${fileId}`;
}

export function saveConfigFileState(profile, fileId, state) {
  if (!profile || !fileId || !state) return;
  configFileStates.set(configStateKey(profile, fileId), state);
}

export function loadConfigFileState(profile, fileId) {
  return configFileStates.get(configStateKey(profile, fileId)) ?? null;
}

export function saveTraceState(profile, state) {
  if (!profile || !state) return;
  traceStates.set(profile, state);
}

export function loadTraceState(profile) {
  return traceStates.get(profile) ?? null;
}

export function clearProfileViewState(profile) {
  for (const k of [...configFileStates.keys()]) {
    if (k.startsWith(`${profile}:`)) configFileStates.delete(k);
  }
  traceStates.delete(profile);
}

export function createUiStore(initial = {}) {
  const state = { ...initial };
  return {
    state,
    get(key) {
      return state[key];
    },
    set(patch) {
      Object.assign(state, patch);
    },
  };
}

export function restoreScroll(el, scrollTop) {
  if (!el || scrollTop == null || scrollTop <= 0) return;
  requestAnimationFrame(() => {
    el.scrollTop = scrollTop;
  });
}
