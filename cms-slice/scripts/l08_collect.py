#!/usr/bin/env python3
"""Follow actual public FHIR pagination and retain explicit incomplete states."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from urllib.parse import urlparse
from l08_acquire import acquire, body, write, digest, BASE


def crawl(job):
    path = BASE / 'acquisition-r1/crawls' / (job['id'] + '.json')
    result = {'id': job['id'], 'query': job, 'pages': [], 'complete': False,
              'match_records': 0, 'included_records': 0, 'unique_matches': 0}
    seen_urls, seen_ids = set(), set()
    url = job['url']
    try:
        while url:
            if url in seen_urls: raise ValueError('Repeated next link')
            if urlparse(url).hostname != urlparse(job['url']).hostname:
                raise ValueError('Cross-host next link requires explicit review')
            seen_urls.add(url)
            r=acquire(url, 'crawl '+job['id'])
            j=json.loads(body(r))
            if j.get('resourceType') != 'Bundle':
                raise ValueError('Expected Bundle, got '+str(j.get('resourceType')))
            errors=[e['resource'] for e in j.get('entry',[]) if e['resource'].get('resourceType')=='OperationOutcome'
                    and any(i.get('severity') in ('error','fatal') for i in e['resource'].get('issue',[]))]
            if errors: raise ValueError('Bundle contains error OperationOutcome: '+str(errors)[:1200])
            matches=[e['resource'] for e in j.get('entry',[])
                     if e.get('search',{}).get('mode','match')=='match'
                     and e['resource']['resourceType']==job['type']]
            for x in matches:seen_ids.add((x['resourceType'],x['id']))
            result['pages'].append({'receipt':r['id'],'sha256':r['sha256'],'matches':len(matches),
                                    'entries':len(j.get('entry',[])), 'advertised_total':j.get('total')})
            result['match_records']+=len(matches)
            result['included_records']+=len(j.get('entry',[]))-len(matches)
            result['unique_matches']=len(seen_ids)
            links=[x['url'] for x in j.get('link',[])if x.get('relation')=='next']
            if len(links)>1:raise ValueError('Multiple next links')
            url=links[0] if links else None
            write(path,result)
            if len(seen_urls)>5000:raise ValueError('More than 5000 pages needs scope review')
        result['complete']=True
        totals={p['advertised_total'] for p in result['pages']if p['advertised_total'] is not None}
        result['advertised_totals']=sorted(totals)
        result['exact_total_agrees']=len(totals)==1 and next(iter(totals))==len(seen_ids)
        result['duplicate_match_occurrences']=result['match_records']-len(seen_ids)
    except Exception as e:
        result['error']=str(e)
    write(path,result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['pages','query']}),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--jobs',type=Path,required=True)
    a=p.parse_args();jobs=json.loads(a.jobs.read_text())
    with ThreadPoolExecutor(max_workers=4)as pool:list(pool.map(crawl,jobs))
