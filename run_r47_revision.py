"""Recompute the corrected 2.2 analysis from committed inputs.

Writes scientific results to data/r47_*.csv. Logs, bootstrap paths and diagnostic
figures are directed to QILIAN_WORK (default ../ChatGPT/revision_2.2_2026-10-20).
Main forecast validation is conditional on the retrospectively reconstructed
eight-indicator index, with rolling five-step errors defining mixture weights.
No leave-one-year-out score is used. Spatial shifts are exhaustive alignment
diagnostics under a periodic-boundary reference, not a calibrated ecological null.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import os
import sys
import warnings
import json
import numpy as np
import pandas as pd
from scipy.special import expit,logit
from scipy import stats

warnings.filterwarnings('ignore',category=UserWarning)
P=Path(__file__).resolve().parent
D=P/'data'
W=Path(os.environ.get('QILIAN_WORK',P.parent/'ChatGPT/revision_2.2_2026-10-20'))
W.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(P))
import r28_core as C
from forecast_models import fit_forecast,ngbm,gm11,grey_accuracy,GAMMA_GRID,select_gamma

MODELS=['GM(1,1)','NGBM','ARIMA(0,1,1)']
ALL=MODELS+['Naive','Drift']
SEED=20261020
THR=np.array([.2,.4,.6,.8])

def save(rows,name):
    df=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    df.to_csv(D/('r47_'+name+'.csv'),index=False,encoding='utf-8-sig',float_format='%.12g')
    return df

def region():return C.compute(C.DEREDUNDANT_SETS['drop_X9'])

def test_response():
    x=np.array([.31,.38,.44,.43,.48,.51,.47,.49])
    f,h,_=ngbm(x,0.,5);g,j=gm11(x,5)
    assert np.allclose(f,g) and np.allclose(h,j)
    f,h,par=ngbm(x,.15,5)
    a,b,g=par
    def acc(t):return ((x[0]**(1-g)-b/a)*np.exp(-a*(1-g)*t)+b/a)**(1/(1-g))
    expected=np.array([acc(t)-acc(t-1) for t in range(1,len(x)+5)])
    assert np.allclose(np.r_[h[1:],f],expected)
    assert np.allclose(h[0],x[0])
    return {'gamma_zero_equals_gm11':True,'consecutive_response_indices':True}

def forecast():
    r=region();ys=np.asarray(r['esi']);years=np.asarray(r['years'])
    save([dict(year=int(y),esi=float(v),warning=str(level))
          for y,v,level in zip(years,ys,r['levels'])],'primary_series')
    save([dict(indicator=name,entropy=w1,subjective=w2,combined=w3)
          for name,w1,w2,w3 in zip(r['keep'],r['w_ent'],r['w_ahp'],r['w'])], 'primary_weights')
    save(pd.DataFrame(r['Xn'],index=pd.Index(years,name='year'),columns=r['keep']).reset_index(),
         'primary_normalized')
    old=pd.read_csv(D/'r28_deredundancy_series.csv')
    assert np.max(np.abs(ys-old.esi_drop_X9))<1e-12
    details=[]
    schemes=[('holdout',[(2018,5)]),('rolling1',[(o,1) for o in range(2013,2023)]),
             ('rolling5',[(o,5) for o in range(2013,2019)])]
    for sch,folds in schemes:
        for origin,H in folds:
            train=ys[years<=origin]
            for model in ALL:
                f,_,meta=fit_forecast(train,model,H)
                for h,pred in enumerate(f,1):
                    target=origin+h;ob=ys[np.where(years==target)[0][0]]
                    details.append(dict(scheme=sch,origin=origin,horizon=h,target_year=target,
                        model=model,observed=ob,predicted=pred,error=pred-ob,gamma=meta['gamma']))
    det=save(details,'validation_detail')
    summaries=[]
    for (sch,m),g in det.groupby(['scheme','model'],sort=False):
        summaries.append(dict(scheme=sch,model=m,n_predictions=len(g),n_origins=g.origin.nunique(),
            rmse=np.sqrt(np.mean(g.error**2)),mae=np.mean(np.abs(g.error)),
            gamma_min=g.gamma.min(),gamma_max=g.gamma.max()))
    summ=save(summaries,'validation')
    rmse=summ[(summ.scheme=='rolling5')&summ.model.isin(MODELS)].set_index('model').rmse
    weights=(1/rmse)/(1/rmse).sum()
    save([dict(model=m,weight=weights[m],basis_rmse=rmse[m],scheme='rolling5',
        n_origins=6,n_predictions=30) for m in MODELS],'mixture_weights')
    results=[];accuracy=[];fits={};point={}
    for m in ALL:
        f,fit,meta=fit_forecast(ys,m,5);point[m]=f;fits[m]=fit
        aa=grey_accuracy(ys,fit)
        accuracy.append(dict(model=m,gamma=meta['gamma'],**aa,fitted_2023=fit[-1],
            observed_2023=ys[-1],first_future_2024=f[0],step_from_fitted=f[0]-fit[-1]))
    point['Mixture']=sum(weights[m]*point[m] for m in MODELS)
    for i,y in enumerate(range(2024,2029)):
        for m,f in point.items():results.append(dict(year=y,model=m,value=f[i],grade=int(np.digitize(f[i],THR))))
    save(results,'forecast');save(accuracy,'fit_accuracy')
    # Each origin contributes one vector of five errors; overlaps are retained
    # explicitly, not treated as independent experiments.
    dp=det[det.scheme=='rolling5'].pivot(index=['origin','horizon','target_year'],columns='model',values='predicted')
    obs=det[(det.scheme=='rolling5')&(det.model==MODELS[0])].set_index(['origin','horizon','target_year']).observed
    mix=sum(weights[m]*dp[m] for m in MODELS)
    save([dict(scheme='rolling5',model='Mixture',rmse=np.sqrt(np.mean((mix-obs)**2)),
        mae=np.mean(np.abs(mix-obs)),n_predictions=len(obs),note='same records used to estimate weights; descriptive score')],
        'mixture_score')
    print('FORECAST',summ.to_string(index=False),flush=True)
    print('WEIGHTS',weights.to_dict(),'2028',point['Mixture'][-1],flush=True)
    return r,weights,point,fits

def blocks(values,n,rng,L=3):
    values=np.asarray(values)
    start=rng.integers(0,len(values),size=int(np.ceil(n/L)))
    return np.concatenate([values[(s+np.arange(L))%len(values)] for s in start])[:n]

def bootstrap(B):
    r,weights,point,fits=forecast()
    ys=np.asarray(r['esi']);n=len(ys);paths={};pure={};counts=[]
    for j,m in enumerate(MODELS):
        rng=np.random.default_rng(SEED+j)
        f0=np.clip(fits[m],1e-6,1-1e-6)
        residual=logit(ys)-logit(f0)
        # First period is an initial condition, not an independently estimated residual.
        residual=residual[1:];residual=residual-residual.mean()
        out=[];parameter=[];ng=0
        for b in range(B):
            pseudo=expit(logit(f0)+np.r_[0.,blocks(residual,n-1,rng)])
            try:
                f,_,meta=fit_forecast(pseudo,m,5)
                if not np.all(np.isfinite(f)) or np.any((f<=0)|(f>=1)):continue
                innovation=np.cumsum(blocks(residual,5,rng))
                out.append(expit(logit(f)+innovation));parameter.append(f)
                if m=='NGBM' and np.isclose(meta['gamma'],GAMMA_GRID[0]):ng+=1
            except (ValueError,FloatingPointError,OverflowError,np.linalg.LinAlgError):continue
            if (b+1)%200==0:print('BOOT',m,b+1,'/',B,flush=True)
        paths[m]=np.asarray(out);pure[m]=np.asarray(parameter)
        assert len(out)>=int(.85*B),(m,len(out))
        counts.append(dict(model=m,requested=B,valid=len(out),gamma_at_lower_bound=ng,
            seed=SEED+j,block_length=3,first_residual_excluded=True,
            interpretation='conditional simulation; no empirical coverage calibration'))
    # A linear pool of model-specific predictive distributions, not path averaging.
    rng=np.random.default_rng(SEED+100);N=3*B
    nums={m:int(round(N*weights[m])) for m in MODELS};nums[MODELS[-1]]+=N-sum(nums.values())
    paths['Mixture']=np.vstack([paths[m][rng.integers(len(paths[m]),size=nums[m])] for m in MODELS])
    pure['Mixture']=np.vstack([pure[m][rng.integers(len(pure[m]),size=nums[m])] for m in MODELS])
    rows=[]
    for m,v in paths.items():
        for i,y in enumerate(range(2024,2029)):
            a=v[:,i];lo,med,hi=np.quantile(a,[.025,.5,.975]);pl,pu=np.quantile(pure[m][:,i],[.025,.975])
            rows.append(dict(model=m,year=y,point=point[m][i],lo=lo,median=med,hi=hi,
                parameter_lo=pl,parameter_hi=pu,n_valid=len(v),
                severe_share=np.mean(a<.2),medium_share=np.mean((a>=.2)&(a<.4)),
                mild_share=np.mean((a>=.4)&(a<.6)),relative_safe_share=np.mean((a>=.6)&(a<.8)),
                safe_share=np.mean(a>=.8)))
    save(rows,'bootstrap');save(counts,'bootstrap_diagnostics')
    np.savez_compressed(W/'bootstrap_paths.npz',**{str(i):paths[m] for i,m in enumerate(paths)})
    print('BOOTSTRAP COMPLETE',flush=True)

def obstacle():
    r=region();years=r['years'];names=r['keep'];X=r['Xn']
    scenarios={'Combined':r['w'],'Entropy':r['w_ent'],'AHP':r['w_ahp'],
        'Equal':np.ones(len(names))/len(names)}
    annual=[];phase=[]
    for scheme,w in scenarios.items():
        z=(1-X)*w;z/=z.sum(1)[:,None]
        for i,y in enumerate(years):
            for j,name in enumerate(names):annual.append(dict(year=y,scheme=scheme,indicator=name,value=z[i,j]))
        for a,b in [(2005,2010),(2011,2023)]:
            mask=(np.asarray(years)>=a)&(np.asarray(years)<=b)
            means=z[mask].mean(0)
            for j,name in enumerate(names):phase.append(dict(phase=f'{a}-{b}',scheme=scheme,
                indicator=name,value=means[j],rank=int(np.sum(means>means[j])+1)))
    save(annual,'obstacle_annual');save(phase,'obstacle_phase')
    sums=pd.read_csv(D/'qilian_landcover.csv').set_index('year').sum(1)
    save([dict(year=int(y),listed_classes_sum=v,unlisted_remainder=100-v) for y,v in sums.items()],
         'landcover_coverage')
    sens=[]
    for direction in ['positive','negative','excluded']:
        rr=C.compute(C.DEREDUNDANT_SETS['drop_X9'],temp_direction=direction)
        yy=np.asarray(rr['esi']);base=np.asarray(r['esi'])
        sens.append(dict(direction=direction,value_2023=yy[-1],peak_year=years[int(np.argmax(yy))],
            max_abs_delta=np.max(np.abs(yy-base)),mean_abs_delta=np.mean(np.abs(yy-base)),
            rank_correlation=stats.spearmanr(yy,base).statistic,
            changed_grades=np.sum(np.digitize(yy,THR)!=np.digitize(base,THR))))
    save(sens,'temperature')
    decomp=[]
    for a,b in [(2005,2023),(2010,2023)]:
        ia,ib=years.index(a),years.index(b);delta=r['esi'][ib]-r['esi'][ia]
        for j,name in enumerate(names):
            value=r['w'][j]*(X[ib,j]-X[ia,j])
            decomp.append(dict(period=f'{a}-{b}',indicator=name,contribution=value,
                total_change=delta,share=value/delta,layer=C.LAYER[name]))
    save(decomp,'decomposition')
    gtrain=select_gamma(np.asarray(r['esi'])[:14]);gfull=select_gamma(r['esi'])
    save([dict(selection_window=window,gamma=g,year=year,value=v)
        for window,g in [('2005-2018',gtrain),('2005-2023',gfull)]
        for year,v in zip(range(2024,2029),ngbm(r['esi'],g,5)[0])],'gamma_sensitivity')

def q(y,s):
    y=np.asarray(y,float).ravel();s=np.asarray(s,int).ravel();s=np.unique(s,return_inverse=True)[1]
    c=np.bincount(s);a=np.bincount(s,weights=y);b=np.bincount(s,weights=y*y)
    return float(1-np.sum(b-a*a/c)/np.sum((y-y.mean())**2))

def spatial():
    pts=pd.read_csv(D/'spatial_samples.csv');esi=pd.read_csv(D/'spatial_esi_points.csv')
    df=esi.merge(pts,on=['lat','lon']);lat=np.sort(df.lat.unique());lon=np.sort(df.lon.unique())
    names=['precip','temp','grass','forest','water','barren_complement']
    raw=np.column_stack([df[n] for n in names[:-1]]+
                        [1-df.grass-df.forest-df.water])
    normalized=C.minmax_normalize(raw,[1,1,1,1,1,-1])
    we=C.entropy_weights(normalized);wc=.4/6+.6*we
    assert np.max(np.abs(normalized@wc-df.esi))<1e-12
    save([dict(indicator=n,entropy=a,subjective=1/6,combined=b)
          for n,a,b in zip(names,we,wc)],'spatial_weights')
    R,CC=len(lat),len(lon);ii=np.searchsorted(lat,df.lat);jj=np.searchsorted(lon,df.lon)
    Y=np.empty((R,CC));Y[ii,jj]=df.esi
    rows=[]
    for fac in ['barren','grass','precip','temp']:
        lab=np.digitize(df[fac],np.quantile(df[fac],[.25,.5,.75]));S=np.empty((R,CC),int);S[ii,jj]=lab
        qo=q(Y,S);null=[]
        for di in range(R):
            for dj in range(CC):
                if di==0 and dj==0:continue
                null.append(q(np.roll(Y,(di,dj),(0,1)),S))
        null=np.asarray(null)
        rows.append(dict(factor=fac,q=qo,n_strata=len(np.unique(lab)),n_nonidentity_shifts=len(null),
            reference_tail_fraction=(1+np.sum(null>=qo))/(1+len(null)),
            reference_q025=np.quantile(null,.025),reference_q50=np.median(null),reference_q975=np.quantile(null,.975),
            assumption='periodic boundary alignment reference; not an independently calibrated null'))
    save(rows,'shift_reference')
    # Fixed-distance diagnostic: enumerate unique offsets with wrapped distances.
    offsets=[]
    for di in range(R):
        for dj in range(CC):
            distance=np.hypot(min(di,R-di),min(dj,CC-dj)*np.cos(np.deg2rad(38.3)))
            if distance>=10:offsets.append(dict(di=di,dj=dj,wrapped_distance_cells=distance))
    save(offsets,'admissible_placebo_offsets')
    print('SPATIAL',rows,flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['all','forecast','bootstrap','spatial'],default='all')
    parser.add_argument('--bootstrap',type=int,default=2000);args=parser.parse_args()
    (W/'response_tests.json').write_text(json.dumps(test_response(),indent=2),encoding='utf-8')
    if args.stage in ['all','bootstrap']:bootstrap(args.bootstrap)
    elif args.stage=='forecast':forecast()
    if args.stage in ['all','spatial']:spatial();obstacle()

if __name__=='__main__':main()
