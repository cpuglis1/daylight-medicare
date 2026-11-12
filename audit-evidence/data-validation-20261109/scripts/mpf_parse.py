import openpyxl,json,time,collections
t=time.time()
L=json.load(open('land_collier.json'))['collier']
keys={(r['Contract ID'],r['Plan ID'].zfill(3),r['Segment ID'].zfill(3)) for r in L}
wb=openpyxl.load_workbook('mpf/MPF_BenefitSummary_CY2026_12232025.xlsx',read_only=True)
ws=wb.worksheets[0]; it=ws.iter_rows(values_only=True); hdr=next(it); out=[]
for i,row in enumerate(it,start=2):
    rec=dict(zip(hdr,row))
    try: key=(str(rec['Contract_ID']).strip(),str(int(rec['Plan_ID'])).zfill(3),str(int(rec['Segment_ID'])).zfill(3))
    except Exception: continue
    if key in keys:
        rec['_key']='-'.join(key); rec['_row']=i; out.append(rec)
print('matched',len(out),'plans',len({r['_key'] for r in out}),'secs',round(time.time()-t,1))
json.dump(out,open('mpf_collier.json','w'),default=str)
c=collections.Counter((r['Category Name'],r['Service_Desc']) for r in out)
for k,v in sorted(c.items()): print(v,'|',k[0],'|',k[1])
