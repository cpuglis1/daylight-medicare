/* Same-page integration boundary. No URL parameters, storage or network transfer. */
(() => {
  'use strict';
  let destination = null;
  window.DaylightPlansHandoff = Object.freeze({
    register(openWorkspace) {
      if (typeof openWorkspace !== 'function') throw new TypeError('Use a plans workspace handler.');
      destination = openWorkspace;
      return () => { if (destination === openWorkspace) destination = null; };
    },
    async open(handoff) {
      if (!handoff || handoff.version !== 'plan-review-20261104-r1'
          || handoff.destination !== 'plans' || handoff.reportedInfoReviewed !== true
          || handoff.expiresAt * 1000 <= Date.now()) return false;
      // A UI receipt conveys reviewed reports, never recommendation permission.
      // The receiving backend must re-resolve the token before dependent work.
      const copy = structuredClone(handoff);
      if (destination) return (await destination(copy)) !== false;
      const event = new CustomEvent('daylight:plans-requested', {detail:copy,cancelable:true});
      return !window.dispatchEvent(event);
    }
  });
})();
