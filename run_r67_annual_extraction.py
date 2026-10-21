"""Extract annual CLCD release 1.0.5 on the existing regional support.

Uses range reads of official COGs; provider MD5 is recorded, not presented as
a locally recomputed whole-file checksum. Exact selected pixels have SHA256.
Cached regional crops and logs go to --work; processed source counts go to data.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse,datetime,hashlib,json,os,time,urllib.request
import numpy as np,pandas as pd,rasterio
from rasterio.windows import from_bounds
from rasterio.transform import Affine
from pyproj import Transformer

P=Path(__file__).resolve().parent
BOX=(93.5,36.,103.5,40.5)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=Path,default=Path(os.environ.get('QILIAN_WORK','work')))
    ap.add_argument('--local-dir',type=Path,action='append',default=[])
    ap.add_argument('--years',type=int,nargs='+',default=list(range(2004,2026)))
    ap.add_argument('--workers',type=int,default=3);ap.add_argument('--proxy',default=None)
    ap.add_argument('--metadata',type=Path);a=ap.parse_args()
    a.work.mkdir(parents=True,exist_ok=True);cache=a.work/'annual_crops';cache.mkdir(exist_ok=True)
    if a.metadata:metadata=json.loads(a.metadata.read_text(encoding='utf-8'))
    else:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':a.proxy,'http':a.proxy}) if a.proxy else urllib.request.ProxyHandler())
        with opener.open('https://zenodo.org/api/records/18180184',timeout=60) as res:metadata=json.load(res)
        (a.work/'CLCD_record_18180184.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    files={f['key']:f for f in metadata['files']}
    controls_path=P/'data/r56_source_manifest.json'
    controls={m['year']:m for m in json.loads(controls_path.read_text(encoding='utf-8'))['CLCD']}
    def worker(y):
        start=time.time();filename=f'CLCD_v01_{y}_albert.tif';f=files[filename]
        dest=cache/f'{y}.json'
        if dest.exists():
            meta=json.loads(dest.read_text(encoding='utf-8'))
            assert meta['provider_md5']=='%s'%f['checksum']
            return meta
        local=next((d/filename for d in a.local_dir if (d/filename).exists()),None)
        url=f'https://zenodo.org/records/18180184/files/{filename}?download=1'
        for attempt in range(3):
            try:
                if local:
                    h=hashlib.md5()
                    with local.open('rb') as stream:
                        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
                    assert 'md5:'+h.hexdigest()==f['checksum'],f'Local version mismatch {y}'
                with rasterio.open(local if local else '/vsicurl/'+url) as src:
                    tr=Transformer.from_crs('EPSG:4326',src.crs,always_xy=True)
                    x0,y0=tr.transform(BOX[0],BOX[1]);x1,y1=tr.transform(BOX[2],BOX[3])
                    win=from_bounds(min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1),src.transform)
                    arr=src.read(1,window=win)
                    hist=np.zeros(256,dtype=np.int64)
                    for row in range(0,len(arr),128):hist+=np.bincount(arr[row:row+128].ravel(),minlength=256)
                    pixel_sha=hashlib.sha256(memoryview(arr).cast('B')).hexdigest()
                    crop=cache/f'CLCD_{y}_region.tif'
                    trans=src.window_transform(win)*Affine.scale(win.width/arr.shape[1],win.height/arr.shape[0])
                    with rasterio.open(crop,'w',driver='GTiff',height=arr.shape[0],width=arr.shape[1],count=1,dtype='uint8',
                                       crs=src.crs,transform=trans,compress='LZW',tiled=True,blockxsize=512,blockysize=512) as out:out.write(arr,1)
                    total=int(hist[1:].sum());assert total>0
                    row={'year':y,'forest_pct':float(hist[2])*100/total,'shrub_pct':float(hist[3])*100/total,
                         'grass_pct':float(hist[4])*100/total,'water_pct':float(hist[5])*100/total,
                         'crop_pct':float(hist[1])*100/total,'valid_pixels':total}
                    if y in controls:
                        assert {str(k):int(v) for k,v in enumerate(hist) if v}==controls[y]['class_counts'],f'Existing raw control differs {y}'
                    meta={'year':y,'record':'https://zenodo.org/records/18180184','version':metadata['metadata']['version'],
                          'filename':filename,'url':url,'provider_md5':f['checksum'],'provider_file_bytes':f['size'],
                          'whole_file_md5_locally_verified':bool(local),'selected_pixels_sha256':pixel_sha,
                          'crop_file_sha256':hashlib.sha256(crop.read_bytes()).hexdigest(),
                          'class_counts':{str(k):int(v) for k,v in enumerate(hist) if v},'proportions':row,
                          'window':[float(v) for v in win.flatten()],'shape':list(arr.shape),'crs':str(src.crs),
                          'support':'same two-corner projected window and nearest-neighbour read as historical extraction',
                          'access_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'seconds':time.time()-start}
                    del arr
                dest.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
                print('EXTRACTED',y,round(time.time()-start,1),row,flush=True)
                return meta
            except Exception:
                if attempt==2:raise
                time.sleep(2*(attempt+1))
    settings=dict(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',CPL_VSIL_CURL_USE_HEAD='NO',
                  CPL_VSIL_CURL_CHUNK_SIZE=1048576,GDAL_HTTP_MULTIRANGE='SERIAL',
                  GDAL_HTTP_MAX_RETRY=2,GDAL_HTTP_RETRY_DELAY=1,GDAL_HTTP_TIMEOUT=50,GDAL_CACHEMAX=128*1024*1024)
    if a.proxy:settings['GDAL_HTTP_PROXY']=a.proxy.removeprefix('http://').removeprefix('https://')
    results=[];errors=[]
    with rasterio.Env(**settings):
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            jobs={ex.submit(worker,y):y for y in a.years}
            for task in as_completed(jobs):
                try:results.append(task.result())
                except Exception as e:
                    errors.append({'year':jobs[task],'error':str(e)});print('ERROR',jobs[task],str(e),flush=True)
    (a.work/'extraction_errors.json').write_text(json.dumps(errors,indent=2),encoding='utf-8')
    assert not errors,errors
    results.sort(key=lambda m:m['year'])
    pd.DataFrame(m['proportions'] for m in results).to_csv(P/'data/r67_annual_landcover.csv',index=False,encoding='utf-8-sig',float_format='%.17g')
    (P/'data/r67_annual_source_manifest.json').write_text(json.dumps({'bbox':BOX,'years':a.years,'sources':results},ensure_ascii=False,indent=2),encoding='utf-8')
    print('COMPLETE',len(results),'years',flush=True)
if __name__=='__main__':main()
