import json,zlib,struct,gzip,os,sys,time
t=time.time()
B=os.environ['HOME']+'/mnt/daylight/'
m=json.load(open(B+'docs/data/l07-pharmacy-networks-2026-10-27/acquisition-r1/source-manifest.json'))
part=int(sys.argv[1]); nchunks=int(sys.argv[2])
mem=m['members'][part-1]
rngs=sorted(mem['compressed_ranges'],key=lambda r:r['start'])
buf=b''.join(open(B+r['path'],'rb').read() for r in rngs[:nchunks])
inner=buf.find(b'PK\x03\x04',0)
print('first PK at',inner)
meth=struct.unpack('<H',buf[inner+8:inner+10])[0]; n2,e2=struct.unpack('<HH',buf[inner+26:inner+30])
name=buf[inner+30:inner+30+n2].decode(); data=inner+30+n2+e2
d=zlib.decompressobj(-15); txt=d.decompress(buf[data:])
lines=txt.split(b'\n'); lines=lines[:-1]  # drop partial last line
hdr=lines[0].decode().strip().split('|'); rows=lines[1:]
L=json.load(open('f_scope.json'))['pi']; keys={tuple(k.split('-')) for k in L}
ci,pi,si=hdr.index('CONTRACT_ID'),hdr.index('PLAN_ID'),hdr.index('SEGMENT_ID')
src={}
for i,l in enumerate(rows,start=1):
    f=l.decode('latin-1').rstrip('\r').split('|')
    k=(f[ci],f[pi].zfill(3),f[si].zfill(3))
    if k in keys: src[(i,)+k+(f[hdr.index('PHARMACY_NUMBER')],)]=f
print('part',part,'inner',name,'method',meth,'source rows sampled',len(rows),'in scope',len(src),'secs',round(time.time()-t,1))
json.dump({'hdr':hdr,'n':len(rows),'rows':[[list(k),v] for k,v in src.items()]},open(f'pn_src_{part}.json','w'))
