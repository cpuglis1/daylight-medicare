/* View-only visit helpers. No inference, persistence, requests or eligibility gates. */
(function (root) {
  'use strict';
  const known = row => row && ['reported', 'derived'].includes(row.status);
  const rows = result => Array.isArray(result?.reportedRows) ? result.reportedRows : [];
  const copy = value => JSON.parse(JSON.stringify(value));
  const present = value => value !== undefined && value !== null && value !== '' &&
    (Array.isArray(value) ? value.length > 0 : typeof value === 'object' ? Object.keys(value).length > 0 : true) &&
    !['unknown', 'deferred', 'skipped', 'stale', 'unresolved'].includes(String(value).toLowerCase());
  // Recognize date-bearing reports without completing or interpreting a date.
  const date = value => typeof value === 'string' && present(value) &&
    /\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b|\b\d{4}-\d{2}(?:-\d{2})?\b/i.test(value);

  function reportedDates(result) {
    const output = [];
    const current = rows(result).filter(row => row.status === 'reported');
    const birthday = current.find(row => row.id === 'S_AGE65' && date(row.value));
    if (birthday) output.push({...copy(birthday), label: '65th birthday'});
    // A preference such as ASAP or after COBRA ends is never a calendar event.
    const start = current.find(row => row.id === 'T04' && row.label === 'Preferred coverage start' && date(row.value)) ||
      current.find(row => row.id === 'T04' && date(row.value));
    if (start) output.push({...copy(start), label: 'Preferred coverage start'});
    for (const row of current.filter(row => row.id === 'RC11')) {
      if (!row.value || typeof row.value !== 'object' || Array.isArray(row.value)) continue;
      for (const [key, label] of [['jobEnd', 'Job end'], ['coverageEnd', 'Insurance end']]) {
        if (date(row.value[key])) output.push({id: 'RC11', label, value: row.value[key], status: 'reported'});
      }
    }
    return output.filter((row, index, all) => all.findIndex(other =>
      other.id === row.id && other.label === row.label && other.value === row.value) === index);
  }

  function timelineFor(previous, result) {
    if (!previous || !result || result.generated?.status === 'unavailable') return [];
    const dates = reportedDates(result);
    return dates.length >= 2 && JSON.stringify(dates) !== JSON.stringify(reportedDates(previous)) ? dates : [];
  }

  function resumeRecap(result) {
    const ids = new Set(rows(result).filter(row => known(row) && present(row.value)).map(row => row.id));
    const categories = [
      [['T03'], 'ZIP'], [['T05', 'RC09'], 'current coverage'],
      [['T06', 'RC21'], 'doctors'], [['T07', 'RC22', 'RC23'], 'prescriptions'],
      [['S_AGE65', 'T04', 'RC11'], 'timing']
    ].filter(([keys]) => keys.some(id => ids.has(id))).map(([, label]) => label);
    if (!categories.length) return 'Your saved details are open. You can review or update them as we go.';
    const list = categories.length === 1 ? categories[0] : categories.slice(0, -1).join(', ') + ' and ' + categories.at(-1);
    return 'Your saved details about ' + list + ' are open. We can review or update them as we go.';
  }

  function comparisonMilestone(previous, result) {
    if (!previous || !result || result.generated?.status === 'unavailable') return false;
    const ready = value => ['T03', 'T06', 'T07'].every(id => {
      const reports = rows(value).filter(row => row.id === id);
      if (reports.some(row => row.status === 'stale')) return false;
      return reports.some(row => ['unknown', 'deferred', 'skipped'].includes(row.status) ||
        (known(row) && present(row.value) && !['list', 'yes', 'add doctors or hospitals', 'add prescriptions'].includes(String(row.value).toLowerCase())));
    });
    return !ready(previous) && ready(result);
  }

  const api = {reportedDates, timelineFor, resumeRecap, comparisonMilestone};
  root.DaylightVisitArtifacts = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
