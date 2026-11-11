'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {reportedDates, timelineFor, resumeRecap, comparisonMilestone} = require('../web/visit-artifacts.js');
const row = (id, value, status = 'reported', label = id) => ({id, value, status, label});
const state = (...reportedRows) => ({reportedRows});
const empty = state();

test('reported date picture preserves month-only precision and distinct end dates', () => {
  const result = state(row('S_AGE65', 'November (year not given)'),
    row('T04', 'after_coverage'), row('RC11', {jobEnd: 'unknown', coverageEnd: 'december'}));
  assert.deepEqual(reportedDates(result).map(r => [r.label, r.value]),
    [['65th birthday', 'November (year not given)'], ['Insurance end', 'december']]);
  assert.equal(timelineFor(null, result).length, 0);
  assert.equal(timelineFor(empty, result).length, 2);
});

test('dates exclude unknown, stale, deferred, derived and non-calendar preferences', () => {
  assert.deepEqual(reportedDates(state(row('S_AGE65', 'November', 'stale'),
    row('T04', 'soonest'), row('T04', '2027-01', 'derived'),
    row('RC11', {coverageEnd: 'unknown'}), row('S_AGE65', 'November', 'deferred'))), []);
});

test('explicit start month wins duplicate preference and remains preferred', () => {
  const result = state(row('T04', 'December 2027'),
    row('T04', '2027-01', 'reported', 'Preferred coverage start'));
  assert.deepEqual(reportedDates(result), [row('T04', '2027-01', 'reported', 'Preferred coverage start')]);
});

test('timeline appears for a changed report, not unchanged or failed turns', () => {
  const previous = state(row('S_AGE65', 'November'), row('RC11', {coverageEnd: 'december'}));
  const result = state(row('S_AGE65', 'November'), row('RC11', {coverageEnd: 'january'}));
  assert.equal(timelineFor(previous, previous).length, 0);
  assert.equal(timelineFor(previous, result).length, 2);
  assert.deepEqual(timelineFor(previous, {...result, generated: {status: 'unavailable'}}), []);
  const snapshot = timelineFor(previous, result);
  result.reportedRows[0].value = 'Changed later';
  assert.equal(snapshot[0].value, 'November');
});

test('saved recap names actual categories without echoing sensitive values or old conversation', () => {
  const text = resumeRecap(state(row('T03', '12345'), row('T06', 'Dr Sensitive'),
    row('T07', 'Private medication'), row('T05', 'old coverage', 'stale'), row('T04', 'unknown', 'unknown')));
  assert.equal(text, 'Your saved details about ZIP, doctors and prescriptions are open. We can review or update them as we go.');
  assert.doesNotMatch(text, /12345|Sensitive|Private|coverage|timing|verified/);
  assert.equal(resumeRecap(empty), 'Your saved details are open. You can review or update them as we go.');
});

test('comparison milestone includes explicit unknown and none but never stale or missing', () => {
  const partial = state(row('T03', '12345'), row('T06', 'none'));
  const resolved = state(...partial.reportedRows, row('T07', 'unknown', 'unknown'));
  assert.equal(comparisonMilestone(empty, partial), false);
  assert.equal(comparisonMilestone(partial, resolved), true);
  assert.equal(comparisonMilestone(resolved, resolved), false);
  assert.equal(comparisonMilestone(null, resolved), false);
  assert.equal(comparisonMilestone(empty, state(...partial.reportedRows, row('T07', 'later', 'deferred'))), true);
  assert.equal(comparisonMilestone(empty, state(...resolved.reportedRows, row('T07', 'old', 'stale'))), false);
  assert.equal(comparisonMilestone(partial, {...resolved, generated: {status: 'unavailable'}}), false);
  assert.equal(comparisonMilestone(empty, state(row('T03', '12345'), row('T06', 'Add doctors or hospitals'), row('T07', 'Add prescriptions'))), false);
  assert.equal(comparisonMilestone(empty, state(row('T03', '12345'), row('T06', []), row('T07', []))), false);
});
