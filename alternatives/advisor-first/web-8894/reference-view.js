/* The original verifier owns acceptance. This view preserves its exact payload. */
(function(root,factory){
  if(typeof module==='object'&&module.exports)module.exports=factory();
  else root.DaylightReference=factory();
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const format=value=>value===null?'null':typeof value==='object'?JSON.stringify(value,null,2):String(value);
  function render(host,payload,offeringId) {
    const reference=payload.reference;
    if(payload.purpose!=='reference_lookup'||payload.audience!=='internal_research_workspace'||
        reference?.package_id!=='L03-PUBLISHED-COLLIER-2026-bounded-r4'||
        reference.mode!=='accepted_bounded_published_reference'||reference.accepted_for_reference!==true||
        reference.offering?.offering_id!==offeringId||
        !Array.isArray(reference.entries)||!Array.isArray(reference.related_reference_entries)||
        !Array.isArray(reference.holds)||reference.holds.some(hold=>hold.value!==null||hold.state!=='unknown_held')||
        ['published_display','personal_comparison','ranking','recommendation','quote','enrollment'].some(purpose=>payload.authority?.[purpose]?.state!=='held')) {
      throw Error('The exact reference boundary was not returned. No reference is displayed.');
    }
    const doc=host.ownerDocument;
    const el=(tag,value,cls)=>{const node=doc.createElement(tag);if(value!==undefined)node.textContent=value;if(cls)node.className=cls;return node;};
    const details=(title,value)=>{const node=el('details',undefined,'research-record');node.append(el('summary',title),el('pre',format(value)));return node;};
    const list=(values)=>{const node=el('ul');for(const value of values)node.append(el('li',format(value)));return node;};
    const entry=(value)=>{
      const article=el('article',undefined,'research-record');
      article.append(el('h4',value.field||value.id),el('p',value.id,'research-identity'));
      article.append(el('p',value.kind==='reconciliation_note'?'Qualified interpretation · no numeric model input':'Published source value: '+format(value.value)+' '+format(value.unit)));
      article.append(el('p','Basis: '+format(value.basis)));
      if(value.qualifications?.length)article.append(list(value.qualifications));
      if(value.scope_warning)article.append(el('p',value.scope_warning));
      // Preserve every original field, including carrier/CMS evidence, context,
      // value role and comparison. No scalar is promoted into a personal charge.
      article.append(details('Complete accepted entry, context and evidence',value));return article;
    };
    host.replaceChildren();
    host.append(el('h3','Accepted r4 published reference · exact subset'),
      el('p',reference.entries.length+' accepted entries returned for '+offeringId+'. The original acceptance checks ran for this request. Full L03 and personal comparisons remain incomplete.'));
    for(const value of reference.entries)host.append(entry(value));
    if(!reference.entries.length)host.append(el('p','No accepted entry was returned for this offering in the historical r4 subset. This establishes neither noncoverage nor current document availability.'));
    if(reference.related_reference_entries.length) {
      const context=el('section');context.append(el('h4','Related reference schedules and context'));
      for(const value of reference.related_reference_entries)context.append(entry(value));host.append(context);
    }
    host.append(details('Unresolved claims · disputed values remain masked',reference.holds),
      details('Original offering status and exact reference scope',{offering:reference.offering,scope:reference.scope}),
      details('Six accepted conservative dispositions',payload.accepted_dispositions),
      details('Acceptance receipt, verifier binding and held purposes',{review_receipt:payload.review_receipt,binding:payload.binding,authority:payload.authority}));
    host.append(list(payload.limitations||[]));
  }
  return {render};
});
