#!/usr/bin/env python3
"""Read-only, exact-identifier L05 research reference; no personal conclusions."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from contextlib import closing

ROOT=Path(__file__).resolve().parents[2]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(4*1024*1024):h.update(b)
    return h.hexdigest()


def verify(package):
    manifest=json.loads((package/'manifest.json').read_text())
    for group,base in [('files',package),('inputs',ROOT),('code',ROOT)]:
        for name,value in manifest[group].items():
            if not (base/name).is_file() or sha(base/name)!=value:raise ValueError('Changed bound '+group+': '+name)
    audit=package.parent/(package.name+'-validation.json')
    if not audit.exists():raise ValueError('Independent source audit is missing')
    result=json.loads(audit.read_text())
    if result.get('manifest_sha256')!=sha(package/'manifest.json') or not result.get('passed'):
        raise ValueError('Independent source audit does not pass for this manifest')
    return manifest


def project(package,request):
    allowed={'year','offering_id','rxcui','ndc','limit','offset'}
    if set(request)-allowed:raise ValueError('Unsupported request fields; personal/commercial inputs are not accepted')
    if request.get('year')!=2026:raise ValueError('This reference supports the pinned 2026 scope only')
    ident=request.get('offering_id')
    limit=request.get('limit',50);offset=request.get('offset',0)
    if type(limit)!=int or not 1<=limit<=100 or type(offset)!=int or offset<0:raise ValueError('Invalid pagination')
    for key,width in [('rxcui',None),('ndc',11)]:
        if key in request and (not isinstance(request[key],str) or not re.fullmatch(r'\d+' if width is None else r'\d{11}',request[key])):
            raise ValueError('Use an exact numeric string '+key)
    if not request.get('rxcui') and not request.get('ndc'):raise ValueError('An exact RxCUI or proxy NDC is required')
    with closing(sqlite3.connect('file:'+str(package/'inventory.sqlite3')+'?mode=ro',uri=True)) as db:
        row=db.execute('SELECT payload FROM plans WHERE offering_id=?',(ident,)).fetchone()
        if row is None:raise ValueError('Offering is outside the 71-plan Part D reference')
        plan=json.loads(row[0]);contract,number=ident.split(':')[1:3]
        clause='((table_name="basic" AND formulary_id=?) OR (table_name IN ("excluded","indication") AND contract_id=? AND plan_id=?))'
        params=[plan['formulary_id'],contract,number]
        if 'rxcui' in request:clause+=' AND rxcui=?';params.append(request['rxcui'])
        if 'ndc' in request:clause+=' AND (ndc=? OR (table_name!="basic" AND ? IS NOT NULL))';params.extend([request['ndc'],request.get('rxcui')])
        total=db.execute('SELECT count(*) FROM drug_rows WHERE '+clause,params).fetchone()[0]
        found=db.execute('SELECT table_name,ordinal,rxcui,modeled_json FROM drug_rows WHERE '+clause+' ORDER BY table_name,ordinal LIMIT ? OFFSET ?',params+[limit,offset]).fetchall()
        records=[]
        for table,ordinal,code,fields in found:
            identity=db.execute('SELECT payload FROM drug_identities WHERE rxcui=?',(code,)).fetchone()
            gaps=[{'missing_fact':r[0],'source_needed':r[1]} for r in db.execute('SELECT missing_fact,source_needed FROM condition_gaps WHERE table_name=? AND ordinal=? ORDER BY missing_fact',(table,ordinal))]
            records.append({'table':table,'source_row':ordinal,'fields':json.loads(fields),'drug_identity':json.loads(identity[0]) if identity else None,
                            'condition_details_not_in_CMS_payload':gaps,'source_grain':'formulary/version/proxy-NDC' if table=='basic' else 'contract/plan/RxCUI; no segment asserted'})
        return {'status':'research_published_reference','year':2026,'source_period':'2026-09','evidence_cutoff':'2026-10-25','plan':plan,
                'matches':records,'total_matching_source_rows':total,'offset':offset,'limit':limit,'next_offset':offset+len(records) if offset+len(records)<total else None,
                'list_state':'listed_in_published_snapshot' if total else 'not_listed_in_published_snapshot',
                'supplemental_ndc_check':'not_possible_without_RxCUI' if 'ndc' in request and 'rxcui' not in request else 'source_grain_preserved',
                'condition_detail_basis':'CMS payload limitations; captured carrier documents and their date/applicability states are assessed separately. No physical quantity unit is inferred.',
                'personal_clinical_approval':'not_assessed','personal_price_available':False,'recommendations_available':False,'consumer_reference_accepted':False}


def lookup(package,request):
    verify(package)
    return project(package,request)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--offering-id',required=True)
    parser.add_argument('--rxcui');parser.add_argument('--ndc');parser.add_argument('--limit',type=int,default=20);parser.add_argument('--offset',type=int,default=0)
    args=parser.parse_args();request={'year':2026,'offering_id':args.offering_id,'limit':args.limit,'offset':args.offset}
    if args.rxcui:request['rxcui']=args.rxcui
    if args.ndc:request['ndc']=args.ndc
    print(json.dumps(lookup(args.package.resolve(),request),indent=2))
