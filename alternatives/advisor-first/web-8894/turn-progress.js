/* D178. Loaded only on :8895/isolated fixtures. No model request. Answer text appears only as
   checked blocks when :8895's checked-block release is on (Nov 17, 2026). */
(function(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.DaylightTurnProgress = api;
})(typeof window !== 'undefined' ? window : globalThis, function() {
  'use strict';
  const words = Object.freeze({
    working: 'Working through your question…',
    doctors: 'Looking up your doctor’s information…',
    medicines: 'Checking medicine and pharmacy information…',
    plans: 'Looking up plan information…',
    composing: 'Preparing your reply…'
  });
  function view(receipt, elapsed, accepted) {
    if (receipt?.state === 'working' && Object.hasOwn(words, receipt.stage)) {
      const value = {stage: receipt.stage, text: words[receipt.stage],
        more: elapsed >= 30000 ? 'This is taking longer than usual. Your message is here. No need to send it again.'
          : elapsed >= 12000 ? 'Your message is here. No need to send it again.' : ''};
      // :8895 checked-block release: reply blocks the server already checked (never drafts).
      if (Array.isArray(receipt.blocks) && receipt.blocks.length) value.blocks = receipt.blocks.filter(b => typeof b === 'string').slice(0, 4);
      return value;
    }
    if (receipt?.state === 'complete') return {stage:'complete',text:'Receiving your reply…',more:''};
    if (receipt?.state === 'failed') return {stage:'failed',text:'Your message is here.',more:''};
    return {stage:'waiting',text:accepted ? 'Waiting for an update…' : 'Sending your message…',more:''};
  }
  function start({read, render, now = () => performance.now(), schedule = setTimeout, cancel = clearTimeout}) {
    const started = now();
    let stopped = false, accepted = false, timer = null, deadline = null, controller = null, previous = '';
    function display(value) {
      const key = JSON.stringify(value);
      if (!stopped && key !== previous) {previous = key;render(value);}
    }
    display(view(null, 0, false));
    async function poll() {
      if (stopped) return;
      controller = new AbortController();
      deadline = schedule(() => controller?.abort(), 4000);
      let terminal = false;
      try {
        const receipt = await read(controller.signal);
        if (stopped) return;
        if (['working','complete','failed'].includes(receipt?.state)) accepted = true;
        display(view(receipt, now() - started, accepted));
        terminal = ['complete','failed'].includes(receipt?.state);
      } catch (_) {
        // Poll failures cannot fail/replay the conversation or pretend a stage is active.
        if (!stopped) display({stage:'waiting',text:'Waiting for an update…',more:''});
      } finally {
        cancel(deadline);deadline = null;controller = null;
        if (!stopped && !terminal) timer = schedule(poll, 1000);
      }
    }
    // The main POST is started first; only a backend receipt claims acceptance.
    timer = schedule(poll, 150);
    function stop() {stopped = true;cancel(timer);cancel(deadline);controller?.abort();}
    return {stop, reconnecting() {
      display({stage:'reconnecting',text:'Reconnecting to your conversation…',more:''});stop();
    }};
  }
  return {start, view};
});
