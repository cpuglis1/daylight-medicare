"""Summarize saved fictional traces without running servers or reading guest stores."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASELINE={'T01':'intent.goal','T02':'knowledge.general','T03':'comparison.scope.zip',
          'T04':'coverage.requestedStart','T05':'coverage.current','T06':'needs.providersStatus',
          'T07':'needs.medicinesStatus','T08':'needs.travel','T09':'needs.costPreference','T10':'needs.priorities'}
ALIASES={'RC11.C1':('RC11','coverageEnd'),'RC16.C1':('RC16','start'),'RC16.C2':('RC16','priorMedigap')}
UNKNOWN={'','unknown','deferred','not sure','declined','check later'}


def present(value):
    return value is not None and (not isinstance(value,str) or value.strip().casefold() not in UNKNOWN) and value!=[]


def grade(case,id,entity,key):
    guide=case['finalGuide'];record=case['finalRecord'];meta=record['conversation']
    if id in BASELINE:
        field=guide['fields'].get(BASELINE[id],{})
        okay=field.get('status') not in {'unknown','skipped','stale'} and present(field.get('value')) and id not in meta['baselineDispositions']
        if id=='T04' and field.get('value')=='month':okay=okay and present(guide['fields'].get('coverage.requestedStartMonth',{}).get('value'))
        if id in {'T06','T07'} and field.get('value') in {'list','yes'}:
            okay=okay and present(guide['fields'].get('needs.providers' if id=='T06' else 'needs.medications',{}).get('value'))
        return bool(okay)
    fact=record['facts'].get(id,{})
    if fact.get('stale') or record['dispositions'].get(id,{}).get('state') in {'explicit_unknown','deferred','not_saved','needs_review'}:return False
    if id+'.'+entity+'.'+key in meta['skippedDetails']:return False
    value=fact.get('value',{})
    if entity!='profile':
        item_key=id+'.'+entity
        if meta['itemInvalidations'].get(item_key,-1)>meta['itemRevisions'].get(item_key,fact.get('revision',0)):return False
        value=next((row for row in value.get('items',[]) if row['entity']==entity),{})
    return present(value.get(key))


if __name__=='__main__':
    source=HERE/'persona-traces.json'
    cases=json.loads(source.read_text())['cases']
    matrix=json.loads((HERE/'coverage-matrix.json').read_text())['rows']
    browser={p['id']:p for p in json.loads((HERE/'browser-personas.json').read_text())['personas']}
    rows=[];union_asked=set();union_exercised=set()
    for case in cases:
        if '-' in case['id']:continue
        trace=case['trace'][:len(case['steps'])]
        questions=[t['askedBefore'] for t in trace if t['askedBefore']]
        ids={q['id'] for q in questions}
        reached=set(ids)
        for alias,(parent,key) in ALIASES.items():
            if any(q['id']==parent and key in [f['key']for f in q['fields']] for q in questions):reached.add(alias)
        targets={(q['id'],q['entity'],f['key']) for q in questions for f in (q['fields'] or [{'key':'choice'}])}
        missing=[{'id':id,'entity':entity,'field':key} for id,entity,key in sorted(targets) if not grade(case,id,entity,key)]
        known=len(targets)-len(missing)
        exercised={r['id']for r in matrix if case['id']in r['askedBy'] or case['id']in r['reportedBy']}
        union_asked|=reached;union_exercised|=exercised
        assert len(browser[case['id']]['steps'])==len(case['steps'])
        rows.append({'id':case['id'],'name':case['name'],'submittedTurnsBeforeSamples':len(case['steps']),
                     'sendsThroughSampleArrival':len(case['steps'])+1,'inventoryQuestionPresentations':len(questions),
                     'distinctPrimaryQuestionIdsShown':len(ids),'distinctPrimaryQuestionIds':sorted(ids),
                     'inventoryEntriesReachedIncludingChildren':len(reached),'inventoryPercentReached':round(100*len(reached)/41,1),
                     'inventoryEntryIdsReached':sorted(reached),'entriesExercisedIncludingVolunteered':len(exercised),
                     'requestedDetailTargets':len(targets),'knownRequestedDetails':known,
                     'knownRequestedDetailPercent':round(100*known/len(targets),1),'unknownDeferredOrStaleRequestedDetails':missing,
                     'sampleRecordsShown':browser[case['id']]['sampleRecords'],'personalRecommendationsAllowed':False})
    total=sum(r['requestedDetailTargets']for r in rows);known=sum(r['knownRequestedDetails']for r in rows)
    result={'sourceTraceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'personas':rows,
            'methodology':{'questionDenominator':41,'primaryQuestionIds':38,'sharedChildAliases':3,
                           'reached':'An inventory entry was shown, including a child alias when its field appeared within its parent. Repeated prompts/items count once for inventory reach.',
                           'questionPresentations':'Inventory question displays before submitted persona turns. Repeated missing details or different medicines can add displays without adding a distinct ID.',
                           'knownRequestedDetails':'Distinct id/entity/field targets requested in the actual journey, evaluated at the final snapshot. Explicit none/already closes the relevant answer. Unknown, deferred and stale values do not count as known. Volunteered targets that were never requested are excluded from this denominator.',
                           'limitations':'This is an asked-detail completion measure, not whole-profile completeness, validation of each answer, 78-field completeness, or personal recommendation readiness. Source readiness remains held. Scripted synthetic transport/pacing supplies no human time-to-completion evidence.'},
            'overall':{'personaCount':5,'submittedTurnsBeforeSamples':sum(r['submittedTurnsBeforeSamples']for r in rows),
                       'averageSubmittedTurns':sum(r['submittedTurnsBeforeSamples']for r in rows)/5,
                       'averageQuestionPresentations':sum(r['inventoryQuestionPresentations']for r in rows)/5,
                       'knownRequestedDetails':known,'requestedDetailTargets':total,'weightedKnownRequestedDetailPercent':round(100*known/total,1),
                       'distinctInventoryEntriesAskedIncludingChildren':len(union_asked),'askedInventoryPercent':round(100*len(union_asked)/41,1),
                       'distinctEntriesExercisedIncludingVolunteered':len(union_exercised),'exercisedInventoryPercent':round(100*len(union_exercised)/41,1),
                       'allNineJourneysEntriesExercised':len(matrix),'allNineJourneysExercisedPercent':100,
                       'sampleArrivalCount':5,'personalRecommendationReadyCount':0}}
    (HERE/'PROFILE_STATISTICS.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['# Synthetic profile summary statistics','',
           'These statistics describe the five main browser-tested profiles. Four additional HTTP variants are reported separately. All destinations were the five labeled sample records, not validated personal plan results.','',
           '| Persona | Replies before samples | Question prompts | 41 entries reached, including child fields | Requested details known |',
           '| --- | ---: | ---: | ---: | ---: |']
    for r in rows:lines.append(f"| {r['id']} {r['name']} | {r['submittedTurnsBeforeSamples']} | {r['inventoryQuestionPresentations']} | {r['inventoryEntriesReachedIncludingChildren']}/41 ({r['inventoryPercentReached']}%) | {r['knownRequestedDetails']}/{r['requestedDetailTargets']} ({r['knownRequestedDetailPercent']}%) |")
    lines += ['', 'One additional explicit See sample plans submission reaches the samples; Get started is not an answer submission. A later Return action is excluded from arrival counts.', '',
              '“Requested details known” deduplicates the actual requested question/entity/field targets and evaluates their final state. Explicit none or already on Medicare can answer the relevant prompt. An unknown, deferred or invalidated value is incomplete even if an old value remains stored. Volunteered, never-requested fields are excluded. Consequently, 100% means all requested details were answered, not that the entire customer profile or a personal recommendation is ready.', '',
              'Open requested details: P1 insurance end unknown; P2 dependent/family impact unknown; P4 four medicine-1 fill details became stale after its strength correction and were deferred. P3 and P5 answered all requested targets, but independent source gates remain held.', '',
              'Across five profiles: 55 persona replies (11 average), 8.2 inventory prompts per profile, and 40/46 requested targets known (87.0%). The union of asked inventory entries is 25/41 (61.0%); adding volunteered/internal reports reaches 33/41 (80.5%). The four additional variants exercise the remaining eight entries, producing 41/41 conversation-level coverage across nine journeys.', '',
              'The tests are deliberately different scopes. P4 switches from doctors to drug coverage/pricing, corrects a strength and tests units; P5 changes among comparison, payer order, budget, SNP and continuity. Their lengths are stress-path measurements, not typical single-task estimates. Samples were available earlier via explicit browsing, so these are the tested arrival paths rather than a mandatory minimum. There is no measured human duration or proof of exhaustive natural-language accuracy.', '',
              'The three child IDs are aliases within RC11/RC16, so an inventory entry reached is not the same as a separately displayed question. Every completeness percentage is based only on reported input; no profile has independently verified recommendation readiness.']
    (HERE/'PROFILE_STATISTICS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'personas':rows,'overall':result['overall']},indent=2))
