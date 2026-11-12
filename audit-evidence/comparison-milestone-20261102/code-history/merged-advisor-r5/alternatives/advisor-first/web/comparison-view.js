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
  function render(host, comparison, {onReturn,document:doc=globalThis.document}={}) {
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
