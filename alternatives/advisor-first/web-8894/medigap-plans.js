/* D129–D131: shared reported profile, exact-source Medigap prices.
   Missing details and corrections belong in the conversation. Rates remain visit-only. */
(() => {
  'use strict';
  const DATE = '2026-11-10', VARIANTS = ['A','B','C','D','F','HDF','G','HDG','K','L','M','N'];
  const chosen = new Set();
  let input = {zipcode:'',age:'',gender:'',tobacco:''}, result = null, error = '', pending = false, revision = 0;
  let host, request, context = null, search = '', variant = 'all', order = 'premium', compare = false, orderTouched = false;
  let profile, conversation, attempt = null, activeDialog = null;
  const el = (tag, text, cls) => {const n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n;};
  const money = cents => cents == null ? 'Not supplied' : new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(cents / 100);
  const planName = v => v === 'HDG' ? 'High-deductible Plan G' : v === 'HDF' ? 'High-deductible Plan F' : `Plan ${v}`;
  const name = p => `${p.company} · ${planName(p.variant)}`;
  const sourceClass = p => p.rating_class && p.rating_class !== 'None' ? p.rating_class : 'Not specified';
  const text = v => v == null || v === '' ? 'Not supplied' : String(v);
  // D138: one deterministic "monthly total" for an Original Medicare pair.
  // Visit-only, display-only: a chosen Medigap rate plus a chosen Part D plan.
  const picks = window.DaylightPicks = window.DaylightPicks || {medigap:null, partD:null, strip() {
    const usd = cents => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(cents / 100);
    const box = document.createElement('section'); box.className = 'plans-notice daylight-picks';
    if (!this.medigap && !this.partD) return null;
    const line = text => {const p = document.createElement('p'); p.textContent = text; box.append(p);};
    line('Your monthly total so far');
    line(this.medigap ? `Medigap: ${this.medigap.label}, ${usd(this.medigap.cents)} listed monthly premium` : 'Medigap: none chosen yet. Use “Use in my monthly total” on a listed rate.');
    line(this.partD ? `Part D: ${this.partD.label}, ${usd(this.partD.cents)} standard monthly premium` : 'Part D: none chosen yet. Use “Use in my monthly total” on a drug plan.');
    if (this.medigap && this.partD) line(`Together: ${usd(this.medigap.cents + this.partD.cents)} a month in listed premiums.`);
    line('This adds two listed premiums only. The Part B premium, deductibles and your medicine costs are separate, and neither amount is a quote or a recommendation.');
    return box;
  }};
  const LETTER_LIMIT = {C:true, F:true, HDF:true};
  // D147: evaluation-only sorting (local demo only) is the default order until the person picks another.
  const fitReady = () => !!window.DaylightRecommend?.tab('medigap');
  const orderChoice = () => !orderTouched && fitReady() ? 'fit' : order === 'fit' && !fitReady() ? 'premium' : order;
  function button(label, run, cls = 'btn-quiet') {const b = el('button',label,cls); b.type = 'button'; b.onclick = run; return b;}
  function clearResult() {revision++; result = null; error = ''; pending = false; chosen.clear(); compare = false;}
  function ageMessage() {
    if (!/^\d+$/.test(input.age)) return '';
    if (Number(input.age) >= 75) return 'Medigap pricing for ages 75+ is not supported in this pilot.';
    if (Number(input.age) < 65) return 'Medigap pricing in this pilot supports ages 65–74, and age 64 for people about to turn 65. Younger ages are not supported.';
    return '';
  }
  function syncProfile(value, visit) {
    profile = value;
    const key = JSON.stringify([visit, value?.status, value?.inputs, value?.held]);
    if (context !== key) {
      context = key; clearResult(); attempt = null;
      if (activeDialog) activeDialog.close();
      input = {...value?.inputs};
    }
  }
  async function load() {
    if (pending || profile?.status !== 'ready') return;
    const body = {...input, age:Number(input.age), effective_date:DATE}, current = ++revision;
    attempt = context;
    pending = true; result = null; error = ''; chosen.clear(); compare = false; renderResults();
    try {
      const value = await request('/api/plans/medigap',body);
      if (current !== revision) return;
      if (!Array.isArray(value.plans)) throw new Error('Medigap prices could not be read. Try again.');
      result = value;
    } catch (e) {if (current === revision) error = e.message || 'Medigap prices are temporarily unavailable. Try again.';}
    finally {if (current === revision) {pending = false; renderResults();}}
  }
  function render(target, options) {
    host = target; request = options.request; conversation = options.conversation; syncProfile(options.profile, options.context);
    const top = el('div',null,'plans-top'), title = el('h1','Medicare Supplement (Medigap)','plans-title'); title.tabIndex = -1;
    top.append(title); host.append(top,el('p','Listed premiums for your exact profile, for November 10, 2026.','plans-lede'),
      el('p','Pilot coverage: ZIPs 34101–34108, ages 65–74. Prices use the details in your chat profile and update when those details change.','plans-help'));
    if (!profile || profile.status === 'missing') {
      const invitation = el('section',null,'medigap-invitation');
      invitation.append(el('h2','Considering Medigap?'),
        el('p','Talk with Daylight about your situation so we can show prices that match your details. We’ll use what you’ve already shared and ask only for what’s missing.','plans-lede'),
        button('Talk to Daylight',()=>conversation(),'primary-button'));
      if (profile?.held.length) invitation.append(el('p','Details you left unknown or chose to check later stay open. You can update them in the conversation whenever you’re ready.','plans-help'));
      host.append(invitation);
    }
    if (profile) {
      const editor = el('details',null,'medigap-editor');editor.append(el('summary','Your pricing details'));
      const rows = [{id:'T03',label:'Home ZIP code',value:input.zipcode},...profile.details];
      for(const item of rows) {
        const row = el('div',null,'plans-row medigap-profile-row');
        row.append(el('p',`${item.label}: ${item.value ?? (item.status === 'unknown' ? 'Unknown' : item.status === 'skipped' ? 'Check later' : 'Not yet provided')}`),
          button('Edit '+item.label+' in conversation',()=>conversation(item.id)));editor.append(row);
      }
      editor.append(el('p','These answers are part of your chat profile. They are saved only if you choose to save sensitive details. Listed prices are not saved in your profile.','plans-help'));host.append(editor);
    }
    const notice = el('p','', 'plans-notice'); notice.id = 'medigap-status'; notice.tabIndex = -1; notice.setAttribute('role','status'); notice.setAttribute('aria-live','polite');
    const output = el('div'); output.id = 'medigap-results'; host.append(notice,output); renderResults();
    if(profile?.status === 'ready' && attempt !== context) void load();
  }
  function select(label, values, current, change) {
    const wrap = el('label',label,'plans-field'), s = el('select');
    for (const [v,t] of values) s.append(new Option(t,v)); s.value = current; s.onchange = () => change(s.value); wrap.append(s); return wrap;
  }
  function renderResults() {
    const output = document.getElementById('medigap-results'), notice = document.getElementById('medigap-status');
    if (!output || !notice) return; output.replaceChildren();
    const unsupported = profile?.message || ageMessage();
    notice.textContent = unsupported || error || (pending ? 'Finding your matched prices…' : result?.message || '');
    if(error && profile?.status === 'ready') output.append(button('Try prices again',load));
    if (unsupported || !result || result.status !== 'matched_source_prices') return;
    const p = result.profile;
    output.append(el('p',`ZIP ${p.zip} · Age ${p.age} · ${p.gender} · ${p.tobacco} · November 10, 2026`,'plans-count'),el('p',result.notice,'plans-help'));
    if (profile?.note) output.append(el('p',profile.note,'plans-help')); // D138: a 64-year-old sees age-65 prices.
    // D138: reviewed statement (ma_trial_right), shown to everyone because the
    // listed premiums say nothing about acceptance.
    output.append(el('p','Outside the 6-month Medigap Open Enrollment Period that starts with Part B at 65 or older, an insurer can usually ask health questions and may decline or charge more. These listed premiums do not show whether an insurer would accept an application.','plans-help'));
    const strip = picks.strip(); if (strip) output.append(strip);
    const fitSummary = window.DaylightRecommend?.summary('medigap', Object.fromEntries(result.plans.map(p => [p.id, name(p)])));
    if (fitSummary) output.append(fitSummary); // D147
    // D138: the plan letters at a glance, so the list is not one long wall.
    const glance = el('section',null,'medigap-glance'); glance.append(el('h2','Plan letters at a glance'));
    const table = el('ul',null,'medigap-letters');
    for (const v of VARIANTS) {
      const rates = result.plans.filter(p => p.variant === v && p.monthly_cents != null).map(p => p.monthly_cents);
      if (!rates.length) continue;
      const item = el('li'), low = Math.min(...rates), high = Math.max(...rates);
      item.append(el('span',`${planName(v)}: ${rates.length} listed ${rates.length === 1 ? 'rate' : 'rates'}, ${money(low)}${high > low ? ' to ' + money(high) : ''} a month. `));
      if (LETTER_LIMIT[v]) item.append(el('span','Only for people who were eligible for Medicare before January 1, 2020. '));
      item.append(button(`Show ${planName(v)} rates`,()=>{variant=v;compare=false;renderResults();document.getElementById('medigap-count')?.focus();}));
      table.append(item);
    }
    glance.append(table,el('p','Each letter is a standardized set of benefits; companies charge different premiums for the same letter. The ranges are listed premiums in display order, not a ranking.','plans-help'));
    output.append(glance);
    const filters = el('div',null,'plans-filters medigap-filters');
    const searchLabel = el('label','Company name','plans-field'), searchBox = el('input'); searchBox.type = 'search'; searchBox.value = search;
    searchBox.oninput = () => {search = searchBox.value; renderList();}; searchLabel.append(searchBox);
    filters.append(searchLabel, select('Plan letter',[['all','All plan letters'],...VARIANTS.map(v=>[v,planName(v)])],variant,v=>{variant=v;renderList();}),
      select('Sort by',[...(fitReady()?[['fit','Daylight’s sorting (evaluation)']]:[]),['premium','Lowest monthly premium'],['name','Company name']],orderChoice(),v=>{order=v;orderTouched=true;renderList();})); output.append(filters);
    const controls = el('div',null,'plans-row medigap-actions'); controls.id = 'medigap-actions'; output.append(controls);
    const count = el('p','', 'plans-count'); count.id = 'medigap-count'; count.tabIndex = -1; count.setAttribute('aria-live','polite');
    const list = el('div'); list.id = 'medigap-list'; output.append(count,list);
    const about = el('details',null,'plans-about'); about.append(el('summary','About these Medigap prices'),
      el('p','Source: CSG Actuarial exports requested for November 10, 2026. Each listed rate retains its rating class, fees and discount conditions. This is a captured subset; complete market coverage is not established.'),
      el('p','Sorting changes the display order only. Monthly and annual amounts are separate source values. Eligibility, policy form, discount qualification and future rates are not confirmed. Part D prices are not included.'));
    output.append(about); renderList();
  }
  function toggle(p) {
    if (chosen.has(p.id)) chosen.delete(p.id);
    else if (chosen.size < 3) chosen.add(p.id);
    else {document.getElementById('medigap-status').textContent = 'You can compare up to three listed rates. Remove one to add another.'; return;}
    if (!chosen.size) compare = false; document.getElementById('medigap-status').textContent = ''; renderList();
  }
  function renderList() {
    const list = document.getElementById('medigap-list'); if (!list || !result) return;
    const controls = document.getElementById('medigap-actions'); controls.replaceChildren();
    controls.append(button('All listed rates',()=>{compare=false;renderList();},compare?'btn-quiet':'btn-secondary'));
    if (chosen.size) controls.append(button(`Compare selected (${chosen.size})`,()=>{compare=true;renderList();},compare?'btn-secondary':'btn-quiet'));
    list.replaceChildren();
    const rows = result.plans.filter(p => compare ? chosen.has(p.id) : (variant === 'all' || p.variant === variant) && p.company.toLowerCase().includes(search.toLowerCase().trim()));
    const effective = orderChoice();
    rows.sort((a,b) => (effective === 'premium' ? (a.monthly_cents ?? Infinity) - (b.monthly_cents ?? Infinity) : 0) || a.company.localeCompare(b.company) || a.variant.localeCompare(b.variant) || sourceClass(a).localeCompare(sourceClass(b)) || a.id.localeCompare(b.id));
    document.getElementById('medigap-count').textContent = `${rows.length} of ${result.plans.length} listed rates${compare?' selected for comparison':''}`;
    if (!rows.length) {list.append(el('p','No listed rates match these filters. Try all plan letters or clear the company name.','plans-help'));return;}
    if (compare) return comparison(list,rows);
    const groups = effective === 'fit' ? window.DaylightRecommend?.arrange('medigap', rows) : null;
    if (groups) {return fitList(list, groups, card, 'rate');} // D147
    for (const p of rows) list.append(card(p));
  }
  // D147: backend groups, in order; the set-aside group starts closed.
  function fitList(list, groups, make, noun) {
    for (const g of groups) {
      const count = `${g.rows.length} ${noun}${g.rows.length === 1 ? '' : 's'}`;
      if (g.id === 'excluded') {
        const d = el('details',null,'plans-group plans-ruled'), s = el('summary');
        s.append(el('span',`${g.label} (${g.rows.length})`,'plans-ruled-title'),el('span','Set aside by who can buy it or by something you need. Each one shows why.','plans-ruled-help'));
        d.append(s); for (const p of g.rows) d.append(make(p)); list.append(d); continue;
      }
      const section = el('section',null,'plans-group'), h = el('h2',g.label,'rec-group-title'); h.append(el('span',count,'rec-count'));
      section.append(h); for (const p of g.rows) section.append(make(p)); list.append(section);
    }
  }
  function addAmount(dl,label,value) {const box = el('div',null,'amount'); box.append(el('dt',label,'amount-label'),el('dd',value,'amount-value')); dl.append(box);}
  function card(p) {
    const c = el('article',null,'plan-card'); c.dataset.medigapId = p.id;
    c.append(el('h3',name(p),'plan-name'),el('p',`Rating class: ${sourceClass(p)}`,'plan-facts'));
    if (p.select_observed === true) c.append(el('p','Medicare SELECT is marked in this source. Check its network conditions.','plan-rule'));
    const amounts = el('dl',null,'plan-amounts');
    addAmount(amounts,'Listed monthly premium',money(p.monthly_cents)); addAmount(amounts,'Listed annual premium',money(p.annual_cents));
    addAmount(amounts,'Listed policy fee',text(p.policy_fee)); c.append(amounts);
    const actions = el('div',null,'plan-actions'), add = button(chosen.has(p.id)?'Added to compare':'Add to compare',()=>toggle(p),'btn-secondary');
    window.DaylightRecommend?.decorate('medigap', p.id, c); // D147
    add.setAttribute('aria-pressed',String(chosen.has(p.id))); actions.append(add,button('See full details',e=>details(p,e)));
    if (p.monthly_cents != null) {
      const mine = picks.medigap?.id === p.id, use = button(mine ? 'In my monthly total' : 'Use in my monthly total',()=>{picks.medigap = mine ? null : {id:p.id,label:name(p),cents:p.monthly_cents};renderResults();});
      use.setAttribute('aria-pressed',String(mine)); actions.append(use);
    }
    c.append(actions); return c;
  }
  const DETAILS = [
    ['Listed monthly premium',p=>money(p.monthly_cents)], ['Listed annual premium',p=>money(p.annual_cents)],
    ['Monthly premium if discount applies',p=>money(p.monthly_with_discounts_cents)], ['Annual premium if discount applies',p=>money(p.annual_with_discounts_cents)],
    ['Household discount in source',p=>text(p.household_discount)], ['Listed policy fee',p=>text(p.policy_fee)],
    ['Rating class',sourceClass], ['Rating method in source',p=>text(p.rating_type)],
    ['Medicare SELECT in source',p=>p.select_observed === true ? 'Yes; network conditions need checking' : p.select_observed === false ? 'No' : 'Not specified'],
    ['Source rate effective date',p=>text(p.source_effective_date)], ['Rate end date',p=>text(p.effective_end)],
    ['Policy form',p=>text(p.policy_form)], ['Policy edition',p=>text(p.policy_edition)]
  ];
  function comparison(list,rows) {
    list.append(el('p','Scroll sideways in the comparison to see each selected rate.','plans-help medigap-scroll-help'));
    const wrap=el('div',null,'plans-compare'), table=el('table'), head=el('tr');
    wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','Medigap rate comparison');
    table.append(el('caption','Compare listed Medigap rates')); head.append(el('th','Source term'));
    for(const p of rows) {const th=el('th'); th.scope='col'; th.append(el('p',name(p)),el('p',`Class: ${sourceClass(p)}`),button('Remove',()=>toggle(p)));head.append(th);}
    const thead=el('thead');thead.append(head);table.append(thead);const body=el('tbody');
    for(const [label,get] of DETAILS) {const row=el('tr'),th=el('th',label);th.scope='row';row.append(th);for(const p of rows)row.append(el('td',get(p)));body.append(row);}
    table.append(body);wrap.append(table);list.append(wrap,el('p','Discount qualification, fee timing and eligibility have not been verified. This comparison does not recommend a policy.','plans-help'));
  }
  function details(p,event) {
    const opener=event.currentTarget, dialog=el('dialog',null,'plan-sheet');dialog.setAttribute('aria-labelledby','medigap-detail-title');
    activeDialog = dialog;
    const head=el('div',null,'sheet-head'), title=el('h2',name(p));title.id='medigap-detail-title';
    const close=button('Close',()=>dialog.close(),'btn-quiet sheet-close');head.append(title,close);dialog.append(head);
    dialog.append(el('p','Listed premiums, not a guaranteed quote. Eligibility, discount qualification and fee timing still need checking.','sheet-note'));
    const section=el('section',null,'sheet-section');
    for(const [label,get] of DETAILS) {const row=el('div',null,'sheet-row'),top=el('div',null,'sheet-row-top');top.append(el('p',label,'sheet-label'),el('p',get(p),'sheet-value'));row.append(top);section.append(row);}
    dialog.append(section); const source=el('details',null,'sheet-more');source.append(el('summary','Source details'),el('p',`CSG Actuarial · requested November 10, 2026 · NAIC ${p.naic}`,'sheet-note'));
    if(p.rating_labels_need_review)source.append(el('p','The source rating/outlook labels need review and are not used to compare insurer quality.','sheet-note'));
    const dl=el('dl');for(const [key,value] of Object.entries(p.source_fields)){dl.append(el('dt',key),el('dd',text(value)));} source.append(dl,el('p',p.source_locator,'sheet-note'));dialog.append(source);
    dialog.addEventListener('close',()=>{activeDialog = null;dialog.remove();if(opener.isConnected)opener.focus();},{once:true}); document.body.append(dialog);dialog.showModal();close.focus();
  }
  window.DaylightMedigap = Object.freeze({render,syncProfile});
})();
