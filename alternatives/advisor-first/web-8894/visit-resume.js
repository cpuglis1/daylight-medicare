/* A tab keeps request references only. Guest cookies authorize server reads. */
(() => {
  'use strict';
  const KEY = 'daylight-visit-reference-v1';
  const pages = new Set(['conversation', 'paths', 'advantage', 'supplement', 'part-d']);
  const validId = value => typeof value === 'string' && /^[A-Za-z0-9-]{10,80}$/.test(value);

  function clear() {
    try {sessionStorage.removeItem(KEY);} catch {}
  }
  function read() {
    try {
      const value = JSON.parse(sessionStorage.getItem(KEY));
      if (!value || !validId(value.requestId) || !Number.isFinite(value.expiresAt)
          || value.expiresAt <= Date.now() || !pages.has(value.page)
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
      page: previous?.page || 'conversation',
      saveGuide: preferences?.saveGuide === true,
      saveSensitive: preferences?.saveGuide === true && preferences?.saveSensitive === true,
      expiresAt: Date.now() + 3600000,
    };
    try {sessionStorage.setItem(KEY, JSON.stringify(value));return true;} catch {return false;}
  }
  function rememberPage(page) {
    const value = read();
    if (!value || !pages.has(page)) return;
    value.page = page;
    try {sessionStorage.setItem(KEY, JSON.stringify(value));} catch {}
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
        return {...result, page: marker.page};
      }
      if (['expired', 'superseded'].includes(result.status)) {clear();return result;}
      if (result.status !== 'working') throw Error('The current visit could not be reopened.');
      if (attempt < 19) await wait(1500);
    }
    return {status: 'working'};
  }
  window.DaylightVisitResume = Object.freeze({read, write, clear, rememberPage, preferences, restore});
})();
