#!/usr/bin/env python3
"""Submit only AHCA's anonymous read-only hospital search, retaining the result."""
from datetime import datetime, timezone
from http.cookiejar import CookieJar
import json
import re
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPCookieProcessor, Request
from l08_acquire import OUT, digest, write


def main():
    # This is the published search form, not an account or contact submission.
    base='https://quality.healthfinder.fl.gov/Facility-Search/FacilityLocateSearch'
    opener=build_opener(HTTPCookieProcessor(CookieJar()))
    headers={'User-Agent':'Daylight public hospital directory reference research'}
    with opener.open(Request(base+'?type=Hospital',headers=headers),timeout=45)as r:
        text=r.read().decode()
    token=re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"',text).group(1)
    fields=[('FacilityTypeSelection','Hospital'),('FacilityProviderType','Hospital'),
            ('SearchType','1'),('OpenClosed_LicenseStatus',''),
            ('countySelection','11'),('countySelection','26'),('countySelection','36'),
            ('__RequestVerificationToken',token)]
    url=base+'?handler=AdvancedSearch'
    with opener.open(Request(url,data=urlencode(fields).encode(),headers=headers),timeout=60)as r:
        result=r.read();final=r.url;status=r.status
    raw=OUT/'raw'/digest(result);raw.write_bytes(result)
    record={'id':'ahca-anonymous-hospital-search-active','requested_url':url,'final_url':final,'http_status':status,
            'method':'POST anonymous read-only search','retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
            'search_fields':dict((k,v)for k,v in fields if k not in ['__RequestVerificationToken','countySelection']),
            'counties':['Collier','Hendry','Lee'],'sha256':digest(result),'bytes':len(result),
            'path':str(raw.relative_to(OUT.parents[3]))}
    # ROOT is clearer than assuming a number of ancestor levels for provenance.
    from l08_acquire import ROOT
    record['path']=str(raw.relative_to(ROOT))
    write(OUT/'receipts/ahca-anonymous-hospital-search-active.json',record)
    print(json.dumps(record))


if __name__=='__main__':main()
