'use strict';
const invitation = location.hash.slice(1);
history.replaceState(null, '', location.pathname);
const status = document.querySelector('[role="status"]');
const button = document.querySelector('button');
if (invitation) {
  button.disabled = false;
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      const response = await fetch('/pilot/redeem', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({invitation})
      });
      if (response.ok) {
        location.replace('/');
        return;
      }
      status.textContent = response.status === 401
        ? 'This invitation is unavailable. Ask Daylight for help.'
        : 'Daylight could not open your invitation. Try again.';
      button.disabled = response.status === 401;
    } catch {
      status.textContent = 'Daylight could not open your invitation. Try again.';
      button.disabled = false;
    }
  });
} else {
  status.textContent = 'Open the invitation link you received.';
}
