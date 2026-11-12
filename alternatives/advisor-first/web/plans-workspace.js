/* Transport only: backend owns profile, facts, holds and recommendation results. */
(() => {
  'use strict';
  let api, activate, ask, data, token=null, selected=null, field=null, mode='all', query='', opened=false;
  const compared=new Set(), $=id=>document.getElementById(id);
  function el(tag,text,cls) {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
  function button(label,run) {const b=el('button',label,'text-button');b.type='button';b.onclick=run;return b;}
  function status(text) {$('plans-status').textContent=text;}
  function invalidate(text) {
    data=null;const host=$('plans-panel');host.replaceChildren(el('h1','Refresh your Plans view'));
    const notice=el('p',text,'plans-hold');notice.id='plans-status';notice.setAttribute('role','status');
    host.append(notice,button('Back to conversation',close),button('Retry current review',refresh),button('Browse dated listings',()=>open()));
  }
  async function refresh() {
    try {data=await api(token?'/api/plans/workspace':'/api/plans/catalog',token?{token}:{});render();}
    catch(e){invalidate(e.message+' Return to the conversation to review your current information.');}
  }
  function chat(open=true) {
    $('workspace').classList.toggle('chat-closed',!open);
    if(open)$('message').focus();
    else $('plans-chat-toggle')?.focus();
  }
  function stage(plan,key) {
    selected=plan.id;field=key;
    ask(`Help me understand ${plan.fields[key].label.toLowerCase()} for ${plan.name}. What is known, and what still needs checking?`);
    chat();render();
  }
  function render() {
    if(!data)return;
    const host=$('plans-panel');host.replaceChildren();
    const actions=el('div',undefined,'plans-actions');
    const toggle=button('Open / close chat',()=>chat($('workspace').classList.contains('chat-closed')));toggle.id='plans-chat-toggle';
    actions.append(button('Back to conversation',close),toggle,button('Refresh plans',refresh));
    host.append(actions,el('h1','Explore your plans'),el('p',data.notice));
    const notice=el('p','', 'plans-hold');notice.id='plans-status';notice.setAttribute('role','status');host.append(notice);
    if(data.profile_binding)host.append(el('p',`Your reviewed profile requests ${data.profile_binding.scope.year}. ${data.recommendation.scope_supported?'This catalog matches that year and county.':'This retained catalog does not match your requested scope.'}`));
    else host.append(el('p','Browse the retained listings here. Review your information in the conversation before a personal comparison.'));
    const rec=data.recommendation;
    const focused=data.plans.find(p=>p.id===selected);
    $('plans-chat-context').textContent=(focused?`About ${focused.name}${field?' · '+focused.fields[field].label:''}. `:'About the plans in view. ')+
      'Send shares this plan context with the selected AI provider. Viewing and selecting plans makes no AI call.';
    host.append(el('h2',rec.state==='supported'?`${rec.top_three.length} plans to consider`:'Recommendations need more evidence'));
    host.append(el('p',rec.state==='supported'?'Ordered by your confirmed priorities. Equal results use plan ID order for display.':
      rec.reason_codes.map(x=>x.replaceAll('_',' ').toLowerCase()).join(' · '),'plans-hold'));
    const costs=data.reference_comparison;
    if(costs?.state==='available')host.append(el('p',`${costs.ordered_ids.length} plans can be ordered by these published costs; ${costs.unranked_ids.length} have a held comparison amount. ${costs.limitation}`,'plans-small'));
    if(token){
      const priorities=el('div',undefined,'plans-actions'),label=el('label','Comparison priority order '),select=el('select');select.id='plan-priorities';
      for(const [value,text] of [['','Choose an order'],['monthly_plan_premium,in_network_medical_limit','Plan premium, then medical limit'],['in_network_medical_limit,monthly_plan_premium','Medical limit, then plan premium']]) {const o=el('option',text);o.value=value;select.append(o);}
      select.value=rec.priority_order.join(',');label.append(select);
      priorities.append(label,button('Confirm priority order',async()=>{if(!select.value)return;try{data=await api('/api/plans/priorities',{token,order:select.value.split(','),confirmed:true});render();}catch(e){status(e.message);}}));host.append(priorities);
      host.append(el('p','These two cost dimensions do not measure total spending. Doctor, medicine, eligibility and other material checks remain separate.','plans-small'));
    }
    const tabs=el('div',undefined,'plans-actions');
    tabs.append(button(`All retained plans (${data.plans.length})`,()=>{mode='all';render();}),button(`Recommended (${rec.top_three.length})`,()=>{mode='recommended';render();}),button(`Compare (${compared.size})`,()=>{mode='compare';render();}));host.append(tabs);
    if(costs?.state==='available')tabs.append(button('Order by published costs',()=>{mode='costs';render();}));
    const label=el('label','Find a plan by name or ID'),search=el('input');search.type='search';search.value=query;search.id='plans-search';label.htmlFor=search.id;search.oninput=()=>{query=search.value;renderCards();};host.append(label,search);
    const list=el('div');list.id='plans-list';host.append(list);renderCards();
  }
  function renderCards(){
    if(!data)return;const list=$('plans-list');list.replaceChildren();
    const plans=data.plans.filter(p=>mode==='recommended'?data.recommendation.top_three.includes(p.id):mode==='compare'?compared.has(p.id):`${p.id} ${p.name}`.toLowerCase().includes(query.toLowerCase()));
    if(mode==='recommended')plans.sort((a,b)=>data.recommendation.top_three.indexOf(a.id)-data.recommendation.top_three.indexOf(b.id));
    if(mode==='costs'){const ids=data.reference_comparison.ordered_ids;plans.sort((a,b)=>(ids.includes(a.id)?ids.indexOf(a.id):999)-(ids.includes(b.id)?ids.indexOf(b.id):999));}
    list.append(el('p',`${plans.length} plans shown. Listing order is not a recommendation.`, 'plans-small'));
    if(mode==='compare'&&plans.length){const wrap=el('div',undefined,'plans-compare'),table=el('table'),head=el('tr');head.append(el('th','Term'));plans.forEach(p=>head.append(el('th',p.name)));table.append(head);for(const key of Object.keys(plans[0].fields)){const row=el('tr');row.append(el('th',plans[0].fields[key].label));plans.forEach(p=>row.append(el('td',p.fields[key].value??'Held — needs review')));table.append(row);}wrap.append(table);list.append(wrap);}
    for(const p of plans){
      const card=el('article',undefined,'plans-card');card.dataset.planId=p.id;card.dataset.selected=String(p.id===selected);
      card.append(el('p',p.id,'plans-small'),el('h2',p.name));
      if(p.retained_restrictions.length)card.append(el('p','Published restrictions; personal qualification unverified: '+p.retained_restrictions.join('; '),'plans-hold'));
      const dl=el('dl');for(const key of ['plan_premium','medical_deductible','medical_maximums']){const cell=p.fields[key],pair=el('div');pair.append(el('dt',cell.label),el('dd',cell.value??'Held — needs review'));
        const explanation=el('details'),meaning=el('summary','What does this mean?'),definition=data.definitions[key==='medical_maximums'?'medical_limit':'costs'];
        explanation.append(meaning,el('p',definition.text,'plans-small'));pair.append(explanation);dl.append(pair);}card.append(dl);
      const actions=el('div',undefined,'plans-actions');actions.append(button('Discuss this plan',()=>{selected=p.id;field=null;ask(`Help me understand ${p.name} and its unresolved tradeoffs.`);chat();render();}),button(compared.has(p.id)?'Remove from comparison':'Add to comparison',()=>{if(compared.has(p.id))compared.delete(p.id);else if(compared.size<3)compared.add(p.id);else{status('Compare up to three plans at a time.');return;}render();}));card.append(actions);
      const detail=el('details'),summary=el('summary','Details, definitions and held checks');detail.append(summary);
      detail.ontoggle=()=>{if(detail.open){selected=p.id;field=null;}};
      for(const [key,cell] of Object.entries(p.fields)){const row=el('div',undefined,'plans-detail');row.append(el('strong',cell.label),el('p',cell.value??'Held — no amount is available for use.'));for(const condition of cell.conditions)row.append(el('p',condition));if(cell.reason_codes.length)row.append(el('p',cell.reason_codes.map(x=>x.replaceAll('_',' ').toLowerCase()).join(' · '),'plans-small'));row.append(button('Ask about '+cell.label.toLowerCase(),()=>stage(p,key)));detail.append(row);}
      const checks=data.recommendation.plans.find(row=>row.id===p.id)?.checks;
      if(checks)for(const [key,check] of Object.entries(checks))detail.append(el('p',`${key.replaceAll('_',' ')}: ${check.state.replaceAll('_',' ')} · ${check.reason_codes.join(', ').replaceAll('_',' ').toLowerCase()}`,'plans-small'));
      const examples=el('details');examples.append(el('summary','Fictional cost examples — not your estimated spending'));
      for(const example of Object.values(p.examples))examples.append(el('p',`${example.label}: ${example.amount?'$'+example.amount.amount:'Held · '+example.reason_codes.join(', ')}`));
      examples.append(el('p','Assumes 12 premium months, four ordinary covered in-network PCP visits, or one covered in-network acute admission of three or four counted days. Required referral and authorization are assumed, with no assistance adjustment and enough room below the medical spending limit. Excludes discharge day, transfers, readmissions and separately billed professional services. These are separate cost components, not a combined annual estimate.','plans-small'));detail.append(examples);card.append(detail);list.append(card);
    }
  }
  async function open(handoff=null){token=handoff?.token||null;opened=true;activate();$('workspace').classList.add('plans-open');$('workspace').classList.toggle('chat-closed',innerWidth<1180);$('plans-panel').hidden=false;$('plans-panel').replaceChildren(el('p','Loading the retained catalog…'));const notice=el('p');notice.id='plans-status';notice.setAttribute('role','status');$('plans-panel').append(notice);await refresh();return !!data;}
  function close(){opened=false;$('workspace').classList.remove('plans-open','chat-closed');$('plans-panel').hidden=true;$('message').focus();}
  function snapshot(){
    if(!opened||!data)return null;
    const visible=[...document.querySelectorAll('[data-plan-id]')].filter(n=>{const r=n.getBoundingClientRect();return r.bottom>0&&r.top<innerHeight;}).map(n=>n.dataset.planId).slice(0,12);
    return {version:'plans-context-v1',reviewToken:token,viewDigest:data.view_digest,visibleIds:visible,comparedIds:[...compared],selectedId:selected,field,mode};
  }
  window.DaylightPlans=Object.freeze({init(options){api=options.request;activate=options.activate;ask=options.ask;$('plans-tab').disabled=false;$('plans-tab').onclick=()=>open();DaylightPlansHandoff.register(open);
      const closeButton=button('Back to plans',()=>chat(false));closeButton.classList.add('plans-close-chat');document.querySelector('.chat-workspace').prepend(closeButton);
      const contextNotice=el('p','', 'plans-chat-context');contextNotice.id='plans-chat-context';document.querySelector('#composer').prepend(contextNotice);
      document.addEventListener('keydown',e=>{if(opened&&e.key==='Escape')chat(false);
        if(opened&&innerWidth<1180&&!$('workspace').classList.contains('chat-closed')&&e.key==='Tab'){
          const nodes=[...document.querySelectorAll('.chat-workspace button,.chat-workspace textarea,.chat-workspace select,.chat-workspace a')].filter(n=>!n.disabled&&n.getClientRects().length);
          if(e.shiftKey&&document.activeElement===nodes[0]){e.preventDefault();nodes.at(-1)?.focus();}
          else if(!e.shiftKey&&document.activeElement===nodes.at(-1)){e.preventDefault();nodes[0]?.focus();}
        }});},snapshot,
    afterTurn(result){if(!opened)return;if(result.plansContext?.profile_changed){invalidate('Your profile changed. Return to the conversation and review it before continuing.');}else if(result.generated?.code==='plans_evidence_changed'){invalidate('Plan evidence changed. Refresh before continuing.');}else if(data&&result.plansContext&&(result.plansContext.view_digest!==data.view_digest||result.plansContext.selected_id!==selected||result.plansContext.focused_field!==field)){status('This reply refers to the plan view at Send.');}},close});
})();
