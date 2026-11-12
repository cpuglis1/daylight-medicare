/* D87: optional identity preparation. Source choices never become coverage findings. */
(() => {
  'use strict';
  const heldPurposes = ['published_display','personal_comparison','ranking','recommendation','quote','enrollment'];
  const stateLabels = {
    unresolved:'Still needs checking', reported:'Reported, not matched',
    incomplete:'More reported detail is needed', held:'Matching is not available yet',
    stale:'Needs a fresh check after a change', invalidated:'Needs a fresh check after a change',
    explicitly_selected_source_identity:'Identity selected; coverage not checked',
    selected:'Identity selected; coverage not checked',
    source_identity_selected:'Identity selected; coverage not checked',
    ready_for_identity_lookup:'Reported, ready for a possible-match search',
    current_report_details_required:'More reported detail is needed',
    selected_needs_source_recheck:'Identity selection retained; source needs a fresh check',
    stale_identity_needs_fresh_lookup:'Needs a fresh check after a change',
  };
  const strings=value => typeof value === 'string' ? [value] : Array.isArray(value) ? value.filter(part => typeof part === 'string') : [];
  function nameText(value) {
    return (Array.isArray(value) ? value : [value]).map(part => {
      if(typeof part === 'string')return part;
      if(!part || typeof part !== 'object')return '';
      return strings(part.text).join(' ') || ['prefix','given','family','suffix'].flatMap(key => strings(part[key])).join(' ');
    }).filter(Boolean).join(' / ');
  }
  function detailsText(candidate) {
    if(typeof candidate.detail === 'string')return candidate.detail;
    if(typeof candidate.details === 'string')return candidate.details;
    if(candidate.details && typeof candidate.details === 'object')return [
      ['ingredient_strength_description','Source strength'],['dose_form','Source form'],['concept_type','Source concept']
    ].filter(([key]) => typeof candidate.details[key] === 'string' && candidate.details[key])
      .map(([key,label]) => label+': '+candidate.details[key]).join(' · ');
    const address=candidate.site?.address;
    const addresses=Array.isArray(address) ? address : [address];
    return addresses.filter(row => row && typeof row === 'object').map(row =>
      [...strings(row.line),...['city','state','postalCode'].flatMap(key => strings(row[key]))].join(', ')).filter(Boolean).join(' / ')
      || (candidate.kind === 'provider_site' ? 'Office address is incomplete in this source.' : '');
  }
  function model(identity) {
    const capability = identity?.capability || {};
    const internal = capability.state === 'internal_research_available' && capability.audience === 'internal_research';
    const held = Array.isArray(identity?.held_purposes) ? identity.held_purposes : [];
    // Require every held purpose as well as the server-owned audience marker.
    // A malformed response cannot turn a research candidate into a consumer one.
    const sourceVisible = internal && heldPurposes.every(purpose => held.includes(purpose));
    return {
      internal:sourceVisible,
      title:sourceVisible ? 'Review possible identity matches' : 'Your reported medicines and doctors',
      notice:sourceVisible
        ? 'Local research preview. A selected identity does not establish plan coverage, network participation or clinical equivalence.'
        : 'Medicine and doctor matching is not available here yet. Your reported details are preserved, and you can continue your conversation.',
      items:(Array.isArray(identity?.items) ? identity.items : []).filter(item =>
        item && typeof item.item_id === 'string' && ['drug','medicine','drug_product','provider','doctor','provider_site'].includes(item.kind)).map(item => ({
          id:item.item_id, kind:['drug','medicine','drug_product'].includes(item.kind) ? 'drug' : 'provider',
          label:typeof item.reported_label === 'string' && item.reported_label.trim()
            ? item.reported_label : item.reported?.name || item.reported?.practice || (['drug','medicine','drug_product'].includes(item.kind) ? 'Reported medicine' : 'Reported doctor or practice'),
          reportedDetails:['strength','form','city'].filter(key => typeof item.reported?.[key] === 'string')
            .map(key => 'Reported '+key+': '+item.reported[key]).join(' · '),
          state:stateLabels[item.state] || 'Still needs checking',
          searchable:sourceVisible && item.searchable !== false,
          selected:['explicitly_selected_source_identity','selected','source_identity_selected','selected_needs_source_recheck'].includes(item.state),
        })),
      candidates:sourceVisible && typeof identity?.choice_token === 'string'
        ? (Array.isArray(identity.candidates) ? identity.candidates : []).filter(candidate =>
            candidate && typeof candidate.candidate_id === 'string' && nameText(candidate.label).trim()).map(candidate => ({
              id:candidate.candidate_id,label:nameText(candidate.label),kind:candidate.kind,
              details:detailsText(candidate),
              detailsState:candidate.details_state,
              selector:candidate.selector && typeof candidate.selector === 'object' ? candidate.selector : null,
              selectable:candidate.selectable !== false,
              siteLookup:candidate.kind === 'provider_entity' && candidate.site_lookup_available === true,
              periods:candidate.source_periods && typeof candidate.source_periods === 'object' ? candidate.source_periods : null,
              contexts:(Array.isArray(identity.source_contexts) ? identity.source_contexts : []).filter(context =>
                context && Array.isArray(candidate.context_refs) && candidate.context_refs.includes(context.record_ref)),
            })) : [],
      choiceToken:sourceVisible ? identity?.choice_token : null,
      itemId:sourceVisible ? identity?.item_id : null,
      noMatch:sourceVisible && Array.isArray(identity?.candidates) && identity.candidates.length === 0 && !!identity?.source,
      page:sourceVisible ? identity?.page : null,
      partial:sourceVisible && (identity?.partial?.is_partial === true || identity?.page?.is_partial === true
        || identity?.page?.entities_have_more === true || identity?.page?.roles_have_more === true
        || identity?.page?.site_candidates_have_more === true || identity?.page?.has_more === true),
      source:sourceVisible && identity?.source ? {...identity.source,
        site_continuation:identity.page?.site_continuation || identity.source.site_continuation} : null,
      preparation:sourceVisible && Number.isInteger(identity?.preparation?.selected_count) && identity.preparation.selected_count > 0
        ? identity.preparation.selected_count+' source identity selection'+(identity.preparation.selected_count === 1 ? '' : 's')+' retained for this visit. Each needs a live recheck before later use. Coverage findings remain unavailable.' : null,
      selectionMessage:sourceVisible && identity?.state === 'explicitly_selected_source_identity'
        ? 'Your source selection is linked for this visit. Its consistency with your reported details still needs a separate check.' : null,
      omittedTitle:sourceVisible && Array.isArray(identity?.search_basis?.leading_title_omitted_for_discovery_only)
        && identity.search_basis.leading_title_omitted_for_discovery_only.length > 0,
    };
  }
  function render(host,identity,{onSearch,onSelect,onForget,onRefresh,onReturn,onMore,document:doc=globalThis.document}={}) {
    const view=model(identity);
    const el=(tag,text,cls) => {const node=doc.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
    const action=(text,handler,cls='text-button') => {const node=el('button',text,cls);node.type='button';node.onclick=handler;return node;};
    const section=el('section',undefined,'identity-preparation');
    section.append(el('h1',view.title),el('p',view.notice,'identity-notice'));
    if(view.selectionMessage)section.append(el('p',view.selectionMessage,'identity-notice'));
    if(!view.items.length)section.append(el('p','No medicine or doctor details are ready for this check. You can add them in your conversation when they matter.'));
    for(const item of view.items) {
      const row=el('section',undefined,'identity-item');row.append(el('h2',item.label),el('p',item.state,'small'));
      if(item.reportedDetails)row.append(el('p',item.reportedDetails,'small'));
      if(item.searchable)row.append(action('Find possible matches',() => onSearch?.(item)));
      if(item.selected && view.internal)row.append(action('Recheck selected source identity',() => onRefresh?.(item.id)),action('Remove this identity selection',() => onForget?.(item.id)));
      section.append(row);
    }
    if(view.candidates.length) {
      section.append(el('h2','Choose only if the details match'));
      if(view.omittedTitle)section.append(el('p','The name search left out the leading doctor title. Your reported name is unchanged.','small'));
      const list=el('ol',undefined,'identity-candidates');
      for(const candidate of view.candidates) {
        const row=el('li');row.append(el('p',candidate.label,'identity-label'));
        if(candidate.details)row.append(el('p',candidate.details,'small'));
        if(candidate.periods || candidate.contexts.length) {
          const context=el('details',undefined,'sources');context.append(el('summary','Retained source dates and qualifications'));
          context.append(el('p','These are source-native entries, not a current-practice or network verification.','small'));
          context.append(el('pre',JSON.stringify({periods:candidate.periods,context:candidate.contexts},null,2),'identity-source-context'));
          row.append(context);
        }
        if(['partial','source_details_partial','pack_requires_separate_resolution'].includes(candidate.detailsState))row.append(el('p','Some source details are missing or need a separate check.','small'));
        if(candidate.selectable || candidate.siteLookup)row.append(action(candidate.siteLookup ? 'Check this person or practice’s sites' : 'Select this source identity',() => onSelect?.(candidate,view), 'secondary'));
        else row.append(el('p','This source entry cannot yet be selected as an exact identity.','small'));
        list.append(row);
      }
      section.append(list);
    }
    if(view.noMatch)section.append(el('p','No matches were returned for this exact search. That does not establish that a medicine, provider or office is unavailable.'));
    if(view.partial)section.append(el('p','This is a partial source result. Other identities or sites may remain outside this view.','small'));
    if(view.page?.next_after_ordinal != null)section.append(action('Show more possible matches',() => onMore?.(view)));
    if(view.source) {
      const source=el('details',undefined,'sources');source.append(el('summary','Source and limits'));
      source.append(el('p','Retained '+String(view.source.year || '2026')+' source snapshot. Current practice, terminology and plan coverage have not been verified.'));
      if(view.source.site_continuation === 'not_supported_within_selected_window')source.append(el('p','The selected source window has a site limit and cannot continue through every omitted site.'));
      section.append(source);
    }
    if(view.preparation)section.append(el('p',view.preparation,'small'));
    section.append(action('Return to comparison preparation',onReturn));host.append(section);return section;
  }
  function accept(state,response) {
    if(!response || response.continuation !== state.continuation || !response.identity
      || typeof response.identity.capability !== 'object')throw Error('Your conversation changed. Review its latest state.');
    const prior=state.identity;
    state.identity={...response.identity};
    if(!Array.isArray(state.identity.items) && Array.isArray(prior?.items))state.identity.items=prior.items;
    if(response.identity.state === 'explicitly_selected_source_identity' && Array.isArray(state.identity.items)) {
      state.identity.items=state.identity.items.map(item => item.item_id === response.identity.item_id
        ? {...item,state:'selected_needs_source_recheck'} : item);
    }
    state.identityViewOpen=true;return state;
  }
  const api={model,render,accept};
  if(typeof module !== 'undefined' && module.exports)module.exports=api;
  else globalThis.DaylightIdentity=api;
})();
