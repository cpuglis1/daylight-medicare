'use strict';
const confirmation = document.querySelector('#confirm-delete');
const button = document.querySelector('#delete-history');
const status = document.querySelector('#delete-status');
confirmation.addEventListener('change', () => { button.disabled = !confirmation.checked; });
button.addEventListener('click', async () => {
  button.disabled = true;
  try {
    const session = await fetch('/api/guest/session', {cache:'no-store'});
    if (!session.ok) throw new Error('access');
    const {csrf} = await session.json();
    const response = await fetch('/api/pilot/history/delete', {
      method:'POST', headers:{'Content-Type':'application/json','X-Daylight-CSRF':csrf},
      body:JSON.stringify({confirm:true})
    });
    if (!response.ok) throw new Error('delete');
    const result = await response.json();
    try { sessionStorage.removeItem('daylight-visit-reference-v1'); sessionStorage.removeItem('daylight-invitation-attempt-v1'); } catch { /* optional browser storage */ }
    status.textContent = 'Your live history was deleted and this visit is closed. Backup copies expire within 30 days.';
    if (result.ownerReentry) {
      const fresh = document.createElement('a');
      fresh.href = '/pilot/join'; fresh.textContent = 'Start a new owner visit';
      const paragraph = document.createElement('p'); paragraph.append(fresh); status.after(paragraph);
    }
    confirmation.disabled = true;
  } catch {
    status.textContent = 'Deletion could not be confirmed. Wait for any reply to finish, then try again.';
    button.disabled = !confirmation.checked;
  }
});

// D200: a fresh start on a shared invitation, at most five per visitor.
const restart = document.querySelector('#restart');
const restartBox = document.querySelector('#confirm-restart');
const restartButton = document.querySelector('#restart-visit');
const restartStatus = document.querySelector('#restart-status');
const restartLeft = document.querySelector('#restart-left');
function showLeft(left, limit) {
  restartLeft.textContent = left > 0 ? `You can do this ${left} more ${left === 1 ? 'time' : 'times'} (up to ${limit}).`
    : 'This invitation has no fresh starts left.';
  restartBox.disabled = left < 1; restartButton.disabled = left < 1 || !restartBox.checked;
}
(async () => {
  try {
    const response = await fetch('/api/pilot/restart', {cache:'no-store'});
    if (!response.ok) return;
    const {left, limit} = await response.json();
    restart.hidden = false; showLeft(left, limit);
    if (location.hash === '#restart') restart.scrollIntoView();
  } catch { /* the section stays hidden */ }
})();
restartBox.addEventListener('change', () => { restartButton.disabled = !restartBox.checked; });
restartButton.addEventListener('click', async () => {
  restartButton.disabled = true;
  try {
    const session = await fetch('/api/guest/session', {cache:'no-store'});
    if (!session.ok) throw new Error('access');
    const {csrf} = await session.json();
    const response = await fetch('/api/pilot/restart', {
      method:'POST', headers:{'Content-Type':'application/json','X-Daylight-CSRF':csrf},
      body:JSON.stringify({confirm:true})
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'restart');
    try { sessionStorage.removeItem('daylight-visit-reference-v1'); } catch { /* optional browser storage */ }
    restartStatus.textContent = 'Starting a new conversation…';
    location.assign('/');
  } catch (error) {
    restartStatus.textContent = error.message && error.message !== 'restart' && error.message !== 'access' ? error.message
      : 'A new conversation could not start. Wait for any reply to finish, then try again.';
    restartButton.disabled = !restartBox.checked;
  }
});
