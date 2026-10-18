"use strict";
const el=id=>document.getElementById(id), selections={};
const node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
async function ask(message){
 const article=node("article");article.append(node("strong",message),node("p","Reading published evidence…"));el("messages").append(article);el("send").disabled=true;
 try{
  const response=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message,selections,use_model:el("use-model").checked})});const result=await response.json();
  if(!response.ok)throw new Error(result.error||"Evidence is unavailable.");
  article.replaceChildren(node("strong",message));
  if(result.facts.length){for(const fact of result.facts){article.append(node("p",fact.text));for(const source of fact.evidence||[]){const url=source.requested_url||source.url;if(url&&url.startsWith("https://")){const label=source.retrieved_at_utc?`Read source · captured ${source.retrieved_at_utc.slice(0,10)}${source.freshness==="review_overdue"?" · recheck overdue":""}`:"Read source";const link=node("a",label);link.href=url;link.target="_blank";link.rel="noopener noreferrer";link.className="source";article.append(link,node("span"," "));}}}
   const remainder=result.text.split("\n\n").slice(result.facts.length).join("\n\n");if(remainder)article.append(node("p",remainder));
  }else article.append(node("p",result.text));
  for(const candidate of result.choices.medicines){const label=candidate.synonym||candidate.name;const button=node("button",label);button.className="choice";button.type="button";button.addEventListener("click",()=>{selections.rxcui=candidate.rxcui;article.append(node("p",`Selected vocabulary product: ${label} (RxCUI ${candidate.rxcui}). Quantity and days supply remain unset. Ask about an exact plan, or type “compare this medicine across all plans”.`));});article.append(button);}
  for(const candidate of result.choices.pharmacies){const a=candidate.address;const button=node("button",`${candidate.organization} — ${a.address_1}, ${a.city} · NPI ${candidate.npi}`);button.type="button";button.className="choice";button.addEventListener("click",()=>{selections.pharmacy_npi=candidate.npi;article.append(node("p",`Selected this reported store: ${a.address_1}. Ask about a medicine and exact plan to inspect dated pharmacy-network evidence.`));});article.append(button);}
  for(const candidate of result.choices.plans||[]){const button=node("button",`${candidate.name} · ${candidate.plan_id}${candidate.comparison_available?"":" · outside comparison scope"}`);button.type="button";button.className="choice";button.addEventListener("click",()=>{selections.plan_id=candidate.plan_id;ask(`Show plan details ${candidate.plan_id}`);});article.append(button);}
 }catch(error){article.replaceChildren(node("strong",message),node("p",error.message));}finally{el("send").disabled=false;}
}
el("chat").addEventListener("submit",event=>{event.preventDefault();const value=el("question").value.trim();if(value){el("question").value="";ask(value);}});
el("clear").addEventListener("click",()=>{el("messages").replaceChildren();Object.keys(selections).forEach(k=>delete selections[k]);el("question").value="";});
fetch("/api/status").then(r=>r.json()).then(status=>{el("mode").textContent="Published-source demo · 2027 Collier County · independent domain review pending";el("model-control").hidden=!status.model_configured;}).catch(()=>{el("mode").textContent="Source connection unavailable.";});
