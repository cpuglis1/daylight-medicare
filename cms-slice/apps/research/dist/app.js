"use strict";
const byId = id => document.getElementById(id);
const selected = new Set();
let snapshot;
const categoryNames = {MA:"Medicare Advantage without Part D", "MA-PD":"Medicare Advantage with Part D", PDP:"Standalone drug plan", SNP:"Special Needs Plan"};
const states = {empty:"Not published in this source", not_applicable:"Not applicable", not_available:"Not available in source", json_null:"No source value", absent:"Not supplied", rejected:"Requires data review"};
const usd = new Intl.NumberFormat("en-US", {style:"currency", currency:"USD"});
function node(tag, text, cls) { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (cls) el.className = cls; return el; }
function factText(fact) { if (!fact) return "Not assessed"; if (fact.state !== "value") return states[fact.state] || "Unresolved"; if (Object.hasOwn(fact,"value_cents")) return fact.value_cents === null ? "Unresolved" : usd.format(fact.value_cents/100); return String(fact.value ?? fact.raw); }
function announce(text, error=false) { byId("status").textContent = text; byId("status").className = error ? "status error" : "status"; }
async function api(path) { const response = await fetch(path); const data = await response.json(); if (!response.ok) throw new Error(data.error || "Could not read source facts"); return data; }
function sourceLink(url, text) { const link=node("a",text); link.href=url; link.target="_blank"; link.rel="noopener noreferrer"; return link; }
function addFact(list, label, value) { list.append(node("dt",label), node("dd",value)); }
function updateSelection() { byId("selection-count").textContent=`${selected.size} of 3 selected`; byId("compare").disabled=!selected.size; byId("clear").disabled=!selected.size; document.querySelectorAll("input[data-option]").forEach(input=>{input.checked=selected.has(input.dataset.option); input.disabled=selected.size===3 && !input.checked;}); }
function card(record, excluded=false) {
  const el=node("article",undefined,"card");
  el.append(node("p",`${record.id} · ${record.plan_type}`,"meta"),node("h3",record.name),node("p",categoryNames[record.category] || record.category,"meta"));
  if (!excluded) {
    const price=node("p",factText(record.plan_premium.fact),"price");price.append(node("span"," / month"));el.append(price,node("p",record.plan_premium.label,"premium-label"));
    const list=node("dl",undefined,"fact-list");addFact(list,"Annual Part D deductible",factText(record.facts.annual_part_d_deductible));addFact(list,"In-network medical spending limit",factText(record.facts.in_network_medical_moop));el.append(list);
    if(record.carrier_sample.sampled) el.append(node("p",`${record.carrier_sample.checks.length} monetary fields checked against carrier documents`,"sample"));
  } else {
    el.append(node("p",`Outside current scope: ${record.exclusion_reasons.map(reason=>({category_outside_experiment:"category",plan_type_outside_experiment:"plan type",sanction_status_requires_review:"sanction status requires review"}[reason] || reason)).join("; ")}`,"premium-label"));
  }
  const actions=node("div",undefined,"card-actions");
  if (!excluded) { const label=node("label",undefined,"select-label");const input=node("input");input.type="checkbox";input.dataset.option=record.id;input.setAttribute("aria-label",`Compare ${record.name}, ${record.id}`);input.addEventListener("change",()=>{if(input.checked){if(selected.size>=3){input.checked=false;announce("Choose at most three records.",true);return;}selected.add(record.id);}else selected.delete(record.id);updateSelection();announce(`${selected.size} records selected. Source order is unchanged.`);});label.append(input,node("span","Add to comparison"));actions.append(label); }
  const inspect=node("button","Inspect sources","secondary");inspect.type="button";inspect.setAttribute("aria-label",`Inspect ${record.name}, ${record.id}`);inspect.addEventListener("click",()=>showDetail(record.id));actions.append(inspect);el.append(actions);return el;
}
async function showDetail(id) {
  try {
    const record=await api(`/api/options/${encodeURIComponent(id)}`);byId("detail-title").textContent=record.name;const content=byId("detail-content");content.replaceChildren();content.append(node("p",`${record.id} · ${categoryNames[record.category] || record.category}`));
    if(record.comparison_available){const list=node("dl",undefined,"detail-facts");for(const [field,label] of Object.entries(snapshot.field_labels)){const wrapper=node("div");addFact(wrapper,label,factText(record.facts[field]));list.append(wrapper);}content.append(list);}
    content.append(node("p",record.carrier_sample.sampled ? "Only the specific fields below were corroborated in a carrier sample. This does not verify the whole plan or your eligibility." : "This record has source identity evidence. It has not been independently checked against carrier benefit documents in this sample."));
    for(const check of record.carrier_sample.checks){const box=node("div",undefined,"source-box");box.append(node("strong",`${snapshot.field_labels[check.field]}: ${check.status}`),node("p",`Carrier amount ${usd.format(check.carrier.value_cents/100)} · PDF page ${check.carrier.pdf_page}`),sourceLink(check.carrier.url,"Open carrier Summary of Benefits"));content.append(box);}
    const origin=node("div",undefined,"source-box");origin.append(node("strong","Published source basis"),node("p",`CMS source data updated ${snapshot.source_data_updated}. Benefit year ${snapshot.benefit_year}.`),sourceLink(snapshot.sources.landscape.url,"Open original CMS landscape download"),node("p",`CSV record ordinal ${record.source.record_ordinal} · ${record.source.member}`),node("p",`Archive SHA-256: ${record.source.archive_sha256}`,"raw"),node("p",`PBP join: ${record.pbp.join_status}. Source workflow labels are not purchase approval.`));content.append(origin);
    const evidence=node("details");evidence.append(node("summary","See field-level lineage and original source values"));
    for(const [field,fact] of Object.entries(record.facts)){if(!fact.evidence)continue;const box=node("div",undefined,"source-box");box.append(node("strong",snapshot.field_labels[field] || field),node("p",`Raw value: ${JSON.stringify(fact.raw)} · state: ${fact.state}`,"raw"),node("p",`Column: ${fact.evidence.column} · CSV record ${fact.evidence.record_ordinal}`));evidence.append(box);}
    const table=node("table");const body=node("tbody");for(const [field,raw] of Object.entries(record.landscape_raw)){const row=node("tr");const th=node("th",field);th.scope="row";row.append(th,node("td",JSON.stringify(raw),"raw"));body.append(row);}table.append(body);evidence.append(table);content.append(evidence);
    const checks=node("ul");record.open_checks.forEach(check=>checks.append(node("li",check)));content.append(checks);byId("detail-dialog").showModal();
  } catch(error){announce(error.message,true);}
}
async function compare() {
  try {
    const comparison=await api(`/api/compare?ids=${encodeURIComponent([...selected].join(","))}`);const content=byId("comparison-content");content.replaceChildren();const grid=node("div",undefined,"comparison-grid");
    for(const record of comparison.options){const el=node("article",undefined,"card");el.append(node("p",record.id,"meta"),node("h3",record.name));const list=node("dl");addFact(list,"Coverage type",categoryNames[record.category] || record.category);addFact(list,record.plan_premium.label,`${factText(record.plan_premium.fact)} / month`);addFact(list,"Annual Part D deductible",factText(record.facts.annual_part_d_deductible));addFact(list,"In-network medical spending limit",factText(record.facts.in_network_medical_moop));el.append(list,node("p","Other Medicare premiums and personal adjustments are not included. Drug and provider checks remain open.","premium-label"));grid.append(el);}content.append(grid);byId("compare-dialog").showModal();
  }catch(error){announce(error.message,true);}
}
byId("close-detail").addEventListener("click",()=>byId("detail-dialog").close());byId("close-compare").addEventListener("click",()=>byId("compare-dialog").close());byId("compare").addEventListener("click",compare);byId("clear").addEventListener("click",()=>{selected.clear();updateSelection();announce("Comparison selection cleared.");});
function rxShare(share) { if(share.status==="not_offered")return "Not offered";if(share.status==="copay")return `${usd.format(Number(share.value))} copay`;if(share.status==="coinsurance")return `${new Intl.NumberFormat("en-US",{style:"percent",maximumFractionDigits:2}).format(Number(share.value))} coinsurance`;return "Requires source review"; }
function sourceYesNo(value) { return ({Y:"Yes",N:"No"})[value] || "Unresolved"; }
async function loadPrescription() {
  try {
    const context=await api("/api/prescription/context");
    for(const plan of context.plans){const opt=node("option",`${plan.name} · ${plan.id}`);opt.value=plan.id;byId("rx-plan").append(opt);}
    byId("rx-plan").value="H5434-002-000-2027";
    for(const item of context.medicine_example.candidates){const opt=node("option",item.name);opt.value=item.rxcui;byId("rx-product").append(opt);}
    const pharmacy=context.pharmacy_example;const opt=node("option",`${pharmacy.organization} · ${pharmacy.location.address_1}, Naples · NPI ${pharmacy.npi}`);opt.value=pharmacy.npi;byId("rx-pharmacy").append(opt);
    byId("rx-controls").hidden=false;byId("rx-status").textContent="Public test example only. The four products have different strengths; none has been confirmed for you.";byId("nlm-attribution").textContent=context.nlm_attribution;
  }catch(error){byId("rx-status").textContent=`Prescription evidence unavailable: ${error.message}`;}
}
async function readPrescription() {
  const button=byId("rx-lookup");const controls=[byId("rx-plan"),byId("rx-product"),byId("rx-pharmacy")];const productLabel=byId("rx-product").selectedOptions[0].textContent;button.disabled=true;controls.forEach(control=>control.disabled=true);byId("rx-status").textContent="Reading the pinned source rows…";
  try {
    const params=new URLSearchParams({plan_id:byId("rx-plan").value,rxcui:byId("rx-product").value});if(byId("rx-pharmacy").value)params.set("pharmacy_npi",byId("rx-pharmacy").value);
    const result=await api(`/api/prescription/lookup?${params}`);const content=byId("rx-result");content.replaceChildren();
    content.append(node("h3",productLabel),node("p",result.id,"meta"));
    content.append(node("p","2027 drug prices are unavailable in this captured source. No fill price or annual cost has been calculated.","notice"));
    for(const fact of result.basic_formulary || []){
      const raw=fact.raw;const list=node("dl",undefined,"detail-facts");for(const [label,value] of [["Published tier",raw.TIER_LEVEL_VALUE],["Prior authorization",raw.PRIOR_AUTHORIZATION_YN==="Y" ? "Required; approval has not been confirmed" : raw.PRIOR_AUTHORIZATION_YN==="N" ? "Not indicated in this source" : "Unresolved"],["Step therapy",raw.STEP_THERAPY_YN==="Y" ? "Indicated" : raw.STEP_THERAPY_YN==="N" ? "Not indicated in this source" : "Unresolved"],["Quantity limit",raw.QUANTITY_LIMIT_YN==="Y" ? `Raw amount ${raw.QUANTITY_LIMIT_AMOUNT} per ${raw.QUANTITY_LIMIT_DAYS} days; unit requires confirmation` : "Not indicated in this source"]]){const wrapper=node("div");addFact(wrapper,label,value);list.append(wrapper);}content.append(list);
      content.append(node("p",`Source: formulary ${raw.FORMULARY_ID}, version ${raw.FORMULARY_VERSION}, benefit year ${raw.CONTRACT_YEAR}; ${fact.evidence.table} row ${fact.evidence.source_row}.`,"premium-label"));
    }
    if(!(result.basic_formulary || []).length)content.append(node("p","This product was not found in the plan's basic formulary snapshot. That alone does not establish noncoverage; supplemental and indication-specific checks may still be needed."));
    if(result.carrier_product_example){const sample=result.carrier_product_example;content.append(node("p",`The carrier's October 15 drug list also shows tier ${sample.tier}, prior authorization and a limit of ${sample.carrier_quantity.amount} ${sample.carrier_quantity.unit} per ${sample.carrier_quantity.days} days. The quantity unit differs from the CMS raw field and remains open for review.`),sourceLink(result.carrier_formulary_url,"Read the carrier drug list · PDF page 64"));}
    if(result.pharmacy && result.pharmacy.status!=="not_requested"){
      content.append(node("h3","Pharmacy evidence"));if(result.pharmacy.rows.length){for(const fact of result.pharmacy.rows){const r=fact.raw;content.append(node("p",`Listed in this pinned plan network. Retail outlet: ${sourceYesNo(r.PHARMACY_RETAIL)}. Preferred retail: ${sourceYesNo(r.PREFERRED_STATUS_RETAIL)}. Pharmacy ZIP: ${r.PHARMACY_ZIPCODE}.`),node("p",`Exact NPI ${result.input.pharmacy_npi}; source ${fact.evidence.table} row ${fact.evidence.source_row}. This is dated network evidence; current store operation has not been confirmed.`,"premium-label"));}}else content.append(node("p","This exact pharmacy NPI is not listed in the captured plan network. Confirm current plan/location participation before relying on it."));
    }
    const costDetails=node("details");costDetails.append(node("summary","Inspect the plan’s tier cost-sharing schedules"),node("p",result.cost_scope || "Not available"));
    const table=node("table");const head=node("thead");const header=node("tr");for(const label of ["Benefit phase","Supply code","Preferred retail","Standard retail"]){const th=node("th",label);th.scope="col";header.append(th);}head.append(header);table.append(head);const body=node("tbody");
    for(const fact of result.beneficiary_cost_rows || []){const r=fact.raw;const row=node("tr");for(const text of [{"0":"Before deductible","1":"Initial coverage","3":"Catastrophic"}[r.COVERAGE_LEVEL] || `Unresolved code ${r.COVERAGE_LEVEL}`, {"1":"30 days","2":"90 days","3":"Other","4":"60 days"}[r.DAYS_SUPPLY] || `Unresolved code ${r.DAYS_SUPPLY}`, rxShare(fact.cost_shares.PREF),rxShare(fact.cost_shares.NONPREF)])row.append(node("td",text));body.append(row);}table.append(body);costDetails.append(table,node("p","These schedules have conditions, minimums, maximums and insulin-specific rules. They are not a quote for a particular prescription. Full raw rows remain available below."));content.append(costDetails);
    const rawDetails=node("details");rawDetails.append(node("summary","Inspect complete returned rows and lineage"),node("pre",JSON.stringify(result,null,2),"raw"));content.append(rawDetails);
    content.append(node("p","Source-date question: the October CMS download has October 31 tokens inside its filenames. That naming discrepancy is unresolved; this view does not claim data as of October 31.","premium-label"),sourceLink(result.source.url,"Open original CMS October release · 2.29 GB ZIP"));
    byId("rx-status").textContent="Exact source lookup complete. This example does not change plan order or confirm a personal choice.";
  }catch(error){byId("rx-status").textContent=`Could not read prescription evidence: ${error.message}`;byId("rx-result").replaceChildren();}finally{button.disabled=false;controls.forEach(control=>control.disabled=false);}
}
byId("rx-lookup").addEventListener("click",readPrescription);
async function init(){try{snapshot=await api("/api/catalog?year=2027&county_fips=12021");byId("total").textContent=snapshot.counts.source_market_rows;byId("included-count").textContent=snapshot.counts.included;byId("excluded-count").textContent=snapshot.counts.excluded;byId("sample-count").textContent=snapshot.validation_counts.sample_records;byId("release-note").textContent=`CMS source data updated ${snapshot.source_data_updated}. Five sampled records from one carrier have limited field checks; other records remain unsampled. This preview does not contain Medigap quotes or Original Medicare bundle comparisons.`;byId("options").replaceChildren(...snapshot.options.map(record=>card(record)));byId("excluded-options").replaceChildren(...snapshot.exclusions.map(record=>card(record,true)));byId("exclusions-summary").textContent=`View all ${snapshot.counts.excluded} exclusions and their sources`;announce(`${snapshot.counts.source_market_rows} source records loaded. No personalized ranking has been computed.`);}catch(error){announce(`Source facts could not be loaded: ${error.message}`,true);}}
init();
loadPrescription();
