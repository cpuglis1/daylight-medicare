/* D134: published PDP terms for the shared conversation profile. No personal
   drug-cost calculation, saved source rows or automatic AI calls. */
(() => {
  'use strict';
  const chosen = new Set();
  let host, options, profile, context, result = null, error = '', pending = false, attempt = null, revision = 0;
  let query = '', sort = 'premium', compare = false, activeDialog = null, sortTouched = false;
  // D147: evaluation-only sorting (local demo only) is the default order until the person picks another.
  const fitReady = () => !!window.DaylightRecommend?.tab('part_d');
  const sortChoice = () => !sortTouched && fitReady() ? 'fit' : sort === 'fit' && !fitReady() ? 'premium' : sort;
  const el = (tag,text,cls) => {const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
  const button = (text,run,cls='btn-quiet') => {const n=el('button',text,cls);n.type='button';n.onclick=run;return n;};
  const value = (p,key) => p.fields[key]?.state === 'published' ? p.fields[key].value : null;
  const money = cents => cents == null ? 'Not supplied' : new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(cents/100);
  const fieldText = (p,key) => {const f=p.fields[key];return !f ? 'Not supplied' : f.state==='not_applicable' ? 'Not applicable in source' : f.state!=='published' ? 'Not supplied' : f.value_encoding==='integer_cents' ? money(f.value) : String(f.value ?? 'Not supplied');};
  const TERMS = [['total_premium','Standard monthly premium'],['annual_deductible','Annual drug deductible'],
    ['has_tier_without_deductible','Drug tiers without a deductible'],['drug_benefit_type','Drug benefit type'],
    ['basic_premium','Basic monthly premium component'],['supplemental_premium','Supplemental monthly premium component']];
  function sync(value,visit) {
    profile=value;
    const key=JSON.stringify([visit,value?.status,value?.inputs]);
    if(key!==context){context=key;revision++;result=null;error='';pending=false;attempt=null;chosen.clear();compare=false;activeDialog?.close();}
  }
  async function load() {
    if(pending||profile?.status!=='ready')return;
    const current=++revision;attempt=context;pending=true;error='';result=null;renderResults();
    try {
      const response=await options.request('/api/plans/part-d',{...profile.inputs});
      if(current!==revision)return;
      if(!Array.isArray(response.plans))throw Error('Part D plan information could not be read. Try again.');
      result=response;
    } catch(e){if(current===revision)error=e.message||'Part D plan information is temporarily unavailable. Try again.';}
    finally{if(current===revision){pending=false;renderResults();}}
  }
  // X-03 (D157): the standard-premium range for the two-path card in the chat.
  const ranges = new Map();
  function range(send, profileValue) {
    if (profileValue?.status !== 'ready') return Promise.resolve(null);
    const key = JSON.stringify(profileValue.inputs);
    if (!ranges.has(key)) ranges.set(key, send('/api/plans/part-d',{...profileValue.inputs}).then(v => {
      const rates = (v.plans || []).map(p => value(p,'total_premium')).filter(n => typeof n === 'number');
      return rates.length ? {low:Math.min(...rates), high:Math.max(...rates), count:rates.length} : null;
    }).catch(() => {ranges.delete(key); return null;}));
    return ranges.get(key);
  }
  function render(target,settings) {
    host=target;options=settings;sync(settings.profile,settings.context);
    const title=el('h1','Part D drug plans','plans-title');title.tabIndex=-1;
    host.append(title);
    if(!profile||profile.status==='missing'){
      const next=profile?.questions?.[0],count=(profile?.missing||[]).length;
      const intro=el('section',null,'medigap-invitation');intro.append(el('h2',count?`${count} detail${count===1?'':'s'} left to see your Part D drug plans`:'A few details to see your Part D drug plans'));
      if(next)intro.append(el('p',next.why||'','plans-lede'),button(next.question,()=>options.conversation(next.id),'primary-button'));
      else intro.append(button('Continue in the conversation',()=>options.conversation(profile?.missing?.[0]),'primary-button'));
      host.append(intro);
    }
    if(profile){
      const edits=el('div',null,'plans-row medigap-edit-row');edits.hidden=true;
      for(const item of profile.details)edits.append(button(item.label,()=>options.conversation(item.id),'btn-quiet'));
      const edit=button('Edit details',()=>{edits.hidden=!edits.hidden;edit.setAttribute('aria-expanded',String(!edits.hidden));},'btn-quiet');edit.setAttribute('aria-expanded','false');
      const line=el('div',null,'plans-row medigap-pricing-line');line.append(edit);host.append(line,edits);
    }
    const notice=el('p','', 'plans-notice');notice.id='part-d-status';notice.setAttribute('role','status');notice.setAttribute('aria-live','polite');
    const output=el('div');output.id='part-d-results';host.append(notice,output);renderResults();
    if(profile?.status==='ready'&&attempt!==context)void load();
  }
  function renderResults(){
    const output=document.getElementById('part-d-results'),notice=document.getElementById('part-d-status');if(!output||!notice)return;
    output.replaceChildren();notice.textContent=profile?.message||error||(pending?'Finding Part D plan information…':result?.message||'');
    if(error&&profile?.status==='ready')output.append(button('Try Part D plans again',load));
    if(profile?.status!=='ready'||!result||result.status!=='published_plans')return;
    output.append(el('p',`ZIP ${result.profile.zipcode} · 2026 plans`,'plans-count'),el('p','Your medicines aren’t checked against each drug list yet.','plans-help'));
    const strip=window.DaylightPicks?.strip();if(strip)output.append(strip); // D138: Medigap plus Part D monthly total.
    const fitSummary=window.DaylightRecommend?.summary('part_d',Object.fromEntries(result.plans.map(p=>[p.id,p.name])));
    const filters=el('div',null,'plans-filters');
    const label=el('label','Plan or company name','plans-field'),search=el('input');search.type='search';search.value=query;search.oninput=()=>{query=search.value;renderList();};label.append(search);
    const orderLabel=el('label','Sort by','plans-field'),order=el('select');if(fitReady())order.append(new Option('Daylight’s sorting','fit'));order.append(new Option('Lowest standard monthly premium','premium'),new Option('Plan name','name'));order.value=sortChoice();order.onchange=()=>{sort=order.value;sortTouched=true;renderList();};orderLabel.append(order);filters.append(label,orderLabel);output.append(filters);
    const actions=el('div',null,'plans-row');actions.id='part-d-actions';const count=el('p','', 'plans-count');count.id='part-d-count';count.setAttribute('aria-live','polite');
    const list=el('div');list.id='part-d-list';output.append(actions,count,list);
    if(fitSummary)output.append(fitSummary); // CN-04: one link below the list
    const about=el('details',null,'plans-about');about.append(el('summary','About this Part D information'),
      el('p','Source: CMS September 2026 published plan snapshot, with a restriction check through October 25, 2026. This dated reference contains ten Florida stand-alone PDP offerings mapped to Collier County; it does not confirm today’s enrollment availability.'),
      el('p','All listed plans are included regardless of commercial relationships. Sorting changes display order only. Standard premiums do not include your medicine costs or establish your subsidy-adjusted payment. A Part D premium is not the total cost of Original Medicare and Medigap.'),
      el('p','Drug coverage, prior authorization, step therapy, quantity limits, pharmacy participation and personal costs have not been checked for you.'));
    const link=el('a','Check current plans at Medicare.gov');link.href='https://www.medicare.gov/plan-compare/';link.target='_blank';link.rel='noopener noreferrer';about.append(link);output.append(about);renderList();
  }
  function toggle(p){
    if(chosen.has(p.id))chosen.delete(p.id);else if(chosen.size<3)chosen.add(p.id);else{document.getElementById('part-d-status').textContent='You can compare up to three plans. Remove one to add another.';return;}
    if(!chosen.size)compare=false;document.getElementById('part-d-status').textContent='';renderList();
  }
  function renderList(){
    const list=document.getElementById('part-d-list');if(!list||!result)return;
    const actions=document.getElementById('part-d-actions');actions.replaceChildren();
    if(chosen.size)actions.append(button('All listed plans',()=>{compare=false;renderList();},compare?'btn-quiet':'btn-secondary'));
    if(chosen.size)actions.append(button(`Compare selected (${chosen.size})`,()=>{compare=true;renderList();},compare?'btn-secondary':'btn-quiet'));
    const rows=result.plans.filter(p=>compare?chosen.has(p.id):`${p.name} ${p.company}`.toLowerCase().includes(query.trim().toLowerCase()));
    const effective=sortChoice();
    rows.sort((a,b)=>(effective==='premium'?(value(a,'total_premium')??Infinity)-(value(b,'total_premium')??Infinity):0)||a.name.localeCompare(b.name)||a.id.localeCompare(b.id));
    document.getElementById('part-d-count').textContent=`${rows.length} of ${result.plans.length} published plans${compare?' selected for comparison':''}`;
    list.replaceChildren();if(!rows.length){list.append(el('p','No plans match this search. Clear the plan or company name to see all published plans.','plans-help'));return;}
    if(compare)return comparison(list,rows);
    const groups=effective==='fit'?window.DaylightRecommend?.arrange('part_d',rows):null;
    if(groups){ // D147: backend groups, in order
      for(const g of groups){const section=el('section',null,'plans-group'),h=el('h2',g.label,'rec-group-title');h.append(el('span',`${g.rows.length} ${g.rows.length===1?'plan':'plans'}`,'rec-count'));section.append(h);for(const p of g.rows)section.append(cardFor(p));list.append(section);}
      return;
    }
    for(const p of rows)list.append(cardFor(p));
  }
  function cardFor(p){
    {
      const card=el('article',null,'plan-card');card.dataset.partDId=p.id;card.append(el('h3',p.name,'plan-name'),el('p',p.company,'plans-help')); // D138: the source ID stays in full details.
      const amounts=el('dl',null,'plan-amounts');for(const [key,label] of TERMS.slice(0,2)){const box=el('div',null,'amount');box.append(el('dt',label,'amount-label'),el('dd',fieldText(p,key),'amount-value'));amounts.append(box);}card.append(amounts);
      card.append(el('p','Personal medicine and pharmacy costs: not checked. Deductible exceptions may apply by drug tier.','plans-help'));
      const controls=el('div',null,'plan-actions'),add=button(chosen.has(p.id)?'Added to compare':'Add to compare',()=>toggle(p),'btn-secondary');add.setAttribute('aria-pressed',String(chosen.has(p.id)));controls.append(add,button('See full details',event=>details(p,event)));
      if(options.prescriptionPreview)controls.append(button('Check fictional drug costs',()=>options.prescriptionPreview(p)));
      const premium=value(p,'total_premium'),picks=window.DaylightPicks;
      if(picks&&premium!=null&&p.fields.total_premium.value_encoding==='integer_cents'){
        const mine=picks.partD?.id===p.id,use=button(mine?'In my monthly total':'Use in my monthly total',()=>{picks.partD=mine?null:{id:p.id,label:p.name,cents:premium};renderResults();},'btn-secondary');
        use.setAttribute('aria-pressed',String(mine));controls.append(use);
      }
      window.DaylightRecommend?.decorate('part_d',p.id,card); // D147
      card.append(controls);return card;
    }
  }
  function comparison(list,rows){
    list.append(el('p','Scroll sideways to see each selected plan. These are published terms, not personal cost estimates.','plans-help'));
    const wrap=el('div',null,'plans-compare');wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','Part D plan comparison');
    const table=el('table'),head=el('tr');table.append(el('caption','Compare published Part D terms'));head.append(el('th','Published term'));
    for(const p of rows){const th=el('th');th.scope='col';th.append(el('p',p.name),button('Remove',()=>toggle(p)));head.append(th);}const thead=el('thead');thead.append(head);table.append(thead);
    const body=el('tbody');for(const [key,label] of TERMS){const row=el('tr'),th=el('th',label);th.scope='row';row.append(th);for(const p of rows)row.append(el('td',fieldText(p,key)));body.append(row);}table.append(body);wrap.append(table);list.append(wrap);
  }
  function details(p,event){
    const opener=event.currentTarget,dialog=el('dialog',null,'plan-sheet');activeDialog=dialog;dialog.setAttribute('aria-labelledby','part-d-detail-title');
    const head=el('div',null,'sheet-head'),title=el('h2',p.name);title.id='part-d-detail-title';const close=button('Close',()=>dialog.close(),'btn-quiet sheet-close');head.append(title,close);dialog.append(head);
    dialog.append(el('p','Published 2026 terms. Your prescription costs, subsidy eligibility and enrollment availability are not determined.','sheet-note'));
    const section=el('section',null,'sheet-section');for(const [key,label] of TERMS){const row=el('div',null,'sheet-row'),top=el('div',null,'sheet-row-top');top.append(el('p',label,'sheet-label'),el('p',fieldText(p,key),'sheet-value'));row.append(top);section.append(row);}dialog.append(section);
    dialog.append(el('p',p.restriction_summary,'sheet-note'));
    const source=el('details',null,'sheet-more');source.append(el('summary','All published fields and source'),el('p','Subsidy-related amounts below are separate published figures, not amounts assigned to you.','sheet-note'));
    const dl=el('dl');for(const [key,f] of Object.entries(p.fields))dl.append(el('dt',f.basis),el('dd',fieldText(p,key)));source.append(dl,el('p',`CMS · ${p.source.member} · record ${p.source.record_ordinal} · plan ID ${p.id}`,'sheet-note'));dialog.append(source);
    dialog.addEventListener('close',()=>{activeDialog=null;dialog.remove();if(opener.isConnected)opener.focus();},{once:true});document.body.append(dialog);dialog.showModal();close.focus();
  }
  window.DaylightPartD=Object.freeze({render,range});
})();
