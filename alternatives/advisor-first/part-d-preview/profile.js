/* D146 conversation task. Served only by the isolated fictional preview. */
(() => {
  'use strict';
  const api = '/api/prescription-preview/profile';
  const dollars = new Intl.NumberFormat('en-US', {style:'currency', currency:'USD'});
  const fields = {
    rxcui:'medicine version', quantity:'fill quantity', unit:'quantity unit', days_supply:'days supply',
    fills:'fill dates', outlet_zip:'pharmacy ZIP', pharmacy:'exact pharmacy', channel:'pharmacy channel',
    period:'estimate period', assistance:'help with drug costs', prior_spending:'opening balances'
  };
  const hold = {
    scope_missing:'Finish the home ZIP, county and coverage year in the conversation.',
    scope_unsupported:'This check uses 2026 Collier County plans. Review the coverage year and location in the conversation.',
    no_reported_medicines:'Add the medicines in your fictional example to the conversation first.',
    profile_needs_confirmation:'Review the open or conflicting details in the conversation first.',
    multiple_outlets_unsupported:'This estimate supports one pharmacy for the medication list.',
    reported_fill_unsupported:'The fill quantity or days supply you reported is outside this check’s supported scope. Review it in the conversation.',
    quantity_limit_rule_unresolved:'This plan lists a quantity limit. The applicable limit needs further review.',
    criteria_unresolved:'This plan lists coverage requirements that need further review.',
    only_in_area_retail_average_available:'The published price averages cover in-area retail fills.',
    assistance_unresolved_or_unsupported:'This calculation needs a supported way to account for drug cost assistance.',
    prior_spending_unresolved_or_unsupported:'This calculation needs supported opening deductible and spending balances.',
    result_changed:'Your details or the evidence changed. Check the estimate again.'
  };
  const options = {
    unit:[['tablet','Tablets'],['capsule','Capsules'],['mL','Milliliters'],['other','Another unit']],
    days_supply:[['30','30 days'],['90','90 days']],
    channel:[['retail','Retail pickup'],['mail','Mail order']],
    assistance:[['none','No help with drug costs'],['reported_help','Yes, help with drug costs'],['unknown','I’m not sure']],
    prior_spending:[['confirmed_zero','Both balances are zero'],['nonzero','I have prior spending or a deductible credit'],['unknown','I’m not sure']]
  };
  let active = null, serial = 0, poll = 0, expiry = 0;

  function add(parent, tag, text, className) {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    parent.append(node);
    return node;
  }
  function button(parent, text, run, className = 'secondary') {
    const node = add(parent, 'button', text, className);
    node.type = 'button';
    node.addEventListener('click', run);
    return node;
  }
  function stopTimers() {
    window.clearTimeout(poll);
    window.clearTimeout(expiry);
  }
  function close() {
    stopTimers();
    serial++;
    active = null;
  }
  function fail(message) {
    if (!active) return;
    stopTimers();
    active.result = null;
    active.message = message;
    paint();
  }
  function evidenceMessage(code) {
    if (code === 'PILOT_EVIDENCE_STALE') return 'This estimate’s evidence is due for review. Your details are still here.';
    if (code?.startsWith('PILOT_SOURCE_')) return 'The estimate’s source evidence is unavailable. Your details are still here.';
    return hold[code] || 'This scenario still needs a supported cost check.';
  }
  async function call(action, fields = {}) {
    const current = active;
    const continuation = current.getHead();
    const id = ++serial;
    stopTimers();
    current.result = null;
    current.message = 'Checking the current details…';
    current.loading = true;
    paint();
    try {
      const result = await current.request(api, {action, continuation,
        offering_id:current.plan.id, ...(action === 'read' ? {} : {revision:current.revision}), ...fields});
      if (id !== serial || active !== current || continuation !== current.getHead()) return;
      current.revision = result.revision;
      current.loading = false;
      current.message = '';
      current.draft = null;
      if (result.editable) current.editable = result.editable;
      if (result.summary) current.summary = result.summary;
      else if (result.state === 'missing') current.summary = null;
      if (result.state === 'offline_average_candidate') {
        if (Date.now() >= Date.parse(result.expires_at)) return fail(evidenceMessage('PILOT_EVIDENCE_STALE'));
        current.result = result;
        current.step = 'ready';
        expiry = window.setTimeout(() => fail(evidenceMessage('PILOT_EVIDENCE_STALE')),
          Math.max(0, Date.parse(result.expires_at) - Date.now()));
        poll = window.setTimeout(revalidate, 5000);
      } else {
        current.step = result.state;
        current.question = result.question;
        if (result.state === 'held') current.message = evidenceMessage(result.hold);
      }
      paint();
      current.panel.querySelector('h2')?.focus({preventScroll:true});
    } catch (error) {
      if (id !== serial || active !== current) return;
      current.loading = false;
      if (error.code !== 422 || action !== 'answer') current.step = 'held';
      fail(error.code === 409 ? 'Your conversation changed. Reopen this check from the latest visit.' :
        'The prescription check is unavailable. Try again shortly.');
    }
  }
  async function revalidate() {
    const current = active, result = current?.result, id = serial;
    if (!result || document.hidden || current.checking) return;
    current.checking = true;
    try {
      if (current.head !== current.getHead() || Date.now() >= Date.parse(result.expires_at))
        return fail('This result expired or your details changed. Run the check again.');
      const value = await current.request(api, {action:'validate', continuation:current.head,
        offering_id:current.plan.id, revision:current.revision, receipt:result.receipt});
      if (active !== current || serial !== id || current.result !== result) return;
      if (value.state !== 'current') return fail(evidenceMessage(value.hold));
      current.panel.hidden = false;
      window.clearTimeout(poll);
      poll = window.setTimeout(revalidate, 5000);
    } catch {
      if (active === current && serial === id && current.result === result)
        fail('This result could not be verified. Reopen the check from your conversation.');
    } finally {
      current.checking = false;
    }
  }
  function prompt(question) {
    const medicine = question.label ? ' for ' + question.label : '';
    return {
      rxcui:'Which exact medicine matches your report' + medicine + '?',
      quantity:'How many units are in each fill' + medicine + '?',
      unit:'What does the fill quantity count' + medicine + '?',
      days_supply:'How many days does a fill last' + medicine + '?',
      fills:'When do you plan to fill this medicine' + medicine + '?',
      outlet_zip:'What is the ZIP code of the pharmacy you want to check?',
      pharmacy:'Which exact pharmacy should we use?',
      channel:'How will you get these prescriptions?',
      period:'What is the first month of the 2026 estimate?',
      assistance:'Do you have help paying for these prescriptions?',
      prior_spending:'What are your opening drug spending and deductible credits?'
    }[question.field];
  }
  function input(form, question) {
    const field = question.field;
    const months = field === 'period' ? Array.from({length:12}, (_, index) => {
      const value = '2026-' + String(index + 1).padStart(2, '0');
      return [value, new Intl.DateTimeFormat('en-US', {month:'long', timeZone:'UTC'}).format(new Date(value + '-01'))];
    }) : null;
    const list = months || options[field] || (question.choices.length ? question.choices.map(x => [x.value, x.label]) : null);
    const control = add(form, list ? 'select' : field === 'fills' ? 'textarea' : 'input');
    control.id = 'prescription-preview-answer';
    control.required = true;
    if (list) {
      control.append(new Option('Choose an answer', ''));
      for (const [value, label] of list) control.append(new Option(label, value));
    } else if (field === 'quantity') {
      control.type = 'number'; control.min = '1'; control.max = '10000'; control.step = '1';
    } else if (field === 'outlet_zip') {
      control.inputMode = 'numeric'; control.pattern = '[0-9]{5}'; control.maxLength = 5;
    } else if (field === 'fills') {
      control.rows = 3;
    }
    return control;
  }
  function paint() {
    const current = active;
    if (!current) return;
    const panel = current.panel;
    panel.hidden = false;
    panel.replaceChildren();
    const heading = add(panel, 'h2', 'Prescription estimate preview');
    heading.tabIndex = -1;
    if (current.plan) add(panel, 'p', current.plan.name);
    add(panel, 'p', '2026 Collier research with fictional details. Estimates use published retail averages. Store prices can differ.', 'plans-help');
    const question = current.step === 'missing' && current.question;
    const hasCandidates = !question || !['rxcui','pharmacy'].includes(question.field) || question.choices.length;
    if (!current.plan && current.plans?.length) {
      const form = add(panel, 'form', null, 'plans-field');
      const label = add(form, 'label', 'Which Part D plan would you like to check?');
      label.htmlFor = 'prescription-preview-plan';
      const choices = add(form, 'select');
      choices.id = label.htmlFor;
      choices.required = true;
      choices.append(new Option('Choose a plan', ''));
      for (const plan of current.plans) choices.append(new Option(plan.name, plan.id));
      const submit = add(form, 'button', 'Continue', 'primary');
      submit.type = 'submit';
      form.addEventListener('submit', event => {
        event.preventDefault();
        const plan = current.plans.find(item => item.id === choices.value);
        if (!plan) return;
        current.plan = plan;
        void call('read');
      });
    } else if (question && hasCandidates && !current.loading) {
      const form = add(panel, 'form', null, 'plans-field');
      const label = add(form, 'label', prompt(question));
      label.htmlFor = 'prescription-preview-answer';
      if (question.field === 'fills') add(form, 'p', 'Enter one date and order per line, for example 2026-01-01, 1. Use a different order for medicines filled on the same day.', 'plans-help');
      if (question.field === 'period') add(form, 'p', 'The estimate runs from the first day of that month through December 31.', 'plans-help');
      if (question.reported) add(form, 'p', 'You reported ' + question.reported + '.', 'plans-help');
      const control = input(form, question);
      if (current.draft?.field === question.field) control.value = current.draft.value;
      const submit = add(form, 'button', 'Continue', 'primary');
      submit.type = 'submit';
      form.addEventListener('submit', event => {
        event.preventDefault();
        let value = control.value;
        current.draft = {field:question.field, value};
        if (['quantity','days_supply'].includes(question.field)) value = Number(value);
        if (question.field === 'period') value += '-01';
        if (question.field === 'fills') {
          const lines = value.trim().split(/\r?\n/).map(line => /^\s*(2026-\d\d-\d\d)\s*,\s*(\d{1,2})\s*$/.exec(line));
          if (lines.some(x => !x)) {
            const message = panel.querySelector('[role=status]');
            message.textContent = 'Enter a 2026 date and a fill order on each line.';
            control.focus();
            return;
          }
          value = lines.map(x => ({date:x[1], order:Number(x[2])}));
        }
        void call('answer', {value});
      });
    } else if (current.step === 'ready' && !current.result && !current.loading) {
      button(panel, 'Continue', () => call('estimate'), 'primary');
    } else if (!hasCandidates && !current.loading) {
      add(panel, 'p', question.field === 'rxcui' ?
        'No exact medicine matches these details. Check the name, strength and form in the conversation.' :
        'No exact outlet matches this ZIP. Check the outlet ZIP and try again.');
    }
    button(panel, 'Back to conversation', current.back);
    if (current.plan && !current.loading && (current.step === 'held' || !hasCandidates))
      button(panel, 'Check current details', () => call('read'));
    if (current.message) add(panel, 'p', current.message, 'plans-help').setAttribute('role','status');
    else add(panel, 'p', '').setAttribute('role','status');
    if (current.result) {
      const result = current.result;
      add(panel, 'h3', result.period_kind === 'full_year' ? 'Full-year estimate' : 'Remaining-year estimate');
      const values = add(panel, 'dl', null, 'plan-amounts');
      for (const [label, cents] of [['Plan premiums',result.plan_premium_cents],
        ['Drug spending',result.drug_spending_cents],['Premiums and drugs',result.plan_premium_plus_drugs_cents]]) {
        const box = add(values, 'div', null, 'amount');
        add(box, 'dt', label, 'amount-label');
        add(box, 'dd', dollars.format(cents / 100), 'amount-value');
      }
    }
    if (current.summary) {
      const summary = add(panel, 'details');
      add(summary, 'summary', 'Review the details used');
      add(summary, 'p', current.summary.pharmacy + ' · ' +
        (current.summary.channel === 'retail' ? 'Retail pickup' : 'Mail order'));
      add(summary, 'p', 'Estimate starts ' + current.summary.period +
        '. ' + (current.summary.assistance === 'none' ? 'No assistance reported.' : 'Assistance needs review.') +
        ' ' + (current.summary.prior_spending === 'confirmed_zero' ? 'Zero opening balances.' : 'Opening balances need review.'));
      const list = add(summary, 'ul');
      for (const med of current.summary.medicines)
        add(list, 'li', `${med.name} · ${med.quantity} ${med.unit} per fill · ${med.days_supply} days · ${med.fill_count} planned fills`);
    }
    if (current.editable.length && !current.loading) {
      const edits = add(panel, 'details');
      add(edits, 'summary', 'Edit estimate details');
      for (const {field,item,medicine} of current.editable)
        button(edits, 'Edit ' + fields[field] + (medicine ? ' for ' + medicine : ''),
          () => call('edit', {field,item}));
    }
    const help = add(panel, 'details');
    add(help, 'summary', 'Help with this check');
    add(help, 'p', 'Use the conversation to correct medicines you reported or change the coverage year. Fill details and results are for this visit.');
  }

  async function choosePlan(current, scope) {
    paint();
    try {
      const response = await current.request('/api/plans/part-d', scope);
      if (active !== current || current.head !== current.getHead()) return;
      current.plans = response.plans || [];
      current.message = current.plans.length ? '' : 'Part D plan information is unavailable. Return to the conversation and check your details.';
    } catch {
      if (active !== current) return;
      current.message = 'Part D plan information is unavailable. Return to the conversation and try again.';
    }
    current.loading = false;
    paint();
    current.panel.querySelector('h2')?.focus();
  }

  window.DaylightPrescriptionPreview = Object.freeze({
    open(plan, request, getHead, back, scope) {
      close();
      active = {plan, request, getHead, back, head:getHead(), panel:document.createElement('section'),
        step:'', editable:[], loading:true};
      active.panel.className = 'task-form';
      if (plan) void call('read');
      else {
        active.message = 'Finding the 2026 Part D plans for this visit…';
        void choosePlan(active, scope);
      }
    },
    render(host) {
      if (!active) return false;
      if (active.head !== active.getHead()) {close();return false;}
      host.append(active.panel);
      return true;
    },
    close
  });
  document.addEventListener('visibilitychange', () => {
    if (!active?.result) return;
    active.panel.hidden = true;
    if (!document.hidden) void revalidate();
  });
  window.addEventListener('focus', () => {if (active?.result) void revalidate();});
  window.addEventListener('pagehide', () => {active?.panel.replaceChildren();close();});
})();
