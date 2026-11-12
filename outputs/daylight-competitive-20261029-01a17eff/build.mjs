import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile, FileBlob } from '@oai/artifact-tool';

const dir = path.dirname(new URL(import.meta.url).pathname);
const data = JSON.parse(await fs.readFile(path.join(dir, 'research.json'), 'utf8'));
const rows = data.rows;
if (rows.length !== 21 || rows.some(r => r.length !== 19)) throw new Error('Unexpected comparison row shape');
const ids = new Set(data.sources.map(s=>s[0]));
for (const r of rows) for (const id of r[17].split(' ')) if (!ids.has(id)) throw new Error('Missing source '+id);
if (new Set(rows.map(r=>r[0])).size !== rows.length) throw new Error('Duplicate service IDs');

const coreMode = process.argv.includes('--add-core');
const inputPath = process.argv.find(a=>a.startsWith('--input='))?.slice(8) || path.join(dir,'Daylight competitive matrix.xlsx');
const wb = coreMode ? await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath)) : Workbook.create();
const sheets = coreMode ? {} : Object.fromEntries(['Landscape','Self-discovery','Independence','Evidence','Method and tests'].map(n=>[n,wb.worksheets.add(n)]));
const ink = '#24344A', muted = '#526174', header = '#283C55', line = '#D6DEE6', pale = '#F1F4F7', amber = '#FFF1D6';
const col = n => { let s=''; while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26);} return s; };
function base(sh,lastCol,lastRow,widths,title){
  sh.showGridLines=false;
  sh.getRange(`A1:${lastCol}${lastRow}`).format.font={name:'Arial',size:10,color:ink};
  sh.getRange(`A1:${lastCol}${lastRow}`).format.verticalAlignment='center';
  widths.forEach((w,i)=>sh.getRange(`${col(i+1)}1:${col(i+1)}${lastRow}`).format.columnWidth=w);
  sh.getRange('A2').values=[[title]];
  sh.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:ink};
  sh.getRange(`A2:${lastCol}2`).format.rowHeight=29;
  sh.getRange(`A3:${lastCol}3`).format.rowHeight=20;
  sh.getRange(`A4:${lastCol}4`).format.borders={bottom:{style:'thin',color:line}};
}
function head(sh,range,values){
  sh.getRange(range).values=[values];
  sh.getRange(range).format={fill:header,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:39,borders:{insideVertical:{style:'thin',color:'#FFFFFF'}}};
}
function body(sh,range,height=84){
  sh.getRange(range).format.wrapText=true;
  sh.getRange(range).format.verticalAlignment='top';
  sh.getRange(range).format.rowHeight=height;
}
function stripes(sh,from,to,last){for(let r=from;r<=to;r++)if((r-from)%2===1)sh.getRange(`A${r}:${last}${r}`).format.fill=pale;}
function table(sh,range,name){const t=sh.tables.add(range,true,name);t.showFilterButton=true;return t;}

if(coreMode){
  const core=JSON.parse(await fs.readFile(path.join(dir,'core-capabilities.json'),'utf8'));
  const allowed=['✓ O','✓ C','✓ L','△ O','△ C','△ L','× O','× C','× L','?','T'];
  const priorSheets=await wb.inspect({kind:'sheet',include:'id,name',maxChars:3000});
  console.log(priorSheets.ndjson);
  if(core.rows.length!==rows.length || new Set(core.rows.map(r=>r[0])).size!==rows.length)throw new Error('Core service coverage mismatch');
  for(const r of core.rows)if(r[1].length!==10 || r[1].some(v=>!allowed.includes(v)))throw new Error('Invalid capability status '+r[0]);
  const sh=wb.worksheets.add('Core differentiators');
  base(sh,'O',65,[6,31,14,16,16,15,17,17,17,17,15,17,32,66,26],'Core differentiators — capability and evidence');
  sh.tabColor=header;
  sh.getRange('A3').values=[['October 29, 2026. Marks summarize the detailed matrices; no overall winner or verified bias score.']];
  const legend=[['A4','✓ O = observed'],['D4','✓ C = claim'],['G4','△ = partial / assisted'],['J4','× = explicit absence or held'],['M4','? = unresolved, not absent'],['A5','✓ L = dated local tests'],['D5','T = target, not delivered'],['G5','O ≠ verified accuracy'],['J5','Hover marks for criteria / sources'],['M5','Test scope describes our review']];
  for(const [cell,value]of legend)sh.getRange(cell).values=[[value]];
  sh.getRange('A4:O5').format.rowHeight=21;
  head(sh,'A7:O7',['ID','Alternative solution',...core.columns.map(c=>c[0]),'Our test scope','Important qualification','Source IDs']);
  sh.getRange('A7:O7').format.rowHeight=62;
  const coreValues=core.rows.map(r=>{
    const original=rows.find(v=>v[0]===r[0]);
    if(!original)throw new Error('Missing alternative '+r[0]);
    const extra=r[0]==='C09'?' N01':r[0]==='C12'?' N02':r[0]==='C04'?' N03':'';
    return [r[0],original[1],...r[1],r[2],r[3],original[17]+extra];
  });
  sh.getRange('A8:O28').values=coreValues;
  body(sh,'A8:O28',61);stripes(sh,8,28,'O');
  table(sh,'A7:O28','CoreDifferentiators');
  sh.getRange('C8:L28').format.horizontalAlignment='center';
  sh.getRange('C8:L28').format.verticalAlignment='center';
  sh.getRange('C8:L28').format.font={name:'Arial',size:12,bold:true,color:ink};
  sh.getRange('A27:B28').format.fill=amber;
  sh.getRange('C8:L28').dataValidation={rule:{type:'list',values:allowed}};
  const grid=sh.getRange('C8:L28');
  for(const value of allowed){
    const observed=value==='✓ O'||value==='✓ L';
    const claimed=value==='✓ C';
    const partial=value.startsWith('△');
    const negative=value.startsWith('×');
    const fill=observed?'#E3F0E8':claimed?'#E7EDF7':partial?'#FFF0D4':negative?'#F6E5E5':value==='T'?'#EEE8F7':'#F1F3F5';
    const color=observed?'#22543D':claimed?'#274D78':partial?'#765315':negative?'#8A3434':value==='T'?'#5B4080':'#687482';
    grid.conditionalFormats.add('cellIs',{operator:'equal',formula:`"${value}"`,format:{fill,font:{bold:true,color}}});
  }
  const statusMeaning={'✓ O':'Observed in the stated limited guest journey.','✓ C':'Published capability / official service model; not independently demonstrated.','✓ L':'Dated local Daylight technical evidence, not a consumer study.','△ O':'Only a narrower visible behavior or control was observed.','△ C':'A narrower or human-assisted capability is described; not a full self-directed implementation.','△ L':'Dated local evidence is partial or includes known defects.','× O':'Observed absence for the defined endpoint.','× C':'The described service requires a different route, such as individual agent contact.','× L':'Known local scope / source gate prevents the defined capability.','?':'Adequate evidence is not established in this review; absence is not inferred.','T':'Target commitment only; not delivered or demonstrated.'};
  for(let i=0;i<core.rows.length;i++)for(let j=0;j<10;j++){
    const address=`${col(j+3)}${i+8}`;
    wb.notes.add({id:`CoreDifferentiators:${address}`,target:{cell:{sheetName:sh.name,sheetId:sh.sheetId,address}},authorId:'',createdAt:'',body:{plainText:`${core.columns[j][1]}\n\n${statusMeaning[core.rows[i][1][j]]}\nSources: ${coreValues[i][14]}\nScope: ${core.rows[i][3]}`}});
  }
  sh.freezePanes.freezeRows(7);sh.freezePanes.freezeColumns(2);
  sh.getRange('B31').values=[['Reading the marks']];sh.getRange('B31').format.font={name:'Arial',size:12,bold:true,color:ink};
  const definitions=[
    ['Review boundary','Six competitor guest journeys were inspected to different stopping points. No new flow tests were run for this tab; previous observations and public claims are reused.'],
    ['Evidence boundary','O is an observed screen/control, C a provider or official claim, L dated Daylight tests. A check mark is limited to the criterion and stated scope.'],
    ['Unknown versus no','? never means no feature exists. × is reserved for an explicit service requirement or a known local hold; △ preserves partial or human-assisted capabilities.'],
    ['AI as an enabler','AI can power adaptive explanations and investigation. It is not a prerequisite for complete data or self-discovery, and an AI claim does not prove an AI-native architecture.'],
    ['Separate AI uses','K includes matching, plan research and advisor data/quality tools. L concerns conversational help; form guides and advisor-facing Q&A receive partial marks.'],
    ['Unproven outcomes','No comparative ease advantage or independently verified scoped plan-data quality was established for an external alternative in this review. This is not a statement that no outside tests exist.'],
    ...core.columns.map(([name,definition])=>[name,definition])
  ];
  for(let i=0;i<definitions.length;i++){
    sh.getRange(`B${i+33}`).values=[[definitions[i][0]]];
    sh.getRange(`C${i+33}`).values=[[definitions[i][1]]];
    sh.getRange(`B${i+33}:O${i+33}`).format.rowHeight=24;
    sh.getRange(`C${i+33}:O${i+33}`).format.wrapText=false;
  }
  sh.getRange('B51').values=[['Additional source records']];sh.getRange('B51').format.font={name:'Arial',size:12,bold:true,color:ink};
  for(let i=0;i<core.additionalSources.length;i++){
    const [id,name,url,meaning]=core.additionalSources[i];const r=53+i*3;
    sh.getRange(`B${r}`).values=[[id+' — '+name]];
    sh.getRange(`C${r+1}`).values=[[url.startsWith('evidence/')?path.join(dir,url):url]];
    sh.getRange(`C${r+2}`).values=[[meaning]];
    sh.getRange(`B${r}:O${r+2}`).format.rowHeight=24;
    sh.getRange(`C${r+1}`).format.font={name:'Arial',size:10,color:'#285F9E'};
  }
  wb.recalculate();
  console.log((await wb.inspect({kind:'table',range:'Core differentiators!A7:O12',tableMaxRows:6,tableMaxCols:15,tableMaxCellChars:45,maxChars:5000})).ndjson);
  console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},maxChars:2000})).ndjson);
  for(const [range,name]of [['A2:H15','core-left'],['I2:O15','core-right'],['A23:H28','core-lower-left'],['I23:O28','core-lower-right'],['B31:O48','core-definitions']]){
    const blob=await wb.render({sheetName:sh.name,range,scale:1,format:'png'});
    await fs.writeFile(path.join(dir,`evidence/preview-${name}.png`),new Uint8Array(await blob.arrayBuffer()));
  }
  await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(dir,'Daylight competitive matrix.xlsx'));
  await fs.writeFile(path.join(dir,'core-tab-verification.json'),JSON.stringify({asOf:core.asOf,alternatives:core.rows.length,criteria:core.columns.length,markedCells:210,newExternalBrowserTests:0,originalTabsPreserved:true},null,2));
  console.log('Added Core differentiators; original worksheets imported without edits.');
  process.exit(0);
}

const sd=sheets['Self-discovery'];
base(sd,'L',29,[6,31,24,25,28,29,29,27,27,29,35,38],'Self-directed Medicare research');
sd.getRange('A3').values=[['As of October 29, 2026. Capability descriptions are not consumer ease ratings.']];
head(sd,'A6:L6',['ID','Service','Delivery model','Learn independently','Understand coverage paths','Compare plans independently','Investigate personal needs','Support mechanism','Revise or return','Independent endpoint','Entry friction / access','Evidence basis and source IDs']);
sd.getRange('A7:L27').values=rows.map(r=>[r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7],r[8],r[9],r[10],r[18]+'\n'+r[17]]);
body(sd,'A7:L27',60);stripes(sd,7,27,'L');table(sd,'A6:L27','SelfDiscovery');
sd.freezePanes.freezeRows(6);sd.freezePanes.freezeColumns(2);
sd.getRange('A26:L27').format.fill=amber;
sd.tabColor=header;

const ind=sheets['Independence'];
base(ind,'I',29,[6,31,40,36,44,43,44,43,27],'Independence, scope and transparency');
ind.getRange('A3').values=[['Financial incentives, option breadth and consumer control are separate dimensions. No overall bias score.']];
head(ind,'A6:I6',['ID','Service','Search / offering universe','Funding and compensation','Published independence controls','Explanation / evidence visibility','Contact and privacy boundary','Material unknown or limitation','Source IDs']);
ind.getRange('A7:I27').values=rows.map(r=>[r[0],r[1],r[11],r[12],r[13],r[14],r[15],r[16],r[17]]);
body(ind,'A7:I27',60);stripes(ind,7,27,'I');table(ind,'A6:I27','IndependenceMatrix');
ind.freezePanes.freezeRows(6);ind.freezePanes.freezeColumns(2);
ind.getRange('A26:I27').format.fill=amber;

const ev=sheets.Evidence;
base(ev,'I',47,[8,26,44,18,36,63,61,3,90],'Evidence register');
ev.getRange('A3').values=[['Primary provider material unless stated. Observed date records review, not original publication or data freshness.']];
head(ev,'A6:G6',['Source ID','Provider','Page / record','Reviewed','Evidence type','Supports','Limitations']);
head(ev,'I6:I6',['Source URL / local record']);
const sourceValues=data.sources.map(s=>[s[0],s[1],s[2],new Date('2026-10-29T12:00:00Z'),s[4],s[5],s[6]]);
ev.getRange(`A7:G${6+sourceValues.length}`).values=sourceValues;
body(ev,`A7:G${6+sourceValues.length}`,68);stripes(ev,7,6+sourceValues.length,'G');
ev.getRange(`D7:D${6+sourceValues.length}`).setNumberFormat('mmm d, yyyy');
ev.getRange(`D7:D${6+sourceValues.length}`).format.horizontalAlignment='right';
for(let i=0;i<data.sources.length;i++){
  let target=data.sources[i][3];
  if(target.startsWith('evidence/'))target=path.join(dir,target);
  ev.getRange(`I${i+7}`).values=[[target]];
}
ev.getRange(`I7:I${6+sourceValues.length}`).format.font={name:'Arial',size:10,color:'#285F9E'};
ev.getRange(`I7:I${6+sourceValues.length}`).format.wrapText=true;
table(ev,`A6:G${6+sourceValues.length}`,'EvidenceRegister');ev.freezePanes.freezeRows(6);ev.freezePanes.freezeColumns(2);

const ls=sheets.Landscape;
base(ls,'D',34,[31,58,63,52],'Daylight competitive landscape');
ls.getRange('A3').values=[['October 29, 2026. US Medicare consumer solutions.']];
ls.getRange('A5:D5').values=[['Two axes','Independent progress','Funding / selection structure','Category placement is analytical, not a bias verdict.']];
body(ls,'A5:D5',32);
head(ls,'A6:D6',['Main user route','Public / no insurer sales revenue claimed','Commercial brokerage or referral model','Consumer-paid advice']);
ls.getRange('A7:D10').values=[
 ['Public reference learning','Medicare Interactive','Public learning exists across commercial providers.','The Medicare Coach free workshop'],
 ['Consumer-operated comparison','Medicare.gov\nMatch Your Medicare: MA results observed','Healthpilot, eHealth, HelloMedicare, PlanEnroll, Via Benefits, GoHealth and CoverRight.\nDepth and access vary; most endpoints are provider claims.','Not established in this review'],
 ['Personal selection largely through a person','SHIP / SHINE','Chapter, Fair Square, SelectQuote, Boomer Benefits, MedicareSchool.com and Ask Claire','The Medicare Coach paid research / concierge'],
 ['Quote / provider referral','Not established in this review','Medigap.com','Not established in this review']
];
body(ls,'A7:D10',93);stripes(ls,7,10,'D');ls.getRange('A8:D8').format.rowHeight=111;
ls.getRange('A12:D12').values=[['Daylight today','Guided teaching, adaptive preparation and labeled samples.','Personal source/coverage gates remain held; known conversational and data-integrity defects.','Intended experience is separately labeled in both detailed matrices.']];
body(ls,'A12:D12',70);ls.getRange('A12:D12').format.fill=amber;
head(ls,'A14:D14',['Your proposed differentiator','Competitive finding','Role in Daylight positioning','Evidence Daylight must produce']);
ls.getRange('A15:D19').values=[
 ['Data quality / comprehensiveness','Broad plan databases are common claims. No comparative whole-market accuracy audit was performed.','A reason to trust the result when demonstrated.','Declared universe, missing options, exact matches, freshness and material-error checks.'],
 ['Unbiased options','Public resources and commission-free claims exist. Salary, company revenue and displayed plan selection must be separated.','A binding design commitment, with testable controls.','Compensation counterfactuals, nonpaying options, keep/defer outcomes and inspected exclusions.'],
 ['Ease of use','Many providers promise simplicity. Limited entry checks do not establish relative human ease.','A measurable product advantage is possible.','Matched task success, comprehension, effort, corrections and drop-off with real users.'],
 ['Self-discovery','Education, personalized tools and human guidance already exist in different combinations.','A promising customer outcome: understand, investigate, challenge and revise.','Users explain tradeoffs and uncertainty and can change course without redoing work.'],
 ['No contact details / pressure upfront','Already present in official tools and digital competitors. Match Your Medicare results were reached without contact details.','An access expectation; useful in the overall experience.','Useful scope-appropriate output before name, email or phone; explicit optional contact later.']
];
body(ls,'A15:D19',82);stripes(ls,15,19,'D');
head(ls,'A21:D21',['Closest benchmark','What to learn from it','What this review does not establish','Implication']);
ls.getRange('A22:D26').values=[
 ['Match Your Medicare','No-account research, editable inputs, optional video guide and commission-free claims.','Full-market completeness, verified personalized costs or adaptive dialogue quality.','Direct overlap with several of Daylight’s intended benefits.'],
 ['Healthpilot','Digital matching, plan fit, online application and optional human help.','Source-level rationale, all-market display or comparative decision quality.','Benchmark the whole digital journey, not only its landing page.'],
 ['Medicare.gov','Official tools, guest access and coverage-path education.','That every relevant fact is correct or every consumer finds it easy.','Current baseline must include recent CMS improvements.'],
 ['Chapter / Fair Square','Advisor explanation and willingness to recommend outside commercial relationships are claimed.','Whether a user can independently reproduce or challenge the full reasoning.','Human help sets a quality benchmark for comprehension and follow-through.'],
 ['SHIP / SHINE','Publicly funded objective assistance for beneficiaries and caregivers.','Local availability, speed or consistent service quality.','Independence and learning support are existing alternatives, not empty territory.']
];
body(ls,'A22:D26',73);stripes(ls,22,26,'D');
ls.getRange('A28:D28').values=[['Assessment','The opportunity is a better combined decision experience.','No empty competitive quadrant or unique feature bundle is established here.','Daylight’s advantage remains a hypothesis to prove through comparative task performance.']];
body(ls,'A28:D28',76);
head(ls,'A30:D30',['Scope','External alternatives','Daylight rows','Source records']);
ls.getRange('A31').values=[['Count']];
ls.getRange('B31:D31').formulas=[['=COUNTA(\'Self-discovery\'!$A$7:$A$25)','=COUNTA(\'Self-discovery\'!$A$26:$A$27)','=COUNTA(Evidence!$A$7:$A$45)']];
ls.getRange('B31:D31').setNumberFormat('0');ls.getRange('B31:D31').format.horizontalAlignment='right';
ls.getRange('A33:D33').values=[['Reading key','Observed means a visible behavior, not verified data or privacy compliance.','Not established means unverified, not absent. Provider claims retain their qualifications.','Six limited browser checks; no accounts, calls, real health data or enrollment.']];body(ls,'A33:D33',63);
ls.tabColor=header;

const mt=sheets['Method and tests'];
base(mt,'D',49,[30,70,72,42],'Definitions, observations and next tests');
mt.getRange('A3').values=[['Task: founder competitive positioning. Accuracy, neutrality and ease are not collapsed into a single score.']];
head(mt,'A6:D6',['Dimension','Operational definition','What would establish an advantage','Boundary of this review']);
mt.getRange('A7:D12').values=[
 ['Self-discovery','User can learn, investigate relevance, compare tradeoffs, ask why and revise a decision while retaining ownership.','Completing matched research tasks independently with accurate understanding and a specific next action.','Capability and workflow evidence; no comparative consumer study.'],
 ['Ease of use','Effort, required prior knowledge, intake burden, interruption, correction and return.','Observe completion, time, errors, repeated facts, abandonment and comprehension on the same task.','Entry friction only in limited desktop guest checks; no numerical ease score.'],
 ['Independence / bias','Separate remuneration, search universe, offered universe, ranking controls and contact autonomy.','Inspect exclusions and repeat decisions while varying commercial inputs, holding consumer needs fixed.','No company is declared unbiased from salary, ownership, disclaimers or marketing alone.'],
 ['Data quality / completeness','Accuracy and conditions within an explicit geography/year/product universe.','Reconcile product identities, costs, networks, drugs, sources, missing facts and refresh dates.','No competitor plan-level dataset or algorithm audit; no inferred Daylight lead.'],
 ['Evidence transparency','Can a person inspect why a result follows and which facts are unknown or unverified?','Reproducible reasons, source/version links, correction history and unresolved checks.','A public explanation or score is not itself a reproducible personal decision record.'],
 ['Access / control','What can be done before contact, account, payment or advisor involvement?','Observe actual boundaries in multiple markets and routes; inspect consent separately.','No contact details is narrower than no personal or device information.']
];body(mt,'A7:D12',85);stripes(mt,7,12,'D');
head(mt,'A14:D14',['Evidence label','Meaning','How to read it','Does not mean']);
mt.getRange('A15:D19').values=[
 ['Observed','A public screen or interaction was directly inspected.','Use only for the exact stated session/stopping point.','Correct backend calculations or privacy compliance.'],
 ['Provider claim','Published by the service itself, including its policy/disclaimer.','Useful for positioning and declared capabilities; actual performance unverified.','Independent verification, legal finding or guaranteed availability.'],
 ['Local technical evidence','Daylight synthetic tests and source contracts, dated October 28.','Preserve failing cases and source/recommendation holds.','Consumer preference, current runtime certification or accepted personal recommendations.'],
 ['Not established','No adequate evidence or no completed test here.','Leave the feature or assurance unresolved.','Proof that the provider lacks it.'],
 ['Target / analytical placement','Owner commitment or this analysis’s classification of a primary user route.','Targets and inferences remain explicit; categories are not exclusive.','A shipped feature, unique market position or measured superiority.']
];body(mt,'A15:D19',65);stripes(mt,15,19,'D');
head(mt,'A21:D21',['Browser check','What was observed','What was not established','Evidence file']);
mt.getRange('A22:D27').values=[
 ['Match Your Medicare','Fictional ZIP/DOB/gender, optional care, MA plan list, change answers and compare controls.','Personal cost accuracy, all-market completeness, video dialogue or supplement comparison.','match-results.png'],
 ['Healthpilot','ZIP/year/type, optional care inputs, extra benefits, utilization and chronic-condition questions.','Plan-results/contact boundary, completed application or model correctness.','healthpilot-flow.png'],
 ['CoverRight','ZIP led to basic DOB/gender/tobacco inputs.','Anonymous results, full comparison, AI dialogue or enrollment.','coverright-entry.png'],
 ['Chapter','Explore on Your Own led to a nine-step intake; first status/drug/benefit questions inspected.','Downstream comparison, contact boundary or advisor quality.','chapter-intake.png'],
 ['eHealth','ZIP entry, public matching description and explicit agent-contact consent.','Results page not reached in limited check; no absolute gate or failure inferred.','ehealth-entry.png'],
 ['Medicare.gov','Guest entry, year and ZIP; account offered separately.','Completed comparison, personalized accuracy or enrollment.','medicare-guest.png']
];body(mt,'A22:D27',77);stripes(mt,22,27,'D');
head(mt,'A29:D29',['Proposed matched test — not executed','Task','Measure / inspect','Purpose']);
mt.getRange('A30:D37').values=[
 ['Start with a question','I am retiring soon. Help me understand what I need to decide.','Help before extensive intake; correct path teaching; explicit supported next step.','Question-first discovery'],
 ['Change priorities','Compare paths, then prioritize doctor access over a low premium.','Tradeoff explanation, changed reasons/results and reuse of prior information.','User control and what-if'],
 ['Correct an uncertain date','Give an uncertain insurance-end date, reject an interpretation, then correct it.','No silent fact replacement; useful clarification and targeted updates.','P6 reliability challenge'],
 ['Keep people separate','Discuss a parent’s coverage and the helper’s different insurance.','Correct attribution, permission and no person merging.','P9 caregiver challenge'],
 ['Distinguish medicine strengths','Report the same medicine at two strengths, then change only one fill.','Separate product identity; correct item binding and affected-result invalidation.','P10 data-integrity challenge'],
 ['Allow unknowns','Leave consequential details unknown and browse honestly labeled information.','No repeated pressure, missing facts visible and no invented recommendation readiness.','P7 completeness challenge'],
 ['Challenge an option','Ask why keeping coverage or a nonpaying option was excluded.','Declared universe, source/date, exclusion rationale and economic invariance.','Independence test'],
 ['Return later','Resume with permission and revise one fact.','Actual persistence receipt, minimized data and no unnecessary repeated intake.','Continuity and effort']
];body(mt,'A30:D37',80);stripes(mt,30,37,'D');
mt.getRange('A39:D42').values=[
 ['Coverage','19 named alternatives plus current and intended Daylight. Direct tools, digital brokerages, public resources, agent-led and fee-based services.','Representative US landscape; a geography/product-specific investigation may change access and scope.','Not an exhaustive market census'],
 ['Source handling','Current provider pages take precedence over legacy directories. Ask Claire’s current agency description supersedes an older non-broker listing.','Primary-domain blocks are labeled. Company-authored hosted descriptions support only their stated service claims.','No anonymous user reviews scored'],
 ['Verification limits','No independent commission, algorithm, full-market, privacy, accessibility or plan-data audit. No matched participant timing or comprehension study.','Browser automation performance is not treated as consumer usability evidence. No provider was contacted.','No adverse conduct finding'],
 ['Daylight protection','No application files, services, data stores, source gates or budget settings changed for this comparison.','Existing defects remain explicit; strategy is not deployment or insurance acceptance.','Research deliverable only']
];body(mt,'A39:D42',89);stripes(mt,39,42,'D');
mt.freezePanes.freezeRows(6);

wb.recalculate();
const check=await wb.inspect({kind:'table',range:'Landscape!A30:D31',include:'values,formulas',tableMaxRows:2,tableMaxCols:4,maxChars:2500});
console.log(check.ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},maxChars:2500});
console.log(errors.ndjson);
const inspection={asOf:data.asOf,external:rows.filter(r=>r[0].startsWith('C')).length,daylightRows:2,sourceRecords:data.sources.length,scope:data.scope};
await fs.writeFile(path.join(dir,'verification.json'),JSON.stringify(inspection,null,2));
const previews=[['Landscape','A2:D19','landscape'],['Self-discovery','A6:G13','self-discovery'],['Self-discovery','H6:L13','self-discovery-right'],['Independence','A6:E13','independence'],['Independence','F6:I13','independence-right'],['Evidence','A6:G12','evidence'],['Method and tests','A6:D12','method'],['Self-discovery','H24:L27','daylight-access'],['Independence','C24:H27','daylight-independence'],['Evidence','I31:I34','source-urls']];
for(const [sheetName,range,name] of previews){const blob=await wb.render({sheetName,range,scale:1,format:'png'});await fs.writeFile(path.join(dir,`evidence/preview-${name}.png`),new Uint8Array(await blob.arrayBuffer()));}
const output=await SpreadsheetFile.exportXlsx(wb);
await output.save(path.join(dir,'Daylight competitive matrix.xlsx'));
console.log(JSON.stringify(inspection));
