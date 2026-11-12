/* :8894 Plans page. Transport only: the backend owns profile, facts, holds and
   recommendation results. This view groups, filters and sorts what the backend
   returns; ordering here is never a recommendation and never leaves the page
   except through the existing plans-context-v1 snapshot on a deliberate Send. */
(() => {
  'use strict';
  let api, activate, ask, opts = {}, data, token = null, selected = null, field = null, mode = 'all', query = '', opened = false, matchesShown = false, railOpen = null;
  // D97 filters: personal details save to the profile; the rest only narrow this list.
  let panel = null, premiumMax = 'any', pharmacy = '', zipIndex = null, saving = false;
  // Owner (Nov 8): the workspace opens on the coverage-path page; the plan list is one step in.
  let view = 'paths'; // 'paths' | 'advantage' | 'supplement'
  const benefits = new Set(), content = {};
  const compared = new Set(), filters = {type: 'any', drugs: 'any', sort: 'premium'}, $ = id => document.getElementById(id);
  const WIDE = 1280;
  const HELD = 'Not confirmed yet';
  const LABELS = {
    plan_premium: 'Monthly premium', part_b_reduction: 'Part B giveback each month',
    medical_deductible: 'Medical deductible each year', medical_maximums: 'Most you’d pay in a year for covered medical care',
    part_d_deductible: 'Drug deductible each year', primary_care_in_network: 'Primary care visit',
    specialist_in_network: 'Specialist visit', hospital_in_network: 'Hospital stay, first four days',
    emergency: 'Emergency room visit', urgent: 'Urgent care visit'};
  const GROUPS = [['Monthly costs', ['plan_premium', 'part_b_reduction']],
    ['Yearly limits', ['medical_deductible', 'medical_maximums', 'part_d_deductible']],
    ['Doctor visits', ['primary_care_in_network', 'specialist_in_network']],
    ['Hospital and emergency', ['hospital_in_network', 'emergency', 'urgent']]];
  const REASONS = {CONFIRM_CURRENT_PROFILE: 'Review and confirm your information in the conversation first.'};
  const METRIC_WORDS = {monthly_plan_premium: 'lower monthly premium', in_network_medical_limit: 'lower yearly medical limit'};

  function el(tag, text, cls) {const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n;}
  function button(label, run, cls = 'btn-quiet') {const b = el('button', label, cls); b.type = 'button'; b.onclick = run; return b;}
  function icon(name) {
    const paths = {chevron: 'M9 6l6 6-6 6', back: 'M15 6l-6 6 6 6', check: 'M5 12.5l4.5 4.5L19 7.5', close: 'M6 6l12 12M18 6L6 18',
      plus: 'M12 6v12M6 12h12', caret: 'M7 10l5 5 5-5', pencil: 'M5 19h3.5L18 9.5 14.5 6 5 15.5V19z', bookmark: 'M7 4.5h10v15l-5-3.8-5 3.8z',
      filter: 'M4.5 6h15l-5.8 6.6V18l-3.4 1.6v-7z'};
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    for (const [k, v] of Object.entries({viewBox: '0 0 24 24', width: '20', height: '20', 'aria-hidden': 'true', fill: 'none', stroke: 'currentColor',
      'stroke-width': '2.2', 'stroke-linecap': 'round', 'stroke-linejoin': 'round'})) svg.setAttribute(k, v);
    svg.classList.add('icon');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path'); path.setAttribute('d', paths[name]); svg.append(path); return svg;
  }
  function withIcon(b, name, after = true) {after ? b.append(icon(name)) : b.prepend(icon(name)); return b;}
  function status(text) {const n = $('plans-status'); if (n) n.textContent = text;}
  function readable(code) {return REASONS[code] || code.replaceAll('_', ' ').toLowerCase().replace(/^./, c => c.toUpperCase()) + '.';}
  function amount(text) {const m = /\$([\d,]+(?:\.\d+)?)/.exec(text || ''); return m ? Number(m[1].replaceAll(',', '')) : Infinity;}
  function value(p, key) {return p.fields[key]?.value ?? null;}
  function inNetworkLimit(p) {
    const v = value(p, 'medical_maximums'); if (!v) return null;
    const m = /\$([\d,]+) in network/.exec(v); return m ? '$' + m[1] : (v.match(/\$[\d,]+/) || [v])[0];
  }
  function combinedLimit(p) {const m = /\$([\d,]+) combined/.exec(value(p, 'medical_maximums') || ''); return m ? '$' + m[1] : null;}
  function family(p) {return /PPO/.test(p.type) ? 'PPO' : 'HMO';}
  function typeLine(p) {
    const base = p.type.replace(/\s*[DCI]-SNP$/, '');
    if (base === 'HMO-POS') return 'HMO-POS: a network plan with some out-of-network coverage';
    if (/PPO/.test(base)) return `${base}: see doctors in or out of network; in network costs less`;
    return 'HMO: you use the plan’s network of doctors';
  }
  function drugs(p) {return p.fields.part_d_deductible?.state !== 'not_applicable';}
  function rule(p) {
    const r = p.retained_restrictions, parts = [];
    if (!r.length) return '';
    if (r.some(x => /Dual Eligible/.test(x))) parts.push('people with both Medicare and Medicaid');
    if (r.some(x => /Chronic Condition/.test(x))) {
      const cat = r.find(x => /condition categories/.test(x));
      parts.push('people with certain chronic conditions' + (cat && cat.includes('—') ? ' (' + cat.split('—')[1].trim().toLowerCase() + ')' : ''));
    }
    if (r.some(x => /Institutional/.test(x))) parts.push('people who live in a nursing home or similar facility');
    if (r.some(x => /Erickson/.test(x))) parts.push('residents of an Erickson retirement community');
    return parts.length ? 'For ' + parts.join(', and ') : r.join('; ');
  }
  function openDialog() {return document.querySelector('dialog.plan-sheet[open]');}
  // Round 4 (owner): no inline sharing notice in the chat panel. What Send
  // shares is stated in Privacy & saving.
  function syncContext() {}

  function invalidate(text) {
    data = null; const host = $('plans-panel'); host.replaceChildren(el('h1', 'Refresh your plans view', 'plans-title'));
    const notice = el('p', text, 'plans-notice'); notice.id = 'plans-status'; notice.setAttribute('role', 'status');
    const row = el('div', undefined, 'plans-row');
    row.append(button('Back to my conversation', close, 'btn-secondary'), button('Try again', refresh, 'primary-button'), button('Browse all plans', () => open()));
    host.append(notice, row);
  }
  async function refresh() {
    try {
      data = await api(token ? '/api/plans/workspace' : '/api/plans/catalog', token ? {token} : {});
      // Once Daylight can order plans for this person, open on those matches first.
      if (!matchesShown && data.recommendation?.state === 'supported' && data.recommendation.top_three?.length) {mode = 'recommended'; matchesShown = true;}
      // With a stated priority and published terms available, open on that order
      // (the sort control still offers premium, limit and name).
      else if (!matchesShown && token && data.reference_comparison?.state === 'available' && data.recommendation?.priority_order?.length) {mode = 'costs'; filters.sort = 'costs'; matchesShown = true;}
      render();
    }
    catch (e) {console.error('[Daylight plans]', e); invalidate(e.message + ' Return to the conversation to review your current information.');}
  }
  // Round 5 (owner): Ask Daylight opens as a large panel over the plans at every width.
  function drawer() {return true;}
  function chat(open = true) {
    $('workspace').classList.toggle('chat-closed', !open);
    const t = $('plans-chat-toggle'); if (t) {t.setAttribute('aria-expanded', String(open)); t.textContent = open ? 'Hide chat' : 'Ask Daylight';}
    $('plans-backdrop').hidden = !(open && drawer());
    $('plans-fab').hidden = open || !opened;
    document.body.classList.toggle('plans-chat-open', open);
    if (open) $('message').focus(); else ($('plans-chat-toggle') || $('plans-fab'))?.focus();
  }
  function stage(plan, key) {
    selected = plan.id; field = key;
    ask(`Help me understand ${(LABELS[key] || plan.fields[key].label).toLowerCase()} for ${plan.name}. What is known, and what still needs checking?`);
    openDialog()?.close(); chat(); render();
  }
  function discuss(p) {
    selected = p.id; field = null;
    ask(`Help me understand ${p.name} and its unresolved tradeoffs.`);
    openDialog()?.close(); chat(); render();
  }
  function toggleCompare(p) {
    if (compared.has(p.id)) compared.delete(p.id);
    else if (compared.size < 3) compared.add(p.id);
    else {status('You can compare up to three plans. Remove one to add another.'); return false;}
    if (compared.size < 2 && mode === 'compare') mode = compared.size ? 'compare' : 'all';
    render(); return true;
  }

  function render() {
    if (!data) return;
    window.DaylightRecommend?.update(prof().recommendation); // D147: inert unless the local demo turns it on
    const host = $('plans-panel'), rec = data.recommendation, scope = data.scope || {};
    host.replaceChildren();
    // Order: sticky header (plan kinds, way back), then the page for this view.
    const sticky = el('div', undefined, 'plans-sticky');
    sticky.append(kinds(), withIcon(button('Back to my conversation', close, 'btn-quiet plans-crumb'), 'back', false));
    if (opts.beforeEnroll) sticky.append(button('Before you enroll', () => opts.beforeEnroll(), 'btn-quiet plans-crumb')); // D138
    host.append(sticky); headerOffset();
    if (view === 'part-d') {
      const nav = sticky.querySelector('.plan-kinds');
      nav.scrollLeft = nav.scrollWidth - nav.clientWidth;
    }
    if (view !== 'advantage') document.body.classList.remove('plans-has-tray');
    if (view === 'paths') {renderPaths(host); return;}
    if (view === 'supplement') {renderSupplement(host); return;}
    if (view === 'part-d') {renderPartD(host); return;}
    // Medicare Advantage list: way back to the two paths, title with ZIP / save / chat, one banner, filters, plans.
    host.append(button('Back to the two paths', () => showView('paths'), 'btn-quiet plans-paths-link'));
    const top = el('div', undefined, 'plans-top');
    const title = el('h1', 'Medicare Advantage plans', 'plans-title'); title.tabIndex = -1;
    top.append(title);
    const acts = el('div', undefined, 'plans-head-actions');
    const zip = fieldValue('comparison.scope.zip'), county = fieldValue('comparison.scope.county');
    const where = button(zip ? `${zip} · ${(county?.name || scope.county || '').replace(/ County.*$/, '')}` : 'Add your ZIP', () => togglePanel('zip'), 'btn-quiet plans-zip');
    where.append(iconPencil()); where.setAttribute('aria-label', zip ? `ZIP ${zip}. Change ZIP code` : 'Add your ZIP code');
    const saveBtn = button('Save progress', () => opts.privacy?.(), 'btn-quiet plans-save'); saveBtn.append(iconBookmark());
    acts.append(where, saveBtn);
    top.append(acts);
    const chatOpen = !$('workspace').classList.contains('chat-closed');
    const toggle = button(chatOpen ? 'Hide chat' : 'Ask Daylight', () => chat($('workspace').classList.contains('chat-closed')), 'btn-secondary plans-chat-toggle');
    toggle.prepend(el('span', undefined, 'sun-mark'));
    toggle.id = 'plans-chat-toggle'; toggle.setAttribute('aria-controls', 'composer'); toggle.setAttribute('aria-expanded', String(chatOpen));
    acts.append(toggle); host.append(top);
    if (data.profile_binding && !rec.scope_supported) host.append(el('p', `Your information asks about ${data.profile_binding.scope.year}. These plans do not match that year and county yet.`, 'plans-year'));

    if (rec.state !== 'supported' && mode !== 'compare' && !reviewedHandoff()) {
      const line = el('p', 'To have plans checked against your situation, finish the review in your conversation. ', 'plans-help plans-review-line');
      line.append(button('Continue my conversation', close, 'btn-quiet')); host.append(line);
    }
    else if (rec.state !== 'supported' && mode !== 'compare') {
      // Owner direction (Nov 8, 2026): once the person has answered the questions,
      // no reason-code warning. The banner says plainly what Daylight does with the
      // list (orders published terms by the priority they stated) and offers the
      // remaining questions only while some are still open. Reason codes stay in
      // the data for diagnostics; they are never the reader's text.
      const banner = el('section', undefined, 'plans-banner'); banner.setAttribute('aria-labelledby', 'plans-banner-title');
      const words = el('div'); const h = el('h2'); h.id = 'plans-banner-title';
      const open = (prof().readiness?.missing || []).length;
      const ref = data.reference_comparison || {};
      const first = METRIC_WORDS[rec.priority_order?.[0]], second = METRIC_WORDS[rec.priority_order?.[1]];
      if (!token) {
        h.textContent = 'Want plans checked against your situation?';
        words.append(h, el('p', 'Answer a few questions here or in your conversation, confirm them, and Daylight ranks plans by what matters to you.'));
      } else if (first && ref.state === 'available') {
        h.textContent = rec.priority_source === 'confirmed' ? 'Ordered by what you chose' : 'Ordered by what you told Daylight';
        const unranked = (ref.unranked_ids || []).length;
        words.append(h, el('p', `${first.charAt(0).toUpperCase() + first.slice(1)} first${second ? ', then ' + second : ''}. ${ref.ordered_ids.length} plans ordered by their published terms${unranked ? `; ${unranked} without a published value stay unranked, not worse` : ''}. This is a comparison of published terms, not a personal recommendation; doctor, medicine and joining checks are in each plan’s details.`));
      } else if (first) {
        h.textContent = 'Ordered by what you told Daylight';
        words.append(h, el('p', `${first.charAt(0).toUpperCase() + first.slice(1)} first${second ? ', then ' + second : ''}. The published terms for this county and year are not available to order yet.`));
      } else {
        h.textContent = 'Tell Daylight what matters more';
        words.append(h, el('p', 'Choose below whether a lower monthly premium or a lower yearly medical limit comes first, and Daylight orders the plans by their published terms.'));
      }
      const bActs = el('div', undefined, 'banner-actions');
      if (!token || open) bActs.append(button(open && token ? `Answer ${open} open ${open === 1 ? 'question' : 'questions'}` : 'Check plans for me', checkFlow, 'primary-button'));
      bActs.append(button('Continue my conversation', close, 'btn-quiet'));
      banner.append(words, bActs);
      host.append(banner);
    }
    if (token) {
      const pr = el('div', undefined, 'plans-row plans-priorities'), label = el('label', rec.priority_source === 'derived_from_conversation' ? 'What matters more to you? (from your conversation)' : 'What matters more to you?', 'plans-field'), select = el('select'); select.id = 'plan-priorities';
      for (const [v, t] of [['', 'Choose one'], ['monthly_plan_premium,in_network_medical_limit', 'Lower monthly premium first'], ['in_network_medical_limit,monthly_plan_premium', 'Lower yearly medical limit first']]) {const o = el('option', t); o.value = v; select.append(o);}
      select.value = rec.priority_order.join(','); label.append(select);
      pr.append(label, button(rec.priority_source === 'confirmed' ? 'Confirmed' : 'Confirm', async () => {if (!select.value) return; try {data = await api('/api/plans/priorities', {token, order: select.value.split(','), confirmed: true}); render();} catch (e) {status(e.message);}}, 'btn-secondary'));
      host.append(pr, el('p', 'These two costs do not measure total spending. Doctor, medicine and eligibility checks stay separate.', 'plans-help'));
    }
    const fitSummary = window.DaylightRecommend?.summary('advantage', Object.fromEntries(data.plans.map(p => [p.id, p.name])));
    if (fitSummary) host.append(fitSummary); // D147
    const notice = el('p', '', 'plans-notice'); notice.id = 'plans-status'; notice.setAttribute('role', 'status'); host.append(notice);

    // Tabs: no tab ever reads (0).
    const tabs = el('div', undefined, 'plans-tabs'); tabs.setAttribute('role', 'group'); tabs.setAttribute('aria-label', 'Plan views');
    const tab = (label, target) => {const b = button(label, () => {mode = target; render();}, 'plans-tab'); b.setAttribute('aria-pressed', String(mode === target || (target === 'all' && mode === 'costs'))); return b;};
    tabs.append(tab(`All plans (${data.plans.length})`, 'all'));
    if (rec.state === 'supported' && rec.top_three.length) tabs.append(tab(`Your top ${rec.top_three.length}`, 'recommended'));
    if (compared.size) tabs.append(tab(`Compare (${compared.size})`, 'compare'));
    if (tabs.children.length > 1) host.append(tabs);
    if (mode !== 'compare' && mode !== 'recommended') {host.append(pillBar()); if (panel) host.append(renderPanel());}
    // Results layout: filters in a left column, results with a sort bar on the right.
    const browsing = mode !== 'compare' && mode !== 'recommended';
    const layout = el('div', undefined, browsing ? 'plans-layout' : 'plans-layout no-rail'), main = el('div', undefined, 'plans-main');
    if (browsing) {
      layout.append(rail());
      const bar = el('div', undefined, 'plans-resultbar'), count = el('p', '', 'plans-result-count'); count.id = 'plans-result-count'; count.setAttribute('aria-live', 'polite');
      bar.append(count, sortControl()); main.append(bar);
    }
    const list = el('div'); list.id = 'plans-list'; main.append(list, about());
    layout.append(main); host.append(layout);
    document.body.classList.toggle('plans-has-tray', compared.size > 0);
    renderCards(); syncContext();
  }

  // The conversation's Review your info step produces a handoff; only then is
  // "Check plans for me" offered here. Until then, the review belongs in the chat.
  function reviewedHandoff() {return !!(token || prof().handoff);}
  function showView(next) {view = next;render(); scrollTo({top: 0}); $('plans-panel').querySelector('h1')?.focus?.();}
  function headerOffset() {
    const header = document.querySelector('.site-header'), host = $('plans-panel');
    if (header && host) host.style.setProperty('--plans-header-h', header.offsetHeight + 'px');
  }
  // Two ways to get Medicare. Bullets are sentences from the reviewed public
  // teaching copy in teaching-facts.json (ids original, advantage, medigap); no new claims.
  const PATHS = [
    {id: 'original', title: 'Original Medicare, with Medigap and a Part D drug plan', view: 'supplement', action: 'See Medigap and Part D options',
      source: 'https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/your-coverage-options',
      points: ['Parts A and B together, run by the federal government and accepted by any U.S. doctor who takes Medicare.',
        'You can add separate drug coverage (Part D) and may be able to buy a Medigap policy for certain A/B costs.',
        'Medigap is a private policy that helps pay your share of costs under Original Medicare. Drug coverage is separate.']},
    {id: 'advantage', title: 'Medicare Advantage', view: 'advantage', action: 'See Medicare Advantage plans',
      source: 'https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/your-coverage-options',
      points: ['Medicare hospital and medical coverage through a private insurance company’s plan instead of Original Medicare.',
        'Most plans include drug coverage. Doctors, costs, and rules vary by plan.',
        'The Part B premium still applies; some plans help pay all or part of it.']}];
  function toldSoFar() {
    const parts = [], zip = fieldValue('comparison.scope.zip'), county = fieldValue('comparison.scope.county');
    if (zip) parts.push(`ZIP ${zip}${county?.name ? ' (' + county.name + ')' : ''}`);
    const current = fieldValue('coverage.current'), codes = Array.isArray(current) ? current : typeof current === 'string' ? current.split(',') : [];
    const labels = codes.map(c => c.trim()).filter(Boolean).map(c => (content.T05?.options || []).find(o => o[0] === c)?.[1] || c);
    if (labels.length) parts.push('current coverage: ' + labels.join(', '));
    const docs = names('needs.providers').length, meds = names('needs.medications').length;
    if (docs) parts.push(`${docs} doctor${docs === 1 ? '' : 's'} added`);
    if (meds) parts.push(`${meds} medicine${meds === 1 ? '' : 's'} added`);
    return parts;
  }
  function renderPaths(host) {
    const h = el('h1', 'Two ways to get Medicare', 'plans-title'); h.tabIndex = -1; host.append(h);
    const R = window.DaylightRecommend; // D147: evaluation-only sorting
    host.append(el('p', R?.active() ? 'Choose a path to see what is available. Daylight’s tiered sorting is on for evaluation.'
      : 'Choose a path to see what is available. Nothing here is a recommendation.', 'plans-lede'));
    const fitSummary = R?.summary('path', Object.fromEntries(PATHS.map(p => [p.id, p.title]))); if (fitSummary) host.append(fitSummary);
    const cards = el('div', undefined, 'path-cards');
    for (const p of PATHS) {
      const card = el('section', undefined, 'path-card'), title = el('h2', p.title); title.id = 'path-' + p.id; card.setAttribute('aria-labelledby', title.id);
      const list = el('ul', undefined, 'path-points'); for (const text of p.points) list.append(el('li', text));
      const src = el('a', 'Medicare.gov source', 'path-source'); src.href = p.source; src.target = '_blank'; src.rel = 'noopener noreferrer';
      card.append(title, list, src, button(p.action, () => showView(p.view), 'btn-secondary path-action'));
      R?.decorate('path', p.id, card, src, 'Suggested path for what you told Daylight'); cards.append(card);
    }
    host.append(cards);
    const told = toldSoFar();
    if (told.length) host.append(el('p', 'What you’ve told us: ' + told.join(' · ') + '.', 'plans-help plans-told'));
    const notice = el('p', '', 'plans-notice'); notice.id = 'plans-status'; notice.setAttribute('role', 'status'); host.append(notice);
  }
  function renderSupplement(host) {
    host.append(button('Back to the two paths', () => showView('paths'), 'btn-quiet plans-paths-link'));
    const medigap = el('section',undefined,'medigap-workspace'); host.append(medigap);
    window.DaylightMedigap.render(medigap, {request:api, profile:prof().medigap, context:prof().visit,
      conversation:async id => {
        if (!await opts.medigapConversation(id)) {
          status('The conversation could not open. Your details and draft are kept; try Talk to Daylight again.');
          return;
        }
        $('current').setAttribute('tabindex','-1');
        close('current');
        const current = $('current'), reading = $('reading');
        reading.scrollTop += current.getBoundingClientRect().top - reading.getBoundingClientRect().top - 18;
        scrollTo({top:0});
      }});
    // D138: Original Medicare is one journey. Offer the drug-plan step here.
    if (prof().partD?.status === 'ready') host.append(button('Next: see Part D drug plans', () => showView('part-d'), 'btn-secondary'));
    const notice = el('p', '', 'plans-notice'); notice.id = 'plans-status'; notice.setAttribute('role', 'status'); host.append(notice);
  }

  function renderPartD(host) {
    host.append(button('Back to the two paths', () => showView('paths'), 'btn-quiet plans-paths-link'));
    const partD = el('section',undefined,'part-d-workspace'); host.append(partD);
    window.DaylightPartD.render(partD, {request:api, profile:prof().partD, context:prof().visit,
      prescriptionPreview: opts.prescriptionPreview ? openPrescriptionPreview : null,
      conversation:async id => {
        if (!await opts.partDConversation(id)) {
          status('The conversation could not open. Your details and draft are kept; try again.'); return;
        }
        $('current').setAttribute('tabindex','-1'); close('current');
        const current = $('current'), reading = $('reading');
        reading.scrollTop += current.getBoundingClientRect().top - reading.getBoundingClientRect().top - 18;
        scrollTo({top:0});
      }});
    if (prof().medigap?.status === 'ready') host.append(button('Back to Medigap prices', () => showView('supplement'), 'btn-secondary'));
    const notice = el('p', '', 'plans-notice'); notice.id = 'plans-status'; notice.setAttribute('role', 'status'); host.append(notice);
  }

  function openPrescriptionPreview(plan) {
    if (!opts.prescriptionPreview(plan))
      status('Open the current conversation before checking fictional prescription costs.');
  }

  function rail() {
    const aside = el('aside', undefined, 'plans-rail'); aside.setAttribute('aria-label', 'Filter plans');
    const box = el('details', undefined, 'rail-box');
    if (railOpen === null) railOpen = innerWidth >= 900;
    box.open = railOpen; box.addEventListener('toggle', () => {railOpen = box.open;});
    box.append(el('summary', 'Filter plans', 'rail-title'));
    const search = el('label', 'Plan or company name', 'plans-field plans-search'), input = el('input'); input.type = 'search'; input.id = 'plans-search'; input.value = query;
    input.autocomplete = 'off'; input.oninput = () => {query = input.value; renderCards(); clearState();}; search.append(input); box.append(search);
    const group = (legend, key, options) => {
      const fs = el('fieldset', undefined, 'rail-group'); fs.append(el('legend', legend));
      for (const [v, t] of options) {
        const row = el('label', undefined, 'rail-option'), r = el('input'); r.type = 'radio'; r.name = 'rail-' + key; r.value = v; r.checked = filters[key] === v;
        r.onchange = () => {filters[key] = v; renderCards(); clearState();}; row.append(r, el('span', t)); fs.append(row);
      }
      return fs;
    };
    box.append(group('Drug coverage', 'drugs', [['any', 'Either'], ['yes', 'Includes drug coverage'], ['no', 'No drug coverage']]));
    const clear = button('Clear filters', () => {query = ''; filters.type = 'any'; filters.drugs = 'any'; premiumMax = 'any'; benefits.clear(); render();}, 'btn-quiet rail-clear'); clear.id = 'rail-clear';
    box.append(clear); aside.append(box, yourDetails());
    queueMicrotask(clearState); return aside;
  }
  function clearState() {const c = $('rail-clear'); if (c) c.hidden = !(query.trim() || filters.type !== 'any' || filters.drugs !== 'any' || premiumMax !== 'any' || benefits.size);}
  // D147: with evaluation sorting on, it is the default order until the person picks another.
  let sortTouched = false;
  function fitReady() {return !!window.DaylightRecommend?.tab('advantage');}
  function sortChoice() {
    if (mode === 'costs') return 'costs';
    if (!sortTouched && fitReady()) return 'fit';
    return filters.sort === 'fit' && !fitReady() ? 'premium' : filters.sort;
  }
  function sortControl() {
    const wrap = el('label', 'Sort by', 'plans-sort'), s = el('select'); s.id = 'plans-sort';
    for (const [v, t] of [...(fitReady() ? [['fit', 'Daylight’s sorting (evaluation)']] : []),
      ['premium', 'Lowest monthly premium'], ['limit', 'Lowest yearly limit'], ['name', 'Plan name, A to Z'],
      ...(data.reference_comparison?.state === 'available' ? [['costs', 'Published cost order']] : [])]) {const o = el('option', t); o.value = v; s.append(o);}
    s.value = sortChoice();
    s.onchange = () => {sortTouched = true; mode = s.value === 'costs' ? 'costs' : 'all'; filters.sort = s.value; renderCards();};
    wrap.append(s); return wrap;
  }

  // ---------- D97: filters, your details and the check-plans flow ----------
  const BENEFITS = {
    giveback: {label: 'Part B giveback', test: p => {const v = value(p, 'part_b_reduction'); return !!v && !/no reduction/i.test(v);}},
    zero_deductible: {label: '$0 medical deductible', test: p => amount(value(p, 'medical_deductible')) === 0},
    zero_primary: {label: '$0 primary care visits', test: p => /^\$0(?![\d.,\-–])/.test(value(p, 'primary_care_in_network') || '')},
    drug_cover: {label: 'Includes drug coverage', test: p => drugs(p)}};
  const PANEL_TITLES = {zip: 'Your ZIP code', doctors: 'Doctors and hospitals', drugs: 'Prescription drugs', pharmacy: 'Your pharmacy',
    premium: 'Monthly premium', benefits: 'Plan benefits', type: 'Plan type', year: 'Plan year'};
  function iconPencil() {return icon('pencil');}
  function iconBookmark() {return icon('bookmark');}
  function prof() {return opts.profile ? opts.profile() : {fields: {}, facts: {}, provenance: {}, readiness: null, busy: false};}
  function fieldValue(name) {
    const f = prof().fields[name];
    return f && !['stale', 'unknown', 'deferred', 'skipped', 'conflicting'].includes(f.status) ? f.value : null;
  }
  function names(name) {const v = fieldValue(name); return typeof v === 'string' ? v.split(/;\s*/).map(x => x.trim()).filter(Boolean) : [];}
  function profileYear() {return prof().facts?.RC03?.value?.year || null;}
  function sourceTag(ref) {
    const m = prof().provenance[ref]?.method;
    if (!m) return null;
    return el('p', m === 'plans_filter' ? 'Added on the Plans page · saved to your profile' : 'From your conversation', 'pill-source');
  }
  function count(test) {return data.plans.filter(test).length;}

  async function save(id, fields, words, quiet = false) {
    if (!opts.answer || saving) return false;
    if (prof().busy) {status('Daylight is finishing another step. Try again in a moment.'); return false;}
    saving = true; if (!quiet) status('Saving…');
    try {
      const ok = await opts.answer(id, fields, words);
      if (!ok) {status('That was not saved. Your entry is still here; please try again.'); return false;}
      if (token) {
        // A ranked view is bound to the details it was built from.
        token = null; matchesShown = false; if (mode === 'recommended') mode = 'all';
        await refresh(); status('Your details changed. Choose “Check plans for me” to update the ranking.');
      } else {render(); if (!quiet) status('Saved to your profile.');}
      return true;
    } finally {saving = false;}
  }

  function kinds() {
    const nav = el('nav', undefined, 'plan-kinds'); nav.setAttribute('aria-label', 'Plan types');
    for (const [label,target] of [['Medicare Advantage','advantage'],['Medicare Supplement (Medigap)','supplement'],['Part D drug plans','part-d']]) {
      const tab = button(label,()=>showView(target),view === target ? 'plan-kind current' : 'plan-kind');
      if (view === target) tab.setAttribute('aria-current','page'); nav.append(tab);
    }
    return nav;
  }

  function pillBar() {
    const bar = el('div', undefined, 'plans-pills'); bar.setAttribute('role', 'group'); bar.setAttribute('aria-label', 'Filters and your details');
    const docs = names('needs.providers'), meds = names('needs.medications');
    const pill = (key, label, n, add) => {
      const b = button('', () => togglePanel(key), 'pill' + (n ? ' pill-on' : '') + (panel === key ? ' pill-open' : ''));
      if (add) b.append(icon('plus'));
      b.append(el('span', label));
      if (n) b.append(el('span', String(n), 'pill-count')); else if (!add) b.append(icon('caret'));
      b.setAttribute('aria-expanded', String(panel === key)); b.setAttribute('aria-controls', 'plans-pill-panel');
      return b;
    };
    const all = button('', () => {railOpen = true; panel = null; render(); $('plans-search')?.focus();}, 'pill pill-all');
    all.append(icon('filter'), el('span', 'All filters'));
    bar.append(all,
      pill('doctors', docs.length ? 'Doctors' : 'Add doctors', docs.length, !docs.length),
      pill('drugs', meds.length ? 'Rx drugs' : 'Add Rx drugs', meds.length, !meds.length),
      pill('pharmacy', pharmacy ? 'Pharmacy' : 'Add pharmacy', pharmacy ? 1 : 0, !pharmacy),
      pill('premium', 'Monthly premium', premiumMax !== 'any' ? 1 : 0),
      pill('benefits', 'Plan benefits', benefits.size),
      pill('type', 'Plan type', filters.type !== 'any' ? 1 : 0),
      pill('year', `Year: ${(data.scope || {}).year || 2026}`, 0));
    return bar;
  }
  function togglePanel(key) {
    panel = panel === key ? null : key; render();
    requestAnimationFrame(() => {
      const box = $('plans-pill-panel');
      if (box) {box.scrollIntoView({block: 'nearest'}); box.querySelector('input:not([disabled]),button:not(.pill-close)')?.focus();}
    });
  }
  function teach(learn, id, ask_, extra) {
    const q = content[id] || {};
    learn.append(el('h3', 'Why it matters'));
    if (q.why) learn.append(el('p', q.why.replace(/^Why we ask:\s*/, '')));
    for (const line of [].concat(extra || [])) learn.append(el('p', line));
    if (q.teach) {const d = el('details'); d.append(el('summary', 'Good to know'), el('p', q.teach)); learn.append(d);}
    const b = button('Ask Daylight about this', () => {ask(ask_); chat();}, 'btn-secondary'); b.prepend(el('span', undefined, 'sun-mark')); learn.append(b);
  }
  function renderPanel() {
    const box = el('section', undefined, 'pill-panel'); box.id = 'plans-pill-panel'; box.setAttribute('aria-labelledby', 'pill-panel-title');
    const head = el('div', undefined, 'pill-panel-head'), h = el('h2', PANEL_TITLES[panel]); h.id = 'pill-panel-title';
    const x = withIcon(button('Close', () => {panel = null; render();}, 'btn-quiet pill-close'), 'close', false);
    head.append(h, x); box.append(head);
    const body = el('div', undefined, 'pill-panel-body'), learn = el('aside', undefined, 'pill-panel-learn');
    ({zip: zipPanel, doctors: (b, l) => listPanel(b, l, 'T06'), drugs: (b, l) => listPanel(b, l, 'T07'), pharmacy: pharmacyPanel,
      premium: premiumPanel, benefits: benefitsPanel, type: typePanel, year: yearPanel})[panel](body, learn);
    box.append(body, learn);
    box.addEventListener('keydown', e => {if (e.key === 'Escape') {e.stopPropagation(); panel = null; render();}});
    return box;
  }
  function radios(body, legend, name, options, current, onPick) {
    const fs = el('fieldset', undefined, 'rail-group pill-group'); fs.append(el('legend', legend));
    for (const [v, t, disabled] of options) {
      const row = el('label', undefined, 'rail-option'), r = el('input'); r.type = 'radio'; r.name = name; r.value = v; r.checked = current === v; r.disabled = !!disabled;
      r.onchange = () => onPick(v); row.append(r, el('span', t)); if (disabled) row.classList.add('disabled'); fs.append(row);
    }
    body.append(fs); return fs;
  }

  async function lookupCounties(zip) {
    if (!zipIndex) {try {zipIndex = (await (await fetch('/zip-counties.json')).json()).zips;} catch {zipIndex = {};}}
    return zipIndex[zip] || [];
  }
  function zipPanel(body, learn) {
    const form = el('form', undefined, 'pill-add'), label = el('label', 'ZIP code', 'plans-field'), input = el('input');
    input.inputMode = 'numeric'; input.maxLength = 5; input.autocomplete = 'postal-code'; input.value = fieldValue('comparison.scope.zip') || ''; label.append(input);
    const countyWrap = el('div'); const go = el('button', 'Save ZIP', 'btn-secondary'); go.type = 'submit';
    form.append(label, countyWrap, go); body.append(form);
    const src = sourceTag('guide.comparison.scope.zip'); if (src) body.append(src);
    let choice = null;
    const check = async () => {
      countyWrap.replaceChildren(); choice = null;
      if (!/^\d{5}$/.test(input.value)) return;
      const rows = await lookupCounties(input.value);
      if (rows.length > 1) {
        const l = el('label', 'County', 'plans-field'), sel = el('select');
        for (const [fips, name, st] of rows) {const o = el('option', `${name}, ${st}`); o.value = fips; sel.append(o);}
        choice = rows[0][0]; sel.onchange = () => {choice = sel.value;}; l.append(sel); countyWrap.append(l);
      } else if (!rows.length) countyWrap.append(el('p', 'We couldn’t find that ZIP. Check the five digits.', 'pill-note'));
    };
    input.oninput = check; check();
    form.onsubmit = async e => {
      e.preventDefault(); const zip = input.value.trim();
      if (!/^\d{5}$/.test(zip)) {status('Enter a five-digit ZIP code.'); return;}
      const rows = await lookupCounties(zip); if (!rows.length) {status('We couldn’t find that ZIP. Check the five digits.'); return;}
      const fips = choice || rows[0][0];
      if (await save('T03', {zip, ...(rows.length > 1 ? {county: fips} : {})}, `From Plans: ZIP ${zip}`))
        status(fips === '12021' ? 'ZIP saved to your profile.' : 'ZIP saved. Plans for that area aren’t loaded yet, so you’re still seeing Collier County plans.');
    };
    teach(learn, 'T03', 'Why does my ZIP code matter when comparing Medicare plans?');
  }

  async function removeName(id, name, gone) {
    const rest = names(name).filter(n => n !== gone), none = id === 'T06' ? 'none' : 'no';
    if (!await save(id, {choice: none}, `From Plans: removed ${gone}`, true)) return;
    if (rest.length) await save(id, {text: rest.join('; ')}, `From Plans: ${rest.join('; ')}`, true);
    status(`Removed ${gone}.`);
  }
  function listPanel(body, learn, id) {
    const doctors = id === 'T06', name = doctors ? 'needs.providers' : 'needs.medications', list = names(name);
    if (list.length) {
      const ul = el('ul', undefined, 'pill-list');
      for (const n of list) {const li = el('li'); li.append(el('span', n), button('Remove', () => removeName(id, name, n), 'btn-quiet')); ul.append(li);}
      body.append(ul); const src = sourceTag('guide.' + name); if (src) body.append(src);
    }
    const form = el('form', undefined, 'pill-add'), label = el('label', doctors ? 'Doctor, practice or hospital' : 'Medicine name and strength', 'plans-field'), input = el('input');
    input.autocomplete = 'off'; input.placeholder = doctors ? 'For example: Dr. Maria Lopez, Naples' : 'For example: Lisinopril 10 mg; metformin 500 mg';
    label.append(input); const add = el('button', 'Add', 'btn-secondary'); add.type = 'submit'; form.append(label, add); body.append(form);
    body.append(el('p', doctors ? 'Add one at a time, or several separated by semicolons.' : 'Add one at a time, or several separated by semicolons or commas.', 'pill-note'));
    form.onsubmit = async e => {
      e.preventDefault();
      // Several names at once; each Add extends the list, never replaces it.
      const have = new Set(list.map(n => n.toLowerCase()));
      const items = input.value.split(doctors ? /\s*[;\n]\s*/ : /\s*[;,\n]\s*/).map(x => x.trim()).filter(x => x && !have.has(x.toLowerCase()));
      if (!items.length) {status(input.value.trim() ? 'Already on your list.' : 'Enter a name first.'); return;}
      if (await save(id, {text: items.join('; ')}, '')) {status(`Added ${items.join(', ')}.`); requestAnimationFrame(() => $('plans-pill-panel')?.querySelector('.pill-add input')?.focus());}
    };
    if (!list.length && fieldValue(doctors ? 'needs.providersStatus' : 'needs.medicinesStatus') !== (doctors ? 'none' : 'no'))
      body.append(button(doctors ? 'I have no doctors to check' : 'I don’t take prescriptions', () => save(id, {choice: doctors ? 'none' : 'no'}, doctors ? 'From Plans: No doctors to check' : 'From Plans: No prescriptions'), 'btn-quiet pill-none'));
    body.append(el('p', doctors ? 'Plan networks aren’t checked yet, so each plan shows your doctors as “not checked”.'
      : 'Drug coverage isn’t checked yet, so each plan shows your prescriptions as “not checked”.', 'pill-note'));
    teach(learn, id, doctors ? 'Why do my doctors matter when choosing a Medicare plan, and how do networks work?' : 'How do my prescriptions affect which Medicare plan fits me?');
  }
  function pharmacyPanel(body, learn) {
    if (!names('needs.medications').length) {
      body.append(el('p', 'Add a prescription first. Daylight keeps the pharmacy with each prescription.', 'pill-note'),
        button('Add Rx drugs', () => togglePanel('drugs'), 'btn-secondary'));
    } else {
      const form = el('form', undefined, 'pill-add'), label = el('label', 'Pharmacy name and location', 'plans-field'), input = el('input');
      input.value = pharmacy; input.placeholder = 'For example: Publix Pharmacy, Pine Ridge Rd'; label.append(input);
      const add = el('button', 'Save', 'btn-secondary'); add.type = 'submit'; form.append(label, add); body.append(form);
      form.onsubmit = e => {e.preventDefault(); pharmacy = input.value.trim(); render(); status(pharmacy ? 'Pharmacy kept for this visit. Daylight will ask which prescriptions you fill there.' : 'Pharmacy cleared.');};
      body.append(el('p', 'No pharmacy directory is connected yet. Enter the exact store or mail service you mean; it stays unverified. It is kept for this visit until you tell Daylight which prescriptions you fill there.', 'pill-note'));
    }
    teach(learn, 'T07', 'Why does my pharmacy matter for Medicare drug costs?');
  }
  function premiumPanel(body, learn) {
    const opt = (v, t) => [v, `${t} (${v === 'any' ? data.plans.length : count(p => amount(value(p, 'plan_premium')) <= Number(v))})`];
    radios(body, 'Show plans with a monthly premium of', 'premium', [opt('any', 'Any amount'), opt('0', '$0'), opt('25', 'Up to $25'), opt('50', 'Up to $50'), opt('100', 'Up to $100')],
      premiumMax, v => {premiumMax = v; render();});
    const q = content.T09;
    if (q?.options?.length) {
      const pref = fieldValue('needs.costPreference'), wrap = el('div', undefined, 'pill-pref');
      wrap.append(el('p', q.question, 'pill-pref-q'));
      const row = el('div', undefined, 'pill-pref-row');
      for (const [v, t] of q.options) {const b = button(t, () => save('T09', {choice: v}, `From Plans: ${t}`), 'choice'); b.setAttribute('aria-pressed', String(pref === v)); row.append(b);}
      wrap.append(row); const src = sourceTag('guide.needs.costPreference'); if (src) wrap.append(src); body.append(wrap);
    }
    teach(learn, 'T09', 'What is a monthly premium, and how should I weigh it against costs when I get care?', 'The filter only narrows this list. Your cost preference is saved to your profile.');
  }
  function benefitsPanel(body, learn) {
    const fs = el('fieldset', undefined, 'rail-group pill-group'); fs.append(el('legend', 'Show plans that have'));
    for (const [k, b] of Object.entries(BENEFITS)) {
      const row = el('label', undefined, 'rail-option'), c = el('input'); c.type = 'checkbox'; c.checked = benefits.has(k);
      c.onchange = () => {c.checked ? benefits.add(k) : benefits.delete(k); render();};
      row.append(c, el('span', `${b.label} (${count(b.test)})`)); fs.append(row);
    }
    body.append(fs, el('p', 'Dental, vision and hearing details aren’t loaded yet.', 'pill-note'));
    teach(learn, null, 'Explain Part B giveback, medical deductibles and primary care copays in Medicare Advantage plans.',
      ['Part B giveback lowers the Part B premium you pay each month. A deductible is what you pay before the plan starts paying. A copay is a set amount per visit.']);
  }
  function typePanel(body, learn) {
    const n = t => count(p => family(p) === t);
    radios(body, 'Plan type', 'ptype', [['any', `All types (${data.plans.length})`], ['HMO', `HMO and HMO-POS (${n('HMO')})`], ['PPO', `PPO (${n('PPO')})`]],
      filters.type, v => {filters.type = v; render();});
    teach(learn, null, 'What is the difference between an HMO and a PPO Medicare Advantage plan?',
      ['HMO: you use the plan’s network of doctors. HMO-POS: a network plan with some out-of-network coverage. PPO: see doctors in or out of network; in network costs less.']);
  }
  function yearPanel(body, learn) {
    const year = String((data.scope || {}).year || 2026);
    radios(body, 'Coverage year', 'pyear', [[year, `${year} plans`], ['2027', '2027 plans · coming soon', true]], year, () => {});
    if (profileYear() !== year) body.append(button(`Use ${year} for my comparison`, () => save('RC03', {year}, `From Plans: ${year}`), 'btn-secondary'));
    else {const src = sourceTag('readiness.RC03.profile.year'); body.append(el('p', `Your comparison year is ${year}.`, 'pill-note')); if (src) body.append(src);}
    teach(learn, 'RC03', 'Why do Medicare plan benefits and prices change from year to year?');
  }

  function yourDetails() {
    const box = el('details', undefined, 'rail-box rail-details'); box.open = innerWidth >= 900;
    const h = el('summary', undefined, 'rail-title'); h.append(el('span', 'Your details')); box.append(h);
    let added = 0;
    const dl = el('dl');
    const row = (label, val, ref, key) => {
      const d = el('div', undefined, 'detail-row'), dd = el('dd');
      dd.append(el('span', val || 'Not added', val ? 'detail-val' : 'detail-val empty')); if (val) added++;
      const m = ref && prof().provenance[ref]?.method;
      if (val && m === 'plans_filter') dd.append(el('span', 'Added on the Plans page', 'detail-tag'));
      d.append(el('dt', label), dd, button(val ? 'Edit' : 'Add', () => togglePanel(key), 'btn-quiet detail-edit')); dl.append(d);
    };
    const zip = fieldValue('comparison.scope.zip'), county = fieldValue('comparison.scope.county');
    row('ZIP', zip ? `${zip}${county?.name ? ' · ' + county.name : ''}` : '', 'guide.comparison.scope.zip', 'zip');
    row('Plan year', profileYear() || '', 'readiness.RC03.profile.year', 'year');
    row('Doctors', names('needs.providers').join('; ') || (fieldValue('needs.providersStatus') === 'none' ? 'None to check' : ''), 'guide.needs.providers', 'doctors');
    row('Prescriptions', names('needs.medications').join('; ') || (fieldValue('needs.medicinesStatus') === 'no' ? 'None' : ''), 'guide.needs.medications', 'drugs');
    row('Pharmacy', pharmacy, null, 'pharmacy');
    const pref = fieldValue('needs.costPreference');
    row('Cost preference', pref ? (content.T09?.options || []).find(o => o[0] === pref)?.[1] || pref : '', 'guide.needs.costPreference', 'premium');
    if (added) h.append(el('span', `${added} added`, 'detail-count'));
    box.append(dl, el('p', 'Saved to your profile. Details entered here are confirmed with you if you chat with Daylight.', 'pill-note'));
    return box;
  }
  function personalChecks() {
    const docs = names('needs.providers'), meds = names('needs.medications');
    if (!docs.length && !meds.length && !pharmacy) return null;
    const box = el('p', undefined, 'plan-checks');
    const add = text => {const s = el('span', undefined, 'check-item'); s.append(el('span', undefined, 'check-dot'), text); box.append(s);};
    if (docs.length) add(`${docs.length === 1 ? 'Your doctor' : `Your ${docs.length} doctors`}: not checked yet`);
    if (meds.length) add(`${meds.length === 1 ? 'Your prescription' : `Your ${meds.length} prescriptions`}: not checked yet`);
    if (pharmacy) add('Your pharmacy: not checked yet');
    return box;
  }

  // ---------- Check plans for me: the existing review checkpoint, no AI call ----------
  async function checkFlow() {
    if (!['compare', 'review'].includes(fieldValue('intent.goal'))) {
      if (!await save('T01', {choice: 'compare'}, 'From Plans: Find coverage', true)) return;
    }
    openCheck();
  }
  function openCheck() {
    openDialog()?.close();
    const d = el('dialog', undefined, 'plan-sheet check-sheet'); d.setAttribute('aria-labelledby', 'check-title');
    const fill = () => {
      d.replaceChildren();
      const head = el('div', undefined, 'sheet-head'), h = el('h2', 'Check plans against your situation'); h.id = 'check-title';
      const x = withIcon(button('Close', () => d.close()), 'close', false); x.classList.add('sheet-close'); head.append(h, x); d.append(head);
      const r = prof().readiness, missing = r?.missing || [];
      d.append(el('p', 'Daylight ranks plans from these details. You can leave a detail open where it says so. Nothing here uses AI.', 'sheet-note'));
      if (r?.criteria?.length) {
        const done = r.criteria.length - missing.length, bar = el('div', undefined, 'check-progress');
        bar.append(el('span', `${done} of ${r.criteria.length} done`)); const pg = el('progress'); pg.max = r.criteria.length; pg.value = done; bar.append(pg); d.append(bar);
      }
      if (r?.canReview) {
        const ready = el('section', undefined, 'sheet-section check-ready');
        ready.append(el('h3', 'You’re ready'), el('p', 'Review your details once, then Daylight ranks plans by what matters to you.', 'sheet-note'),
          button('Review and confirm', async () => {d.close(); chat(true); await opts.review?.();}, 'primary-button'));
        d.append(ready);
      }
      for (const m of missing) d.append(questionBlock(m, fill));
    };
    fill();
    d.addEventListener('close', () => d.remove(), {once: true});
    d.addEventListener('click', e => {if (e.target === d) d.close();});
    document.body.append(d); d.showModal(); d.querySelector('button,input')?.focus();
  }
  function questionBlock(m, refresh_) {
    const id = m.question_id, q = content[id] || {}, sec = el('section', undefined, 'sheet-section check-q');
    sec.append(el('h3', q.question || m.label));
    if (q.why) sec.append(el('p', q.why.replace(/^Why we ask:\s*/, ''), 'sheet-note'));
    const answer = async (fields, words) => {if (await save(id, fields, `From Plans: ${words}`, true)) refresh_();};
    if (id === 'T03') {
      const f = el('form', undefined, 'pill-add'), l = el('label', 'ZIP code', 'plans-field'), i = el('input'); i.inputMode = 'numeric'; i.maxLength = 5; i.value = fieldValue('comparison.scope.zip') || '';
      const b = el('button', 'Save', 'btn-secondary'); b.type = 'submit'; l.append(i); f.append(l, b); sec.append(f);
      f.onsubmit = async e => {e.preventDefault(); const rows = await lookupCounties(i.value.trim()); if (!rows.length) {status('Check the five-digit ZIP.'); return;}
        await answer({zip: i.value.trim(), ...(rows.length > 1 ? {county: rows[0][0]} : {})}, `ZIP ${i.value.trim()}`);};
    } else if (id === 'RC03') {
      const row = el('div', undefined, 'pill-pref-row');
      row.append(button(String((data.scope || {}).year || 2026), () => answer({year: String((data.scope || {}).year || 2026)}, String((data.scope || {}).year || 2026)), 'choice'));
      sec.append(row);
    } else if (id === 'T06' || id === 'T07') {
      const f = el('form', undefined, 'pill-add'), l = el('label', id === 'T06' ? 'Doctor, practice or hospital' : 'Medicine name and strength', 'plans-field'), i = el('input');
      const b = el('button', 'Add', 'btn-secondary'); b.type = 'submit'; l.append(i); f.append(l, b); sec.append(f);
      f.onsubmit = e => {e.preventDefault(); if (i.value.trim()) answer({text: i.value.trim()}, i.value.trim());};
      sec.append(button(id === 'T06' ? 'No doctors to check' : 'No prescriptions', () => answer({choice: id === 'T06' ? 'none' : 'no'}, id === 'T06' ? 'No doctors to check' : 'No prescriptions'), 'btn-quiet'));
    } else if (q.multi) {
      const fs = el('fieldset', undefined, 'rail-group pill-group'), picked = new Set();
      fs.append(el('legend', q.max ? `Choose up to ${q.max}` : 'Choose all that apply'));
      for (const [v, t] of q.options || []) {
        const row = el('label', undefined, 'rail-option'), c = el('input'); c.type = 'checkbox';
        c.onchange = () => {if (c.checked && q.max && picked.size >= q.max) {c.checked = false; return;} c.checked ? picked.add(v) : picked.delete(v);};
        row.append(c, el('span', t)); fs.append(row);
      }
      const go = button('Save', () => {if (picked.size) answer({choice: [...picked].join(',')}, (q.options || []).filter(o => picked.has(o[0])).map(o => o[1]).join(', '));}, 'btn-secondary');
      sec.append(fs, go);
    } else {
      const row = el('div', undefined, 'pill-pref-row');
      for (const [v, t] of q.options || []) row.append(button(t, () => answer({choice: v}, t), 'choice'));
      sec.append(row);
    }
    return sec;
  }

  function sorted(plans) {
    const byName = (a, b) => a.name.localeCompare(b.name);
    if (mode === 'costs') {const ids = data.reference_comparison.ordered_ids; return plans.sort((a, b) => (ids.includes(a.id) ? ids.indexOf(a.id) : 999) - (ids.includes(b.id) ? ids.indexOf(b.id) : 999));}
    if (filters.sort === 'name') return plans.sort(byName);
    const metric = filters.sort === 'limit' ? p => amount(inNetworkLimit(p)) : p => amount(value(p, 'plan_premium'));
    return plans.sort((a, b) => (metric(a) - metric(b)) || byName(a, b));
  }

  function renderCards() {
    if (!data) return; const list = $('plans-list'); list.replaceChildren();
    if (mode === 'compare') return renderCompare(list);
    if (mode === 'recommended') {
      const best = data.recommendation.top_three.map(id => data.plans.find(p => p.id === id)).filter(Boolean);
      const first = {monthly_plan_premium: 'lower monthly premium', in_network_medical_limit: 'lower yearly medical limit'}[data.recommendation.priority_order?.[0]];
      list.append(el('h2', `Your top ${best.length}`, 'plans-compare-title'),
        el('p', `In order of what you said matters most${first ? ': ' + first + ' first' : ''}. Doctor, medicine and joining checks are listed in each plan’s details.`, 'plans-help'));
      best.forEach((p, n) => list.append(card(p, n + 1))); return tray(list);
    }
    const q = query.trim().toLowerCase();
    const shown = sorted(data.plans.filter(p => (!q || `${p.id} ${p.name}`.toLowerCase().includes(q))
      && (filters.type === 'any' || family(p) === filters.type)
      && (filters.drugs === 'any' || (filters.drugs === 'yes') === drugs(p))
      && (premiumMax === 'any' || amount(value(p, 'plan_premium')) <= Number(premiumMax))
      && [...benefits].every(b => BENEFITS[b].test(p))));
    const joinable = shown.filter(p => !p.retained_restrictions.length), ruled = shown.filter(p => p.retained_restrictions.length);
        const count = $('plans-result-count');
    if (count) count.textContent = shown.length < data.plans.length ? `${shown.length} of ${data.plans.length} plans match` : `${data.plans.length} plans`;
    // D147: evaluation-only groups from the backend replace the joining-rule split.
    const fitGroups = (mode === 'all' || mode === 'costs') ? window.DaylightRecommend?.arrange('advantage', shown) : null;
    if (fitGroups) {
      if (!shown.length) list.append(el('p', 'No plans match these choices. Try “Any type” or clear the search.', 'plans-help'));
      const fit = sortChoice() === 'fit';
      for (const g of fitGroups) {
        const rows = fit ? g.rows : sorted(g.rows);
        if (g.id === 'excluded') {
          const d = el('details', undefined, 'plans-group plans-ruled'); d.open = !!q || rows.some(p => p.id === selected || compared.has(p.id));
          const s = el('summary'); s.append(el('span', `${g.label} (${rows.length})`, 'plans-ruled-title'),
            el('span', 'Set aside by who can join or by something you need. Each plan shows why.', 'plans-ruled-help'));
          d.append(s); rows.forEach(p => d.append(card(p))); list.append(d); continue;
        }
        const section = el('section', undefined, 'plans-group'), h = el('h2', g.label, 'rec-group-title'); h.id = 'rec-group-' + g.id;
        h.append(el('span', `${rows.length} ${rows.length === 1 ? 'plan' : 'plans'}`, 'rec-count'));
        section.setAttribute('aria-labelledby', h.id); section.append(h); rows.forEach(p => section.append(card(p))); list.append(section);
      }
      return tray(list);
    }
    const section = el('section', undefined, 'plans-group'); section.setAttribute('aria-labelledby', 'group-open');
    const h = el('h2', `Plans most people can join (${joinable.length})`); h.id = 'group-open'; section.append(h);
    if (!joinable.length) section.append(el('p', 'No plans match these choices. Try “Any type” or clear the search.', 'plans-help'));
    joinable.forEach(p => section.append(card(p))); list.append(section);
    if (ruled.length) {
      const d = el('details', undefined, 'plans-group plans-ruled'); d.open = !!q || ruled.some(p => p.id === selected || compared.has(p.id));
      const s = el('summary'); s.append(el('span', `Plans with joining rules (${ruled.length})`, 'plans-ruled-title'),
        el('span', 'For people with both Medicare and Medicaid, certain chronic conditions, a nursing-home stay, or who live in an Erickson community.', 'plans-ruled-help'));
      d.append(s); ruled.forEach(p => d.append(card(p))); list.append(d);
    }
    tray(list);
  }

  function card(p, rank = 0) {
    const c = el('article', undefined, 'plan-card'); c.dataset.planId = p.id; c.dataset.selected = String(p.id === selected);
    const nameId = 'name-' + p.id.replaceAll(':', '-'); c.setAttribute('aria-labelledby', nameId);
    const name = el('h3', undefined, 'plan-name'); name.id = nameId;
    if (rank) {c.classList.add('plan-ranked'); const badge = el('span', undefined, 'plan-rank'); badge.append(el('span', 'Number ', 'sr-only'), String(rank)); name.append(badge, el('span', ': ', 'sr-only'));}
    name.append(p.name); c.append(name);
    const facts = el('p', undefined, 'plan-facts');
    facts.append(el('span', typeLine(p)), el('span', drugs(p) ? 'Includes drug coverage' : 'No drug coverage', drugs(p) ? 'fact-yes' : 'fact-no'));
    c.append(facts);
    const r = rule(p); if (r) {const n = el('p', undefined, 'plan-rule'); n.append(el('strong', 'Joining rule: '), r + '.'); c.append(n);}
    const amounts = el('dl', undefined, 'plan-amounts');
    const add = (label, v, extra) => {
      const box = el('div', undefined, 'amount');
      box.append(el('dt', label, 'amount-label'), el('dd', v ?? HELD, v ? 'amount-value' : 'amount-value held'));
      if (extra) box.append(el('dd', extra, 'amount-extra')); amounts.append(box);
    };
    add('Monthly premium', value(p, 'plan_premium'));
    const combined = combinedLimit(p);
    add('Most you’d pay in a year, in network', inNetworkLimit(p), combined ? `${combined} if you also use out-of-network care` : null);
    const giveback = value(p, 'part_b_reduction');
    if (giveback && !/no reduction/i.test(giveback)) add('Part B giveback each month', giveback);
    else add('Medical deductible each year', value(p, 'medical_deductible'));
    c.append(amounts);
    const fitted = window.DaylightRecommend?.plan('advantage', p.id); // D147: its checks replace the generic not-checked line
    const checks = fitted ? null : personalChecks(); if (checks) c.append(checks);
    window.DaylightRecommend?.decorate('advantage', p.id, c);
    const actions = el('div', undefined, 'plan-actions');
    const cmp = button(compared.has(p.id) ? 'Added to compare' : 'Add to compare', () => toggleCompare(p), 'btn-secondary');
    cmp.setAttribute('aria-pressed', String(compared.has(p.id))); if (compared.has(p.id)) withIcon(cmp, 'check', false);
    actions.append(cmp, withIcon(button('See full details', () => details(p)), 'chevron'));
    if (opts.prescriptionPreview && drugs(p) && p.id.startsWith('2026:'))
      actions.append(button('Check fictional drug costs', () => openPrescriptionPreview(p)));
    c.append(actions); return c;
  }

  function tray(list) {
    if (!compared.size) return;
    const bar = el('div', undefined, 'compare-tray'); bar.setAttribute('role', 'region'); bar.setAttribute('aria-label', 'Plans to compare');
    const names = [...compared].map(id => data.plans.find(p => p.id === id)?.name).filter(Boolean);
    const words = el('p'); words.append(el('strong', `${compared.size} ${compared.size === 1 ? 'plan' : 'plans'} selected`), el('span', names.join(' · '), 'tray-names'));
    if (compared.size < 2) words.append(el('span', 'Add one more plan to compare side by side.', 'tray-names'));
    const go = button('Compare', () => {mode = 'compare'; render(); scrollTo({top: 0}); $('plans-panel').scrollTop = 0;}, 'primary-button');
    go.disabled = compared.size < 2;
    const acts = el('div', undefined, 'tray-actions'); acts.append(button('Clear', () => {compared.clear(); render();}), go);
    bar.append(words, acts); list.append(bar);
  }

  function rowsFor(plans) {
    const keys = Object.keys(plans[0].fields), seen = new Set(), groups = [];
    for (const [title, ks] of GROUPS) {const present = ks.filter(k => keys.includes(k)); present.forEach(k => seen.add(k)); if (present.length) groups.push([title, present]);}
    const rest = keys.filter(k => !seen.has(k)); if (rest.length) groups.push(['Other details', rest]);
    return groups;
  }
  function renderCompare(list) {
    const plans = [...compared].map(id => data.plans.find(p => p.id === id)).filter(Boolean);
    list.append(withIcon(button('Back to all plans', () => {mode = 'all'; render();}), 'back', false));
    const intro = el('div', undefined, 'compare-head');
    intro.append(el('h2', `Comparing ${plans.length} ${plans.length === 1 ? 'plan' : 'plans'}`, 'plans-compare-title'));
    if (plans.length > 1) intro.append(button('Ask Daylight about these plans', () => {selected = null; field = null; ask('What are the main differences between the plans I’m comparing?'); chat();}, 'btn-secondary'));
    list.append(intro);
    list.append(el('p', plans.length > 1 ? 'Each column is one plan. Shaded rows are where they differ.' : 'Add another plan from All plans to compare side by side.', 'plans-help'));
    const wrap = el('div', undefined, 'plans-compare'), table = el('table'), head = el('tr'), same = [];
    const cap = el('caption', `Costs for ${plans.map(p => p.name).join(' and ')}`, 'sr-only'); table.append(cap);
    const corner = el('th', 'Plan'); corner.scope = 'col'; head.append(corner);
    for (const p of plans) {
      const th = el('th'); th.scope = 'col';
      th.append(el('span', p.name, 'compare-name'), el('span', p.type, 'compare-type'), button('Remove', () => toggleCompare(p)));
      head.append(th);
    }
    const thead = el('thead'); thead.append(head); table.append(thead);
    for (const [title, keys] of rowsFor(plans)) {
      const body = el('tbody'), g = el('tr', undefined, 'compare-group'), gh = el('th', title); gh.colSpan = plans.length + 1; gh.scope = 'colgroup'; g.append(gh); body.append(g);
      let rows = 0;
      for (const key of keys) {
        const values = plans.map(p => p.fields[key]?.value ?? HELD), label = LABELS[key] || plans[0].fields[key].label;
        if (plans.length > 1 && values.every(v => v === values[0])) {same.push([label, values[0]]); continue;}
        const tr = el('tr', undefined, plans.length > 1 ? 'differs' : ''), th = el('th', label); th.scope = 'row'; tr.append(th);
        values.forEach(v => tr.append(el('td', v, v === HELD ? 'held' : ''))); body.append(tr); rows++;
      }
      if (rows) table.append(body);
    }
    if (same.length) {
      const body = el('tbody', undefined, 'compare-same-rows'), g = el('tr', undefined, 'compare-group'), gh = el('th', `The same for ${plans.length === 2 ? 'both' : 'all ' + plans.length} plans`);
      gh.colSpan = plans.length + 1; gh.scope = 'colgroup'; g.append(gh); body.append(g);
      for (const [label, v] of same) {
        const tr = el('tr', undefined, 'same'), th = el('th', label); th.scope = 'row'; tr.append(th);
        const td = el('td', v, v === HELD ? 'held' : ''); td.colSpan = plans.length; tr.append(td); body.append(tr);
      }
      table.append(body);
    }
    wrap.append(table); list.append(wrap);
  }

  function details(p) {
    openDialog()?.close();
    selected = p.id; field = null; renderCards(); syncContext();
    const d = el('dialog', undefined, 'plan-sheet'); d.setAttribute('aria-labelledby', 'sheet-title');
    const head = el('div', undefined, 'sheet-head'), title = el('h2', p.name); title.id = 'sheet-title';
    const closeBtn = withIcon(button('Close', () => d.close()), 'close', false); closeBtn.classList.add('sheet-close');
    head.append(title, closeBtn); d.append(head);
    const facts = el('p', undefined, 'plan-facts'); facts.append(el('span', typeLine(p)), el('span', drugs(p) ? 'Includes drug coverage' : 'No drug coverage', drugs(p) ? 'fact-yes' : 'fact-no')); d.append(facts);
    const r = rule(p); if (r) {const n = el('p', undefined, 'plan-rule'); n.append(el('strong', 'Joining rule: '), r + '. Daylight has not checked whether you qualify.'); d.append(n);}
    const acts = el('div', undefined, 'plans-row');
    const cmp = button(compared.has(p.id) ? 'Remove from compare' : 'Add to compare', () => {if (toggleCompare(p)) cmp.textContent = compared.has(p.id) ? 'Remove from compare' : 'Add to compare';}, 'btn-secondary');
    acts.append(button('Ask Daylight about this plan', () => discuss(p), 'primary-button'), cmp); d.append(acts);
    for (const [titleText, keys] of rowsFor([p])) {
      const sec = el('section', undefined, 'sheet-section'); sec.append(el('h3', titleText));
      for (const key of keys) {
        const cell = p.fields[key], row = el('div', undefined, 'sheet-row'), top = el('div', undefined, 'sheet-row-top');
        const lab = el('div'); lab.append(el('p', LABELS[key] || cell.label, 'sheet-label'));
        if (LABELS[key] && LABELS[key] !== cell.label) lab.append(el('p', 'Official term: ' + cell.label, 'sheet-official'));
        top.append(lab, el('p', cell.value ?? HELD, cell.value == null ? 'sheet-value held' : 'sheet-value')); row.append(top);
        for (const c of cell.conditions) row.append(el('p', c, 'sheet-note'));
        if (cell.value == null && cell.state !== 'not_applicable' && cell.reason_codes.length) row.append(el('p', 'Why it is not confirmed: ' + cell.reason_codes.map(x => x.replaceAll('_', ' ').toLowerCase()).join('; ') + '.', 'sheet-note'));
        row.append(button('Ask about this', () => {d.close(); stage(p, key);}));
        sec.append(row);
      }
      d.append(sec);
    }
    const checks = data.recommendation.plans?.find(row => row.id === p.id)?.checks;
    if (checks) {
      const sec = el('section', undefined, 'sheet-section'); sec.append(el('h3', 'Checks still needed for you'));
      for (const [key, check] of Object.entries(checks)) sec.append(el('p', `${key.replaceAll('_', ' ')}: ${check.state.replaceAll('_', ' ')}${check.reason_codes.length ? ' · ' + check.reason_codes.join(', ').replaceAll('_', ' ').toLowerCase() : ''}`, 'sheet-note'));
      d.append(sec);
    }
    const ex = el('details', undefined, 'sheet-more'); ex.append(el('summary', 'Example costs (made-up situations, not your spending)'));
    for (const e of Object.values(p.examples)) ex.append(el('p', `${e.label}: ${e.amount ? '$' + Number(e.amount.amount).toLocaleString('en-US', {maximumFractionDigits: 2}) : HELD + (e.reason_codes.length ? ' (' + e.reason_codes.join(', ').replaceAll('_', ' ').toLowerCase() + ')' : '')}`, 'sheet-note'));
    ex.append(el('p', 'Assumes 12 premium months, four ordinary covered in-network primary care visits, or one covered in-network hospital admission of three or four counted days. Required referral and authorization are assumed, with no assistance adjustment and enough room below the medical spending limit. Excludes discharge day, transfers, readmissions and separately billed professional services. These are separate cost pieces, not a combined yearly estimate.', 'sheet-note'));
    d.append(ex);
    const fine = el('details', undefined, 'sheet-more'); fine.append(el('summary', 'Fine print'));
    fine.append(el('p', `Plan ID ${p.id} · ${p.type}`, 'sheet-note'), el('p', 'Listed in published data. Daylight has not verified that this plan is available to you.', 'sheet-note'));
    if (p.retained_restrictions.length) fine.append(el('p', 'Published restrictions: ' + p.retained_restrictions.join('; ') + '.', 'sheet-note'));
    d.append(fine);
    d.addEventListener('close', () => {
      d.remove();
      [...document.querySelectorAll('[data-plan-id]')].find(n => n.dataset.planId === p.id)?.querySelector('.plan-actions .btn-quiet')?.focus();
    }, {once: true});
    d.addEventListener('click', e => {if (e.target === d) d.close();});
    document.body.append(d); d.showModal(); closeBtn.focus();
  }

  function about() {
    const d = el('details', undefined, 'plans-about'); d.append(el('summary', 'About this plan data'));
    const scope = data.scope || {}, dated = scope.landscape_data_date ? new Date(scope.landscape_data_date + 'T12:00:00').toLocaleDateString('en-US', {month: 'long', day: 'numeric', year: 'numeric'}) : null;
    d.append(el('p', `${scope.year} plans from Medicare’s public plan data${dated ? ', dated ' + dated : ''}. ${window.DaylightRecommend?.active() ? 'Daylight’s tiered sorting is on for evaluation; the other sort choices only change the order.' : 'The list is not ranked for you; sorting only changes the order.'}${scope.year === 2026 ? ' 2027 plans are not loaded yet.' : ''}`));
    d.append(el('p', `“${HELD}” means the published data didn’t settle that amount yet. Ask Daylight about it, or check with the plan.`));
    d.append(el('p', data.notice));
    const cov = data.coverage;
    if (cov) d.append(el('p', `${cov.usable_reference_fields} of ${cov.prepared_fields} plan amounts are ready to show; ${cov.material_held_fields} are not confirmed yet. Availability has been verified for ${cov.verified_availability} plans.`));
    if (data.reference_comparison?.limitation) d.append(el('p', data.reference_comparison.limitation));
    for (const def of Object.values(data.definitions || {})) d.append(el('h3', def.title), el('p', def.text));
    return d;
  }

  async function open(handoff = null, target = null) {
    // After the conversation's review has produced a handoff, open straight on
    // the checked list; every other open starts on the two coverage paths.
    // D138: when the conversation is about Medigap or Part D, open that tab.
    // The person asked for it; Medicare Advantage stays one click away.
    const asked = target || {medigap: 'supplement', drug_pricing: 'part-d'}[prof().task] || null;
    token = handoff?.token || null; opened = true; view = asked || (token ? 'advantage' : 'paths'); activate();
    const ws = $('workspace'); document.body.classList.add('plans-page'); ws.classList.add('plans-open'); ws.classList.toggle('chat-closed', drawer());
    $('plans-backdrop').hidden = true; $('plans-fab').hidden = false; $('plans-tab').setAttribute('aria-current', 'page');
    $('plans-panel').hidden = false; $('plans-panel').replaceChildren(el('p', 'Loading plans…', 'plans-lede'));
    const notice = el('p'); notice.id = 'plans-status'; notice.setAttribute('role', 'status'); $('plans-panel').append(notice);
    await refresh(); scrollTo({top: 0}); return !!data;
  }
  function close(focusId = 'message') {
    opened = false; openDialog()?.close(); $('workspace').classList.remove('plans-open', 'chat-closed'); document.body.classList.remove('plans-page');
    $('plans-panel').hidden = true; $('plans-backdrop').hidden = true; $('plans-fab').hidden = true; document.body.classList.remove('plans-chat-open', 'plans-has-tray'); $('plans-tab').removeAttribute('aria-current');
    if (focusId === 'current') $('current').focus({preventScroll:true}); else $('message').focus();
  }
  function snapshot() {
    if (!opened || !data || ['supplement','part-d'].includes(view)) return null;
    const visible = [...document.querySelectorAll('[data-plan-id]')].filter(n => {const r = n.getBoundingClientRect(); return r.height && r.bottom > 0 && r.top < innerHeight;}).map(n => n.dataset.planId).slice(0, 12);
    return {version: 'plans-context-v1', reviewToken: token, viewDigest: data.view_digest, visibleIds: visible, comparedIds: [...compared], selectedId: selected, field, mode};
  }
  window.DaylightPlans = Object.freeze({init(options) {
    api = options.request; activate = options.activate; ask = options.ask; opts = options;
    // D147: evaluation-only sorting results arrive after the page renders; draw them when they do.
    window.DaylightRecommend?.configure(api);
    window.DaylightRecommend?.onChange(() => {if (opened && data && !openDialog() && !saving) render();});
    // Reviewed question wording, reasons and teaching notes explain each filter.
    Promise.all([fetch('/baseline-content.json').then(r => r.json()), fetch('/readiness-content.json').then(r => r.json())]).then(([base, rc]) => {
      for (const q of base) content[q.id] = {question: q.question, why: q.why, teach: q.teach, options: q.options, multi: q.multi, max: q.max};
      for (const t of rc.triggers || []) content[t.id] = {question: t.question, why: t.why, teach: '', options: t.choices || [], multi: false};
      if (opened && data) render();
    }).catch(() => {});
    $('plans-tab').disabled = false; $('plans-tab').onclick = () => open(); DaylightPlansHandoff.register(handoff => open(handoff));
    const head = el('div', undefined, 'plans-chat-head'), name = el('p', 'Ask Daylight', 'plans-chat-title');
    const closeButton = withIcon(button('Close', () => chat(false)), 'close', false); closeButton.classList.add('plans-close-chat');
    head.append(name, closeButton); document.querySelector('.chat-workspace').prepend(head);
    const backdrop = el('div', undefined, 'plans-backdrop'); backdrop.id = 'plans-backdrop'; backdrop.hidden = true; backdrop.onclick = () => chat(false); document.body.append(backdrop);
    const fab = button('Ask Daylight', () => chat(true), 'plans-fab'); fab.id = 'plans-fab'; fab.hidden = true; fab.setAttribute('aria-controls', 'composer');
    fab.prepend(el('span', undefined, 'sun-mark')); document.body.append(fab);
    addEventListener('resize', () => {if (opened) {$('plans-backdrop').hidden = !(drawer() && !$('workspace').classList.contains('chat-closed')); headerOffset();}});
    document.addEventListener('keydown', e => {
      if (opened && e.key === 'Escape' && !openDialog()) chat(false);
      if (opened && drawer() && !$('workspace').classList.contains('chat-closed') && e.key === 'Tab') {
        const nodes = [...document.querySelectorAll('.chat-workspace button,.chat-workspace textarea,.chat-workspace select,.chat-workspace a')].filter(n => !n.disabled && n.getClientRects().length);
        if (e.shiftKey && document.activeElement === nodes[0]) {e.preventDefault(); nodes.at(-1)?.focus();}
        else if (!e.shiftKey && document.activeElement === nodes.at(-1)) {e.preventDefault(); nodes[0]?.focus();}
      }
    });
  }, snapshot,
  afterTurn(result) {
    if (!opened) return;
    if (['supplement','part-d'].includes(view) && !saving) {render(); return;}
    if (result.plansContext?.profile_changed) invalidate('Your information changed. Return to the conversation and review it before continuing.');
    else if (result.generated?.code === 'plans_evidence_changed') invalidate('The plan data changed. Try again to load the latest.');
    else if (data && result.plansContext && (result.plansContext.view_digest !== data.view_digest || result.plansContext.selected_id !== selected || result.plansContext.focused_field !== field)) status('This reply is about the plans you were viewing when you pressed Send.');
    else if (data && !saving && !openDialog()) render();
  }, close,
  // D138: the conversation can open a ready tab directly.
  openView(target) {return ['paths', 'advantage', 'supplement', 'part-d'].includes(target) ? open(null, target) : open();}});
})();
