'use strict';
const tokenPattern = /^[0-9a-f]{32}\.[0-9]{1,12}\.[0-9a-f]{64}$/;
function invitationFrom(url) {
  if (url.origin !== location.origin) return '';
  const candidate = url.pathname.startsWith('/pilot/invite/')
    ? url.pathname.slice('/pilot/invite/'.length) : url.pathname === '/pilot/join' ? url.hash.slice(1) : '';
  return tokenPattern.test(candidate) ? candidate : '';
}
let invitation = invitationFrom(new URL(location.href));
const status = document.querySelector('[role="status"]');
const button = document.querySelector('#continue-invitation');
const consent = document.querySelector('#save-history');
const pasteArea = document.querySelector('#invitation-entry');
const pasteInput = document.querySelector('#invitation-link');
let entry = {active:false, savedHistory:false, ownerReentry:false};
let opening = false;
let checking = true;
const attemptKey = 'daylight-invitation-attempt-v1';
async function boundedFetch(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(path, {...options, credentials:'same-origin', cache:'no-store', signal:controller.signal});
    const data = await response.json();
    return {ok:response.ok, status:response.status, json:async () => data};
  }
  finally { clearTimeout(timer); }
}
function ready() {
  button.disabled = opening || checking || !(invitation || entry.active || entry.ownerReentry);
  button.textContent = opening ? 'Opening Daylight…' : entry.active ? 'Continue your visit' : entry.ownerReentry ? 'Start a new visit' : 'Continue';
  pasteArea.hidden = !!(invitation || entry.active || entry.ownerReentry);
}
pasteInput.addEventListener('input', () => {
  try {
    const url = new URL(pasteInput.value.trim());
    invitation = invitationFrom(url);
    if (invitation) {
      history.replaceState(null, '', url.pathname + url.hash);
      status.textContent = 'Your invitation is ready. Choose whether to save this visit, then continue.';
    } else status.textContent = 'Paste the complete invitation for this Daylight address, including everything after the slash or #.';
  } catch { invitation = ''; }
  ready();
});
function attempt() {
  const link = invitation ? invitation.split('.')[0] : 'owner-or-existing-visit';
  let prior = pendingAttempt;
  try { prior ||= JSON.parse(sessionStorage.getItem(attemptKey)); } catch { /* private browsing may disable storage */ }
  const save = !!consent?.checked;
  if (prior?.link === link && prior?.nonce && prior.save === save) return prior.nonce;
  if (prior?.link === link && prior?.nonce && prior.save !== save) throw new Error('Keep the same saved-chat choice while retrying this invitation.');
  const nonce = crypto.randomUUID();
  pendingAttempt = {link, nonce, save};
  try { sessionStorage.setItem(attemptKey, JSON.stringify(pendingAttempt)); } catch { /* current page still retains the nonce */ }
  return nonce;
}
let pendingAttempt = null;
button.addEventListener('click', async () => {
  if (opening || checking) return;
  opening = true; ready(); status.textContent = 'Opening your visit…';
  try {
    const requestId = attempt();
    const response = await boundedFetch('/pilot/redeem', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({...(invitation ? {invitation} : {}), requestId,
        ...(consent?.checked ? {historyConsent:'hosted-demo-history-2026-11-18-v1'} : {})})
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'This invitation could not be opened. Try again.');
    try {
      sessionStorage.removeItem(attemptKey);
      if (result.newVisit) sessionStorage.removeItem('daylight-visit-reference-v1');
    } catch { /* secure cookies and navigation still work */ }
    location.assign('/');
  } catch (error) {
    status.textContent = error.name === 'AbortError'
      ? 'Opening took too long. Try Continue again; it will reuse the same visit.'
      : error.message || 'The connection was interrupted. Try Continue again.';
    opening = false; ready();
  }
});
ready();
status.textContent = invitation ? 'Choose whether to save this visit, then continue.' : 'Checking for your current visit…';
boundedFetch('/pilot/access').then(async response => {
  if (!response.ok) throw new Error('access');
  entry = await response.json();
  checking = false;
  if (invitation && entry.invitationId !== invitation.split('.')[0]) entry = {...entry, active:false, savedHistory:false};
  if (entry.active && entry.savedHistory && consent) { consent.checked = true; consent.disabled = true; }
  if (!opening) status.textContent = entry.active
    ? (entry.savedHistory ? 'Your existing visit is ready to continue.' : 'Continue browsing, or agree above to enable saved AI chat from now on.')
    : entry.ownerReentry ? 'Your previous visit is closed. Choose whether to save a new visit, then continue.'
    : invitation ? 'Choose whether to save this visit, then continue.' : 'Open your full invitation link, or paste it below.';
  ready();
}).catch(() => {
  checking = false;
  if (!opening) status.textContent = invitation ? 'Your invitation is ready. Continue to try opening it.' : 'Open your full invitation link, or paste it below.';
  ready();
});
