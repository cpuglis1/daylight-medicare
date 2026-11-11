"""Retain exact PDF image masks: Poppler's RGB output alone loses stencil shapes.

Run with the bundled Python (pypdf/Pillow). A raw black image can have a distinct
hard mask; dimensions/black pixels alone must never supply a clinical flag.
"""
import collections,gzip,json
from pathlib import Path
from pypdf import PdfReader
from PIL import Image,ImageDraw
from l08_r5_common import ROOT,BASE,write,digest,assert_open

def main():
    assert_open();assets=BASE/'image-assets';assets.mkdir(exist_ok=True);out=[];unique={};mismatches=[]
    for inv in json.loads((BASE/'document-inventory.json').read_text()):
        reader=PdfReader(ROOT/inv['path']);by_page=collections.defaultdict(list)
        for x in inv['image_objects']:by_page[x['page']].append(x)
        cache={}
        def info(ref):
            obj=ref.get_object();refkey=(getattr(ref,'idnum',None),getattr(ref,'generation',None))
            if refkey in cache:return cache[refkey]
            w,h=int(obj['/Width']),int(obj['/Height']);data=obj.get_data();mask=obj.get('/Mask');mask=mask.get_object()if hasattr(mask,'get_object')else mask
            md=mask.get_data()if hasattr(mask,'get_data')else b''
            meta={'width':w,'height':h,'colorspace':str(obj.get('/ColorSpace')),'bits':int(obj.get('/BitsPerComponent',1)),
                  'pixels_sha256':digest(data),'mask_sha256':digest(md)if md else None,'mask_decode':str(mask.get('/Decode'))if hasattr(mask,'get')else None,
                  'source_ref':list(refkey)}
            key=digest(json.dumps({k:v for k,v in meta.items()if k!='source_ref'},sort_keys=True).encode());meta['asset_key']=key
            if key not in unique:
                (assets/(key+'.pixels.bin')).write_bytes(data)
                if md:(assets/(key+'.mask.bin')).write_bytes(md)
                if md:
                    # The exact mask is rendered as a black/white QA image.
                    im=Image.frombytes('1',(w,h),md).convert('RGB')
                else:
                    mode={'/DeviceCMYK':'CMYK','/DeviceRGB':'RGB','/DeviceGray':'L'}.get(str(obj.get('/ColorSpace')))
                    im=Image.frombytes(mode,(w,h),data).convert('RGB')if mode and meta['bits']==8 else None
                if im is not None:im.save(assets/(key+'.png'))
                unique[key]={**meta,'example_document_sha256':inv['sha256']}
            cache[refkey]=meta;return meta
        def multiply(a,m):
            A,B,C,D,E,F=a;g,h,i,j,k,l=map(float,m)
            return[A*g+C*h,B*g+D*h,A*i+C*j,B*i+D*j,A*k+C*l+E,B*k+D*l+F]
        def draws(content,resources,height,initial=None):
            result=[];ctm=initial or[1,0,0,1,0,0];stack=[]
            for args,op in content.operations:
                if op==b'q':stack.append(ctm[:]);continue
                if op==b'Q':ctm=stack.pop();continue
                if op==b'cm':ctm=multiply(ctm,args);continue
                if op!=b'Do':continue
                ref=resources['/XObject'].raw_get(args[0]);obj=ref.get_object()
                if obj.get('/Subtype')=='/Image':
                    A,B,C,D,E,F=ctm;xs=[E,E+A,E+C,E+A+C];ys=[F,F+B,F+D,F+B+D]
                    result.append({**info(ref),'PDF_geometry':{'left':min(xs),'top':height-max(ys),'width':max(xs)-min(xs),'height':max(ys)-min(ys)}})
                elif obj.get('/Subtype')=='/Form':
                    from pypdf.generic import ContentStream
                    result+=draws(ContentStream(obj,reader),obj.get('/Resources',resources),height,multiply(ctm,obj.get('/Matrix',[1,0,0,1,0,0])))
            return result
        for pn,xs in sorted(by_page.items()):
            page=reader.pages[pn-1];assert not page.get('/Rotate',0)
            ds=draws(page.get_contents(),page['/Resources'],float(page.mediabox.height))
            if len(ds)!=len(xs):mismatches.append({'document_sha256':inv['sha256'],'page':pn,'PDF_images':len(ds),'XML_images':len(xs)});continue
            for x,d in zip(xs,ds):
                delta=max(abs(float(x['attributes'][k])-d['PDF_geometry'][k])for k in ['left','top','width','height'])
                if delta>1.1:mismatches.append({'document_sha256':inv['sha256'],'page':pn,'XML_node':x['node'],'geometry_delta':delta})
                out.append({'document_sha256':inv['sha256'],'page':pn,'XML_image_node':x['node'],'XML_image_sha256':x['sha256'],
                   'geometry':{k:float(x['attributes'][k])for k in ['left','top','width','height']},'max_rounding_delta':delta,**d})
    with gzip.open(BASE/'image-occurrences.jsonl.gz','wt')as f:
        for r in out:f.write(json.dumps(r)+'\n')
    write(BASE/'image-asset-inventory.json',list(unique.values()))
    write(BASE/'image-extraction-validation.json',{'passed':not mismatches,'occurrences':len(out),'unique_assets':len(unique),'mismatches':mismatches,
        'hard_masks_preserved':True,'source_color_and_mask_hashes_separate':True,'PDF_graphics_positions_independently_compared':len(out),
        'maximum_geometry_rounding_delta':max(x['max_rounding_delta']for x in out)})
    small=[(k,v)for k,v in sorted(unique.items())if v['height']<250 and v.get('mask_sha256')]
    sheet=Image.new('RGB',(800,max(1,len(small))*120),'white');draw=ImageDraw.Draw(sheet)
    for n,(key,meta)in enumerate(small):
        im=Image.open(assets/(key+'.png'));im.thumbnail((170,90));sheet.paste(im,(20,n*120+10));draw.text((220,n*120+45),key+' '+str(meta['width'])+'x'+str(meta['height']),fill='black')
    sheet.save(BASE/'render/actual-mask-QA.png')
    print(json.dumps({'passed':not mismatches,'occurrences':len(out),'unique_assets':len(unique),'mismatches':mismatches[:5]}),flush=True)
    if mismatches:raise SystemExit(1)

if __name__=='__main__':main()
