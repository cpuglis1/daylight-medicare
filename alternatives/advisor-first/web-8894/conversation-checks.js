/* D154: render one server-owned next question in the existing conversation. */
(() => {
  'use strict';
  let staged = null;
  const money = new Intl.NumberFormat('en-US', {style:'currency',currency:'USD'});
  const node = (tag,text,cls) => {
    const item=document.createElement(tag);
    if(text!=null)item.textContent=text;
    if(cls)item.className=cls;
    return item;
  };
  // Shown the way a person writes them (owner, November 13, 2026): "December 1, 2026", "Fort Myers, FL 33901-9311".
  const MONTHS=['January','February','March','April','May','June','July','August','September','October','November','December'];
  const dates = text => String(text ?? '').replace(/\b(\d{4})-(\d{2})-(\d{2})\b/g,(all,y,m,d) => MONTHS[m-1] ? MONTHS[m-1]+' '+Number(d)+', '+y : all);
  const KEEP=new Set(['N','S','E','W','NE','NW','SE','SW','PO','US','MD','DO','PA','NP','II','III','IV']);
  function office(text) {
    text=String(text ?? '');
    if(!text || /[a-z]/.test(text)) return text;   // already written normally
    const parts=text.split(',').map(part => part.trim()).filter(Boolean).map(part => {
      if(/^\d{9}$/.test(part)) return part.slice(0,5)+'-'+part.slice(5);
      if(/^[A-Z]{2}$/.test(part)) return part;
      return part.split(/\s+/).map(word => KEEP.has(word) ? word : /^\d/.test(word) ? word.toLowerCase() : word.charAt(0)+word.slice(1).toLowerCase()).join(' ');
    });
    const zip=parts.length>1 && /^\d{5}(-\d{4})?$/.test(parts.at(-1)) ? parts.pop() : '';
    const place=zip && /^[A-Z]{2}$/.test(parts.at(-1) || '') ? parts.pop()+' '+zip : zip;
    return [...parts,place].filter(Boolean).join(', ');
  }
  // The data layer now sends each office in parts, and says whether it is in the place the person named.
  function officeParts(o) {
    const zip=o.zip5 ? (o.zip4 ? o.zip5+'-'+o.zip4 : o.zip5) : '';
    return [o.line ? office(o.line) : '', o.city ? office(o.city) : '', [o.state,zip].filter(Boolean).join(' ')].filter(Boolean).join(', ');
  }
  function shown(q,row) {
    const candidate=(q.candidates || []).find(item => item.candidate_id===row.value);
    if(candidate) {
      // A match in another town is offered, and says so, whenever some match is in the place the person named.
      const named=(q.candidates || []).some(item => (item.offices || []).some(o => o.place_match));
      const away=named && !(candidate.offices || []).some(o => o.place_match);
      return candidate.label+' — '+(candidate.offices || []).map(officeParts).join('; ')+(away ? ' · different town' : '');
    }
    const site=(q.offices || []).find(item => item.site_id===row.value);
    return site ? officeParts(site) : row.label;
  }
  function button(text,run,cls='text-button') {
    const item=node('button',text,cls);item.type='button';item.addEventListener('click',run);return item;
  }
  function matrixCard(result, editCheck, edit) {
    const section=node('section',null,'conversation-check-result');
    section.append(node('h3',result.name));
    const doctor=result.kind==='doctor_matrix';
    if(doctor) section.append(node('p',officeParts(result.office_parts)),node('p','Date checked: '+dates(result.date)));
    for(const text of result.details || []) section.append(node('p',dates(text),'plans-help'));
    if(!doctor && result.evidence_date) section.append(node('p','CMS drug lists published '+dates(result.evidence_date)+'. Plan rules can change.'));
    const matrix=node('details');
    const entries=Object.values(result.plans).sort((a,b)=>a.name.localeCompare(b.name));
    matrix.append(node('summary',`Check results for ${entries.length} ${doctor?'Medicare Advantage plans':'plans with drug coverage'}`));
    const list=node('ul');
    for(const plan of entries) {
      const row=node('li');
      if(doctor) {
        const status={listed_in_network:'Listed in network',in_network:'Confirmed in network',out_of_network:'Confirmed out of network'}[plan.membership]
          || {conflict:'Conflicting evidence',stale:'Listing is out of date'}[plan.state] || 'Network status unresolved';
        row.append(node('p',plan.name+' · '+status+(plan.evidence_dates?.length?' · '+plan.evidence_dates.map(dates).join(', '):'')));
      } else {
        row.append(node('strong',plan.name));
        const meds=node('ul');
        for(const med of plan.medicines) {
          const status={covered:'Listed',not_listed:'Not listed',unknown:'Coverage unresolved',needs_detail:'Exact medicine needed'}[med.state];
          const flags=[['Prior authorization',med.prior_authorization],['Quantity limit',med.quantity_limit],['Step therapy',med.step_therapy]];
          const terms=med.state==='covered'
            ? [med.tier ? 'Tier '+med.tier : 'Tier unavailable', ...flags.map(([label,flag])=>label+': '+(flag==null?'unknown':flag?'yes':'no'))]
            : [];
          meds.append(node('li',[med.name,status,...terms].join(' · ')));
        }
        row.append(meds);
      }
      list.append(row);
    }
    matrix.append(list);
    section.append(matrix);
    if(doctor) {
      section.append(button('Change office',()=>editCheck(result.key,'office')));
      section.append(button('Correct doctor details',()=>edit('doctor')));
    } else {
      section.append(button('Change medicine strength or form',()=>editCheck(result.key,'products')));
      section.append(button('Correct medicine list',()=>edit('medicineList')));
    }
    return section;
  }
  function renderResults(host,results,edit,editCheck,question) {
    for(const result of results || []) {
      if(result.kind==='drug_comparison') {
        const section=node('section',null,'conversation-check-result');
        section.append(node('h3',result.name));
        const entries=Object.values(result.plans);
        const priced=entries.filter(row=>row.state==='offline_average_candidate').length;
        section.append(node('p',`${priced} of ${entries.length} plans have a supported estimate. The others still need checking.`));
        for(const text of result.details || []) section.append(node('p',text,'plans-help'));
        const details=node('details');details.append(node('summary','Compare pharmacy listings and estimates'));
        const list=node('ul');
        for(const row of entries.sort((a,b)=>a.name.localeCompare(b.name))) {
          const item=node('li');item.append(node('strong',row.name));
          item.append(node('p', ['preferred','standard'].includes(row.pharmacy.state)
            ? 'Pharmacy listing: '+row.pharmacy.state : 'Pharmacy participation: unresolved'));
          item.append(node('p',row.state==='offline_average_candidate'
            ? `${money.format(row.plan_premium_plus_drugs_cents/100)} in plan premiums and drug spending · ${dates(row.start)} through ${dates(row.end)}`
            : 'Cost estimate unresolved.'));
          list.append(item);
        }
        details.append(list);section.append(details);
        section.append(button('Correct medicine or pharmacy details',()=>edit('prescription')));
        const edits=node('details');edits.append(node('summary','Edit estimate details'));
        for(const entry of result.editable || []) {
          const labels={quantity:'refill quantity',unit:'quantity unit',days_supply:'days supply',fills:'refill dates',
            pharmacy:'pharmacy location',channel:'pickup or delivery',period:'start month',prior_spending:'earlier spending',assistance:'help with costs',rxcui:'medicine version',outlet_zip:'pharmacy ZIP'};
          edits.append(button('Change '+(labels[entry.field] || entry.field)+(entry.medicine?' for '+entry.medicine:''),
            ()=>editCheck(entry.item?'drug:'+entry.item:'drug',entry.field)));
        }
        if(result.editable?.length) section.append(edits);
        host.append(section);continue;
      }
      if(result.kind==='doctor_matrix' || result.kind==='formulary') {
        host.append(matrixCard(result,editCheck,edit));
        continue;
      }
      if(result.kind==='note') {
        // D157: one plain line on what was left open or not checked; no controls.
        const note=node('section',null,'conversation-check-result conversation-check-note');
        note.setAttribute('aria-label','Not checked');
        note.append(node('h3',result.name));
        for(const text of result.details || []) note.append(node('p',text,'plans-help'));
        host.append(note);
        continue;
      }
      const section=node('section',null,'conversation-check-result');
      section.setAttribute('aria-label', result.kind==='doctor' ? 'Doctor evidence' : 'Prescription estimate');
      section.append(node('h3',result.name));
      if(result.kind==='doctor') {
        // The date is the one the check was run for, not a confirmed start date, so it says so.
        section.append(node('p',result.office_parts ? officeParts(result.office_parts) : office(result.office)),node('p',result.plan+' · date checked: '+dates(result.date)));
      } else {
        section.append(node('p','Estimate for '+dates(result.start)+' through '+dates(result.end)));
        const list=node('dl',null,'plan-amounts');
        for(const [label,key] of [['Drug spending','drug_spending_cents'],['Plan premiums','plan_premium_cents'],['Premiums and drugs','plan_premium_plus_drugs_cents']]) {
          const row=node('div',null,'amount');row.append(node('dt',label,'amount-label'),node('dd',money.format(result.amounts[key]/100),'amount-value'));list.append(row);
        }
        section.append(list);
        if(result.summary) {
          const details=node('details');details.append(node('summary','Details used'));
          details.append(node('p',result.summary.pharmacy));
          const meds=node('ul');
          for(const med of result.summary.medicines) meds.append(node('li',`${med.name} · ${med.quantity} ${med.unit} · ${med.days_supply} days${med.days_supply_assumed?' (assumed)':''} · ${med.fill_count} fills`));
          details.append(meds);section.append(details);
        }
        if(result.editable?.length) {
          const edits=node('details');edits.append(node('summary','Edit estimate details'));
          const labels={rxcui:'medicine version',quantity:'refill quantity',unit:'quantity unit',days_supply:'days supply',fills:'refill dates and order',outlet_zip:'pharmacy ZIP code',pharmacy:'pharmacy location',channel:'pickup or delivery',period:'estimate start month',assistance:'help with drug costs',prior_spending:'earlier spending'};
          for(const entry of result.editable)edits.append(button('Change '+labels[entry.field]+(entry.medicine?' for '+entry.medicine:''),()=>editCheck(entry.item?'drug:'+entry.item:'drug',entry.field)));
          section.append(edits);
        }
      }
      for(const text of result.details || []) section.append(node('p',dates(text),'plans-help'));
      section.append(button(result.kind==='doctor'?'Correct doctor details':'Correct medicine or pharmacy details',()=>edit(result.kind)));
      section.append(button('Change '+(result.kind==='doctor'?'coverage':'drug plan'),()=>editCheck(result.key,'plan')));
      if(result.kind==='doctor') {
        section.append(button('Change date',()=>editCheck(result.key,'date')));
        section.append(button('Change office',()=>editCheck(result.key,'office')));
      }
      if((question?.kind==='drug' && result.kind==='doctor') || (results.length>1 && result!==results.at(-1))) {
        const earlier=node('details');earlier.append(node('summary',result.name+' — '+(result.kind==='doctor'?'doctor evidence':'prescription estimate')),section);host.append(earlier);
      } else host.append(section);
    }
  }
  window.DaylightConversationChecks=Object.freeze({
    clear(){
      staged=null;
      for(const choice of document.querySelectorAll('#conversation-check-choices button')) {
        choice.setAttribute('aria-pressed','false');choice.classList.remove('selected');
      }
      const select=document.getElementById('conversation-check-choice');if(select)select.value='';
    },
    answer(q){return staged?.token===q?.token ? staged : null;},
    render(host,view,{changed,defer,edit,editCheck,back}) {
      renderResults(host,view?.results,edit,editCheck,view?.question);
      const q=view?.question;
      if(!q){staged=null;return false;}
      if(staged?.token!==q.token)staged=null;
      const heading=node('h2',q.question);heading.tabIndex=-1;host.append(heading);
      if(q.why)host.append(node('p',q.why,'why'));
      if(q.choices.length>8) {
        const label=node('label','Choose an answer');label.htmlFor='conversation-check-choice';
        const select=node('select');select.id=label.htmlFor;select.append(new Option('Choose an answer',''));
        q.choices.forEach((row,index)=>select.append(new Option(shown(q,row),String(index))));
        select.value=staged?String(q.choices.findIndex(row=>row.value===staged.value)):'';
        select.addEventListener('change',()=>{const row=q.choices[Number(select.value)];staged=select.value!==''?{token:q.token,value:row.value,label:shown(q,row)}:null;changed();});
        const field=node('div',null,'plans-field');field.append(label,select);host.append(field);
      } else if(q.choices.length) {
        const choices=node('div',null,'choices');choices.id='conversation-check-choices';choices.setAttribute('role','group');choices.setAttribute('aria-label',q.question);
        for(const row of q.choices) {
          const item=button(shown(q,row),()=>{
            staged={token:q.token,value:row.value,label:shown(q,row)};
            for(const other of choices.children) {other.setAttribute('aria-pressed',String(other===item));other.classList.toggle('selected',other===item);}
            changed();
          },'choice');
          item.setAttribute('aria-pressed',String(staged?.value===row.value));item.classList.toggle('selected',staged?.value===row.value);choices.append(item);
        }
        host.append(choices);
      }
      const slot=node('div',null,'chat-selection');slot.id='selection';slot.hidden=!staged;host.append(slot);
      const actions=node('div',null,'conversation-check-actions');
      actions.append(button('Leave this detail open for now',()=>defer(q)));
      if(view.canBack)actions.append(button('Back',back));
      actions.append(button('Edit '+(q.kind==='doctor'?'doctor details':'medicine or pharmacy details'),()=>edit(q.kind)));
      host.append(actions);
      return true;
    }
  });
})();
