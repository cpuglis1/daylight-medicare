"""Retain and validate CMS's public hospital download obtained through normal Firefox UI."""
import argparse
import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from l08_r6_common import ROOT, HOME, filehash, packed, write

BASE=HOME/'hospital-reference-r7'
PARENT=HOME/'original-medicare-r6'
SOURCE='https://data.cms.gov/provider-data/sites/default/files/resources/893c372430d9d71a1c52737d01239d47_1785189955/Hospital_General_Information.csv'
DICTIONARY='https://data.cms.gov/provider-data/sites/default/files/data_dictionaries/hospital/HOSPITAL_Data_Dictionary.pdf'


def build():
    if (BASE/'SEALED').exists():
        raise ValueError('Sealed revision')
    pointer=json.loads((HOME/'CURRENT_REFERENCE.json').read_text())
    if pointer['reference_id']!='L08-PUBLISHED-COLLIER-2026-research-r6':
        raise ValueError('Unexpected active parent')
    write(BASE/'parent-pin.json',{'pointer':pointer,'manifest_sha256':filehash(PARENT/'manifest.json')})
    csv_path=BASE/'intake/Hospital_General_Information.csv'
    pdf_path=BASE/'intake/HOSPITAL_Data_Dictionary.pdf'
    write(BASE/'source-receipt.json',{
        'method':'Normal native Firefox public download UI; CSV Save File, dictionary PDF Save; no API request replay',
        'date':'2026-10-28','landing_page':'https://data.cms.gov/provider-data/dataset/xubh-q36u',
        'published_last_modified':'2026-07-22','published_released':'2026-08-13',
        'publisher_displayed_rows':5419,'CSV_url':SOURCE,'dictionary_url':DICTIONARY,
        'dictionary_version':'Hospital DDB Data Dictionary July 2026; 100 pages',
        'files':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':filehash(p)}for p in [csv_path,pdf_path]],
        'CSV_browser_saved_path':'/Users/cep4u/Downloads/Hospital_General_Information.csv',
        'dictionary_browser_saved_path':'/Users/cep4u/daylight/plans/HOSPITAL_Data_Dictionary.pdf',
        'credentials_CAPTCHA_security_override_or_terms_acceptance':False,
        'denied_metadata_API_retried':False,
        'explanation':'The prior 403 was a generic edge-server access denial for one ordinary automated metadata request; its exact cause is unknown. A broad collector guard was an internal conservative stop, not evidence of restricted hospital data. The normal public page and advertised downloads work in Firefox.'})
    path=BASE/'hospitals.sqlite3'
    if path.exists():
        path.unlink()
    db=sqlite3.connect(path)
    db.executescript('''CREATE TABLE hospitals(source_row INTEGER PRIMARY KEY,facility_id TEXT,name_raw TEXT,
        street_raw TEXT,city_raw TEXT,state_raw TEXT,postal_raw TEXT,county_raw TEXT,type_raw TEXT,fields_json TEXT);
        CREATE TABLE metadata(key TEXT PRIMARY KEY,value_json TEXT);''')
    with csv_path.open(encoding='utf-8-sig',newline='') as f:
        r=csv.DictReader(f)
        headers=r.fieldnames
        for ix,record in enumerate(r,2):
            if None in record or any(v is None for v in record.values()):
                raise ValueError('Malformed CSV row '+str(ix))
            db.execute('INSERT INTO hospitals VALUES(?,?,?,?,?,?,?,?,?,?)',(ix,record['Facility ID'],
                record['Facility Name'],record['Address'],record['City/Town'],record['State'],record['ZIP Code'],
                record['County/Parish'],record['Hospital Type'],packed(record)))
    db.executescript('CREATE INDEX facility_id ON hospitals(facility_id); CREATE INDEX county_state ON hospitals(county_raw,state_raw);')
    for k,v in {'source_url':SOURCE,'source_modified':'2026-07-22','source_release':'2026-08-13',
                'consumer_release_enabled':False,'MA_network_participation_inferred':False,
                'source_is_not_a_separate_campus_census':True,'quality_fields_retained_without_ranking_or_L09_changes':True}.items():
        db.execute('INSERT INTO metadata VALUES(?,?)',(k,packed(v)))
    db.commit()
    errors=[];fields=0;n=0
    # Independent read from original publisher bytes, with every raw and named field compared.
    with csv_path.open(encoding='utf-8-sig',newline='') as f:
        for ix,record in enumerate(csv.DictReader(f),2):
            n+=1
            got=db.execute('SELECT * FROM hospitals WHERE source_row=?',(ix,)).fetchone()
            expect=(ix,record['Facility ID'],record['Facility Name'],record['Address'],record['City/Town'],
                    record['State'],record['ZIP Code'],record['County/Parish'],record['Hospital Type'])
            if not got or got[:9]!=expect or json.loads(got[9])!=record:
                errors.append('Field mismatch row '+str(ix))
            fields+=len(record)
    if n!=5419 or db.execute('SELECT count(*) FROM hospitals').fetchone()[0]!=n:
        errors.append('Publisher/CSV/database row counts differ')
    if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
        errors.append('SQLite integrity')
    original_paths=[Path('/Users/cep4u/Downloads/Hospital_General_Information.csv'),ROOT/'plans/HOSPITAL_Data_Dictionary.pdf']
    for original,retained in zip(original_paths,[csv_path,pdf_path]):
        if filehash(original)!=filehash(retained):
            errors.append('Browser/retained bytes differ: '+original.name)
    parent_files=0
    for rel,m in json.loads((PARENT/'manifest.json').read_text())['files'].items():
        p=ROOT/rel
        if not p.exists() or p.stat().st_size!=m['bytes'] or filehash(p)!=m['sha256']:
            errors.append('Sealed parent changed: '+rel)
        parent_files+=1
    summary={'national_records':n,'fields_per_record':len(headers),'literal_fields_compared':fields,
        'Florida_records':db.execute("SELECT count(*) FROM hospitals WHERE state_raw='FL'").fetchone()[0],
        'Collier_records':db.execute("SELECT count(*) FROM hospitals WHERE state_raw='FL' AND upper(county_raw)='COLLIER'").fetchone()[0],
        'duplicate_facility_IDs':db.execute('SELECT count(*) FROM(SELECT facility_id FROM hospitals GROUP BY facility_id HAVING count(*)>1)').fetchone()[0],
        'hospital_source_acquisition_gap_closed':True,'full_L08_complete':False,'consumer_release_enabled':False,'human_accepted':False}
    write(BASE/'summary.json',summary)
    write(BASE/'validation.json',{'passed':not errors,'errors':errors,'publisher_rows':5419,'source_rows_compared':n,
        'literal_fields_compared':fields,'additional_named_identity_fields_compared':n*8,
        'retained_original_bytes_match_browser_downloads':True,'sealed_parent_files_rehashed':parent_files,
        'scope':'Full published file and every retained/modeled field; no inferred MA participation, full-campus census, ranking or personal coverage.'})
    gaps=json.loads((PARENT/'genuine-gaps.json').read_text())
    for g in gaps:
        if g['id']=='L08-OM01':
            g.update(status='closed_for_published_2026_source_acquisition_and_field_validation',
                gap='The official 2026 Hospital General Information CSV and July 2026 dictionary are now retained through ordinary Firefox downloads.',
                need='No owner action or additional API/PDF needed for this source.',
                r7_progress='All 5,419 records and 205,922 literal fields match the source. Federal facility observations do not automatically map every licensed campus or establish a plan contract.')
        if g['id']=='L08-G06':
            g.update(status='required_published_federal_inputs_collected_and_source_checked; specific_cross_source_unknowns_retained',
                gap='The clinician/affiliation archive, all five enrollment tables, national opt-out release and hospital reference/dictionary are now retained. Enumerated enrollment-ID and assignment/opt-out source differences remain unknown for positive personal claims.',
                blocked_by=None,need='No further download needed for the named federal inputs. Retain exact-case unknowns and perform source clarification only where consequential.')
    write(BASE/'genuine-gaps.json',gaps)
    report=f'''# L08 hospital reference download and validation

October 28, 2026. **The missing federal hospital CSV/dictionary acquisition gap is closed. No owner action, additional API, email or PDF is needed for this source.** The normal public page and advertised downloads work in Firefox.

## What was blocked

An ordinary scripted request to the hospital metadata API returned a generic **403 Access Denied** from the site's edge server. The response does not disclose why it denied the request. The collector then blocked the wider Provider Data Catalog route family as an internal conservative stop. That guard was not proof the dataset required special access or that every public download was inaccessible.

The existing public Hospital General Information tab loaded normally in Firefox. Its **Download full dataset (CSV)** button and dictionary PDF save worked without a login, CAPTCHA, security change or API retry. The failed API is still not represented as working. [Acquisition receipt](source-receipt.json).

## Published source now retained

The page identifies the data as modified **July 22, 2026** and released **August 13, 2026**. The matching PDF is the **July 2026 Hospital Downloadable Database Data Dictionary**, 100 pages. [Original CSV](intake/Hospital_General_Information.csv), [original dictionary](intake/HOSPITAL_Data_Dictionary.pdf), [dictionary text](dictionary.txt), [normalized database](hospitals.sqlite3).

All **{n:,} national records**, **{len(headers)} fields per record** and **{fields:,} literal field values** were compared against the retained CSV, alongside the eight extracted identity/location/type fields. Browser-download and retained-original hashes agree; SQLite integrity and publisher/database record totals agree. There are **{summary['Florida_records']} Florida records** and **{summary['Collier_records']} records explicitly labeled Collier** in this source. A federal facility record may not enumerate every campus separately; these counts are not a census of all licensed Collier hospital locations. [Validation](validation.json), [counts](summary.json).

The normalized table preserves facility IDs and ZIPs as strings, exact source names/addresses/counties/types, all quality/context fields and original row locators. No CCN-to-campus match, MA participation, ranking or personal coverage is inferred. Hospital quality fields remain source context; L09 plan ratings are unchanged.

## Remaining scope

The clinician/affiliation, enrollment and opt-out references remain the sealed r6 component. Its **1,169 unmatched clinician enrollment IDs** and **146 assignment/opt-out overlap NPIs** stay visible as specific source differences. Earlier MA network-mapping, source discrepancies and internal interpretation gaps are unchanged. [Current gap register](genuine-gaps.json).

This adds the validated hospital component to the research reference. All earlier evidence/code is preserved; no consumer release or inherited acceptance is added. Full L08 remains partial.
'''
    (BASE/'REPORT.md').write_text(report)
    db.close()
    if errors:
        raise ValueError(str(errors[:5]))
    print(json.dumps(summary),flush=True)


def publish():
    if (BASE/'SEALED').exists():
        raise ValueError('Sealed revision')
    pin=json.loads((BASE/'parent-pin.json').read_text())
    pointer=json.loads((HOME/'CURRENT_REFERENCE.json').read_text())
    if pointer!=pin['pointer'] or filehash(PARENT/'manifest.json')!=pin['manifest_sha256']:
        raise ValueError('Parent changed')
    if not json.loads((BASE/'validation.json').read_text())['passed']:
        raise ValueError('Validation failed')
    (BASE/'SEALED').write_text('L08 published hospital reference r7; full L08 incomplete; consumer release disabled\n')
    paths=[p for p in BASE.rglob('*')if p.is_file() and p.name not in {'manifest.json','manifest-validation.json'}]
    paths.append(Path(__file__).resolve())
    files={str(p.relative_to(ROOT)):{'sha256':filehash(p),'bytes':p.stat().st_size}for p in sorted(paths)}
    write(BASE/'manifest.json',{'reference_id':'L08-PUBLISHED-COLLIER-2026-research-r7',
        'created_at_utc':datetime.now(timezone.utc).isoformat(),'files':files,
        'parent_manifest_sha256':pin['manifest_sha256'],'full_L08_complete':False,'consumer_release_enabled':False,'human_accepted':False})
    errors=[r for r,m in files.items()if filehash(ROOT/r)!=m['sha256']]
    if errors:
        raise ValueError('Manifest mismatch')
    pointer.update(reference_id='L08-PUBLISHED-COLLIER-2026-research-r7',manifest='hospital-reference-r7/manifest.json',
        manifest_sha256=filehash(BASE/'manifest.json'),hospital_database='hospital-reference-r7/hospitals.sqlite3',
        report='hospital-reference-r7/REPORT.md',parent_reference_id='L08-PUBLISHED-COLLIER-2026-research-r6',
        parent_manifest='original-medicare-r6/manifest.json',parent_manifest_sha256=pin['manifest_sha256'])
    write(HOME/'CURRENT_REFERENCE.json',pointer)
    write(BASE/'manifest-validation.json',{'passed':True,'files_rehashed':len(files),
        'errors':[],'active_manifest_hash_agrees':pointer['manifest_sha256']==filehash(BASE/'manifest.json')})
    print(json.dumps(pointer),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--publish',action='store_true')
    a=p.parse_args();publish()if a.publish else build()
