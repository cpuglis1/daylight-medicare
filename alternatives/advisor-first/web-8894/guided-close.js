/* D180: read-only profile payoff and navigation through the existing Plans tool.
   No messages, profile writes, inference or provider requests on navigation. */
(() => {
  const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
  const button=(text,run,cls='secondary-button')=>{const b=node('button',text,cls);b.type='button';b.addEventListener('click',run);return b;};
  function progress(host,value) {
    host.hidden=!value?.active || !value.total;
    if(host.hidden)return;
    host.setAttribute('aria-label','Comparison preparation');
    const bar=node('progress',null,'profile-progress');bar.max=value.total;bar.value=value.addressed;
    bar.setAttribute('aria-label','Comparison preparation');
    bar.setAttribute('aria-valuetext',`${value.addressed} of ${value.total} areas addressed. Details left open still need checking.`);
    host.append(bar);
  }
  function summary(brief,{review,open}={}) {
    const host=node('section',null,'guided-close');host.dataset.kind='guided-close';
    const supporting=[];
    host.append(node('h2',brief.title || 'Your plan from here'));
    if(brief.decision)host.append(node('p',brief.decision));
    if(brief.learned?.length) {
      // D181: what we learned, from the person's own reports (code-built).
      const list=node('ul',null,'close-highlights');
      for(const item of brief.learned)list.append(node('li',item.label+': '+item.value));host.append(list);
    }
    if(brief.direction)host.append(node('p',brief.direction,'close-direction'));
    if(brief.rows?.length) {
      const highlights=brief.learned ? [] : ['T10','T09','RC11','T05'].map(id=>brief.rows.find(r=>r.id===id && r.status==='reported')).filter(Boolean).slice(0,2);
      if(highlights.length){const list=node('ul',null,'close-highlights');
        for(const row of highlights)list.append(node('li',row.label+': '+row.value));host.append(list);}
      const facts=node('section',null,'close-details');facts.append(node('h3','Your details'));
      const list=node('dl');
      for(const row of brief.rows){list.append(node('dt',row.label),node('dd',row.value));}
      facts.append(list);supporting.push(facts);
    }
    if(brief.findings?.length || brief.open?.length){const details=node('section',null,'close-details');details.append(node('h3','Checks and details still open'));
      for(const finding of brief.findings || [])details.append(node('p',finding));
      const list=node('ul');for(const text of brief.open || [])list.append(node('li',text));details.append(list);supporting.push(details);}
    host.append(node('h3','Next steps'));
    const steps=node('ol');for(const step of brief.steps || [])steps.append(node('li',step.text));host.append(steps);
    if(review && brief.ready)host.append(button('Review my information and continue',review,'primary-button'));
    else if(open && brief.steps?.some(s=>s.view)) {
      const step=brief.steps.find(s=>s.view);host.append(button('Open the next step',()=>open(step.view),'primary-button'));
    }
    host.append(...supporting);
    return host;
  }
  const GUIDES={
    paths:{title:'Compare the two coverage paths',text:'Start with the differences that matter to you: doctor access, monthly payments and what you pay when you use care. Open either path to explore its steps.'},
    ab:{title:'Step 1: Parts A and B',text:'Use the status and sign-up guide on this page to identify the next enrollment step. A plan comparison does not submit an enrollment application.'},
    guide:{title:'Work through your sign-up guide',text:'Follow the steps shown in the guide. You can ask about any term or instruction here, then return to the same place.'},
    supplement:{title:'Step 2: Compare Medigap options',text:'Compare the policy benefits, then the available prices for the same policy type. Your doctor and medicine checks remain available in this conversation.',next:'part-d',label:'Continue to Part D'},
    'part-d':{title:'Step 3: Compare drug plans',text:'Include the medicines and pharmacy you use. Review coverage and personal costs together; a premium alone does not establish the best option.'},
    advantage:{title:'Step 2: Compare Advantage plans',text:'Open plan details to compare doctor access, costs and coverage. You can ask about the plan you are viewing here. Choose a plan for exploration before checking its drugs.',next:'advantage-drugs',label:'Continue to the drug check'},
    'advantage-drugs':{title:'Step 3: Check drug coverage',text:'Use this page to check the selected plan’s drug coverage. Any missing medicine or pharmacy details stay open until supplied.'}
  };
  // D189 (owner review): the chat beside every Plans view opens on this one line.
  const PLANS_INVITATION='Any questions about these plans?';
  function guide(view,open,plain) {
    const spec=GUIDES[view];if(!spec)return null;
    const host=node('section',null,'plans-conversation-guide');host.dataset.view=view;
    // No step button: the Plans pages already offer "Next: see Part D drug plans" and the move to the drug check.
    if(plain){host.dataset.plain='true';host.append(node('p',PLANS_INVITATION,'guide-invitation'));return host;}
    host.append(node('h2',spec.title),node('p',spec.text));
    if(spec.next)host.append(button(spec.label,()=>open(spec.next),'primary-button'));
    host.append(node('p','Ask Daylight below, or continue on the Plans page.','guide-help'));
    return host;
  }
  window.DaylightGuidedClose=Object.freeze({progress,summary,guide});
})();
