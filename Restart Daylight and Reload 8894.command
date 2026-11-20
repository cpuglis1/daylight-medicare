#!/bin/bash
# Restart the local advisor and reload its existing Firefox preview tab.
status_ok() {
  [[ $(/usr/bin/curl --noproxy '*' --silent --max-time 2 --output /dev/null \
    --write-out '%{http_code}' "http://127.0.0.1:$1/api/status") == 200 ]]
}

echo 'Restarting Daylight 8893…'
if ! /bin/launchctl kickstart -k "gui/$(/usr/bin/id -u)/com.daylight.advisor-first.8893"; then
  echo 'Could not restart the Daylight 8893 launch agent.' >&2
  exit 1
fi

for ((attempt = 0; attempt < 40; attempt++)); do
  if status_ok 8893; then break; fi
  sleep 1
done
if (( attempt == 40 )); then
  echo '8893 did not come back up. Check alternatives/advisor-first/var/logs/errors.log.' >&2
  exit 1
fi
echo '8893 is back up.'

if ! status_ok 8894; then
  echo '8894 is not responding. Start it with Start Daylight 8894.command, then reload its tab.' >&2
  exit 1
fi

/usr/bin/osascript -l JavaScript <<'JXA'
ObjC.import('AppKit');
ObjC.import('ApplicationServices');

function attribute(element, name) {
  const result = Ref();
  return $.AXUIElementCopyAttributeValue(element, name, result) === 0 ? result[0] : null;
}

function text(element, name) {
  return ObjC.unwrap(attribute(element, name));
}

function items(array) {
  const result = [];
  for (let index = 0; array && index < array.count; index++) {
    result.push(array.objectAtIndex(index));
  }
  return result;
}

function browserElements(root) {
  const containers = ['AXGroup', 'AXSplitGroup', 'AXToolbar', 'AXTabGroup', 'AXScrollArea'];
  const elements = [];
  for (const element of items(attribute(root, 'AXChildren'))) {
    const role = text(element, 'AXRole');
    elements.push({element, role});
    // Read browser controls and the top-level document URL without walking page content.
    if (containers.includes(role)) elements.push(...browserElements(element));
  }
  return elements;
}

function labelMatches(element, pattern) {
  return ['AXTitle', 'AXDescription'].some(name => pattern.test(text(element, name) || ''));
}

function reloadPreview(browserWindow, firefox) {
  const elements = browserElements(browserWindow);
  const preview = elements.some(({element, role}) => {
    if (role !== 'AXWebArea') return false;
    const url = attribute(element, 'AXURL');
    return url && /^http:\/\/(?:127\.0\.0\.1|localhost):8894(?:[/?#]|$)/i.test(ObjC.unwrap(url.absoluteString));
  });
  if (!preview) return false;

  const reload = elements.find(({element, role}) => role === 'AXButton' && labelMatches(element, /^Reload$/));
  if (!reload || $.AXUIElementPerformAction(reload.element, 'AXPress') !== 0) {
    throw new Error('Found the 8894 tab, but Firefox could not reload it. Press Command-R in that tab.');
  }
  firefox.activateWithOptions(0);
  $.AXUIElementPerformAction(browserWindow, 'AXRaise');
  return true;
}

function run() {
  const firefox = items($.NSRunningApplication.runningApplicationsWithBundleIdentifier('org.mozilla.firefox'))[0];
  if (!firefox) throw new Error('Open the 8894 page in Firefox first.');
  if (!$.AXIsProcessTrusted()) {
    throw new Error('To let the shortcut reload Firefox, enable Terminal in System Settings > Privacy & Security > Accessibility.');
  }

  const app = $.AXUIElementCreateApplication(firefox.processIdentifier);
  for (const browserWindow of items(attribute(app, 'AXWindows'))) {
    if (reloadPreview(browserWindow, firefox)) return 'Reloaded the Firefox tab on 8894.';

    const tabs = browserElements(browserWindow).filter(({element, role}) =>
      (role === 'AXRadioButton' || role === 'AXTab') &&
      labelMatches(element, /^(?:Daylight|Local plan research · Daylight)(?:\n|$)/));
    for (const {element} of tabs) {
      if ($.AXUIElementPerformAction(element, 'AXPress') !== 0) continue;
      // Firefox updates the accessible document after changing tabs.
      for (let attempt = 0; attempt < 8; attempt++) {
        $.NSThread.sleepForTimeInterval(0.075);
        if (reloadPreview(browserWindow, firefox)) return 'Reloaded the Firefox tab on 8894.';
      }
    }
  }
  throw new Error('No 8894 tab was found. Open http://127.0.0.1:8894/ in Firefox and try again.');
}
JXA
