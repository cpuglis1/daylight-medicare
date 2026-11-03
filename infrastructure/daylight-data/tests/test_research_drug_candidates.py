"""Literal research discovery, synthetic sources and no customer/database writes."""
from contextlib import contextmanager
import copy
import json
import re

import pytest

from daylight_data.serving.binding import ResearchServingError, digest
from daylight_data.serving.drug_candidates import (ACCESS, CONTROLS, SEARCH, EXPECTED_CONTROLS,
    SELECTION, DrugCandidateRepository, candidate_repository_from_env)
from test_research_identity import binding, record


def item(name='Synthetic ingredient 5 MG ORAL TABLET', *, ordinal=1, cui=None,
         strength='Synthetic ingredient 5 MG', form='ORAL TABLET', concept='SCD', partial=False):
    row=record(cui or str(1000000+ordinal),ordinal,concept=concept,partial=partial)
    payload=json.loads(row['raw_payload']['payload']);payload['name']=name
    row['fields']['drug_name']=name
    if not partial:
        payload.update(ingredient_strength_description=strength,dose_form=form)
        row['fields'].update(ingredient_strength_description=strength,dose_form=form)
    row['raw_payload']['payload']=json.dumps(payload)
    row['raw_sha256']=digest(row['raw_payload'])
    return row


def like(pattern,value):
    if pattern is None:return None
    pieces=[];index=0
    while index<len(pattern):
        char=pattern[index]
        if char=='!':
            index+=1;pieces.append(re.escape(pattern[index]))
        elif char=='%':pieces.append('.*')
        elif char=='_':pieces.append('.')
        else:pieces.append(re.escape(char))
        index+=1
    return bool(re.fullmatch(''.join(pieces),value,re.IGNORECASE|re.DOTALL))


class Cursor:
    def __init__(self,rows):self.rows=rows
    def fetchall(self):return copy.deepcopy(self.rows)
    def fetchone(self):return copy.deepcopy(self.rows[0])


class Connection:
    def __init__(self,rows):
        self.rows=rows;self.calls=[];self.access=[];self.controls=copy.deepcopy(EXPECTED_CONTROLS)
        self.override=None
    def execute(self,query,params):
        self.calls.append((query,copy.deepcopy(params)))
        if query==ACCESS:return Cursor(self.access)
        if query==CONTROLS:return Cursor([self.controls])
        if query!=SEARCH:raise AssertionError('Unexpected discovery query')
        if self.override is not None:return Cursor(self.override)
        derivation,after,name,strength,unused_strength,form,unused_form,limit,unused_name,unused_s,unused_f=params
        out=[]
        for original in sorted(self.rows,key=lambda r:r['source_row_ordinal']):
            row=copy.deepcopy(original);fields=row['fields']
            if row['source_row_ordinal']<=after or not like(name,fields['drug_name']):continue
            sm=None if not fields.get('ingredient_strength_description','') or not fields['ingredient_strength_description'].strip() else like(strength,fields['ingredient_strength_description'])
            fm=None if not fields.get('dose_form','') or not fields['dose_form'].strip() else like(form,fields['dose_form'])
            if strength is not None and sm is False or form is not None and fm is False:continue
            row.update(name_literal_observed=True,strength_literal_observed=sm,form_literal_observed=fm)
            out.append(row)
        return Cursor(out[:limit])


class FixtureRepository(DrugCandidateRepository):
    def __init__(self,rows=None):
        super().__init__(lambda:None,binding())
        self.connection=Connection([item()] if rows is None else rows);self.reads=0
    @contextmanager
    def _read(self):
        self.reads+=1
        yield self.connection,[{'source_id':'L03','state':'unrelated_not_identity_permission'}]


def test_literal_name_strength_form_discovery_retains_exact_evidence_and_all_holds():
    repository=FixtureRepository()
    out=repository.search(' synthetic ',strength_text='5 mg',form_text='tablet')
    candidate=out['candidates'][0]
    assert out['requested']['name_text']=='synthetic'
    assert candidate['identity']['ingredient_strength_description']=='Synthetic ingredient 5 MG'
    assert candidate['identity']['dose_form']=='ORAL TABLET'
    assert candidate['raw_source_payload']==repository.connection.rows[0]['raw_payload']
    assert candidate['conditions']==repository.connection.rows[0]['conditions']
    assert candidate['lineage']['raw_sha256']==digest(candidate['raw_source_payload'])
    assert candidate['lexical_states']==dict.fromkeys(('name','strength','form'),'literal_substring_observed')
    assert candidate['lexical_occurrence_is_not_identity_or_dose_equivalence']
    assert candidate['discovery_state']=='requires_explicit_identity_confirmation'
    assert candidate['requires_identity_confirmation'] and not candidate['automatic_profile_binding']
    assert candidate['lookup_snapshot_id']==out['binding']['snapshot_id']
    assert out['discovery_state']=='literal_candidates_require_confirmation'
    assert out['operator_only'] and out['binding']['accepted_release_id'] is None
    assert all(purpose['state']=='held' for purpose in out['authority'].values())
    assert not out['consumer_release'] and not out['clinical_or_dose_equivalence']
    assert not out['personal_coverage_result'] and not out['clinical_substitution']
    assert out['dictionary_scope']['offering_grain'] is None
    assert 'county_fips' not in out['scope']


def test_partial_strength_form_remains_unknown_even_with_apparent_details_in_name():
    out=FixtureRepository([item(partial=True)]).search('Synthetic',strength_text='5 MG',form_text='TABLET')
    candidate=out['candidates'][0]
    assert candidate['identity']['dose_form'] is None
    assert candidate['identity']['ingredient_strength_description'] is None
    assert candidate['lexical_states']['strength']==candidate['lexical_states']['form']=='source_detail_unknown'
    assert candidate['source_history']['isCurrent']=='YES'
    assert not candidate['current_terminology_status_verified']
    assert out['partial']['is_partial']
    assert out['partial']['source_dictionary_missing_details']=={'name':0,'strength':28,'form':28}


def test_optional_filters_keep_partial_candidates_and_exclude_only_explicit_literal_nonmatches():
    rows=[item(ordinal=1),item(ordinal=2,strength='Synthetic ingredient 10 MG'),
          item(ordinal=3,form='INJECTION'),item(ordinal=4,partial=True)]
    out=FixtureRepository(rows).search('Synthetic',strength_text='5 MG',form_text='TABLET')
    assert [c['lineage']['source_row_ordinal'] for c in out['candidates']]==[1,4]
    assert out['partial']['optional_filters_retain_name_candidates_with_missing_source_details']


def test_lexical_strength_occurrence_is_not_a_dose_equivalence_claim():
    out=FixtureRepository([item(strength='Synthetic ingredient 2.5 MG')]).search('Synthetic',strength_text='5 MG')
    assert len(out['candidates'])==1
    assert out['candidates'][0]['lexical_states']['strength']=='literal_substring_observed'
    assert out['candidates'][0]['lexical_occurrence_is_not_identity_or_dose_equivalence']
    assert not out['clinical_or_dose_equivalence']


@pytest.mark.parametrize('concept',['GPCK','BPCK'])
def test_pack_concepts_are_returned_without_decomposition_or_substitution(concept):
    out=FixtureRepository([item(concept=concept)]).search('Synthetic')
    assert out['candidates'][0]['identity_grain']=='pack_concept'
    assert 'PACK_CONCEPT_NOT_SINGLE_PRODUCT' in out['candidates'][0]['reason_codes']
    assert out['candidates'][0]['lexical_states']['strength']=='not_requested'
    assert not out['clinical_substitution']


@pytest.mark.parametrize('needle',['%','_','!','\\',"';SELECT 1--"])
def test_wildcards_backslash_and_sql_text_are_literal_bound_parameters(needle):
    row=item(name='Synthetic '+needle+' source text')
    repository=FixtureRepository([row,item(name='Unrelated source record',ordinal=2)])
    out=repository.search(needle)
    assert len(out['candidates'])==1
    query,params=next((q,p) for q,p in repository.connection.calls if q==SEARCH)
    assert query==SEARCH and query.count("ESCAPE '!'")==6
    assert params[2]=='%'+needle.replace('!','!!').replace('%','!%').replace('_','!_')+'%'
    assert params[2]==params[8]
    assert 'Unrelated' not in out['candidates'][0]['identity']['drug_name']


def test_no_fuzzy_synonym_brand_or_unit_expansion_and_no_result_stays_unknown():
    repository=FixtureRepository([item(name='Synthetic ingredient 0.5 MG ORAL TABLET')])
    for query in ('Syntetic','different brand','500 MCG','unlisted'):
        out=repository.search(query)
        assert out['discovery_state']=='not_observed_in_selected_literal_query'
        assert out['candidates']==[] and not out['personal_coverage_result']
    out=repository.search('Synthetic',strength_text='500 MCG')
    assert out['candidates']==[] and not out['clinical_or_dose_equivalence']


def test_continuation_keeps_source_order_nonoverlap_and_same_snapshot():
    rows=[item(ordinal=i,cui=str(1000100-i)) for i in range(1,6)]
    repository=FixtureRepository(list(reversed(rows)))
    first=repository.search('Synthetic',limit=2)
    assert first['page']['has_more'] and first['page']['next_after_ordinal']==2
    second=repository.search('Synthetic',limit=2,after_ordinal=2,expected_snapshot_id=first['binding']['snapshot_id'])
    last=repository.search('Synthetic',limit=2,after_ordinal=4,expected_snapshot_id=first['binding']['snapshot_id'])
    assert [[c['lineage']['source_row_ordinal'] for c in p['candidates']] for p in (first,second,last)]==[[1,2],[3,4],[5]]
    assert not last['page']['has_more'] and last['page']['next_after_ordinal'] is None
    assert set(c['candidate_id'] for c in first['candidates']).isdisjoint(c['candidate_id'] for c in second['candidates'])
    assert first['binding']==second['binding']==last['binding']


@pytest.mark.parametrize('name,kwargs',[(None,{}),('',{}),(' ',{}),(True,{}),('a'*161,{}),
    ('Synthetic\n',{}),('Synthetic',{'strength_text':''}),('Synthetic',{'form_text':False}),
    ('Synthetic',{'limit':True}),('Synthetic',{'limit':0}),('Synthetic',{'limit':21}),
    ('Synthetic',{'after_ordinal':True}),('Synthetic',{'after_ordinal':4548}),
    ('Synthetic',{'after_ordinal':1}),('Synthetic',{'expected_snapshot_id':{}}),
    ('Synthetic',{'year':True}),('Synthetic',{'year':2026.0}),('Synthetic',{'year':2027})])
def test_invalid_or_unbound_discovery_never_reads(name,kwargs):
    repository=FixtureRepository()
    with pytest.raises(ResearchServingError,match='INVALID_LITERAL_DRUG_REQUEST'):
        repository.search(name,**kwargs)
    assert repository.reads==0 and not repository.connection.calls


def test_missing_source_permission_is_explicit_and_stop_state_changes_snapshot_without_authority():
    repository=FixtureRepository();first=repository.search('Synthetic')
    assert first['source_access_registration']['state']=='unregistered'
    assert not first['source_access_registration']['absence_is_permission']
    assert first['source_access_states']==[]
    repository.connection.access=[{'source_id':'L05','state':'source_STOP','reason':'Synthetic stop'}]
    out=repository.search('Synthetic')
    assert out['source_access_states'][0]['state']=='source_STOP'
    assert all(purpose['state']=='held' for purpose in out['authority'].values())
    with pytest.raises(ResearchServingError,match='STALE_RESEARCH_SNAPSHOT'):
        repository.search('Synthetic',after_ordinal=1,expected_snapshot_id=first['binding']['snapshot_id'])


@pytest.mark.parametrize('control',['rows','missing_name','missing_strength','missing_form','pack_rows','min_year','offering_rows'])
def test_population_missing_detail_or_grain_drift_does_not_change_selected_dictionary(control):
    repository=FixtureRepository();repository.connection.controls[control]+=1
    with pytest.raises(ResearchServingError,match='DRUG_CANDIDATE_POPULATION_MISMATCH'):
        repository.search('Synthetic')
    assert not any(q==SEARCH for q,p in repository.connection.calls)


def test_existing_immutable_candidate_verifier_rejects_source_or_projection_drift():
    for change in ('raw_hash','projected_strength','entity_id'):
        bad=item()
        if change=='raw_hash':bad['raw_sha256']='bad'
        elif change=='projected_strength':bad['fields']['ingredient_strength_description']='invented'
        else:bad['entity_id']='bad'
        with pytest.raises(ResearchServingError,match='DRUG_IDENTITY_LINEAGE_MISMATCH'):
            FixtureRepository([bad]).search('Synthetic')


@pytest.mark.parametrize('change',['over_limit','name_flag','strength_flag','ordinal','duplicate_ordinal'])
def test_unbounded_or_malformed_query_rows_are_not_discovery_candidates(change):
    repository=FixtureRepository()
    row=item();row.update(name_literal_observed=True,strength_literal_observed=True,form_literal_observed=True)
    if change=='over_limit':repository.connection.override=[row]*22;code='LOOKUP_LIMIT'
    elif change=='duplicate_ordinal':repository.connection.override=[row,row];code='QUERY_MISMATCH'
    else:
        if change=='name_flag':row['name_literal_observed']=False
        elif change=='strength_flag':row['strength_literal_observed']=False
        else:row['source_row_ordinal']=0
        repository.connection.override=[row];code='QUERY_MISMATCH'
    with pytest.raises(ResearchServingError,match='DRUG_CANDIDATE_'+code):
        repository.search('Synthetic',strength_text='5 MG')


def test_response_limit_is_explicit_not_silent_evidence_trimming(monkeypatch):
    import daylight_data.serving.drug_candidates as module
    monkeypatch.setattr(module,'MAX_RESPONSE_BYTES',100)
    with pytest.raises(ResearchServingError,match='DRUG_CANDIDATE_RESPONSE_LIMIT'):
        FixtureRepository().search('Synthetic')


def test_source_rows_are_not_mutated_and_results_repeat_with_identical_inputs():
    repository=FixtureRepository();before=copy.deepcopy(repository.connection.rows)
    first=repository.search('Synthetic');second=repository.search('Synthetic')
    assert first==second and before==repository.connection.rows
    assert all(q.lstrip().startswith(('SELECT','WITH matched AS MATERIALIZED')) for q,p in repository.connection.calls)


def test_wrong_selection_is_rejected_before_read_and_factory_reuses_existing_guards(monkeypatch):
    repository=FixtureRepository();repository.binding.selections['drug_identity']['layer_id']='L08'
    with pytest.raises(ResearchServingError,match='DRUG_IDENTITY_SELECTION_REQUIRED'):
        repository.search('Synthetic')
    assert repository.reads==0
    import daylight_data.serving.drug_candidates as module
    seen={};connection=lambda:None
    class Base:_connection_factory=staticmethod(connection)
    def base(**kw):seen['base']=kw;return Base()
    def load(root,**kw):seen['selection']=kw;return binding()
    monkeypatch.setattr(module,'repository_from_env',base);monkeypatch.setattr(module,'load_local_binding',load)
    repo=candidate_repository_from_env(repository_root='fixture:root',dsn='fixture:dsn')
    assert isinstance(repo,DrugCandidateRepository) and repo._connection_factory is connection
    assert seen['base']=={'repository_root':'fixture:root','dsn':'fixture:dsn','timeout_ms':5000}
    assert seen['selection']=={'selection':SELECTION}
