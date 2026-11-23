/* D129–D131: shared reported profile, exact-source Medigap prices.
   Missing details and corrections belong in the conversation. Rates remain visit-only. */
(() => {
  'use strict';
  const DATE = '2026-11-10', VARIANTS = ['A','B','C','D','F','HDF','G','HDG','K','L','M','N'];
  const chosen = new Set();
  let input = {zipcode:'',age:'',gender:'',tobacco:''}, result = null, error = '', pending = false, revision = 0;
  let host, request, context = null, search = '', variant = 'all', order = 'premium', compare = false, orderTouched = false;
  let profile, conversation, attempt = null, activeDialog = null, requestedVariant = null;
  const el = (tag, text, cls) => {const n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n;};
  const money = cents => cents == null ? 'Not supplied' : new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(cents / 100);
  const planName = v => v === 'HDG' ? 'High-deductible Plan G' : v === 'HDF' ? 'High-deductible Plan F' : `Plan ${v}`;
  // PG-05: a plain display name on the card; the legal name stays in the full details.
  const displayCompany = company => String(company || '').replace(/\s*\((?:f\/k\/a|fka|formerly|d\/b\/a|dba)\b[^)]*\)/gi,'').replace(/\s{2,}/g,' ').trim();
  const name = p => `${displayCompany(p.company)} · ${planName(p.variant)}`;
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
    line('Listed premiums only. The Part B premium, deductibles and your medicine costs are separate.');
    return box;
  }};
  const LETTER_LIMIT = {C:true, F:true, HDF:true};
  // CN-12 (D157): one plain line per plan letter, from Medicare's comparison
  // chart (medicare.gov/health-drug-plans/medigap/basics/compare-plan-benefits
  // and CMS Product No. 02110, March 2026; read November 12, 2026). Shown where
  // the letter is: under the filter when one letter is chosen, on each rate
  // when letters are mixed, and in the full details. The wording awaits the
  // owner's sign-off, given November 12, 2026 (STATEMENTS.md in the D157 packet).
  const LETTER_NOTES_RELEASED = true; // owner sign-off November 12, 2026: one sentence each
  const LETTER_NOTES = {
    A:'Covers the basic benefits: your share of hospital stays and doctor bills, with no deductibles, skilled nursing or foreign travel.',
    B:'Covers the basic benefits plus the Part A hospital deductible.',
    C:'Covers everything Medigap can cover except Part B excess charges.',
    D:'Covers most costs, leaving you the yearly Part B deductible and any excess charges.',
    F:'Covers everything Medigap can cover.',
    HDF:'Gives Plan F coverage after you pay the first $2,950 of costs in 2026.',
    G:'Covers everything Medigap can cover except the yearly Part B deductible.',
    HDG:'Gives Plan G coverage after you pay the first $2,950 of costs in 2026.',
    K:'Pays 50% of most costs until you’ve paid $8,000 in 2026 plus the Part B deductible, then 100% for the rest of the year.',
    L:'Pays 75% of most costs until you’ve paid $4,000 in 2026 plus the Part B deductible, then 100% for the rest of the year.',
    M:'Covers what Plan D covers, but only half of the Part A hospital deductible.',
    N:'Covers what Plan G covers, except you pay up to $20 for some office visits, up to $50 for some emergency room visits, and any excess charges.'};
  const letterNote = v => LETTER_NOTES_RELEASED || window.location?.port === '8895' ? LETTER_NOTES[v] || '' : '';
  let medigapWindow = null;
  // D147: evaluation-only sorting (local demo only) is the default order until the person picks another.
  const fitReady = () => !!window.DaylightRecommend?.tab('medigap');
  const orderChoice = () => !orderTouched && fitReady() ? 'fit' : order === 'fit' && !fitReady() ? 'premium' : order;
  function button(label, run, cls = 'btn-quiet') {const b = el('button',label,cls); b.type = 'button'; b.onclick = run; return b;}
  function clearResult() {revision++; result = null; error = ''; pending = false; chosen.clear(); compare = false;}
  function ageMessage() {
    if (!/^\d+$/.test(input.age)) return '';
    if (Number(input.age) >= 75) return 'Daylight doesn’t have Medigap prices for ages 75 and older yet. You can still look at Medicare Advantage and Part D plans.';
    if (Number(input.age) < 65) return 'Daylight has Medigap prices for ages 65 to 74, and for people about to turn 65. You can still look at Medicare Advantage and Part D plans.';
    return '';
  }
  function syncProfile(value, visit) {
    profile = value;
    const key = JSON.stringify([visit, value?.status, value?.inputs, value?.held, value?.first_eligible]);
    if (context !== key) {
      context = key; clearResult(); attempt = null;
      if (activeDialog) activeDialog.close();
      input = {...value?.inputs};
    }
  }
  async function load() {
    if (pending || profile?.status !== 'ready') return;
    const body = {...input, age:Number(input.age), effective_date:DATE}, current = ++revision;
    if(profile.continuation) body.continuation=profile.continuation;
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
  // X-03 (D157): the listed range for the two-path card in the chat, from the
  // same request this tab makes. Plans the person can't buy are left out.
  const ranges = new Map();
  function range(send, value) {
    if (value?.status !== 'ready') return Promise.resolve(null);
    const body = {...value.inputs, age:Number(value.inputs.age), effective_date:DATE};
    if(value.continuation) body.continuation=value.continuation;
    const key = JSON.stringify([value.inputs,value.first_eligible,value.continuation?.split('.')[0]]);
    if (!ranges.has(key)) ranges.set(key, send('/api/plans/medigap',body).then(v => {
      const rates = (v.plans || []).filter(p => p.monthly_cents != null && !p.set_aside).map(p => p.monthly_cents);
      return rates.length ? {low:Math.min(...rates), high:Math.max(...rates), count:rates.length} : null;
    }).catch(() => {ranges.delete(key); return null;}));
    return ranges.get(key);
  }
  function render(target, options) {
    host = target; request = options.request; conversation = options.conversation; syncProfile(options.profile, options.context);
    if (options.variant && VARIANTS.includes(options.variant) && requestedVariant !== options.variant) {
      requestedVariant = options.variant; variant = options.variant;
    }
    const top = el('div',null,'plans-top'), title = el('h1','Medicare Supplement (Medigap)','plans-title'); title.tabIndex = -1;
    top.append(title); host.append(top); medigapWindow = options.window || null;
    if (!profile || profile.status === 'missing') {
      const invitation = el('section',null,'medigap-invitation');
      const next = profile?.questions?.[0], count = (profile?.missing || []).length;
      invitation.append(el('h2', count ? `${count} detail${count === 1 ? '' : 's'} left to see your Medigap prices` : 'A few details to see your Medigap prices'));
      if (next) invitation.append(el('p',next.why,'plans-lede'),button(next.question,()=>conversation(next.id),'primary-button'));
      else invitation.append(button('Continue in the conversation',()=>conversation(profile?.missing?.[0]),'primary-button'));
      host.append(invitation);
    }
    if (profile) {
      const rows = [{id:'T03',label:'ZIP',value:input.zipcode},...profile.details.map(item => ({...item,label:{MG_AGE:'Age',MG_SEX:'Sex',MG_TOBACCO:'Tobacco'}[item.id] || item.label}))];
      const shown = value => value === 'Non-Tobacco' ? 'Non-tobacco' : value === 'Tobacco User' ? 'Tobacco' : value;
      const line = el('div',null,'plans-row medigap-pricing-line');
      line.append(el('p',rows.filter(item => item.value != null).map(item => item.id === 'T03' ? 'ZIP '+item.value : item.id === 'MG_AGE' ? 'Age '+item.value : shown(item.value)).join(' · ')
        + (profile.status === 'ready' ? ' · prices dated November 10, 2026' : ''),'plans-count'));
      const edits = el('div',null,'plans-row medigap-edit-row');edits.hidden = true;
      for (const item of rows) edits.append(button(item.label,()=>conversation(item.id),'btn-quiet'));
      const edit = button('Edit',()=>{edits.hidden = !edits.hidden;edit.setAttribute('aria-expanded',String(!edits.hidden));},'btn-quiet');
      edit.setAttribute('aria-expanded','false');line.append(edit);
      if (options.compact) {
        // Owner, November 13, 2026 (two-path dashboard only): the person's details and their Medigap
        // window are one tap away, not stacked between the top of the page and the prices.
        const box = el('section',null,'plans-tucked'), slot = el('div');slot.id = 'medigap-window-slot';
        box.append(el('h3','Your details'),line,edits,slot);host.append(box);
      } else host.append(line,edits);
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
    if (profile?.note) output.append(el('p',profile.note,'plans-help')); // D138: a 64-year-old sees age-65 prices.
    const tucked = document.getElementById('medigap-window-slot'), windowHost = tucked || output; tucked?.replaceChildren();
    if (medigapWindow?.text) windowHost.append(el('p',medigapWindow.text,'plans-help medigap-window'));
    else if (medigapWindow?.state === 'closed' || !medigapWindow && Number(p.age) > 65)
      // Reviewed statement (ma_trial_right), only for someone outside the window.
      windowHost.append(el('p','Outside the 6-month Medigap Open Enrollment Period that starts with Part B at 65 or older, an insurer can usually ask health questions and may decline or charge more.','plans-help medigap-window'));
    const strip = picks.strip(); if (strip) output.append(strip);
    // PG-03: someone inside their window is not told what happens outside it.
    const fitSummary = window.DaylightRecommend?.summary('medigap', Object.fromEntries(result.plans.map(p => [p.id, name(p)])),
      medigapWindow?.text ? note => /^Outside the 6-month Medigap Open Enrollment Period/.test(note) : null);
    // D138: the plan letters at a glance, so the list is not one long wall.
    const letterText = v => {
      const rates = result.plans.filter(p => p.variant === v && p.monthly_cents != null).map(p => p.monthly_cents);
      if (!rates.length) return planName(v);
      const low = Math.min(...rates), high = Math.max(...rates);
      return `${planName(v)} · ${rates.length} ${rates.length === 1 ? 'rate' : 'rates'} · ${money(low)}${high > low ? ' to ' + money(high) : ''}`
        + (LETTER_LIMIT[v] ? ' · eligible before 2020 only' : '');
    };
    const filters = el('div',null,'plans-filters medigap-filters');
    const searchLabel = el('label','Company name','plans-field'), searchBox = el('input'); searchBox.type = 'search'; searchBox.value = search;
    searchBox.oninput = () => {search = searchBox.value; renderList();}; searchLabel.append(searchBox);
    filters.append(searchLabel, select('Plan letter',[['all','All plan letters'],...VARIANTS.map(v=>[v,letterText(v)])],variant,v=>{variant=v;renderList();}),
      select('Sort by',[...(fitReady()?[['fit','Daylight’s sorting']]:[]),['premium','Lowest monthly premium'],['name','Company name']],orderChoice(),v=>{order=v;orderTouched=true;renderList();})); output.append(filters);
    const chosenLetter = el('p','','plans-help medigap-letter-note'); chosenLetter.id = 'medigap-letter-note'; chosenLetter.hidden = true; output.append(chosenLetter);
    const controls = el('div',null,'plans-row medigap-actions'); controls.id = 'medigap-actions'; output.append(controls);
    const count = el('p','', 'plans-count'); count.id = 'medigap-count'; count.tabIndex = -1; count.setAttribute('aria-live','polite');
    const list = el('div'); list.id = 'medigap-list'; output.append(count,list);
    output.append(button('Questions about plan letters? Ask Daylight',()=>conversation(),'btn-quiet'));
    if (fitSummary) output.append(fitSummary); // CN-04: one link below the list
    const about = el('details',null,'plans-about'); about.append(el('summary','About these Medigap prices'),
      el('p','Source: CSG Actuarial, for the date in the pricing line. Each listed rate keeps its rating class, fees and discount conditions. The insurer confirms the price, any discount and whether it accepts the application. Part D prices are separate.'));
    output.append(about); renderList();
  }
  function toggle(p) {
    if (chosen.has(p.id)) chosen.delete(p.id);
    else if (chosen.size < 3) chosen.add(p.id);
    else {document.getElementById('medigap-status').textContent = 'You can compare up to three listed rates. Remove one to add another.'; return;}
    if (!chosen.size) compare = false; document.getElementById('medigap-status').textContent = ''; renderList();
    // Keep the person's place: the list was redrawn, so return focus to the button they pressed.
    if (trayOn()) [...document.querySelectorAll('#medigap-list [data-medigap-id]')].find(n => n.dataset.medigapId === p.id)?.querySelector('button')?.focus({preventScroll:true});
  }
  // Owner, November 18, 2026 (:8895): "Add to compare" worked here but showed nothing where the person was;
  // the only way into the comparison was a button far above the list. Same tray as the Medicare Advantage list.
  const trayOn = () => !!window.DaylightGuidedClose;
  function tray(list) {
    if (trayOn()) document.body.classList.toggle('plans-has-tray', chosen.size > 0);
    if (!trayOn() || !chosen.size) return;
    const bar = el('div',null,'compare-tray'); bar.setAttribute('role','region'); bar.setAttribute('aria-label','Medigap rates to compare');
    const names = [...chosen].map(id => result.plans.find(p => p.id === id)).filter(Boolean).map(name);
    const words = el('p'); words.append(el('strong',`${chosen.size} ${chosen.size === 1 ? 'rate' : 'rates'} selected`),el('span',names.join(' · '),'tray-names'));
    if (chosen.size < 2) words.append(el('span','Add one more rate to compare side by side.','tray-names'));
    const go = button('Compare',()=>{compare = true; renderList(); document.getElementById('medigap-count')?.scrollIntoView({block:'start'});},'primary-button');
    go.disabled = chosen.size < 2;
    const acts = el('div',null,'tray-actions'); acts.append(button('Clear',()=>{chosen.clear(); compare = false; renderList();}),go);
    bar.append(words,acts); list.append(bar);
  }
  function renderList() {
    const list = document.getElementById('medigap-list'); if (!list || !result) return;
    const controls = document.getElementById('medigap-actions'); controls.replaceChildren();
    // Shown only once something is chosen to compare; alone it did nothing.
    if (chosen.size) controls.append(button('All listed rates',()=>{compare=false;renderList();},compare?'btn-quiet':'btn-secondary'));
    if (chosen.size) controls.append(button(`Compare selected (${chosen.size})`,()=>{compare=true;renderList();},compare?'btn-secondary':'btn-quiet'));
    list.replaceChildren();
    const about = document.getElementById('medigap-letter-note'), note = variant === 'all' || compare ? '' : letterNote(variant);
    if (about) {about.textContent = note ? `${planName(variant)}: ${note}` : ''; about.hidden = !note;}
    const rows = result.plans.filter(p => compare ? chosen.has(p.id) : (variant === 'all' || p.variant === variant) && p.company.toLowerCase().includes(search.toLowerCase().trim()));
    const effective = orderChoice();
    rows.sort((a,b) => (effective === 'premium' ? (a.monthly_cents ?? Infinity) - (b.monthly_cents ?? Infinity) : 0) || a.company.localeCompare(b.company) || a.variant.localeCompare(b.variant) || sourceClass(a).localeCompare(sourceClass(b)) || a.id.localeCompare(b.id));
    document.getElementById('medigap-count').textContent = `${rows.length} of ${result.plans.length} listed rates${compare?' selected for comparison':''}`;
    if (!rows.length) {list.append(el('p','No listed rates match these filters. Try all plan letters or clear the company name.','plans-help'));return;}
    if (compare) {if (trayOn()) document.body.classList.remove('plans-has-tray'); return comparison(list,rows);}
    const groups = effective === 'fit' ? window.DaylightRecommend?.arrange('medigap', rows) : null;
    if (groups) {fitList(list, groups, card, 'rate'); return tray(list);} // D147
    // PG-02: letters only people eligible for Medicare before 2020 can buy stay
    // visible in a separate group when the backend has first-eligibility evidence.
    const open = rows.filter(p => !p.set_aside), aside = rows.filter(p => p.set_aside);
    for (const p of open) list.append(card(p));
    if (aside.length) {
      const d = el('section',null,'plans-group plans-ruled'), s = el('h3');
      s.append(el('span',`Plans C, F and high-deductible F (${aside.length})`,'plans-ruled-title'),
        el('span','Only for people who were eligible for Medicare before January 1, 2020.','plans-ruled-help'));
      d.append(s); for (const p of aside) d.append(card(p)); list.append(d);
    }
    tray(list);
  }
  // D147: backend groups, in order; the set-aside group stays visible.
  function fitList(list, groups, make, noun) {
    for (const g of groups) {
      const count = `${g.rows.length} ${noun}${g.rows.length === 1 ? '' : 's'}`;
      if (g.id === 'excluded') {
        const d = el('section',null,'plans-group plans-ruled'), s = el('h3');
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
    c.append(el('h3',name(p),'plan-name'));
    if (variant === 'all' && letterNote(p.variant)) c.append(el('p',letterNote(p.variant),'plan-facts plan-letter-note'));
    c.append(el('p',`Rating class: ${sourceClass(p)}`,'plan-facts'));
    if (p.select_observed === true) c.append(el('p','Medicare SELECT is marked in this source. Check its network conditions.','plan-rule'));
    const amounts = el('dl',null,'plan-amounts');
    addAmount(amounts,'Listed monthly premium',money(p.monthly_cents)); addAmount(amounts,'Listed annual premium',money(p.annual_cents));
    addAmount(amounts,'Listed policy fee',text(p.policy_fee)); c.append(amounts);
    const actions = el('div',null,'plan-actions'), add = button(chosen.has(p.id)?'Added to compare':'Add to compare',()=>toggle(p),'btn-quiet');
    window.DaylightRecommend?.decorate('medigap', p.id, c); // D147
    add.setAttribute('aria-pressed',String(chosen.has(p.id))); actions.append(add,button('See full details',e=>details(p,e)));
    if (p.monthly_cents != null) {
      const mine = picks.medigap?.id === p.id, use = button(mine ? 'In my monthly total' : 'Use in my monthly total',()=>{picks.medigap = mine ? null : {id:p.id,label:name(p),cents:p.monthly_cents};renderResults();},'btn-secondary');
      use.setAttribute('aria-pressed',String(mine)); actions.append(use);
    }
    c.append(actions); return c;
  }
  const DETAILS = [
    ['Company (legal name)',p=>text(p.company)], ['Listed monthly premium',p=>money(p.monthly_cents)], ['Listed annual premium',p=>money(p.annual_cents)],
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
    if (letterNote(p.variant)) dialog.append(el('p',`${planName(p.variant)}: ${letterNote(p.variant)}`,'sheet-note plan-letter-note'));
    dialog.append(el('p','Listed premium. The insurer confirms the price, any discount and whether it accepts the application.','sheet-note'));
    const section=el('section',null,'sheet-section');
    for(const [label,get] of DETAILS) {const row=el('div',null,'sheet-row'),top=el('div',null,'sheet-row-top');top.append(el('p',label,'sheet-label'),el('p',get(p),'sheet-value'));row.append(top);section.append(row);}
    dialog.append(section); const source=el('details',null,'sheet-more');source.append(el('summary','Source details'),el('p',`CSG Actuarial · requested November 10, 2026 · NAIC ${p.naic}`,'sheet-note'));
    if(p.rating_labels_need_review)source.append(el('p','The source rating/outlook labels need review and are not used to compare insurer quality.','sheet-note'));
    const dl=el('dl');for(const [key,value] of Object.entries(p.source_fields)){dl.append(el('dt',key),el('dd',text(value)));} source.append(dl,el('p',p.source_locator,'sheet-note'));dialog.append(source);
    dialog.addEventListener('close',()=>{activeDialog = null;dialog.remove();if(opener.isConnected)opener.focus();},{once:true}); document.body.append(dialog);dialog.showModal();close.focus();
  }
  window.DaylightMedigap = Object.freeze({render,syncProfile,range,letterNote:v=>LETTER_NOTES[v]||'',selected:()=>[...chosen]});
})();
