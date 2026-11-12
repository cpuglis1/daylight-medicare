/* D87: optional deterministic preparation view. No source promotion or model call. */
(() => {
  'use strict';
  const priorityLabels = {doctors:'Doctors and hospitals',drugs:'Medicines',travel:'Care away from home',total_cost:'Total costs',bills:'Predictable bills',other:'Another priority'};
  const coverageLabels = {original:'Original Medicare',advantage:'Medicare Advantage',medigap:'Medicare supplement (Medigap)',drug:'Separate drug coverage',employer:'Insurance from a current job',retiree:'Retiree insurance',cobra:'COBRA',military:'Military-related coverage',medicaid:'Medicaid',none:'No current insurance reported',soonest:'As soon as possible',month:'A stated month',unknown:'I don’t know'};
  function text(value) {
    if (Array.isArray(value)) return value.map(text).join('; ');
    if (value && typeof value === 'object') return Object.entries(value).map(([key,item]) => key+': '+text(item)).join(' · ');
    return value == null ? 'Not established' : coverageLabels[value] || String(value);
  }
  function model(comparison) {
    const held = !comparison || comparison.status === 'unavailable' || comparison.status === 'stale_binding';
    const prepared = comparison?.case_preparation || {};
    return {
      title:'Your comparison, in preparation',
      notice: held ? 'This comparison needs a fresh check. Your reported information is preserved.' : 'Your reports can guide the research. Personal plan results still need accepted evidence and comparison methods.',
      baseline: held ? [] : (prepared.baseline_reports || []).map(row => ({label:row.label,value:text(row.value),state:'Reported, not verified'})),
      priorities: held ? [] : (comparison?.preference_context?.priority_topics || []).map(value => priorityLabels[value] || 'Another reported priority'),
      dimensions: held ? [] : (comparison.dimensions || []).map(dimension => {
        const findings = (comparison.findings || []).filter(finding => finding.dimension_id === dimension.dimension_id);
        const absent = findings.length && findings.every(finding => finding.result === 'not_applicable' && finding.reason_codes?.includes('REPORTED_REQUIREMENT_ABSENT'));
        return {label:dimension.label,state:absent ? 'You reported no items for this check' : 'Still needs evidence and review'};
      }),
      // Research units, values, inferred scores and the private decision trace
      // are deliberately absent from this consumer preparation model.
      outcomes:['Continue checking your options','Consider keeping current coverage','Defer the decision'],
      outcomesNote:'Keeping or deferring can be considered; their costs, timing and consequences still need checking.',
      research: !held && comparison?.research?.state === 'connected_research_only' ? 'Local research records are connected. They have not been released as personal plan findings.' : null,
    };
  }
  function renderPreview(host, preview, {onReturn,onScenario,doc}) {
    const el = (tag,value,cls) => {
      const node=doc.createElement(tag);
      if(value!==undefined)node.textContent=value;
      if(cls)node.className=cls;
      return node;
    };
    const control = (label, action) => {
      const node=el('button',label,'text-button');node.type='button';node.onclick=action;
      return node;
    };
    const money = amount => '$'+amount.replace(/\.00$/,'').replace(/\B(?=(\d{3})+(?!\d))/g,',');
    const section=el('section',undefined,'comparison-preparation comparison-preview');
    section.append(control('Return to my conversation',onReturn),
      el('h1','Compare plan costs'),
      el('p','2026 · Collier County, Florida · Local preview','small'),
      el('p','Two real plans selected to test cost rules, using fictional care.'));
    const stay=el('div',undefined,'comparison-preview-stay');
    stay.append(el('h2','One hospital admission'),el('p',preview.days+' covered inpatient days'));
    const next=preview.days===3 ? 4 : 3;
    const change=control('Use '+next+' covered days',() => onScenario(next));
    change.id='comparison-stay-change';stay.append(change);
    const results=el('dl',undefined,'comparison-preview-results');
    for(const plan of preview.plans) {
      const result=el('div');
      const held=plan.hospital_copay===null;
      const amount=el('dd',held ? 'Copay subtotal unresolved' : money(plan.hospital_copay)+' in facility copays');
      amount.append(el('small',held ?
        'Published rate '+money(plan.hospital_rate)+' a day for days 1–'+plan.hospital_band_end+'. '+plan.hospital_hold :
        money(plan.hospital_rate)+' per covered day × '+preview.days+'.'));
      result.append(el('dt',plan.short_name),amount);results.append(result);
    }
    stay.append(results);
    section.append(stay,el('p','Your doctors, medicine coverage and costs, and eligibility still need checking.','comparison-notice'));

    const grid=el('div',undefined,'comparison-preview-grid');
    for(const plan of preview.plans) {
      const column=el('section',undefined,'comparison-preview-plan');
      column.append(el('h2',plan.name),el('p',plan.id,'small'),el('p',plan.coverage));
      const list=el('dl');
      const row=(label,value,note) => {
        const dd=el('dd',value);
        if(note)dd.append(el('small',note));
        list.append(el('dt',label),dd);
      };
      row('Plan premium',money(plan.premium_monthly)+' a month',money(plan.premium_monthly)+' × 12 = '+money(plan.premium_12_months)+' for 2026');
      row('Four in-network primary care visits',money(plan.pcp_four_visits)+' in copays',
        money(plan.pcp_rate)+' per visit × 4. '+plan.pcp_deductible);
      row('Medical deductible',money(plan.medical_deductible)+' annually');
      row('Medical out-of-pocket maximum',plan.medical_maximum,'Published medical limits. Premiums and prescription drug costs are separate.');
      row('Specialist visit',plan.specialist,plan.specialist_access);
      row('Part D deductible',plan.drug_deductible,plan.drug_deductible_note);
      column.append(list);
      const sources=el('details');
      sources.append(el('summary','Published schedule and source records'),
        el('p',plan.inpatient_schedule,'comparison-preview-terms'));
      const locations=el('ul');
      for(const location of plan.source_locations)locations.append(el('li',location));
      sources.append(locations);column.append(sources);grid.append(column);
    }
    section.append(grid);
    const assumptions=el('details');
    assumptions.append(el('summary','What the examples assume'),
      el('p','Four ordinary covered office visits and one formally ordered acute admission in network. Hospital days exclude discharge day. Required authorization is assumed for the example. It assumes room under the medical out-of-pocket maximum and no assistance adjustment.'),
      el('p','Federal premiums, optional packages, tests, procedures, professional fees, drug spending, transfers and readmissions fall outside these examples.'));
    for(const source of preview.sources) {
      const link=el('a',source.label);link.href=source.url;link.target='_blank';link.rel='noopener noreferrer';
      const line=el('p');line.append(link);assumptions.append(line);
    }
    section.append(assumptions);host.append(section);
    return section;
  }
  function render(host, comparison, {onReturn,onScenario,document:doc=globalThis.document}={}) {
    const preview=comparison?.educational_preview;
    if(preview?.state==='local_fixture_only' && typeof onScenario==='function') {
      return renderPreview(host,preview,{onReturn,onScenario,doc});
    }
    const view = model(comparison);
    const el = (tag,value,cls) => {const node=doc.createElement(tag);if(value!==undefined)node.textContent=value;if(cls)node.className=cls;return node;};
    const section=el('section',undefined,'comparison-preparation');
    section.append(el('h1',view.title),el('p',view.notice,'comparison-notice'));
    if(view.baseline.length) {
      section.append(el('h2','Your reported starting point'));
      const list=el('dl');
      for(const row of view.baseline)list.append(el('dt',row.label),el('dd',row.value+' · '+row.state));
      section.append(list);
    } else section.append(el('p','Your current arrangement is not yet bound to a verified policy.'));
    if(view.priorities.length)section.append(el('h2','What you said matters'),el('p',view.priorities.join(' · ')),el('p','These priorities have no inferred weights or order.','small'));
    if(view.dimensions.length) {
      const table=el('table'),caption=el('caption','The same checks apply across the options');table.append(caption);
      const body=el('tbody');for(const row of view.dimensions){const tr=el('tr'),th=el('th',row.label);th.scope='row';tr.append(th,el('td',row.state));body.append(tr);}table.append(body);section.append(table);
    }
    if(view.research)section.append(el('p',view.research,'small'));
    section.append(el('h2','Your choices remain open'));
    const list=el('ul');for(const outcome of view.outcomes)list.append(el('li',outcome));section.append(list,el('p',view.outcomesNote,'small'));
    const back=el('button','Return to my conversation','text-button');back.type='button';back.onclick=onReturn;section.append(back);host.append(section);
    return section;
  }
  function acceptReview(state,response) {
    if(!response || response.continuation!==state.continuation || !response.comparison)throw Error('Your conversation changed. Review its latest state.');
    state.comparison=response.comparison;state.comparisonViewOpen=true;return state;
  }
  const api={model,render,acceptReview};
  if(typeof module!=='undefined' && module.exports)module.exports=api;
  else globalThis.DaylightComparison=api;
})();
