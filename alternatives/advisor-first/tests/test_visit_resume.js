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

test('browser storage keeps references and presentation without profile or chat', () => {
  const h = harness();
  h.api.write('request-123456789', {saveGuide: true, saveSensitive: false, health: 'fictional-private'});
  h.api.rememberPage('supplement');
  const value = JSON.parse([...h.stored.values()][0]);
  assert.deepEqual(Object.keys(value).sort(), ['expiresAt','page','requestId','saveGuide','saveSensitive'].sort());
  assert.equal(value.page, 'supplement');
  assert.doesNotMatch(JSON.stringify(value), /fictional-private/);
});

test('reload polls free reads and uses latest explicit saving choices', async () => {
  const h = harness(), calls = [];
  h.api.write('request-completed', {saveGuide: true, saveSensitive: true});
  h.api.write('request-inflight', {saveGuide: true, saveSensitive: true}, true);
  h.api.preferences({saveGuide: false, saveSensitive: false});
  let count = 0;
  const result = await h.api.restore(async (url, body) => {
    calls.push({url, body});
    if (++count === 1) return {status: 'working'};
    return {status: 'resumed', requestId: 'request-inflight', response: {
      continuation: 'server-bound-state', guide: {preferences: {saveGuide: true, saveSensitive: true}},
    }};
  }, async () => {});
  assert.equal(calls.length, 2);
  assert.ok(calls.every(call => call.url === '/api/conversation/resume'));
  assert.equal(calls[0].body.previousRequestId, 'request-completed');
  assert.equal(result.response.guide.preferences.saveGuide, false);
  assert.equal(result.response.guide.preferences.saveSensitive, false);
  assert.equal(h.api.read().previousRequestId, undefined);
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
