'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../web-8894/visit-resume.js'), 'utf8');

function harness() {
  const stored = new Map();
  const window = {};
  const sessionStorage = {
    getItem: key => stored.get(key) || null,
    setItem: (key, value) => stored.set(key, value),
    removeItem: key => stored.delete(key),
  };
  vm.runInNewContext(source, {window, sessionStorage, Date, setTimeout});
  return {api: window.DaylightVisitResume, stored, sessionStorage};
}

test('browser storage keeps only references and saving choices', () => {
  const h = harness();
  h.api.write('request-123456789', {saveGuide: true, saveSensitive: false, health: 'fictional-private'});
  const value = JSON.parse([...h.stored.values()][0]);
  assert.deepEqual(Object.keys(value).sort(), ['expiresAt','requestId','saveGuide','saveSensitive'].sort());
  assert.doesNotMatch(JSON.stringify(value), /fictional-private/);
});

test('reload polls free reads and uses latest explicit saving choices', async () => {
  const h = harness(), calls = [];
  h.api.write('request-completed', {saveGuide: true, saveSensitive: true});
  h.api.write('request-inflight', {saveGuide: true, saveSensitive: true}, true);
  h.api.preferences({saveGuide: false, saveSensitive: false});
  const [key, oldMarker] = [...h.stored.entries()][0];
  h.stored.set(key, JSON.stringify({...JSON.parse(oldMarker), page: 'supplement'}));
  let count = 0;
  const result = await h.api.restore(async (url, body) => {
    calls.push({url, body});
    if (++count === 1) return {status: 'working'};
    return {status: 'resumed', requestId: 'request-inflight', response: {
      continuation: 'server-bound-state', guide: {preferences: {saveGuide: true, saveSensitive: true}},
    }, history: [{requestId:'request-completed',reply:'Earlier fictional reply'}]};
  }, async () => {});
  assert.equal(calls.length, 2);
  assert.ok(calls.every(call => call.url === '/api/conversation/resume'));
  assert.equal(calls[0].body.previousRequestId, 'request-completed');
  assert.equal(result.response.guide.preferences.saveGuide, false);
  assert.equal(result.response.guide.preferences.saveSensitive, false);
  assert.equal(result.history[0].reply, 'Earlier fictional reply');
  assert.equal(result.page, undefined);
  assert.equal(h.api.read().previousRequestId, undefined);
  assert.doesNotMatch([...h.stored.values()][0], /supplement|fictional reply/);
});

test('expired or superseded visits clear the pointer without issuing another turn', async () => {
  for (const status of ['expired','superseded']) {
    const h = harness();
    h.api.write('request-123456789', {});
    const result = await h.api.restore(async url => {
      assert.equal(url, '/api/conversation/resume');return {status};
    });
    assert.equal(result.status, status);
    assert.equal(h.api.read(), null);
  }
});

test('a failed read preserves the pointer for deliberate recovery', async () => {
  const h = harness();h.api.write('request-123456789', {});
  await assert.rejects(h.api.restore(async () => {throw Error('offline');}), /offline/);
  assert.equal(h.api.read().requestId, 'request-123456789');
});

test('unavailable browser storage does not break ordinary use', () => {
  const h = harness();
  h.sessionStorage.getItem = h.sessionStorage.setItem = () => {throw Error('blocked');};
  assert.equal(h.api.read(), null);
  assert.equal(h.api.write('request-123456789', {}), false);
  h.api.clear();
});
