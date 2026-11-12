import json,zlib,struct,gzip,os,sys,time
t=time.time()
B=os.environ['HOME']+'/mnt/daylight/'
m=json.load(open(B+'docs/data/l07-pharmacy-networks-2026-10-27/acquisition-r1/source-manifest.json'))
part=int(sys.argv[1]); mem=m['members'][part-1]
rngs=sorted(mem['compressed_ranges'],key=lambda r:r['start'])
L=json.load(open('f_scope.json'))['pi']
pref={('|'.join(k.split('-'))+'|').encode() for k in L}
outer=zlib.decompressobj(-15) if mem['compression']==8 else None
inner=None; ibuf=b''; rest=b''; hdr=None; n=0; src={}
def feed_inner(data):
    global inner, ibuf, rest, hdr, n
    if inner is None:
        ibuf+=data
        if len(ibuf)<64: return
        assert ibuf[:4]==b'PK\x03\x04'
        n2,e2=struct.unpack('<HH',ibuf[26:30]); data=ibuf[30+n2+e2:]; inner=zlib.decompressobj(-15)
    out=rest+inner.decompress(data)
    lines=out.split(b'\n'); rest=lines.pop()
    if hdr is None:
        hdr=lines.pop(0).decode().strip().split('|')
    n+=len(lines)
    for l in lines:
        if l[:14] in pref:
            f=l.decode('latin-1').rstrip('\r').split('|'); src[(f[0],f[1],f[2],f[3])]=f
for r in rngs:
    chunk=open(B+r['path'],'rb').read()
    if outer is not None: chunk=outer.decompress(chunk)
    feed_inner(chunk)
if rest.strip():
    n+=1; l=rest
    if l[:14] in pref:
        f=l.decode('latin-1').rstrip('\r').split('|'); src[(f[0],f[1],f[2],f[3])]=f
t1=time.time()-t
dl={}
with gzip.open(B+f'docs/data/l07-pharmacy-networks-2026-10-27/build-r1/network-part-{part}.psv.gz','rt') as fh:
    h=fh.readline().rstrip('\n').split('|')
    for line in fh:
        f=line.rstrip('\n').split('|'); r=dict(zip(h,f))
        dl[(r['CONTRACT_ID'],r['PLAN_ID'],r['SEGMENT_ID'],r['PHARMACY_NUMBER'])]=r
diff=0; ex=[]
for k,f in src.items():
    r=dl.get(k)
    if r is None: diff+=1; ex.append(('missing in DL',k)); continue
    for i,c in enumerate(hdr):
        if c in r and r[c]!=f[i]: diff+=1; ex.append((k,c,f[i],r[c])); break
print(json.dumps({'part':part,'hdr0':hdr[:4],'source_rows':n,'in_scope_source':len(src),'daylight_rows':len(dl),'field_or_row_diffs':diff,'only_in_daylight':len(set(dl)-set(src)),'examples':ex[:5],'parse_secs':round(t1,1),'secs':round(time.time()-t,1)}))
