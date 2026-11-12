import json,zlib,struct,gzip,os,sys,time,hashlib
t=time.time()
B=os.environ['HOME']+'/mnt/daylight/'
m=json.load(open(B+'docs/data/l07-pharmacy-networks-2026-10-27/acquisition-r1/source-manifest.json'))
part=int(sys.argv[1]); mem=m['members'][part-1]
rngs=sorted(mem['compressed_ranges'],key=lambda r:r['start'])
L=json.load(open('f_scope.json'))['pi']
pref={('|'.join(k.split('-'))+'|').encode() for k in L}
outer=zlib.decompressobj(-15) if mem['compression']==8 else None
inner=None; ibuf=b''; rest=b''; hdr=None; n=0; src=set(); nin=0
H=lambda b: hashlib.blake2b(b,digest_size=8).digest()
for r in rngs:
    chunk=open(B+r['path'],'rb').read()
    if outer is not None: chunk=outer.decompress(chunk)
    if inner is None:
        ibuf+=chunk; n2,e2=struct.unpack('<HH',ibuf[26:30]); chunk=ibuf[30+n2+e2:]; inner=zlib.decompressobj(-15)
    out=rest+inner.decompress(chunk); lines=out.split(b'\n'); rest=lines.pop()
    if hdr is None: hdr=lines.pop(0)
    n+=len(lines)
    for l in lines:
        if l[:14] in pref: src.add(H(l.rstrip(b'\r'))); nin+=1
    del out,lines
if rest.strip():
    n+=1
    if rest[:14] in pref: src.add(H(rest.rstrip(b'\r'))); nin+=1
dl=set(); nd=0
with gzip.open(B+f'docs/data/l07-pharmacy-networks-2026-10-27/build-r1/network-part-{part}.psv.gz','rb') as fh:
    fh.readline()
    for line in fh:
        native=line.rstrip(b'\r\n').split(b'|',2)[2]   # drop SOURCE_PART|SOURCE_ORDINAL
        dl.add(H(native)); nd+=1
print(json.dumps({'part':part,'source_rows':n,'in_scope_source':nin,'daylight_rows':nd,'only_in_source':len(src-dl),'only_in_daylight':len(dl-src),'secs':round(time.time()-t,1)}))
