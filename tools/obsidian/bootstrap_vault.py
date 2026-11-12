"""Seed authored navigation, templates and dashboards without replacing existing notes."""
from pathlib import Path
import json
import re
import sys
sys.path.insert(0, str(Path(__file__).parent))
from sync import ROOT, VAULT_NAME, frontmatter, note_path, wiki, rewrite_links, inventory

V = ROOT / VAULT_NAME
def src(path, label=None):
    return wiki(note_path('Local', path.replace('/', ' - '), 'local:' + path), label or Path(path).name)
def drive(id, title):
    return wiki(note_path('Drive', title, 'drive:' + id), title)
def put(path, title, content, **properties):
    p = V / path
    if p.exists(): return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(frontmatter({'title': title, 'type': 'knowledge', 'status': 'authored', 'created': '2026-11-09', **properties}) + '# ' + title + '\n\n' + content.rstrip() + '\n')

put('00 Start/Daylight Home.md', 'Daylight', f'''**Your coverage, plain as day.**

Medicare expertise while the person retains control. Start with {wiki('01 Mission/Mission and principles')} and {wiki('00 Start/Current state')}.

> [!important] Current boundary
> The local advisor and research foundation exist. Personal recommendation, enrollment and pilot admission still require their exact evidence and operating gates. This vault adds knowledge access; it grants no product acceptance.

## Find your way

| I need to… | Open |
|---|---|
| Understand the mission and company | {wiki('01 Mission/Mission and principles')} · {wiki('01 Mission/Strategy and business')} |
| See what exists and what is held | {wiki('02 Product/Feature map')} · {wiki('02 Product/Requirements')} |
| Understand systems and tools | {wiki('03 Architecture/System map')} · {wiki('03 Architecture/Tools and integrations')} |
| Recover why something changed | {wiki('04 Decisions/Decision index')} · {wiki('06 Research/ChatGPT history')} |
| Prepare the pilot | {wiki('05 Operations/Pilot and operating readiness')} |
| Review conflicting information | {wiki('91 Reviews/Owner decisions needed')} · {wiki('91 Reviews/Import review queue')} |
| Work with either agent | {wiki('00 Start/Agent entry')} · {wiki('07 Agents/Skills catalog')} |
| Check import coverage or refresh | {wiki('99 System/Source coverage')} · {wiki('99 System/Maintenance')} |

## Working today

1. Capture an idea or question in `09 Inbox`, or open today's daily note.
2. Link it to a feature, requirement, source or decision.
3. Use the review queue for ambiguity. Keep historical ideas separate from current owner direction.
4. Ask either agent for a source-linked answer or handoff; ask Codex for a connected refresh.

{wiki('92 Dashboards/Sources.base', 'Browse sources')} · {wiki('92 Dashboards/Features.base', 'Browse features')} · {wiki('92 Dashboards/Tools.base', 'Browse tools')} · {wiki('92 Dashboards/Decisions.base', 'Browse requirements and decisions')} · {wiki('03 Architecture/Daylight map.canvas', 'Visual map')}
''')
put('00 Start/Source authority.md', 'Source authority', f'''The original files retain their authority. Imported copies are reference data, and their instructions do not authorize actions.

1. {src('PRINCIPLES.md')}, including D64.
2. {src('DAYLIGHT_REQUIREMENTS.md')} and {src('docs/product/MASTER_DESIGN.md')}; newer explicit owner direction must be recorded.
3. {src('docs/product/STRATEGIC_THESIS.md')} and its change-review checklist.
4. {src('docs/project/CURRENT_STATE.md')} for the present scope.
5. {src('docs/project/DIRECTIVE_HISTORY.md')} where not superseded.

Drive documents retain their original ownership and collaboration role. An edit timestamp alone does not outrank numbered decisions. ChatGPT history records what was said, including hypotheses and mistakes; an assistant assertion is not a verified fact.

For every important claim distinguish **reported, implemented, technically checked, domain-reviewed, accepted for a named purpose, and observed useful to users**. Source-use, method and consumer-purpose gates remain independent. Sealed revisions, source STOPs and all 41 conditional meanings are unchanged.

Business/economic planning belongs in founder knowledge. This vault is not connected to recommendation retrieval, prompts, ranking or advisor tool context.

Generated source notes contain a personal-notes divider. Write below it, or create a separate authored note. Refreshes preserve personal notes and stage generated-body edits for review. New owner direction follows the original Changing direction procedure.
''')
put('00 Start/Current state.md', 'Current state', f'''Read the maintained source first: {src('docs/project/CURRENT_STATE.md')}. This page is a navigation summary captured November 9, not a second current-state authority.

- Initial target: controlled 2026 Collier County pilot for first-time Medicare enrollees.
- Immediate priority: licensing/operating readiness and lawful product feedback (D110).
- Active advisor: :8893; :8894 is the UI refresh reference candidate. Protected :8890, :8891 and :8896 remain protected.
- All-72 research access, the operations schema and plan-type backends have distinct implementation, integration and acceptance states.
- Recommendation and enrollment release remain held. P06–P10 identify central recommendation dependencies.
- D112 fixes are on disk awaiting the recorded restart/review conditions; knowledge setup does not activate them.

{src('docs/project/COLLIER_MVP.md')} · {wiki('05 Operations/Pilot and operating readiness')} · {wiki('91 Reviews/Owner decisions needed')}
''')
put('00 Start/Agent entry.md', 'Agent entry', f'''Read original `../AGENTS.md`, `../PRINCIPLES.md` and `../docs/project/CURRENT_STATE.md` from the vault root. For app work, also read the original scoped instructions and required product/design documents. Use {wiki('00 Start/Source authority')}.

| Task | Read next |
|---|---|
| Mission or positioning | {wiki('01 Mission/Mission and principles')} · {wiki('01 Mission/Strategy and business')} |
| Feature work | {wiki('02 Product/Feature map')} · relevant feature card · original requirement/scoped AGENTS |
| Data or tool access | {wiki('03 Architecture/System map')} · {wiki('03 Architecture/Tools and integrations')} |
| Decision rationale | {wiki('04 Decisions/Decision index')} · source messages/records |
| Knowledge refresh | {wiki('99 System/Maintenance')} · `$daylight-knowledge` |
| Session closeout | `$daylight-handoff` or `$daylight-reflect` |

Search first; load only relevant references. File paths and dates matter more than confident summaries. Read back the original before a consequential change. Document unknowns and source limits. Do not use the vault as a replacement for sealed evidence or infer acceptance from imports.

Both agents share `.agents/skills`; Claude's `.claude/skills` points to the same directory. One writer per file; code work uses deliberate isolated worktrees when concurrent. No schedules or cross-agent task dispatch are implied.
''')
put('01 Mission/Mission and principles.md', 'Mission and principles', f'''Daylight's purpose is **Medicare expertise without giving up control of the process**. Its approved brand line is **Your coverage, plain as day**.

The intended service helps people understand, compare and act on their own terms, with humans available when needed. Ambition is distinct from today's accepted capability.

- The user's interests determine the answer. Economics cannot affect eligibility, inclusion, filtering, ranking, explanation, uncertainty or personal fit.
- Independence and comprehensiveness are separate obligations. Unknown evidence remains unknown and visible.
- Compare coverage paths before policies. Keeping coverage and deferring can be good outcomes.
- The agent should complete supported useful work while the person retains control, corrections and appropriate permissions.
- Explain source, scope, costs, uncertainty and material alternatives.
- Prove the operating model through evidence and observed outcomes.

Authority: {src('PRINCIPLES.md')} · {src('docs/product/INDEPENDENCE_ACCEPTANCE.md')}

Related: {wiki('01 Mission/Strategy and business')} · {wiki('02 Product/Feature map')} · {wiki('01 Mission/Glossary')}
''')
put('01 Mission/Strategy and business.md', 'Strategy and business', f'''The strategic thesis is an AI-native Medicare brokerage with a free consumer platform and a staged continuing service. The proposed broader scope includes supported fulfillment, continuing coverage help, permissioned family participation and services other assistants could call. These are ambitions and hypotheses with separate operating and acceptance requirements.

Start with independent researchers facing their first Medicare transition. Test whether directed conversation improves consequential fact capture, comprehension and control, and separately whether richer evidence improves useful outcomes. Interface preference and test counts are not consumer proof.

Commercial viability must work across neutral outcomes, including keeping coverage, deferral and uncompensated options. Business economics remain downstream of evidence-based decisions and outside advisor decision context.

Primary sources: {src('docs/product/STRATEGIC_THESIS.md')} · {src('docs/company/AI_NATIVE_BROKERAGE_PLAN_2026-11-05.md')} · {src('docs/project/CURRENT_STATE.md')}

Explore history in {wiki('06 Research/ChatGPT history')}; older brainstorming is not automatically the current thesis.
''')
put('01 Mission/Glossary.md', 'Glossary', f'''| Term | Meaning in Daylight |
|---|---|
| Coverage path | Original Medicare with optional Medigap/separate Part D, Medicare Advantage, or another relevant route; considered before individual policies. |
| Offering | A source-identified coverage option with exact plan/year/geography identity; a record is not proof of availability or personal eligibility. |
| Report | What the person says about their situation; distinct from an externally verified finding. |
| Conditional meaning | One of the protected 41 semantic requirements; preserve the original contract rather than redefining it here. |
| Unknown | Missing or unverified information, never automatically poor fit. |
| Hold | An unresolved dependency preventing a specified conclusion or use. |
| Source STOP | A source-specific access/use restriction that discovery or a new tool cannot bypass. |
| Sealed revision | Immutable evidence/code/data selection; changes require a new revision and applicable review. |
| Source-use acceptance | Permission/evidence for using an exact source in its declared scope. |
| Method acceptance | Review of the interpretation/calculation method. |
| Consumer-purpose acceptance | Authorization for a specified consumer-facing use; not implied by acquisition or testing. |
| Independence | Commercial economics do not influence substantive coverage decisions. |
| Comprehensiveness | The actual relevant universe and exclusions are accounted for; independence alone does not establish it. |
| Handoff | Permissioned transfer/context for a supported action; preparation alone sends nothing. |

Definitions are navigation aids grounded in {src('PRINCIPLES.md')} and {src('docs/project/CURRENT_STATE.md')}. Resolve disagreements against the original contracts and recorded direction.
''')

# Preserve the dated capability ledger, including its stated limits.
source_mapping = {r['path']: note_path('Local', r['path'].replace('/', ' - '), 'local:' + r['path']) for r in inventory(ROOT) if r['disposition'] == 'snapshot'}
cap_source = (ROOT/'docs/project/CAPABILITIES.md').read_text()
feature_links=[]
for line in cap_source.splitlines():
    if not re.match(r'\| \*\*CAP-\d+', line): continue
    cols=[x.strip() for x in line.strip('|').split('|')]
    cols = [rewrite_links(c, ROOT/'docs/project/CAPABILITIES.md', ROOT, source_mapping) for c in cols]
    title=cols[0].replace('**',''); id=title.split()[0]
    path='02 Product/Features/'+title.replace('/','-')+'.md'
    feature_links.append(wiki(path,title))
    put(path,title,f'''**Dated capability assessment: November 2, 2026.** Reconcile with {src('docs/project/CURRENT_STATE.md')} and later exact evidence before acting.

## Recorded maturity

{cols[1]}

## What the ledger records

{cols[2]}

## Principal gap and next deliverable

{cols[3]}

## Verification contract

Use the original linked evidence in {src('docs/project/CAPABILITIES.md')}. Identify the feature's actual entry points, expected outcome, unknown/error/correction paths, exact revision and existing permitted offline checks. Record executed checks in a separate evidence note. This import does not claim fresh feature verification.

{wiki('02 Product/Feature map')} · {wiki('02 Product/Requirements')} · {wiki('00 Start/Source authority')}
''',type='feature',feature_id=id,status='dated_assessment',assessed_on='2026-11-02',implementation=cols[1],acceptance='see_exact_source_and_purpose',verification='not_rerun_by_knowledge_setup')
put('02 Product/Feature map.md','Feature map','The fifteen company capabilities connect the product, data, operations and evidence. Cards preserve the November 2 assessment; later current-state records govern.\n\n'+ '\n'.join('- '+l for l in feature_links) + '\n\n' + src('docs/project/CAPABILITIES.md')+' · '+src('docs/project/COLLIER_MVP.md')+'\n\n'+wiki('92 Dashboards/Features.base'))

# Requirement rows are indexed verbatim; newer change-log entries stay linked, not flattened.
req_text=(ROOT/'DAYLIGHT_REQUIREMENTS.md').read_text(); ids={}
for line in req_text.splitlines():
    m=re.match(r'\| (D\d+) \| (.+)',line)
    if m: ids[m.group(1)]=line
for m in re.finditer(r'^- \*\*[^\n]*?\b(D\d+)\b[^\n]*',req_text,re.M):
    ids.setdefault(m.group(1),m.group(0))
req_links=[]
for id,record in sorted(ids.items(),key=lambda x:int(x[0][1:])):
    record = rewrite_links(record, ROOT/'DAYLIGHT_REQUIREMENTS.md', ROOT, source_mapping)
    path='04 Decisions/Requirements/'+id+'.md';req_links.append(wiki(path,id))
    put(path,id,f'''## Recorded requirement or change-log entry

{record}

Read the complete original {src('DAYLIGHT_REQUIREMENTS.md')} for chronology and superseding entries, and {src('docs/product/MASTER_DESIGN.md')} for current flow. This is an index of recorded text, not a conclusion that the requirement is implemented or still governs every historical variant.

{wiki('04 Decisions/Decision index')} · {wiki('00 Start/Source authority')}
''',type='requirement',requirement_id=id,status='read_original_chronology')
put('02 Product/Requirements.md','Requirements',f'''The requirement register is {src('DAYLIGHT_REQUIREMENTS.md')}. Requirement IDs connect owner direction to features and evidence. Later explicit direction may supersede an older row; do not treat every historical row as current.

{wiki('04 Decisions/Decision index')} · {wiki('92 Dashboards/Decisions.base')}

The historical D14 row names 2027. The newer D91/current-state pilot is **2026 Collier County**. Keep that supersession explicit.

'''+' · '.join(req_links))
put('04 Decisions/Decision index.md','Decision index',f'''Binding direction lives in {src('DAYLIGHT_REQUIREMENTS.md')}, {src('docs/product/MASTER_DESIGN.md')} and {src('docs/project/DIRECTIVE_HISTORY.md')} under the current authority order.

Important navigation: D64 independence; D73 strategic thesis; D91 Collier scope and release sequence; D94 preserved storage/evidence; D95 database readiness; D96 plan-type research backend; D98–D105 pilot/security decisions; D109 conversation rules; D110 licensing and feedback priority; D111–D112 evaluation/fixes; D113 knowledge setup.

{wiki('02 Product/Requirements')} · {wiki('92 Dashboards/Decisions.base')} · {wiki('91 Reviews/Owner decisions needed')}

Record a new owner decision with source/date, requirement entry, directive-history entry and the affected current-state lines. Leave prior evidence intact. A historical ChatGPT brainstorm or an agent's reflection is not a new direction.
''')

tool_data=[
 ('Advisor 8893','active development','alternatives/advisor-first/','docs/project/CURRENT_STATE.md','Local advisor development; restart and acceptance states must be checked against current evidence.'),
 ('UI refresh 8894','candidate surface','alternatives/advisor-first/web-8894/','docs/project/CURRENT_STATE.md','Forwards other requests to 8893; promotion and owner review are separate.'),
 ('Protected variants','protected','alternatives/chat-first/','AGENTS.md','8890, 8891, 8896 and their stores are not migrated by this setup.'),
 ('Research database and API','research only','infrastructure/daylight-data/','infrastructure/daylight-data/README.md','Public-evidence plane, immutable lineage, role and source STOP controls; not consumer authority.'),
 ('Operations schema','implemented not connected','infrastructure/daylight-operations/','infrastructure/daylight-operations/README.md','Permissioned customer-plane and numeric traces; current-state records it as not deployed/connected to advisor.'),
 ('Plan-type research backend','implemented research held for consumers','infrastructure/daylight-data/src/daylight_data/plan_types/','docs/reviews/collier-plan-type-backend-2026-11-06/implementation-r1/README.md','PDP and Medigap source/serving data; source/method/output approvals remain separate.'),
 ('Offline evaluation harness','offline tool','tools/evaluation/','tools/evaluation/README.md','Five suites; fictional/offline execution. Owner evaluates live conversational quality.'),
 ('Paperclip','documented on demand','tools/paperclip/','docs/project/PAPERCLIP.md','Existing coordinator; timer heartbeats off. No configuration or work dispatch changed here.'),
 ('Google Drive connector','available in Codex','docs/project/OBSIDIAN.md','docs/project/OBSIDIAN.md','Captured documents are local snapshots; refresh requires authorized connected tools.'),
 ('ChatGPT history reader','available in Codex','docs/project/OBSIDIAN.md','docs/project/OBSIDIAN.md','Relevant owner history only. No Codex/Claude histories, customer stores or all-account content dump.'),
 ('Codex and Claude shared skills','configured','tools/obsidian/skills.lock.json','docs/project/OBSIDIAN.md','One .agents/skills source; .claude/skills links to it. Runtime model validation is not part of setup.'),
 ('Obsidian refresh and backup','local configured','tools/obsidian/sync.py','docs/project/OBSIDIAN.md','On-demand projection, conflict staging, consistency checks and verified same-Mac archives.')]
tool_links=[]
for name,state,location,evidence,limit in tool_data:
    path='03 Architecture/Tools/'+name+'.md';tool_links.append(wiki(path,name))
    put(path,name,f'''**Recorded state:** {state}. Product tool states come from the linked source; this setup does not restart or probe those services.

**Location:** [{location}]({(ROOT/location).as_uri()})

{limit}

**Evidence/runbook:** {src(evidence)}

{wiki('03 Architecture/Tools and integrations')} · {wiki('00 Start/Source authority')}
''',type='tool',status=state,scope='founder_engineering_knowledge',checked_on='2026-11-09',check_basis='configuration_or_document_read_not_live_execution')
put('03 Architecture/Tools and integrations.md','Tools and integrations','Start with the evidence/runbook on each card. A documented tool, connected tool and verified supported action are different states.\n\n'+'\n'.join('- '+x for x in tool_links)+'\n\n'+wiki('92 Dashboards/Tools.base'))
put('03 Architecture/System map.md','System map',f'''The founder knowledge vault connects source documents and engineering workflows. It is separate from the product's decision and customer planes.

```mermaid
flowchart TD
  Local[Local governing documents and evidence] --> Vault[Private Obsidian knowledge]
  Drive[Google Drive snapshots] --> Vault
  History[Relevant owner ChatGPT history] --> Vault
  Vault --> Agents[Codex and Claude Code]
  Agents --> Review[Reviewable changes and evidence]
  Review --> Local
  Research[Public evidence research plane] --> Gates[Source, method and purpose gates]
  Gates --> Advisor[Supported advisor tools]
  Operations[Permissioned operations plane] -. not connected yet .-> Advisor
```

The vault is not a source of consumer recommendation authority. Keep commercial planning outside decision retrieval and model inputs. Runtime integrations remain exactly as recorded in {src('docs/project/CURRENT_STATE.md')}.

{src('docs/ARCHITECTURE.md')} · {src('infrastructure/daylight-data/README.md')} · {src('infrastructure/daylight-operations/README.md')} · {wiki('03 Architecture/Tools and integrations')} · {wiki('03 Architecture/Daylight map.canvas')}
''')
put('05 Operations/Pilot and operating readiness.md','Pilot and operating readiness',f'''D110 prioritizes licensing and legally scoped product feedback. The pilot plan, source acceptance and operating permissions are distinct workstreams.

Read {src('docs/project/CURRENT_STATE.md')} and {src('docs/project/COLLIER_MVP.md')} before relying on older plans. The working Drive plan is {drive('1p_iJMHDlZGM5cMRniWyp5lLk9QJDo3WY4ny1iVI0cL0','Daylight_MVP_Requirements_2026-11-07_Plan')}.

Track participant scope, consent/privacy readiness, licensing/operating route, exact source/method/purpose approvals, deployment evidence and an enrollment/handoff route separately. The documented $100 cumulative pilot model budget is distinct from local development allowances. A spend alert is not deployed enforcement.

Human-involvement choice, counsel questions, exact AWS verification and enrollment/FMO route remain recorded open items. This knowledge setup makes no legal or launch determination.

{src('docs/company/AI_NATIVE_BROKERAGE_PLAN_2026-11-05.md')} · {src('docs/reviews/pilot-security-stage1-2026-11-07/README.md')} · {wiki('91 Reviews/Owner decisions needed')}
''')
put('06 Research/Research index.md','Research index',f'''Research sources include local research/evidence packets, Drive planning and competitive material, and selected historical conversations.

- {wiki('06 Research/ChatGPT history')}
- {wiki('92 Dashboards/Sources.base')}
- {src('docs/product/STRATEGIC_THESIS.md')}
- {wiki('99 System/Local file catalog')}

Distinguish source publication, inference, owner hypothesis and observed outcome. Capture exact source/date/scope and counterevidence. Repeated claims across AI-generated documents are not independent corroboration.
''')
selection=json.loads((V/'.knowledge-imports/chatgpt-selection.json').read_text())
chatlinks=[]
for id,entry in selection.items():
    if entry['disposition']=='excluded_unrelated':continue
    chatlinks.append('- '+wiki(note_path('ChatGPT',entry['title'],'chatgpt:'+id),entry['title'])+' — '+entry['disposition'].replace('_',' '))
put('06 Research/ChatGPT history.md','ChatGPT history','The available history listing was paginated: 146 active chats, no archived chats returned. All titles were screened; 20 directly relevant or ambiguous business discussions were read. Thirteen are retained here; seven unrelated inspected conversations were removed from staging, leaving their originals untouched. Other clearly unrelated personal chats were not read.\n\nFive retained discussions directly address Daylight or Medicare; eight are background context flagged for relevance review. This is relevance-based selection, not a claim that title screening finds every hidden Daylight mention.\n\n'+'\n'.join(chatlinks)+'\n\nOwner messages and assistant replies are labeled separately. Missing attachment text and unresolved historic citations are recorded in the import queue. Earlier Medicare/Medicaid and retirement concepts remain historical exploration, not a replacement for the current mission.')
put('07 Agents/Lessons.md','Lessons',f'''Capture a durable lesson only when an observed event, owner correction or verified check supports it. Use the Lesson template and record scope, evidence and a review date. Keep proposed practices distinct from governing requirements.

Initial setup lesson: **knowledge refresh must preserve annotations and detect edited generated content**. The isolated fictional tests in `tools/obsidian/test_sync.py` exercise those behaviors. This lesson applies to knowledge projection, not to product source acceptance.

{wiki('07 Agents/Skills catalog')} · {wiki('00 Start/Agent entry')}
''')
lock=json.loads((ROOT/'tools/obsidian/skills.lock.json').read_text())
skillnames=sorted(p.name for p in (ROOT/'.agents/skills').iterdir() if (p/'SKILL.md').exists())
put('07 Agents/Skills catalog.md','Skills catalog','Codex and Claude Code use one project skill directory. Invoke a relevant skill by name; do not load every skill on every task.\n\n'+'\n'.join('- ['+n+']('+ (ROOT/'.agents/skills'/n/'SKILL.md').as_uri()+')' for n in skillnames)+'''\n\nUpstream foundations:

- [Kepano Obsidian skills](https://github.com/kepano/obsidian-skills): Markdown, Bases and Canvas format skills.
- [Matt Pocock skills](https://github.com/mattpocock/skills): adapted handoff/domain modeling and diagnostic workflow concepts.
- [Lauren Tan brainmaxxing](https://github.com/poteto/brainmaxxing): reflection and memory review concepts, adapted to Daylight governance.
- [Lauren Tan feature verification](https://github.com/poteto/verification-skill-example): feature-to-check maps; the example's omitted drivers are not installed as functioning tools.

Pinned revisions and installed file hashes are recorded in `tools/obsidian/skills.lock.json`. No auto-updates, startup memory-dump hooks, autonomous schedules or paid model evaluations were installed. Changes to a skill need a concrete reason and proportionate behavior checks.
''')
put('91 Reviews/Owner decisions needed.md','Owner decisions needed',f'''The entries below separate unresolved choices from already-resolved historical drift. Originals have not been changed to reconcile these items.

## Owner choices

1. **Competitive matrix authority.** Two distinct Drive documents share the title “Daylight competitive matrix.” Keep both until you designate the working one or reconcile them. {drive('16TvznB2V1_fns3TBNZPTROwrV98t9dylL3s1J75d0_g','Daylight competitive matrix')} · {drive('154X3wrMq9ly4O23i7uGF6Yjaev0BM1ueLpO5LwyF5X0','Daylight competitive matrix')}.
2. **Historical context scope.** Eight ChatGPT discussions are retained as possible background. Review their relevance in {wiki('06 Research/ChatGPT history')}; none is promoted to Daylight policy.
3. **Independent backup destination.** The setup creates and verifies same-Mac archives. Select an off-machine destination when ready; no cloud publication or new subscription was enabled.
4. **Existing business decisions.** Async licensed review preference still needs the numbered decision described by CURRENT_STATE; counsel/operating route, exact AWS verification and enrollment/FMO route remain open. Knowledge setup does not settle them. {src('docs/project/CURRENT_STATE.md')}.

## Known supersession and document drift

- **2027 vs 2026:** older requirement/source materials refer to 2027. Current pilot authority is 2026 Collier County under newer D91/current state. The old bytes remain unchanged.
- **Vendor register:** the explicitly superseded HP-03 Word draft remains historical; the live Google Doc is the working register. Do not merge them by timestamp alone.
- **Capability ledger:** November 2 statuses predate November 5–9 work. Cards retain that assessment date and direct readers to current-state and later evidence.
- **Stack implementation record:** its original PostgreSQL/cloud-choice gaps are dated; CURRENT_STATE records later tests and AWS direction. Keep historical execution evidence intact.
- **Assistant market/legal claims:** historical chat claims and internal citation placeholders require source verification before reuse in consequential decisions.

## Extraction limits

- The Drive Landscape spreadsheet export returned 403. Its source link and metadata are retained; no workaround was attempted.
- The large October 19 audit workbook text fetch failed in transport. A same-name, same-size local file exists, but byte equivalence to Drive has not been established. Both originals remain available.
- Readable spreadsheet/deck/Word copies are not full-fidelity archives of formulas, comments, formatting or embedded media. Open originals for those details.

For per-source details use {wiki('91 Reviews/Import review queue')}. Record resolutions in separate notes with source IDs, evidence and date. Preserve this initial audit as history.
''')
put('99 System/Maintenance.md','Maintenance',f'''## Local refresh

```sh
cd /Users/cep4u/daylight
python3 tools/obsidian/sync.py refresh
python3 tools/obsidian/sync.py check
python3 tools/obsidian/sync.py backup
```

These commands require no new paid API and make no network calls. They refresh local files and render the latest staged connected captures. For live Drive/ChatGPT refresh, ask Codex to use `$daylight-knowledge`; the connected refresh procedure uses authorized connectors. Claude can consume the same local notes without a separate Drive login.

## Where to write

- Your own ideas and annotations: `09 Inbox`, `08 Journal`, subject notes, or below a source note's personal-notes divider.
- Source bodies: generated. An edit there causes a conflict copy rather than silent overwrite.
- Conflicts: write a separate resolution note in `91 Reviews`, referencing original evidence.
- Decisions: follow {wiki('00 Start/Source authority')}; a vault note alone does not grant acceptance.

## Weekly review, when useful

Review changed sources and unanswered decisions, clear the inbox into linked notes, check the last capture date, and create a backup. This is a suggested manual habit; no recurring task is installed.

Search with Quick Switcher or global search. Use Bases for statuses and filters, backlinks for context, and the Canvas for the system map. Core plugins suffice; no community plugin was installed.

Full runbook: {src('docs/project/OBSIDIAN.md')}. Coverage: {wiki('99 System/Source coverage')}. Verification: {wiki('99 System/Setup verification')}.
''')

templates={
'Daily note':'## Focus\n\n- [ ] \n\n## Work and evidence\n\n## Decisions and questions\n\n## Next session\n',
'Feature':'## User outcome and entry points\n\n## Requirements and sources\n\n## Current behavior\n\n## Unknown, error and correction paths\n\n## Verification actually run\n\n## Acceptance and remaining gaps\n',
'Decision':'## Decision or proposal\n\nStatus: proposal until recorded through project governance.\n\n## Owner instruction and date\n\n## Evidence and alternatives\n\n## Consequences and scope\n\n## Requirement and directive links\n',
'Research':'## Question\n\n## Findings and source dates\n\n## Inferences and counterevidence\n\n## Unknowns\n\n## Relevance to Daylight\n',
'Handoff':'## Objective and scope\n\n## Exact current artifacts\n\n## Decisions and evidence\n\n## Checks actually run\n\n## Remaining work and next step\n',
'Lesson':'## Observed lesson\n\n## Evidence\n\n## Applies when\n\n## Exceptions\n\n## Review date\n',
'Conflict':'## Conflicting claims\n\n## Original sources, versions and dates\n\n## Applicable authority\n\n## Decision needed\n\n## Resolution and evidence\n'}
for name,body in templates.items():
    p=V/'98 Templates'/f'{name}.md'
    if not p.exists():p.write_text('---\ntype: '+name.lower().replace(' ','_')+'\nstatus: draft\ncreated: "{{date:YYYY-MM-DD}}"\n---\n\n# {{title}}\n\n'+body)
put('08 Journal/2026-11-09.md','2026-11-09','## Focus\n\nSet up shared Daylight knowledge while preserving source authority.\n\n## Work and evidence\n\n'+wiki('99 System/Setup verification')+'\n\n## Decisions and questions\n\n'+wiki('91 Reviews/Owner decisions needed')+'\n\n## Next session\n\nOpen Daylight Home and try a source-linked question with either agent.')
put('09 Inbox/Start here.md','Inbox','Capture a thought, question or rough draft here. Link it to a source or subject when you know where it belongs. Leave uncertain ideas as proposals; do not turn them into accepted facts.')

for name,kind,order in [('Sources','source',['file.name','source_kind','source_role','status','fidelity','source_modified','captured_at','review_state']),('Features','feature',['file.name','feature_id','implementation','assessed_on','acceptance','verification']),('Tools','tool',['file.name','status','checked_on','check_basis']),('Decisions','requirement',['file.name','requirement_id','status'])]:
    p=V/'92 Dashboards'/f'{name}.base'
    if not p.exists():
        p.write_text('filters:\n  and:\n    - \'!file.inFolder("98 Templates")\'\n    - \'type == "'+kind+'"\'\n    - \'file.ext == "md"\'\nviews:\n  - type: table\n    name: "'+name+'"\n    order:\n'+'\n'.join('      - '+x for x in order)+'\n')

canvas=V/'03 Architecture/Daylight map.canvas'
if not canvas.exists():
    paths=['01 Mission/Mission and principles.md','02 Product/Feature map.md','03 Architecture/System map.md','05 Operations/Pilot and operating readiness.md','04 Decisions/Decision index.md','06 Research/Research index.md','07 Agents/Skills catalog.md','91 Reviews/Owner decisions needed.md']
    nodes=[{'id':f'{i+1:016x}','type':'file','file':path,'x':(i%4)*470,'y':(i//4)*360,'width':420,'height':300} for i,path in enumerate(paths)]
    edges=[{'id':f'{100+i:016x}','fromNode':f'{a:016x}','toNode':f'{b:016x}','fromSide':'right','toSide':'left','label':label} for i,(a,b,label) in enumerate([(1,2,'guides'),(2,3,'implemented by'),(3,4,'operated through'),(5,1,'records direction'),(6,5,'informs'),(7,3,'supports work'),(8,5,'needs resolution')])]
    canvas.write_text(json.dumps({'nodes':nodes,'edges':edges},indent=2))

# Update only intended settings; preserve all unrelated existing keys and files.
def config(name, changes):
    p=V/'.obsidian'/name;d=json.loads(p.read_text()) if p.exists() else {};d.update(changes);p.write_text(json.dumps(d,indent=2)+'\n')
config('templates.json',{'folder':'98 Templates','dateFormat':'YYYY-MM-DD','timeFormat':'HH:mm'})
config('daily-notes.json',{'folder':'08 Journal','format':'YYYY-MM-DD','template':'98 Templates/Daily note'})
config('app.json',{'alwaysUpdateLinks':True,'newFileLocation':'folder','newFileFolderPath':'09 Inbox','attachmentFolderPath':'99 System/Attachments'})
bookmarks=V/'.obsidian/bookmarks.json';b=json.loads(bookmarks.read_text()) if bookmarks.exists() else {'items':[]}
for path in ['00 Start/Daylight Home.md','00 Start/Current state.md','91 Reviews/Owner decisions needed.md','92 Dashboards/Sources.base','99 System/Maintenance.md']:
    if not any(x.get('path')==path for x in b['items']):b['items'].append({'type':'file','ctime':1794268800000,'path':path,'title':Path(path).stem})
bookmarks.write_text(json.dumps(b,indent=2)+'\n')
print(json.dumps({'feature_cards':len(feature_links),'requirement_cards':len(req_links),'tool_cards':len(tool_links),'templates':len(templates),'skills':len(skillnames)}))
