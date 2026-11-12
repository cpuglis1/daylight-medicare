(() => {
  'use strict';

  function createFlow(root, {onView, onExit, initialName = ''} = {}) {
    const element = id => root.querySelector('#' + id);
    const form = element('doctor-form');
    const heading = element('doctor-question');
    const fields = element('doctor-fields');
    const options = element('doctor-options');
    const forward = element('doctor-continue');
    const back = element('doctor-back');
    const state = {
      step: 'name', history: [], name: initialName, city: '', practice: '', region: 'regional',
      candidates: [], offices: [], doctor: null, office: null, coverage: '', date: '', result: null
    };
    let csrf;
    let catalog;
    let revision;
    let busy = false;
    let closed = false;
    let nextCandidate = null;
    let nextOffice = null;
    const apiPrefix = location.pathname === '/d146/' ? '/d146' : '';

    function node(tag, text, className) {
      const item = document.createElement(tag);
      if (text) item.textContent = text;
      if (className) item.className = className;
      return item;
    }

    function notice(id, text = '') {
      const item = element(id);
      item.textContent = text;
      item.hidden = !text;
    }

    async function session() {
      const response = await fetch(apiPrefix + '/api/guest/session', {cache: 'no-store'});
      if (!response.ok) throw new Error('The demo could not start a visit. Try again.');
      csrf = (await response.json()).csrf;
    }

    async function post(route, value) {
      if (!csrf) await session();
      const response = await fetch(apiPrefix + route, {
        method: 'POST', cache: 'no-store',
        headers: {'Content-Type': 'application/json', 'X-Daylight-CSRF': csrf},
        body: JSON.stringify(value)
      });
      if (response.status === 401 || response.status === 403) {
        csrf = undefined;
        revision = undefined;
        throw new Error('The visit expired. Try again to start a new visit.');
      }
      if (response.status === 409) {
        revision = undefined;
        throw new Error('This check changed or expired. Review the details and try again.');
      }
      if (response.status === 429) throw new Error('The lookup is busy. Try again in a moment.');
      if (response.status >= 500) throw new Error('The 2026 records are unavailable right now. Try again later.');
      const data = await response.json();
      if (!response.ok) {
        if (data.error === 'DOCTOR_SEARCH_NEEDS_NAME_OR_DETAIL') {
          throw new Error('Enter a last name, or add a city or practice.');
        }
        throw new Error('Daylight couldn’t complete that check. Review the details and try again.');
      }
      return data;
    }

    function doctorApi(operation, body) {
      return post('/api/pilot-doctors/' + operation, body);
    }

    function setBusy(value) {
      busy = value;
      form.setAttribute('aria-busy', String(value));
      for (const control of form.elements) {
        control.disabled = value;
      }
      updateChat();
    }

    async function run(message, action) {
      if (busy || closed) return;
      notice('doctor-error');
      notice('doctor-status', message);
      setBusy(true);
      try {
        await action();
      } catch (error) {
        notice('doctor-error', error.message === 'Failed to fetch'
          ? 'Daylight couldn’t reach the local demo. Try again.' : error.message);
      } finally {
        setBusy(false);
        notice('doctor-status');
      }
    }

    function action(label, callback) {
      const button = node('button', label, 'text-button');
      button.type = 'button';
      button.addEventListener('click', callback);
      options.append(button);
    }

    function question(title, primary = 'Continue') {
      heading.textContent = title;
      forward.textContent = primary;
      forward.hidden = false;
    }

    function field(label, input) {
      const item = node('label', label, 'doctor-field');
      item.append(input);
      fields.append(item);
    }

    function textField(label, key, required = false) {
      const input = node('input');
      input.type = 'text';
      input.name = key;
      input.value = state[key];
      input.required = required;
      input.maxLength = 140;
      input.autocomplete = 'off';
      input.addEventListener('input', () => {
        if (key === 'name') setName(input.value);
        else state[key] = input.value;
      });
      field(label, input);
    }

    function setName(value) {
      if (state.name.trim() !== value.trim()) {
        state.city = '';
        state.practice = '';
        state.region = 'regional';
      }
      state.name = value;
    }

    function updateChat(focus = false) {
      if (!closed) onView?.({composer: state.step === 'name', busy, name: state.name, focus});
    }

    function choices(group, rows, selected) {
      const list = node('fieldset');
      list.setAttribute('aria-label', group);
      for (const row of rows) {
        const label = node('label', '', 'doctor-choice');
        const input = node('input');
        input.type = 'radio';
        input.name = group;
        input.value = row.id;
        input.required = true;
        input.checked = row.id === selected;
        const body = node('span');
        body.append(node('strong', row.label));
        for (const detail of row.details) body.append(node('small', detail));
        label.append(input, body);
        list.append(label);
      }
      fields.append(list);
    }

    function address(office) {
      const postal = office.postal?.replace(/^(\d{5})(\d{4})$/, '$1-$2');
      return [office.street, office.city, [office.state, postal].filter(Boolean).join(' ')]
        .filter(Boolean).join(', ');
    }

    function sourceLabel(source) {
      return ({
        federal_provider_rows: 'Federal clinician records',
        ma_aetna_query: 'Aetna directory',
        ma_aetna_additive_query: 'Aetna directory',
        ma_wellcare_listings: 'Wellcare directory',
        ma_humana_listings: 'Humana directory',
        provider_entities: 'Carrier directory'
      })[source?.dataset] || 'Retained directory';
    }

    function doctorChoices() {
      const seen = new Set();
      const rows = [];
      for (const doctor of state.candidates) {
        const office = doctor.office_previews[0];
        // Repeated publisher rows can stand for one display choice only when the
        // evidence lookup already recognizes this exact NPI and full office.
        const key = doctor.source_npis.length === 1 && doctor.site_count === 1 && office
          ? JSON.stringify([doctor.source_npis[0], office.street, office.city, office.state, office.postal])
          : doctor.candidate_id;
        if (seen.has(key)) continue;
        seen.add(key);
        rows.push({id: doctor.candidate_id, label: doctor.label,
          details: [...new Set(doctor.office_previews.map(address))], doctor});
      }
      const counts = new Map();
      for (const row of rows) {
        const key = JSON.stringify([row.label, row.details]);
        counts.set(key, (counts.get(key) || 0) + 1);
      }
      for (const row of rows) {
        if (counts.get(JSON.stringify([row.label, row.details])) > 1) {
          const source = row.doctor.source;
          row.details.push(sourceLabel(source) + ' · Record ' + (source.ordinal ?? source.key.source_row));
        }
      }
      return rows;
    }

    function selectionSummary(includeCoverage = false) {
      const details = node('dl', '', 'doctor-selection');
      const rows = [['Doctor', state.doctor.label], ['Office', address(state.office.address)]];
      if (includeCoverage) rows.push(['Coverage', coverageName()], ['Date', formatDate(state.date)]);
      for (const [label, value] of rows) {
        const row = node('div');
        row.append(node('dt', label), node('dd', value));
        details.append(row);
      }
      fields.append(details);
    }

    function go(step) {
      state.history.push(state.step);
      state.step = step;
      render();
    }

    function render(focus = true) {
      fields.replaceChildren();
      options.replaceChildren();
      notice('doctor-error');
      back.hidden = state.history.length === 0;
      switch (state.step) {
        case 'name':
          question('What’s your doctor’s name?');
          if (onView) forward.hidden = true;
          else textField('Doctor’s name', 'name', true);
          break;
        case 'refine':
          question('What city or practice is your doctor in?');
          fields.append(node('p', state.candidates.length
            ? 'A city or practice can help narrow down the matches for ' + state.name.trim() + '.'
            : 'We couldn’t find a doctor with a listed office under that name. A city or practice may help.'));
          textField('City', 'city');
          textField('Practice name', 'practice');
          if (state.candidates.length || nextCandidate !== null) {
            action('See matches without more details', () => go('doctor'));
          } else if (state.region === 'regional') {
            action('Search all loaded areas', () => run('Searching all loaded areas…', async () => {
              await search(0, 'all_retained');
              go('doctor');
            }));
          }
          break;
        case 'doctor':
          question(state.candidates.length ? 'Which doctor is yours?' : 'No doctor found in these records');
          if (state.candidates.length) {
            choices('doctor', doctorChoices(), state.doctor?.candidate_id);
          } else {
            forward.hidden = true;
            fields.append(node('p', 'You can edit the name, add a city or practice, or search all loaded areas.'));
          }
          if (nextCandidate !== null) action('Show more matches', () => run('Looking for more matches…',
            async () => { await search(nextCandidate); render(); }));
          action('Add or edit city or practice', () => go('refine'));
          action('Edit doctor’s name', () => editName());
          if (state.region === 'regional') {
            action('Search all loaded areas', () => run('Searching all loaded areas…', async () => {
              await search(0, 'all_retained');
              render();
            }));
          }
          break;
        case 'office':
          question('Which office do you go to?');
          fields.append(node('p', state.doctor.label));
          choices('office', state.offices.map(office => ({
            id: office.site_id, label: address(office.address),
            details: [...office.organizations.map(org => org.label), ...office.specialties]
          })), state.office?.site_id);
          if (nextOffice !== null) action('Show more offices', () => run('Loading offices…', async () => {
            await loadOffices(state.doctor, nextOffice);
            render();
          }));
          action('I don’t see my office', () => go('missing_office'));
          break;
        case 'missing_office':
          question('The office is still unconfirmed');
          forward.hidden = true;
          fields.append(node('p', 'Daylight needs the exact office to check this doctor against a plan.'));
          action('Edit doctor’s name', () => editName());
          break;
        case 'plan':
          question('Which coverage should we check?', 'Check this office');
          selectionSummary();
          const plan = node('select');
          plan.name = 'coverage';
          plan.required = true;
          plan.append(new Option('Choose coverage', ''), new Option('Original Medicare', 'original_medicare'));
          const advantage = node('optgroup');
          advantage.label = '2026 Collier Medicare Advantage plans';
          for (const entry of catalog) advantage.append(new Option(entry.name + ' · ' + entry.id.slice(5), entry.id));
          plan.append(advantage);
          plan.value = state.coverage;
          plan.addEventListener('change', () => { state.coverage = plan.value; });
          field('Coverage', plan);
          const date = node('input');
          date.type = 'date';
          date.name = 'date';
          date.required = true;
          date.min = '2026-01-01';
          date.max = '2026-12-31';
          date.value = state.date;
          date.addEventListener('change', () => { state.date = date.value; });
          field('Date you want to check in 2026', date);
          break;
        case 'result':
          renderEvidence();
          action('Check another doctor', () => editName(true));
          break;
      }
      if (onExit) action('Back to conversation', onExit);
      if (busy) setBusy(true);
      updateChat(focus);
      if (focus && !(onView && state.step === 'name')) heading.focus({preventScroll:!!onView});
    }

    async function search(offset = 0, region = state.region) {
      const query = {name: state.name.trim(), year: 2026, region, offset};
      if (state.city.trim()) query.location = state.city.trim();
      if (state.practice.trim()) query.practice = state.practice.trim();
      const result = await doctorApi('search', query);
      const found = result.candidates.filter(candidate => candidate.kind === 'clinician' && candidate.site_count);
      state.region = region;
      state.candidates = offset ? [...state.candidates, ...found] : found;
      nextCandidate = result.next_offset;
      if (!offset) {
        state.doctor = null;
        state.office = null;
      }
    }

    async function loadOffices(doctor, offset = 0) {
      const result = await doctorApi('sites', {candidate_id: doctor.candidate_id, offset});
      const matching = new Set(doctor.matching_site_ids);
      state.offices = [...(offset ? state.offices : []), ...result.sites]
        .sort((a, b) => Number(matching.has(b.site_id)) - Number(matching.has(a.site_id)));
      nextOffice = result.next_offset;
    }

    function coverageName() {
      return state.coverage === 'original_medicare' ? 'Original Medicare' :
        catalog.find(plan => plan.id === state.coverage)?.name;
    }

    function formatDate(value) {
      return new Intl.DateTimeFormat('en-US', {dateStyle: 'medium', timeZone: 'UTC'}).format(new Date(value));
    }

    async function clearSelection() {
      if (!revision) return;
      const previous = revision;
      revision = undefined;
      await doctorApi('selection', {expected_revision: previous, selection: null, confirmed: false});
    }

    function editName(reset = false) {
      const goToName = () => {
        if (reset) Object.assign(state, {name: '', coverage: '', date: ''});
        Object.assign(state, {step: 'name', history: [], city: '', practice: '', region: 'regional',
          candidates: [], offices: [], doctor: null, office: null, result: null});
        nextCandidate = null;
        nextOffice = null;
        render();
      };
      if (revision) {
        run('Clearing the previous check…', async () => { goToName(); await clearSelection(); });
      } else if (!busy) goToName();
    }

    const messages = {
      confirmed: ['Network participation confirmed', 'The dated confirmation applies to this doctor, office, plan and date.'],
      dated_listing: ['Listed in the retained records', 'The directory lists this doctor at this office for this plan. Confirm participation for your intended date if keeping this doctor matters to you.'],
      conflict: ['The records disagree', 'Daylight couldn’t resolve which record applies to this doctor and office.'],
      stale: ['The records are out of date', 'Daylight needs newer evidence to check this doctor and office.'],
      unknown: ['Network participation is unknown', 'Daylight couldn’t verify this doctor and office for the selected plan and date.']
    };

    function renderEvidence() {
      const result = state.result;
      const original = state.coverage === 'original_medicare';
      let [title, description] = messages[result.state] || messages.unknown;
      if (original && result.state === 'dated_listing') {
        title = 'Original Medicare records found';
        description = 'The dated records below report separate facts about the doctor and office.';
      } else if (original && result.state === 'unknown') {
        title = 'Original Medicare status is unresolved';
        description = 'Daylight couldn’t establish which Original Medicare records apply to this doctor and date.';
      } else if (result.state === 'confirmed' && result.membership === 'out_of_network') {
        title = 'Confirmed out of network';
      }
      question(title);
      forward.hidden = true;
      selectionSummary(true);
      fields.append(node('p', description));
      if (original) renderOriginal(result);
      else if (result.observations?.length) {
        const records = [...new Set(result.observations.filter(item => item.observed_on).map(item =>
          (item.kind === 'targeted_confirmation' ? 'Targeted confirmation' : sourceLabel(item.source)) +
          ' · ' + formatDate(item.observed_on)))];
        if (records.length) {
          const list = node('ul', '', 'doctor-evidence');
          list.setAttribute('aria-label', 'Evidence sources and dates');
          for (const record of records) list.append(node('li', record));
          fields.append(list);
        }
      }
      if (result.held_plan_joins?.length) {
        fields.append(node('p', 'Some network records could not be linked to this exact plan.'));
      }
      fields.append(node('p', 'Appointment availability was not checked.'));
      back.textContent = 'Edit coverage or date';
    }

    function renderOriginal(result) {
      if (result.state === 'stale') return;
      const enrollment = result.enrollment || [];
      const assignment = result.assignment || [];
      const optout = result.opt_out || [];
      const assignmentText = {
        published_accepts_assignment: 'accepts assignment',
        published_may_accept_assignment: 'may accept assignment',
        unknown: 'assignment unknown'
      };
      const list = node('ul', '', 'doctor-evidence');
      list.append(node('li', enrollment.length
        ? 'Enrollment: ' + [...new Set(enrollment.map(row =>
          (row.published_state === 'published_approved_billing_enrollment_in_extract'
            ? 'approved billing enrollment'
            : row.published_state === 'published_ordering_referring_only_enrollment'
              ? 'ordering and referring only' : 'enrollment type unresolved') + ' in the ' +
          formatDate(row.published_on) + ' record'))].join('; ') + '.'
        : 'Enrollment: no matching record found.'));
      list.append(node('li', assignment.length
        ? 'Assignment at this office: ' + [...new Set(assignment.map(row =>
          'individual ' + assignmentText[row.individual_state] + ', group ' +
          assignmentText[row.group_state] + ' as of ' + formatDate(row.published_on)))].join('; ') + '.'
        : 'Assignment at this office: unknown.'));
      const spansDate = optout.some(row => row.interval_state === 'published_interval_contains_date');
      const boundary = optout.some(row => row.interval_state === 'boundary_review');
      list.append(node('li', spansDate ? 'Opt-out: a published interval covers the selected date.'
        : boundary ? 'Opt-out: the selected date is on a published boundary and needs verification.'
          : 'Opt-out: no matching interval was verified for the selected date.'));
      fields.append(list);
    }

    async function checkPlan() {
      const original = state.coverage === 'original_medicare';
      const selection = {candidate_id: state.doctor.candidate_id, site_id: state.office.site_id,
        offering_id: original ? null : state.coverage, intended_date: state.date,
        route: original ? 'original_medicare' : 'medicare_advantage'};
      const current = await doctorApi('visit', {});
      if (closed) return;
      const confirmed = await doctorApi('selection', {expected_revision: current.revision, selection, confirmed: true});
      revision = confirmed.revision;
      if (closed) {
        await clearSelection();
        return;
      }
      try {
        state.result = await doctorApi('evidence', {revision});
      } catch (error) {
        try { await clearSelection(); } catch { /* The failed result stays hidden. */ }
        throw error;
      }
      if (!closed) go('result');
    }

    back.addEventListener('click', () => run('', async () => {
      const previous = state.step;
      state.step = state.history.pop();
      if (previous === 'result') {
        state.result = null;
        back.textContent = 'Back';
      }
      render();
      if (previous === 'result') await clearSelection();
    }));

    form.addEventListener('submit', event => {
      event.preventDefault();
      if (busy) return;
      const values = new FormData(form);
      if (state.step === 'name' || state.step === 'refine') {
        submitSearch();
      } else if (state.step === 'doctor' && values.get('doctor')) {
        run('Loading this doctor’s offices…', async () => {
          const doctor = state.candidates.find(item => item.candidate_id === values.get('doctor'));
          await loadOffices(doctor);
          if (state.doctor?.candidate_id !== doctor.candidate_id) state.office = null;
          state.doctor = doctor;
          go('office');
        });
      } else if (state.step === 'office' && values.get('office')) {
        run('Loading coverage options…', async () => {
          const plans = catalog || (await post('/api/plans/catalog', {})).plans;
          catalog = [...plans].sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
          state.office = state.offices.find(item => item.site_id === values.get('office'));
          go('plan');
        });
      } else if (state.step === 'plan') {
        state.coverage = values.get('coverage');
        state.date = values.get('date');
        run('Checking the 2026 records…', checkPlan);
      }
    });

    function submitSearch() {
      return run('Searching for your doctor…', async () => {
        if (!state.name.trim()) throw new Error('Enter your doctor’s name.');
        await search();
        const unclear = state.candidates.length !== 1 || nextCandidate !== null;
        if (!closed) go(state.step === 'name' && unclear ? 'refine' : 'doctor');
      });
    }

    render(false);
    return {root, setName, submitSearch, sync: updateChat, close() {
      closed = true;
      void clearSelection().catch(() => {});
    }};
  }

  const standalone = document.querySelector('.doctor-demo .doctor-flow');
  if (standalone) {
    createFlow(standalone);
    window.addEventListener('pageshow', event => { if (event.persisted) location.reload(); });
  }

  const template = document.getElementById('daylight-doctor-template');
  if (!template) return;
  let active;
  window.DaylightDoctorCheck = Object.freeze({
    open(options) {
      const root = document.createElement('section');
      root.className = 'doctor-flow doctor-inline';
      root.append(template.content.cloneNode(true));
      active = createFlow(root, options);
    },
    render(host) {
      if (!active) return false;
      host.append(active.root);
      active.sync();
      return true;
    },
    get active() { return !!active; },
    setName(value) { active?.setName(value); },
    submitName() { return active?.submitSearch(); },
    close() {
      active?.close();
      active = undefined;
    }
  });

  window.addEventListener('pageshow', event => {
    if (event.persisted && active) location.reload();
  });
})();
