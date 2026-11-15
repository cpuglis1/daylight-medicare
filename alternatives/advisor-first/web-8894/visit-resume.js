/* A tab keeps request references only. Guest cookies authorize server reads. */
(() => {
  'use strict';
  const KEY = window.location?.pathname === '/d146/' ? 'daylight-d146-visit-reference-v1' : 'daylight-visit-reference-v1';
  const validId = value => typeof value === 'string' && /^[A-Za-z0-9-]{10,80}$/.test(value);

  function clear() {
    try {sessionStorage.removeItem(KEY);} catch {}
  }
  function read() {
    try {
      const value = JSON.parse(sessionStorage.getItem(KEY));
      if (!value || !validId(value.requestId) || !Number.isFinite(value.expiresAt)
          || value.expiresAt <= Date.now()
          || value.previousRequestId && !validId(value.previousRequestId)) return null;
      return value;
    } catch {return null;}
  }
  function write(requestId, preferences, pending = false) {
    if (!validId(requestId)) return false;
    const previous = read();
    const value = {
      requestId,
      ...(pending && previous ? {previousRequestId: previous.previousRequestId || previous.requestId} : {}),
      saveGuide: preferences?.saveGuide === true,
      saveSensitive: preferences?.saveGuide === true && preferences?.saveSensitive === true,
      expiresAt: Date.now() + 86400000, // D157: 24 hours, matching the server's visit memory
    };
    try {sessionStorage.setItem(KEY, JSON.stringify(value));return true;} catch {return false;}
  }
  function preferences(value) {
    const marker = read();
    if (!marker) return;
    marker.saveGuide = value.saveGuide === true;
    marker.saveSensitive = marker.saveGuide && value.saveSensitive === true;
    try {sessionStorage.setItem(KEY, JSON.stringify(marker));} catch {clear();}
  }
  async function restore(api, wait = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds))) {
    const marker = read();
    if (!marker) return null;
    const payload = {requestId: marker.requestId,
      ...(marker.previousRequestId ? {previousRequestId: marker.previousRequestId} : {})};
    for (let attempt = 0; attempt < 20; attempt++) {
      const result = await api('/api/conversation/resume', payload);
      if (result.status === 'resumed' && result.response?.continuation) {
        // A newer explicit privacy choice in this tab takes precedence.
        const current = read();
        result.response.guide.preferences.saveGuide = current?.saveGuide === true;
        result.response.guide.preferences.saveSensitive = current?.saveGuide === true && current?.saveSensitive === true;
        write(result.requestId, result.response.guide.preferences);
        return result;
      }
      if (['expired', 'superseded'].includes(result.status)) {clear();return result;}
      if (result.status !== 'working') throw Error('The current visit could not be reopened.');
      if (attempt < 19) await wait(1500);
    }
    return {status: 'working'};
  }
  window.DaylightVisitResume = Object.freeze({read, write, clear, preferences, restore});
})();
