"""External annual MODIS Terra NPP on the CLCD regional support (2005-2023).

Raw public COGs and catalogue caches go to --work. Access uses short-lived public
Planetary Computer signatures; signed URLs are never stored in source manifests.
NPP is a model-derived ecosystem-function proxy, not ecological-event ground truth.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse,hashlib,json,os,re,urllib.request,urllib.parse,datetime,time,threading
import numpy as np,pandas as pd,rasterio
from rasterio.windows import from_bounds,Window
from rasterio.warp import transform_bounds
from pyproj import Transformer,CRS
from scipy.stats import pearsonr,spearmanr

P=Path(__file__).resolve().parent;D=P/'data'
BASE='https://planetarycomputer.microsoft.com/api/stac/v1/search'
ALBERS=CRS.from_proj4('+proj=aea +lat_1=25 +lat_2=47 +lat_0=0 +lon_0=105 +datum=WGS84 +units=m +no_defs')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=Path,default=Path(os.environ.get('QILIAN_WORK','work')))
    ap.add_argument('--proxy',default=None);ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
    a.work.mkdir(parents=True,exist_ok=True);raw=a.work/'NPP_raw';raw.mkdir(exist_ok=True)
    def opener():return urllib.request.build_opener(urllib.request.ProxyHandler({'https':a.proxy,'http':a.proxy}) if a.proxy else urllib.request.ProxyHandler())
    def get_json(url):
        with opener().open(url,timeout=60) as res:return json.load(res)
    tr=Transformer.from_crs('EPSG:4326',ALBERS,always_xy=True)
    x0,y0=tr.transform(93.5,36.);x1,y1=tr.transform(103.5,40.5)
    bounds=(min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1))
    bbox=transform_bounds(ALBERS,'EPSG:4326',*bounds,densify_pts=21)
    catalog=a.work/'NPP_catalogue_2005_2023.json'
    if catalog.exists():meta=json.loads(catalog.read_text(encoding='utf-8'))
    else:
        url=BASE+'?'+urllib.parse.urlencode({'collections':'modis-17A3HGF-061','bbox':','.join(map(str,bbox)),
                'datetime':'2005-01-01/2023-12-31','limit':500})
        meta=get_json(url);catalog.write_text(json.dumps(meta,indent=2),encoding='utf-8')
    assert not any(l['rel']=='next' for l in meta.get('links',[])),'Catalogue pagination required'
    candidates=[f for f in meta['features'] if f['id'].startswith('MOD17A3HGF.')]
    # Keep the most recent provider processing timestamp for duplicate year/tiles.
    latest={}
    for f in candidates:
        key=(re.search(r'\.A(\d{4})',f['id']).group(1),re.search(r'\.h\d+v\d+\.',f['id']).group(0))
        if key not in latest or f['id']>latest[key]['id']:latest[key]=f
    features=list(latest.values())
    assert features and {int(re.search(r'\.A(\d{4})',f['id']).group(1)) for f in features}==set(range(2005,2024))
    downloads=[]
    for f in features:
        for asset in ['Npp_500m','Npp_QC_500m']:
            url=f['assets'][asset]['href'];dest=raw/url.rsplit('/',1)[1]
            downloads.append((f,asset,url,dest))
    signing={};sign_lock=threading.Lock()
    def signed_url(url):
        with sign_lock:
            if signing.get('container_query'):return url+'?'+signing['container_query']
            href=get_json('https://planetarycomputer.microsoft.com/api/sas/v1/sign?'+urllib.parse.urlencode({'href':url}))['href']
            query=urllib.parse.urlsplit(href).query
            if urllib.parse.parse_qs(query).get('sr')==['c']:signing['container_query']=query
            return href
    def download(job):
        f,asset,url,dest=job
        if not dest.exists():
            for attempt in range(3):
                try:
                    signed=signed_url(url)
                    temp=dest.with_suffix('.part')
                    with opener().open(signed,timeout=75) as res,temp.open('wb') as out:
                        while True:
                            block=res.read(1024*1024)
                            if not block:break
                            out.write(block)
                    temp.replace(dest);break
                except Exception:
                    if attempt==2:raise
                    time.sleep(2)
        with rasterio.open(dest) as src:assert src.count==1 and src.width==2400
        return {'item_id':f['id'],'asset':asset,'href':url,'file':dest.name,
                'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size}
    manifests=[];errors=[]
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i,job in enumerate(as_completed([ex.submit(download,j) for j in downloads]),1):
            try:manifests.append(job.result())
            except Exception as error:
                errors.append(type(error).__name__+': '+str(error).split('?')[0]);print('NPP_DOWNLOAD_ERROR',errors[-1],flush=True)
            if i%20==0 or i==len(downloads):print('NPP_ASSETS',i,'/',len(downloads),flush=True)
    (a.work/'NPP_download_errors.json').write_text(json.dumps(errors,indent=2),encoding='utf-8')
    assert not errors,errors
    # A tile-wise common mask keeps the sampled ecosystem support identical over years.
    tiles=sorted({re.search(r'\.h\d+v\d+\.',f['id']).group(0) for f in features})
    stats={y:{'sum':0.,'n':0,'common_sum':0.,'common_n':0,'qc_sum':0.,'common_qc_sum':0.} for y in range(2005,2024)}
    tile_stats=[]
    for tile in tiles:
        fs=sorted([f for f in features if tile in f['id']],key=lambda f:f['id'])
        assert len(fs)==19,(tile,len(fs))
        arrays=[];qas=[];masks=[];yearlist=[];support=None
        for f in fs:
            year=int(re.search(r'\.A(\d{4})',f['id']).group(1));yearlist.append(year)
            path=raw/f['assets']['Npp_500m']['href'].rsplit('/',1)[1]
            with rasterio.open(path) as src:
                rb=transform_bounds(ALBERS,src.crs,*bounds,densify_pts=21)
                full=from_bounds(*rb,src.transform)
                col=max(0,int(np.floor(full.col_off)));row=max(0,int(np.floor(full.row_off)))
                right=min(src.width,int(np.ceil(full.col_off+full.width)));bottom=min(src.height,int(np.ceil(full.row_off+full.height)))
                if right<=col or bottom<=row:break
                win=Window(col,row,right-col,bottom-row)
                arr=src.read(1,window=win)
                if support is None:
                    transform=src.window_transform(win)
                    xx=transform.c+(np.arange(arr.shape[1])+.5)*transform.a
                    yy=transform.f+(np.arange(arr.shape[0])+.5)*transform.e
                    xx,yy=np.meshgrid(xx,yy)
                    px,py=Transformer.from_crs(src.crs,ALBERS,always_xy=True).transform(xx,yy)
                    support=(px>=bounds[0])&(px<=bounds[2])&(py>=bounds[1])&(py<=bounds[3])
            qpath=raw/f['assets']['Npp_QC_500m']['href'].rsplit('/',1)[1]
            with rasterio.open(qpath) as src:qa=src.read(1,window=win)
            mask=support&(arr>=-30000)&(arr<=32700)&(qa>=0)&(qa<=100)
            arrays.append(arr);qas.append(qa);masks.append(mask)
        if not arrays:continue
        assert len(arrays)==19
        common=np.logical_and.reduce(masks)
        tile_stats.append({'tile':tile.strip('.'),'region_pixels':int(support.sum()),'common_valid_pixels':int(common.sum())})
        for year,arr,qa,mask in zip(yearlist,arrays,qas,masks):
            s=stats[year]
            s['sum']+=float(arr[mask].astype(np.float64).sum())*.0001;s['n']+=int(mask.sum());s['qc_sum']+=float(qa[mask].astype(np.float64).sum())
            s['common_sum']+=float(arr[common].astype(np.float64).sum())*.0001;s['common_n']+=int(common.sum());s['common_qc_sum']+=float(qa[common].astype(np.float64).sum())
    rows=[]
    for year,s in sorted(stats.items()):
        assert s['n']>0 and s['common_n']>0
        rows.append({'year':year,'npp_kgC_m2_yr':s['sum']/s['n'],'common_mask_npp_kgC_m2_yr':s['common_sum']/s['common_n'],
                     'valid_pixels':s['n'],'common_valid_pixels':s['common_n'],
                     'mean_QC_percent':s['qc_sum']/s['n'],'common_mean_QC_percent':s['common_qc_sum']/s['common_n']})
    out=pd.DataFrame(rows);out.to_csv(D/'r67_NPP_annual.csv',index=False,encoding='utf-8-sig',float_format='%.17g')
    assert np.all(out.valid_pixels.to_numpy()==out.common_valid_pixels.to_numpy()),'Annual and common-mask supports differ; revise the support summary.'
    manifest={'product':'MOD17A3HGF.061 Terra','doi':'https://doi.org/10.5067/MODIS/MOD17A3HGF.061',
              'catalogue':'https://planetarycomputer.microsoft.com/api/stac/v1/collections/modis-17A3HGF-061',
              'scale':.0001,'unit':'kg C m-2 year-1','years':[2005,2023],
              'valid_NPP_raw_range':[-30000,32700],'valid_QC_range':[0,100],
              'support':'pixel centres within the existing CLCD two-corner Albers rectangle; equal-area MODIS grid',
              'Albers_bounds':bounds,'geographic_search_bbox':bbox,'tiles':tile_stats,'assets':sorted(manifests,key=lambda m:m['file']),
              'access_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'duplicate_policy':'latest provider processing timestamp per year and tile within Collection 6.1',
              'interpretation':'external model-derived ecosystem-function proxy; not field measurements or warning-event labels'}
    (D/'r67_NPP_source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    annual=D/'r67_annual_series.csv'
    if annual.exists():
        series=pd.read_csv(annual).set_index('year');associations=[]
        for index in ['annual_esi','first_year_zero_esi','reconstructed_esi']:
            col='common_mask_npp_kgC_m2_yr'
            frame=series[[index]].join(out.set_index('year')[[col]]).dropna()
            for mode in ['levels','first_differences']:
                use=frame if mode=='levels' else frame.diff().dropna()
                associations.append({'index':index,'NPP_support':'716,907 pixels valid in every year','comparison':mode,'n_years_or_differences':len(use),
                                     'pearson_r':float(pearsonr(use.iloc[:,0],use.iloc[:,1]).statistic),
                                     'spearman_rho':float(spearmanr(use.iloc[:,0],use.iloc[:,1]).statistic)})
        pd.DataFrame(associations).to_csv(D/'r67_NPP_associations.csv',index=False,encoding='utf-8-sig',float_format='%.17g')
        # Descriptive sensitivity for the year with unusually high reliance on
        # gap-filled inputs. First-difference pairs touching 2014 are excluded.
        nppframe=series[['annual_esi']].join(out.set_index('year')[['common_mask_npp_kgC_m2_yr','common_mean_QC_percent']]).dropna()
        yrs=nppframe.index.to_numpy(dtype=int);esi=nppframe.annual_esi.to_numpy(float);nppv=nppframe.common_mask_npp_kgC_m2_yr.to_numpy(float)
        def corr(a,b):return float(pearsonr(np.asarray(a,float),np.asarray(b,float)).statistic)
        def detrend(v,t):return np.asarray(v,float)-np.polyval(np.polyfit(t,np.asarray(v,float),1),t)
        keep=yrs!=2014;dkeep=(yrs[:-1]!=2014)&(yrs[1:]!=2014)
        sensitivity=[
            {'comparison':'Levels, all years','n':len(yrs),'pearson_r':corr(esi,nppv),'mean_QC_2014_percent':float(nppframe.loc[2014,'common_mean_QC_percent'])},
            {'comparison':'Linearly detrended levels, all years','n':len(yrs),'pearson_r':corr(detrend(esi,yrs),detrend(nppv,yrs)),'mean_QC_2014_percent':float(nppframe.loc[2014,'common_mean_QC_percent'])},
            {'comparison':'Levels excluding 2014','n':int(keep.sum()),'pearson_r':corr(esi[keep],nppv[keep]),'mean_QC_2014_percent':float(nppframe.loc[2014,'common_mean_QC_percent'])},
            {'comparison':'Linearly detrended levels excluding 2014','n':int(keep.sum()),'pearson_r':corr(detrend(esi[keep],yrs[keep]),detrend(nppv[keep],yrs[keep])),'mean_QC_2014_percent':float(nppframe.loc[2014,'common_mean_QC_percent'])},
            {'comparison':'First differences, all adjacent years','n':len(yrs)-1,'pearson_r':corr(np.diff(esi),np.diff(nppv)),'mean_QC_2014_percent':float(nppframe.loc[2014,'common_mean_QC_percent'])},
            {'comparison':'First differences excluding pairs touching 2014','n':int(dkeep.sum()),'pearson_r':corr(np.diff(esi)[dkeep],np.diff(nppv)[dkeep]),'mean_QC_2014_percent':float(nppframe.loc[2014,'common_mean_QC_percent'])}]
        pd.DataFrame(sensitivity).to_csv(D/'r67_NPP_sensitivity.csv',index=False,encoding='utf-8-sig',float_format='%.17g')
    print('NPP_COMPLETE',len(out),'years','common pixels',int(out.common_valid_pixels.iloc[0]),flush=True)
if __name__=='__main__':main()
