"""Validate the 2023-origin ESI forecasts against 2024-2025 observations.

Historical inputs, scaling bounds, weights, models and forecasts remain fixed.
Raw extraction requires CLCD 2020, original/new 2023 and 2024-2025 rasters
and CRU TS 4.10 NetCDFs; --from-processed uses supplied extraction summaries.
"""
from pathlib import Path
import argparse,hashlib,json,os,sys
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
from pyproj import Transformer
import r28_core as C
import io_utils

P=Path(__file__).resolve().parent;D=P/'data'
LC_MD5={2023:'114c1e8a4c6fd98f2ef8347e2dc11a2a',2024:'724ee40c48f5149410d721ec6cb693b5',2025:'293d0375c282e359ccbaa98b68173cce'}
LEVELS=['Severe warning','Medium warning','Mild warning','Relatively safe','Safe']
BOX=(93.5,36.0,103.5,40.5)
CLIMATE_BOX={'lat':slice(36.5,40.0),'lon':slice(94.0,103.0)}
NAMES={'X1_降水mm':'Precipitation (mm)','X2_气温C':'Temperature (deg C)',
       'X3_草地占比%':'Grassland (%)','X4_森林占比%':'Forest (%)',
       'X5_水域占比%':'Water (%)','X6_裸地荒漠%':'Barren/degraded residual (%)',
       'X7_农田占比%':'Cropland (%)','X8_草地变化率':'Grassland change (%/yr)'}

def md5(path):
    h=hashlib.md5()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def save(df,name):
    df=pd.DataFrame(df)
    df.to_csv(D/f'r56_{name}.csv',index=False,encoding='utf-8-sig',float_format='%.17g')
    return df

def extract_lc(path,year,cache=None):
    # Same projected two-corner window and nearest-neighbour read as process_clcd.py.
    # Read the original window once; histogram row chunks avoid an int64 copy of it.
    checksum=md5(path)
    cached=cache/(checksum+'.json') if cache else None
    if cached and cached.exists():
        meta=json.loads(cached.read_text(encoding='utf-8'))
        return meta['proportions'],meta
    with rasterio.Env(GDAL_CACHEMAX=128*1024*1024):
        with rasterio.open(path) as src:
            if src.crs is None or src.crs.to_epsg()==4326:
                win=from_bounds(*BOX,src.transform)
            else:
                tr=Transformer.from_crs('EPSG:4326',src.crs,always_xy=True)
                x0,y0=tr.transform(BOX[0],BOX[1]);x1,y1=tr.transform(BOX[2],BOX[3])
                win=from_bounds(min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1),src.transform)
            arr=src.read(1,window=win)
            hist=np.zeros(256,dtype=np.int64)
            for i in range(0,arr.shape[0],128):hist+=np.bincount(arr[i:i+128].ravel(),minlength=256)
            total=int(hist[1:].sum());assert total>0
            pct=lambda k:float(hist[k])*100/total
            row=dict(year=year,forest_pct=pct(2),shrub_pct=pct(3),grass_pct=pct(4),water_pct=pct(5),crop_pct=pct(1),valid_pixels=total,rows=arr.shape[0],columns=arr.shape[1])
            meta=dict(filename=Path(path).name,year=year,md5=checksum,bytes=Path(path).stat().st_size,crs=str(src.crs),window=[float(win.col_off),float(win.row_off),float(win.width),float(win.height)],valid_pixels=total,class_counts={str(k):int(v) for k,v in enumerate(hist) if v},proportions=row)
    if cached:cached.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print('LANDCOVER',json.dumps(row),flush=True)
    return row,meta

def climate(cru):
    rows={y:{'year':y} for y in [2023,2024,2025]};sources=[]
    for var,col,agg in [('pre','precip_mm','sum'),('tmp','temp_c','mean')]:
        path=Path(cru)/f'cru_ts4.10.2021.2025.{var}.dat.nc'
        ds,engine=io_utils.open_netcdf(path)
        a=ds[var].sel(time=slice('2023-01','2025-12'),**CLIMATE_BOX)
        assert a.sizes['time']==36
        annual=getattr(a.groupby('time.year'),agg)('time').mean(['lat','lon'])
        for y in rows:
            assert int((a.time.dt.year==y).sum())==12
            rows[y][col]=float(annual.sel(year=y).values)
        sources.append(dict(filename=path.name,md5=md5(path),engine=engine,months=36,lat_cells=a.sizes['lat'],lon_cells=a.sizes['lon']))
        ds.close()
    return pd.DataFrame(rows.values()).set_index('year'),sources

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lc-dir',type=Path)
    parser.add_argument('--old-lc-dir',type=Path,help='CLCD v1.0.3 directory containing the original 2023 raster')
    parser.add_argument('--from-processed',action='store_true',help='Reproduce scores from supplied class counts and climate summaries')
    parser.add_argument('--baseline-lc-dir',type=Path)
    parser.add_argument('--cru-dir',type=Path)
    parser.add_argument('--work',type=Path,default=Path(os.environ.get('QILIAN_WORK','work')))
    a=parser.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    protected={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in D.iterdir() if f.is_file() and not f.name.startswith('r56_')}
    checks=[]
    def check(name,passed,detail=''):
        checks.append(dict(check=name,passed=bool(passed),detail=str(detail)))
        assert passed,(name,detail)
    if a.from_processed:
        previous=json.loads((D/'r56_source_manifest.json').read_text(encoding='utf-8'))
        metadata=previous['CLCD'];land=[m['proportions'] for m in metadata]
        oldmeta=previous['historical_2023_control'];oldrow=oldmeta['proportions']
        cli=pd.read_csv(D/'r56_climate.csv',float_precision='round_trip').set_index('year');cm=previous['climate']
    else:
        if a.lc_dir is None or a.old_lc_dir is None:parser.error('--lc-dir and --old-lc-dir are required for raw-data extraction')
        baseline=a.baseline_lc_dir or Path(io_utils.resolve_lc_dir(verbose=False))
        cru=a.cru_dir or Path(io_utils.resolve_cru_dir(verbose=False))
        cache=a.work/'histogram_cache';cache.mkdir(exist_ok=True)
        land=[];metadata=[]
        for y,path in [(2020,baseline/'CLCD_v01_2020_albert.tif')]+[(y,a.lc_dir/f'CLCD_v01_{y}_albert.tif') for y in [2023,2024,2025]]:
            row,meta=extract_lc(path,y,cache);land.append(row);metadata.append(meta)
        oldrow,oldmeta=extract_lc(a.old_lc_dir/'CLCD_v01_2023_albert.tif',2023,cache)
        cli,cm=climate(cru)
    for meta in metadata:
        y=meta['year']
        if y in LC_MD5:check(f'official_CLCD_{y}_md5',meta['md5']==LC_MD5[y],meta['md5'])
    check('original_2023_v103_md5',oldmeta['md5']=='23abf385627eff72d2fc1d0a3868e145')
    lc=save(land,'landcover').set_index('year')
    archived=pd.read_csv(D/'qilian_landcover.csv').set_index('year')
    bridge=[]
    for col in ['forest_pct','shrub_pct','grass_pct','water_pct','crop_pct']:
        check('baseline_2020_'+col,abs(lc.loc[2020,col]-archived.loc[2020,col])<1e-10)
        check('original_2023_'+col,abs(oldrow[col]-archived.loc[2023,col])<1e-10,float(oldrow[col]-archived.loc[2023,col]))
        bridge.append(dict(indicator=col,archived_2023=archived.loc[2023,col],v103_2023=oldrow[col],v105_2023=lc.loc[2023,col],revision_percentage_points=lc.loc[2023,col]-oldrow[col]))
    save(bridge,'release_bridge')
    check('identical_valid_pixel_support',lc.valid_pixels.nunique()==1 and lc.rows.nunique()==1 and lc['columns'].nunique()==1)
    save(cli.reset_index(),'climate')
    oldcli=pd.read_csv(D/'qilian_climate.csv');oldcli=oldcli[(oldcli.unit=='区域(祁连山盒)')&(oldcli.year==2023)].iloc[0]
    for col in ['precip_mm','temp_c']:check('baseline_2023_climate_'+col,abs(cli.loc[2023,col]-oldcli[col])<1e-4)
    r=C.compute(C.DEREDUNDANT_SETS['drop_X9']);keep=r['keep'];raw=r['raw'][keep]
    hist=raw.to_numpy(float);lo=hist.min(axis=0);hi=hist.max(axis=0);span=hi-lo
    check('eight_nonconstant_indicators',len(keep)==8 and np.all(span>0))
    def normalize(x):
        z=(x-lo)/span
        return np.where(r['directions']>0,z,1-z)
    check('frozen_history_reproduces_ESI',np.max(np.abs(normalize(hist)@r['w']-r['esi']))<1e-12)
    stored=pd.read_csv(D/'r47_primary_weights.csv').set_index('indicator')
    check('fixed_weights_match_reported',np.max(np.abs(stored.loc[keep,'combined'].to_numpy()-r['w']))<1e-12)
    futures=[];inputrows=[];values={}
    prev_grass=float(archived.loc[2023,'grass_pct'])
    for y in [2024,2025]:
        obs=[cli.loc[y,'precip_mm'],cli.loc[y,'temp_c'],lc.loc[y,'grass_pct'],lc.loc[y,'forest_pct'],lc.loc[y,'water_pct'],100-lc.loc[y,['grass_pct','forest_pct','water_pct','crop_pct']].sum(),lc.loc[y,'crop_pct'],(lc.loc[y,'grass_pct']/prev_grass-1)*100]
        x=np.asarray(obs,float);z=normalize(x);clipped=np.clip(z,0,1)
        common=x.copy()
        if y==2024:common[-1]=(lc.loc[y,'grass_pct']/lc.loc[2023,'grass_pct']-1)*100
        commonz=normalize(common)
        linear=float(z@r['w']);bounded=float(clipped@r['w']);same_release=float(commonz@r['w']);values[y]=(linear,bounded,same_release)
        check(f'clipping_anchor_invariance_{y}',abs(float(np.clip(commonz,0,1)@r['w'])-bounded)<1e-12)
        grade=int(np.digitize(linear,C.THRESHOLDS)) if 0<=linear<=1 else np.nan
        cgrade=int(np.digitize(bounded,C.THRESHOLDS))
        futures.append(dict(year=y,observed_esi=linear,clipped_esi=bounded,same_release_esi=same_release,grade=grade,grade_label=LEVELS[int(grade)] if np.isfinite(grade) else 'Outside reference scale',clipped_grade=cgrade,clipped_grade_label=LEVELS[cgrade],out_of_range_inputs=int(((z<0)|(z>1)).sum())))
        for j,name in enumerate(keep):inputrows.append(dict(year=y,indicator=name,name_en=NAMES[name],raw=x[j],same_release_raw=common[j],historical_min=lo[j],historical_max=hi[j],direction=int(r['directions'][j]),weight=r['w'][j],normalized=z[j],same_release_normalized=commonz[j],clipped_normalized=clipped[j],out_of_range=bool(z[j]<0 or z[j]>1),contribution=z[j]*r['w'][j],clipped_contribution=clipped[j]*r['w'][j]))
        prev_grass=float(lc.loc[y,'grass_pct'])
    observed=save(futures,'observed_series');save(inputrows,'inputs')
    fc=pd.read_csv(D/'r47_forecast.csv');fc=fc[fc.year.isin([2024,2025])].copy()
    fc['observed']=fc.year.map({y:v[0] for y,v in values.items()});fc['clipped_observed']=fc.year.map({y:v[1] for y,v in values.items()})
    fc['same_release_observed']=fc.year.map({y:v[2] for y,v in values.items()})
    fc=fc.rename(columns={'value':'predicted','grade':'predicted_grade'})
    fc['error']=fc.predicted-fc.observed;fc['clipped_error']=fc.predicted-fc.clipped_observed;fc['same_release_error']=fc.predicted-fc.same_release_observed
    fc['observed_grade']=fc.year.map(observed.set_index('year').grade)
    fc['grade_match']=np.where(fc.observed_grade.notna(),fc.predicted_grade==fc.observed_grade,np.nan)
    fc['clipped_observed_grade']=fc.year.map(observed.set_index('year').clipped_grade)
    fc['clipped_grade_match']=fc.predicted_grade==fc.clipped_observed_grade
    save(fc,'forecast_comparison')
    summary=[]
    for model,g in fc.groupby('model',sort=False):
        summary.append(dict(model=model,n_years=len(g),mae=float(np.abs(g.error).mean()),rmse=float(np.sqrt(np.mean(g.error**2))),same_release_mae=float(np.abs(g.same_release_error).mean()),same_release_rmse=float(np.sqrt(np.mean(g.same_release_error**2))),clipped_mae=float(np.abs(g.clipped_error).mean()),clipped_rmse=float(np.sqrt(np.mean(g.clipped_error**2))),linear_grade_eligible_years=int(g.observed_grade.notna().sum()),grades_matching=int((g.grade_match==1).sum()),clipped_grades_matching=int(g.clipped_grade_match.sum())))
    summary=save(summary,'forecast_summary')
    env=pd.read_csv(D/'r47_bootstrap.csv');env=env[env.year.isin([2024,2025])].copy()
    env['observed']=env.year.map({y:v[0] for y,v in values.items()});env['clipped_observed']=env.year.map({y:v[1] for y,v in values.items()})
    env['same_release_observed']=env.year.map({y:v[2] for y,v in values.items()})
    env['within_conditional_envelope']=(env.observed>=env.lo)&(env.observed<=env.hi)
    env['clipped_within_conditional_envelope']=(env.clipped_observed>=env.lo)&(env.clipped_observed<=env.hi)
    env['same_release_within_conditional_envelope']=(env.same_release_observed>=env.lo)&(env.same_release_observed<=env.hi)
    save(env,'envelope_check')
    check('all_original_data_unchanged',all(hashlib.sha256((D/n).read_bytes()).hexdigest()==h for n,h in protected.items()))
    check('two_observed_years_all_six_forecasts',len(observed)==2 and len(fc)==12 and len(summary)==6)
    save(checks,'checks')
    manifest=dict(CLCD=metadata,historical_2023_control=oldmeta,CLCD_record='https://zenodo.org/records/18180184',historical_2023_record='https://zenodo.org/records/12779975',CLCD_new_version='1.0.5',climate=cm,landcover_bbox=BOX,climate_bbox={'lat':[36.5,40.0],'lon':[94,103]},history=[2005,2023],forecast_origin=2023,scaling='historical-anchor affine continuation; same-release 2023 bridge; per-input clipping',grading='linear scores outside [0,1] ungraded',mixture_weights='r47_mixture_weights.csv unchanged',independent_temporal_years=2,interpretation='index forecast check with product-version bridge, not ecological-event calibration',python=sys.version.split()[0],numpy=np.__version__,pandas=pd.__version__,rasterio=rasterio.__version__)
    (D/'r56_source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('OBSERVED\n'+observed.to_string(index=False),flush=True)
    print('FORECAST ERRORS\n'+summary.to_string(index=False),flush=True)
    print('CHECKS',len(checks),'PASS',flush=True)

if __name__=='__main__':main()
