/* Internal source-review client. No personal facts, model calls or release action. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const scope={year:2026,state:'FL',county_fips:'12021',category:'medicare_advantage'};
  const el=(tag,value,cls)=>{const node=document.createElement(tag);if(value!==undefined)node.textContent=value;if(cls)node.className=cls;return node;};
  const format=value=>value===null ? 'Unknown (source null)' : typeof value==='object' ? JSON.stringify(value,null,2) : String(value);
  let session,plans=[],snapshot=null,busy=false;
  const selected=new Set();
  async function api(path,payload) {
    const response=await fetch(path,{method:payload?'POST':'GET',credentials:'same-origin',headers:{'Content-Type':'application/json',...(session?{'X-Daylight-CSRF':session.csrf}:{})},...(payload?{body:JSON.stringify(payload)}:{})});
    const value=await response.json();if(!response.ok)throw Error(value.error||'The local research request did not finish.');return value;
  }
  function note(value){$('research-status').textContent=value;}
  function updateControls() {
    $('plan-filter').disabled=busy||!plans.length;
    $('inspect-selected').disabled=busy||!selected.size;
    $('selection-status').textContent=selected.size+' of 3 selected · source order, without a fit score or ranking.';
    for(const checkbox of $('catalog').querySelectorAll('input'))checkbox.disabled=busy||selected.size===3&&!checkbox.checked;
  }
  function catalog() {
    const host=$('catalog');host.replaceChildren();
    const query=$('plan-filter').value.trim().toLocaleLowerCase();
    const visible=plans.filter(plan=>(plan.display_name+' '+plan.offering_id).toLocaleLowerCase().includes(query));
    const wrap=el('div',undefined,'research-table-wrap'),table=el('table',undefined,'research-table research-catalog');
    table.append(el('caption',visible.length+' of '+plans.length+' retained source offerings · 2026, Collier County · not an accepted all-market inventory'));
    const head=el('thead'),tr=el('tr');for(const label of ['Select','Source offering','Published plan type','Output status'])tr.append(el('th',label));head.append(tr);table.append(head);
    const body=el('tbody');
    for(const plan of visible) {
      const row=el('tr'),choice=el('td'),label=el('label'),check=el('input');check.type='checkbox';check.checked=selected.has(plan.offering_id);check.setAttribute('aria-label','Select '+plan.display_name+' '+plan.offering_id);
      check.onchange=()=>{check.checked?selected.add(plan.offering_id):selected.delete(plan.offering_id);updateControls();};label.append(check);choice.append(label);
      const name=el('td',plan.display_name);name.append(el('span',plan.offering_id,'research-identity'));
      row.append(choice,name,el('td',plan.plan_type==null?'Not supplied':format(plan.plan_type)),el('td','Held · research only'));body.append(row);
    }
    table.append(body);wrap.append(table);host.append(wrap);if(!visible.length)host.append(el('p','No retained record matches that name or identity. This does not establish that a plan is unavailable.'));
    updateControls();
  }
  function sourceDetails(value,title='Source-native data and lineage') {
    const details=el('details',undefined,'research-record');details.append(el('summary',title),el('pre',format(value)));return details;
  }
  function recordView(record) {
    const article=el('article',undefined,'research-record');
    article.append(el('h4',record.entity_type+' · '+record.entity_id));
    article.append(el('p','Observed source record · personal applicability unassessed · output held','small'));
    if(record.amount!==null && record.amount!==undefined)article.append(el('p','Source amount: '+format(record.amount)+' · '+format(record.amount_unit)+' · '+format(record.amount_period)+' · '+format(record.amount_basis)));
    if(record.raw_value!==null && record.raw_value!==undefined)article.append(el('p','Source value: '+format(record.raw_value)));
    if(!record.conditions||!Object.keys(record.conditions).length)article.append(el('p','The typed condition object is empty. This does not mean there are no conditions; inspect the native fields, original row and linked source context. Complete offering interpretation remains unreviewed.','small'));
    article.append(sourceDetails(record.source_native_fields,'Complete retained fields for this source record'),sourceDetails(record.conditions,'Retained conditions and context for this record'),sourceDetails({states:record.states,lineage:record.lineage,raw_source_payload:record.raw_source_payload},'Source, status and original row'));
    return article;
  }
  function evidenceLayer(host,detail,layer) {
    const page=detail.evidence_by_layer[layer],section=el('section',undefined,'research-evidence');
    section.append(el('h3',layer==='L03'?'Benefit claims and condition records':'Contract quality observations'),el('p',layer==='L03'?'These are source-scoped claims and predicates. A page is not the complete offering condition inventory or completed semantic verification.':'Quality observations apply at contract grain. They do not verify each plan or personal fit.','small'));
    const records=el('div');for(const record of page.records)records.append(recordView(record));section.append(records);
    let after=page.next_after_entity_id;
    if(!page.records.length)section.append(el('p','No record was returned by this exact selected query. No coverage or quality conclusion follows.'));
    if(page.has_more) {
      const more=el('button','Load the next source records','secondary');more.type='button';
      more.onclick=async()=>{
        more.disabled=true;note('Loading another source page…');
        try {
          const next=await api('/api/research/query',{operation:'inspect',offering_id:detail.plan.offering_id,layers:[layer],limit:10,expected_snapshot_id:snapshot,after_entity_id_by_layer:{[layer]:after}});
          if(next.binding.snapshot_id!==snapshot)throw Error('The source snapshot changed. Load a fresh comparison.');
          const following=next.evidence_by_layer[layer];for(const record of following.records)records.append(recordView(record));after=following.next_after_entity_id;more.hidden=!following.has_more;
          note('Source page loaded. Personal outputs remain held.');
        } catch(error){note(error.message);}finally{more.disabled=false;}
      };
      section.append(more);
    }
    host.append(section);
  }
  function renderComparison(details) {
    const host=$('research-comparison');host.replaceChildren();host.hidden=false;
    host.append(el('h2','Selected source records'),el('p','Compare the same source-native fields. Differences are observations, not personal suitability, eligibility or total-cost findings. All consumer purposes remain held.'));
    const wrap=el('div',undefined,'research-table-wrap'),table=el('table',undefined,'research-table research-comparison-table');
    table.append(el('caption','Research comparison · immutable source order · '+scope.year+' Collier County'));
    const head=el('thead'),titles=el('tr');titles.append(el('th','Source field'));
    for(const detail of details){const th=el('th',detail.plan.display_name);th.scope='col';th.append(el('span',detail.plan.offering_id,'research-identity'));titles.append(th);}head.append(titles);table.append(head);
    const body=el('tbody'),keys=[...new Set(details.flatMap(detail=>Object.keys(detail.plan.source_native_fields)))];
    const cell=(detail,value)=>{const td=el('td');td.append(el('span',detail.plan.display_name+' · '+detail.plan.offering_id,'research-mobile-plan'),el('span',value));return td;};
    for(const key of keys){const row=el('tr'),name=el('th',key.replaceAll('_',' '));name.scope='row';row.append(name);for(const detail of details){const fields=detail.plan.source_native_fields;row.append(cell(detail,Object.hasOwn(fields,key)?format(fields[key]):'Not supplied in this source record'));}body.append(row);}
    for(const [label,get] of [['Retained restrictions and context',detail=>detail.plan.restrictions],['Evidence and acceptance states',detail=>detail.plan.states]]){const row=el('tr'),th=el('th',label);th.scope='row';row.append(th);for(const detail of details)row.append(cell(detail,format(get(detail))));body.append(row);}
    table.append(body);wrap.append(table);host.append(wrap);
    for(const detail of details) {
      const section=el('section');section.append(el('h2',detail.plan.display_name),el('p',detail.plan.offering_id,'small'),sourceDetails({identity:detail.plan.identity,lineage:detail.plan.lineage,identity_bridge:detail.plan.identity_bridge,authority:detail.authority,binding:detail.binding},'Exact identity, source lineage and held authority'));
      const referenceHost=el('section'),referenceButton=el('button','Inspect accepted r4 reference for '+detail.plan.offering_id,'secondary');referenceButton.type='button';
      referenceButton.onclick=async()=>{
        referenceButton.disabled=true;note('Replaying the original reference acceptance checks…');
        try {
          const reference=await api('/api/research/query',{operation:'reference',offering_id:detail.plan.offering_id,year:2026});
          DaylightReference.render(referenceHost,reference,detail.plan.offering_id);
          note('Exact accepted subset loaded with qualifications and evidence. Personal outputs remain held.');
        }catch(error){referenceHost.replaceChildren();note(error.message);}finally{referenceButton.disabled=false;}
      };
      section.append(referenceButton,referenceHost);
      for(const layer of ['L03','L09'])if(detail.evidence_by_layer[layer])evidenceLayer(section,detail,layer);
      host.append(section);
    }
    host.focus({preventScroll:true});host.scrollIntoView({block:'start'});
  }
  $('plan-filter').oninput=catalog;
  $('inspect-selected').onclick=async()=>{
    if(busy||!selected.size)return;busy=true;updateControls();note('Reading the selected source records…');
    try {
      const details=[];
      // Keep requests within the server's bounded concurrency. The source order
      // comes from the catalog, never the order in which checkboxes were clicked.
      for(const plan of plans.filter(item=>selected.has(item.offering_id))) {
        const detail=await api('/api/research/query',{operation:'inspect',offering_id:plan.offering_id,layers:['L02','L03','L09'],limit:5,expected_snapshot_id:snapshot});
        if(detail.status!=='research_only'||detail.binding.snapshot_id!==snapshot)throw Error('The source snapshot changed. Reload the retained catalog.');details.push(detail);
      }
      renderComparison(details);note('Source records loaded. No personal comparison or recommendation was released.');
    }catch(error){note(error.message);}finally{busy=false;updateControls();}
  };
  (async()=>{
    try {
      session=await api('/api/guest/session');const status=await api('/api/research/status');
      if(!status.configured)throw Error('The local PostgreSQL research connection is not enabled for this server.');
      const result=await api('/api/research/query',{operation:'list',scope,limit:100});
      if(result.status!=='research_only'||result.page.has_more||result.plans.length!==result.total)throw Error('The retained catalog was not completely returned.');
      plans=result.plans;snapshot=result.binding.snapshot_id;catalog();note(plans.length+' retained offering identities loaded from PostgreSQL. Consumer outputs remain held.');
    }catch(error){note(error.message);}
  })();
})();
