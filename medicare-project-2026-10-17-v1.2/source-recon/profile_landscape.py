from pathlib import Path
import csv, io, zipfile, json, collections, hashlib
root=Path(__file__).parent
with zipfile.ZipFile(root/'landscape.zip') as z:
    name=next(n for n in z.namelist() if n.endswith('.csv'))
    counts=collections.Counter(); states=set(); plans=set(); contract_plans=set(); offerings=set(); duplicated=0
    empties=collections.Counter(); nas=collections.Counter(); negatives=collections.Counter(); category=collections.Counter(); types=collections.Counter(); per_plan=collections.defaultdict(set); zero_segments=0; samples=[]; full_repeat=0; last_rows=set()
    with z.open(name) as raw:
        reader=csv.DictReader(io.TextIOWrapper(raw,encoding='utf-8-sig',newline=''))
        fields=reader.fieldnames
        for row in reader:
            counts['rows']+=1
            key=tuple(row.get(k,'') for k in ['Contract Year','Contract ID','Plan ID','Segment ID'])
            cp=key[:3]; plans.add(key); contract_plans.add(cp)
            offer=key+tuple(row.get(k,'') for k in ['State Territory Abbreviation','County Name'])
            if offer in offerings: duplicated+=1
            offerings.add(offer)
            states.add(row['State Territory Abbreviation']); category[row['Contract Category Type']]+=1; types[row['Plan Type']]+=1
            if row['Segment ID']=='0': zero_segments+=1
            counts['all_counties_rows']+=row['County Name']=='All Counties'
            for k,v in row.items():
                if not v or not v.strip(): empties[k]+=1
                if v and v.strip()=='Not Applicable': nas[k]+=1
                if v and v.strip().startswith('(') and '$' in v: negatives[k]+=1
            per_plan[key].add(tuple(row[k] for k in ['Part C Premium','Part D Total Premium','Monthly Consolidated Premium (Part C + D)']))
            if len(samples)<3: samples.append({k:row[k] for k in ['Contract Year','Contract Category Type','State Territory Abbreviation','County Name','Contract ID','Plan ID','Segment ID','Part D Basic Premium','Part D Supplemental Premium','Part D Total Premium','Monthly Consolidated Premium (Part C + D)']})
profile={'source':'https://www.cms.gov/files/zip/cy2027-landscape-202609-1.zip','zip_sha256':hashlib.sha256((root/'landscape.zip').read_bytes()).hexdigest(),'member':name,'columns':fields,'column_count':len(fields),'row_count':counts['rows'],'distinct_year_contract_plan_segment':len(plans),'distinct_year_contract_plan':len(contract_plans),'distinct_candidate_offering_keys':len(offerings),'duplicate_candidate_offering_keys':duplicated,'jurisdiction_codes':sorted(states),'category_row_counts':dict(category),'plan_type_row_counts':dict(types),'all_counties_rows':counts['all_counties_rows'],'segment_literal_zero_rows':zero_segments,'empty_counts':dict(empties),'not_applicable_counts':dict(nas),'parenthesized_currency_counts':dict(negatives),'plan_segment_keys_with_multiple_premium_tuples':sum(len(v)>1 for v in per_plan.values()),'sample_rows':samples,'limitations':['A descriptive profile of one artifact, not a validated canonical key or completeness audit.','No inferred provider networks, actual drug prices, Medigap products or transaction availability.']}
(root/'landscape-profile.json').write_text(json.dumps(profile,indent=2))
print(json.dumps({k:v for k,v in profile.items() if k not in ['columns','empty_counts','not_applicable_counts','sample_rows']},indent=2))
