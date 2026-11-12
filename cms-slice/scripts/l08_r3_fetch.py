"""Download links actually advertised by public L08 directory pages."""
import argparse,json
from concurrent.futures import ThreadPoolExecutor
from l08_r3_common import BASE,acquire,assert_open,write

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--humana',action='store_true');p.add_argument('--jobs')
    a=p.parse_args();assert_open()
    if a.humana:
        links=json.loads((BASE/'ui/humana-2026-directory-links.json').read_text())
        jobs=[{'url':x['href'],'label':x['text'].strip()} for x in links
              if ('Gulf Coast' in x['text'] and 'Employer' not in x['text'])
              or 'CareComplete Platinum' in x['text']]
        write(BASE/'humana-advertised-download-jobs.json',jobs)
    else:jobs=json.loads(open(a.jobs).read())
    with ThreadPoolExecutor(max_workers=2) as pool:
        for r in pool.map(lambda j:acquire(j['url'],j.get('label')),jobs):
            print(json.dumps(r),flush=True)
