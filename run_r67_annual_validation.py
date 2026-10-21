"""Annual observed-input reconstruction and training-window forecast evaluation.

The older reconstruction remains unchanged. This is a retrospective analysis of
a common released land-cover product, not historical real-time product access.
"""
from pathlib import Path
import argparse,json,os,warnings
import numpy as np,pandas as pd
from scipy.stats import pearsonr,spearmanr
import r28_core as C
from forecast_models import fit_forecast

P=Path(__file__).resolve().parent;D=P/'data';KEEP=C.DEREDUNDANT_SETS['drop_X9']
MODELS=['GM(1,1)','NGBM','ARIMA(0,1,1)','Naive','Drift']
MIX='Training-weighted mixture'
def fit_annual(x,model,horizon):
    if model!='ARIMA(0,1,1)':return fit_forecast(x,model,horizon)
    from statsmodels.tsa.arima.model import ARIMA
    result=ARIMA(np.asarray(x,float),order=(0,1,1)).fit(method_kwargs={'warn_convergence':False,'maxiter':1000})
    solver='lbfgs'
    if not result.mle_retvals.get('converged',True):
        retry=ARIMA(np.asarray(x,float),order=(0,1,1)).fit(method_kwargs={'warn_convergence':False,'maxiter':1000,'method':'powell'})
        if retry.mle_retvals.get('converged',False):result=retry;solver='powell'
    fitted=np.asarray(result.fittedvalues,float).copy();fitted[0]=x[0]
    return np.asarray(result.forecast(horizon),float),fitted,{'gamma':np.nan,'converged':bool(result.mle_retvals.get('converged',True)),'solver':solver}
def save(rows,name):
    frame=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    frame.to_csv(D/f'r67_{name}.csv',index=False,encoding='utf-8-sig',float_format='%.17g')
    return frame
def inputs():
    lc=pd.read_csv(D/'r67_annual_landcover.csv',float_precision='round_trip').set_index('year').sort_index()
    assert list(lc.index)==list(range(2004,2026))
    clim=pd.read_csv(D/'qilian_climate.csv',float_precision='round_trip')
    clim=clim[clim.unit=='区域(祁连山盒)'].set_index('year')[['precip_mm','temp_c']]
    cli2=pd.read_csv(D/'r56_climate.csv',float_precision='round_trip').set_index('year')
    cli=pd.concat([clim,cli2.loc[[2024,2025],['precip_mm','temp_c']]])
    years=np.arange(2005,2026);data=pd.DataFrame(index=years)
    data['X1_降水mm']=cli.loc[years,'precip_mm'];data['X2_气温C']=cli.loc[years,'temp_c']
    for key,col in [('X3_草地占比%','grass_pct'),('X4_森林占比%','forest_pct'),('X5_水域占比%','water_pct'),('X7_农田占比%','crop_pct')]:data[key]=lc.loc[years,col]
    data['X6_裸地荒漠%']=100-lc.loc[years,['grass_pct','forest_pct','water_pct','crop_pct']].sum(axis=1)
    data['X8_草地变化率']=lc.grass_pct.pct_change().loc[years]*100
    assert not data.isna().any().any()
    return data[KEEP]
def estimate(train):
    x=np.asarray(train,float);lo=x.min(axis=0);hi=x.max(axis=0);span=hi-lo
    assert np.all(span>1e-12),span
    z=(x-lo)/span;dirs=C.directions_for(KEEP);z[:,dirs<0]=1-z[:,dirs<0]
    ent=C.entropy_weights(z);ahp=C.ahp_weights_for(KEEP)
    weights=C.combined_weights(ahp,ent,.4)
    return {'lo':lo,'hi':hi,'weights':weights,'entropy':ent,'train_z':z,'train_esi':z@weights,'directions':dirs}
def transform(values,spec):
    z=(np.asarray(values,float)-spec['lo'])/(spec['hi']-spec['lo'])
    z[:,spec['directions']<0]=1-z[:,spec['directions']<0]
    return z
def mixture_weights(train):
    errors={m:[] for m in MODELS[:3]};nonconverged=0
    for n in range(6,len(train)):
        for m in errors:
            with warnings.catch_warnings(record=True):
                f,_,meta=fit_annual(train[:n],m,1)
            errors[m].append(float(f[0]-train[n]));nonconverged+=int(meta.get('converged',True) is False)
    assert all(errors[m] for m in errors)
    rmse=np.array([np.sqrt(np.mean(np.square(errors[m]))) for m in errors])
    inv=1/np.maximum(rmse,1e-12)
    return inv/inv.sum(),rmse,nonconverged
def forecast_at(data,origin,horizon):
    spec=estimate(data.loc[2005:origin]);train=spec['train_esi']
    predictions={};metadata={}
    for m in MODELS:
        with warnings.catch_warnings(record=True):
            f,_,meta=fit_annual(train,m,horizon)
        assert np.all(np.isfinite(f)),(m,origin)
        predictions[m]=f;metadata[m]=meta
    weights,basis,inner_nonconverged=mixture_weights(train)
    predictions[MIX]=sum(weights[i]*predictions[m] for i,m in enumerate(MODELS[:3]))
    metadata[MIX]={'converged':all(metadata[m].get('converged',True) for m in MODELS[:3])}
    return spec,predictions,metadata,weights,basis,inner_nonconverged

def same_release_five_epoch(data):
    """Build a five-epoch interpolation from the annual CLCD v1.0.5 release.

    The same 2004 v1.0.5 grassland observation initializes the 2005 rate in both
    this control and the complete annual series, isolating temporal sampling.
    """
    lc=pd.read_csv(D/'r67_annual_landcover.csv',float_precision='round_trip').set_index('year').sort_index()
    anchors=[2005,2010,2015,2020,2023]
    cols=['grass_pct','forest_pct','water_pct','crop_pct']
    lc5=lc.loc[anchors,cols].reindex(range(2005,2024)).interpolate(method='linear')
    control=data.loc[2005:2023].copy()
    control['X3_草地占比%']=lc5.grass_pct
    control['X4_森林占比%']=lc5.forest_pct
    control['X5_水域占比%']=lc5.water_pct
    control['X6_裸地荒漠%']=100-lc5[cols].sum(axis=1)
    control['X7_农田占比%']=lc5.crop_pct
    grass=pd.concat([lc.loc[[2004],'grass_pct'],lc5.grass_pct])
    control['X8_草地变化率']=grass.pct_change().loc[2005:2023]*100
    assert len(control)==19 and not control.isna().any().any()
    return control[KEEP]

def compare_indices(name,a,b,years):
    a=np.asarray(a,float);b=np.asarray(b,float);years=np.asarray(years,int)
    ga=np.digitize(a,[.2,.4,.6,.8]);gb=np.digitize(b,[.2,.4,.6,.8])
    return {'contrast':name,'n_years':len(years),'changed_grades':int((ga!=gb).sum()),
            'peak_year_a':int(years[a.argmax()]),'peak_year_b':int(years[b.argmax()]),
            'max_abs_difference':float(np.max(np.abs(a-b))),
            'pearson_r':float(np.corrcoef(a,b)[0,1]),
            'rmse':float(np.sqrt(np.mean((a-b)**2)))}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=Path,default=Path(os.environ.get('QILIAN_WORK','work')))
    a=ap.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    data=inputs();save(data.rename_axis('year').reset_index(),'annual_inputs')
    hist=data.loc[2005:2023];spec=estimate(hist)
    zero=hist.copy();zero.loc[2005,'X8_草地变化率']=0;sz=estimate(zero)
    freq= same_release_five_epoch(data)
    sf=estimate(freq)
    # For the product-release bridge, match the historical series' zero initial
    # rate convention so that the contrast does not include a first-year change.
    freq_zero=freq.copy();freq_zero.loc[2005,'X8_草地变化率']=0
    sf_zero=estimate(freq_zero)
    original=pd.read_csv(D/'r47_primary_series.csv').set_index('year')
    series=pd.DataFrame({'year':hist.index,'annual_esi':spec['train_esi'],'first_year_zero_esi':sz['train_esi'],
                         'same_release_5epoch_esi':sf['train_esi'],
                         'same_release_5epoch_zero_esi':sf_zero['train_esi'],
                         'reconstructed_esi':original.loc[hist.index,'esi'].values})
    for c in ['annual_esi','first_year_zero_esi','same_release_5epoch_esi','same_release_5epoch_zero_esi','reconstructed_esi']:
        series[c+'_grade']=np.digitize(series[c],[.2,.4,.6,.8])
    save(series,'annual_series')
    frequency_rows=[
        compare_indices('Legacy five-epoch vs annual v1.0.5 (combined contrast)',
                        series.reconstructed_esi,series.annual_esi,series.year),
        compare_indices('Five-epoch vs annual, both CLCD v1.0.5 (sampling contrast)',
                        series.same_release_5epoch_esi,series.annual_esi,series.year),
        compare_indices('Legacy vs five-epoch CLCD v1.0.5 (release bridge; first rate zero)',
                        series.reconstructed_esi,series.same_release_5epoch_zero_esi,series.year)]
    frequency=save(frequency_rows,'frequency_control_summary')
    save([{'indicator':k,'entropy':spec['entropy'][i],'subjective':C.ahp_weights_for(KEEP)[i],
           'combined':spec['weights'][i],'min':spec['lo'][i],'max':spec['hi'][i]} for i,k in enumerate(KEEP)],'annual_weights')
    frozen=pd.read_csv(D/'r47_primary_weights.csv').set_index('indicator').loc[KEEP,'combined'].values
    oldraw=C.build_indicators()[KEEP].values;oldlo=oldraw.min(axis=0);oldhi=oldraw.max(axis=0)
    z=(data.values-oldlo)/(oldhi-oldlo);z[:,C.directions_for(KEEP)<0]=1-z[:,C.directions_for(KEEP)<0]
    frozen_series=pd.DataFrame({'year':data.index,'affine_esi':z@frozen,'clipped_esi':np.clip(z,0,1)@frozen})
    save(frozen_series,'annual_on_historical_scale')
    # Sensitivity: hold the historical normalization bounds and weights fixed so
    # that only the land-cover observation sequence/interpolation changes.
    directions=C.directions_for(KEEP)
    def fixed_scale_score(frame):
        values=frame.loc[2005:2023].to_numpy(float)
        normalized=(values-oldlo)/(oldhi-oldlo)
        normalized[:,directions<0]=1-normalized[:,directions<0]
        return normalized@frozen
    annual_fixed=fixed_scale_score(data)
    five_epoch_fixed=fixed_scale_score(freq)
    fixed_series=pd.DataFrame({'year':hist.index,'annual_fixed_esi':annual_fixed,
                               'same_release_5epoch_fixed_esi':five_epoch_fixed})
    for column in ['annual_fixed_esi','same_release_5epoch_fixed_esi']:
        fixed_series[column+'_grade']=np.digitize(fixed_series[column],[.2,.4,.6,.8])
    save(fixed_series,'frequency_fixed_scale_series')
    fixed_summary=compare_indices('Five-epoch vs annual CLCD v1.0.5 (fixed historical bounds and weights)',
                                  five_epoch_fixed,annual_fixed,hist.index)
    save([fixed_summary],'frequency_fixed_scale_summary')
    associations=[]
    for filename,column,mask in [('r28_external_ndvi_annual.csv','ndvi_growing_season_mean','all_clear'),
                                 ('r28_external_ndvi_annual_commonmask.csv','ndvi_commonmask_mean','common_mask')]:
        ndvi=pd.read_csv(D/filename).set_index('year')[column]
        for index in ['annual_esi','first_year_zero_esi','reconstructed_esi']:
            frame=series.set_index('year')[[index]].join(ndvi).dropna()
            for mode in ['levels','first_differences','differences_excluding_2014']:
                use=frame if mode=='levels' else frame.diff().dropna()
                if mode=='differences_excluding_2014':use=use[use.index!=2014]
                x,y=use.iloc[:,0],use.iloc[:,1]
                associations.append({'index':index,'mask':mask,'comparison':mode,'n_years_or_differences':len(use),
                                     'pearson_r':float(pearsonr(x,y).statistic),'spearman_rho':float(spearmanr(x,y).statistic)})
    save(associations,'NDVI_associations')
    details=[];weightrows=[];fits=[];origins=range(2013,2025)
    for origin in origins:
        horizon=5 if origin<=2020 else 1
        s,pred,meta,weights,basis,inner_nonconverged=forecast_at(data,origin,horizon)
        for j,k in enumerate(KEEP):weightrows.append({'origin':origin,'indicator':k,'train_min':s['lo'][j],
            'train_max':s['hi'][j],'entropy':s['entropy'][j],'combined':s['weights'][j]})
        for i,m in enumerate(MODELS[:3]):fits.append({'origin':origin,'model':m,'mixture_weight':weights[i],
            'training_one_step_rmse':basis[i],'n_inner_origins':len(s['train_esi'])-6,
            'inner_ARIMA_nonconverged_fits':inner_nonconverged})
        future=data.loc[origin+1:origin+horizon];zt=transform(future,s)
        # Use one outer fit per origin for both one-step and five-step evaluation.
        for scheme,H in [('rolling1',1)]+([('rolling5',5)] if origin<=2020 else []):
            for h in range(1,H+1):
                for target,zo in [('affine',zt[h-1]),('input_clipped',np.clip(zt[h-1],0,1))]:
                    observed=float(zo@s['weights'])
                    for m in pred:
                        predicted=float(pred[m][h-1])
                        details.append({'scheme':scheme,'origin':origin,'horizon':h,'target_year':origin+h,'model':m,
                            'target_scaling':target,'observed':observed,'predicted':predicted,'error':predicted-observed,
                            'n_outside_inputs':int(((zt[h-1]<0)|(zt[h-1]>1)).sum()),
                            'observed_grade':int(np.digitize(observed,[.2,.4,.6,.8])) if 0<=observed<=1 else np.nan,
                            'predicted_grade':int(np.digitize(predicted,[.2,.4,.6,.8])) if 0<=predicted<=1 else np.nan,
                            'gamma':meta.get(m,{}).get('gamma',np.nan),'converged':meta.get(m,{}).get('converged',True)})
        print('FORECAST_ORIGIN',origin,flush=True)
    detail=save(details,'forecast_detail');save(weightrows,'origin_weights');save(fits,'mixture_training')
    summary=[]
    for (scheme,target,m),g in detail.groupby(['scheme','target_scaling','model'],sort=False):
        eligible=g.observed_grade.notna()&g.predicted_grade.notna()
        summary.append({'scheme':scheme,'target_scaling':target,'model':m,'n_origins':g.origin.nunique(),
            'n_target_records':len(g),'n_distinct_target_years':g.target_year.nunique(),
            'rmse':float(np.sqrt(np.mean(g.error**2))),'mae':float(np.abs(g.error).mean()),
            'grade_eligible_records':int(eligible.sum()),'grade_matches':int((g.loc[eligible,'observed_grade']==g.loc[eligible,'predicted_grade']).sum()),
            'nonconverged_predictions':int((~g.converged.astype(bool)).sum())})
    sm=save(summary,'forecast_summary')
    changed=int((series.annual_esi_grade!=series.reconstructed_esi_grade).sum())
    summary_values=[{'metric':'changed_grades_vs_reconstruction','value':changed},
                    {'metric':'annual_peak_year','value':int(series.loc[series.annual_esi.idxmax(),'year'])},
                    {'metric':'annual_2023','value':float(series.loc[series.year==2023,'annual_esi'].iloc[0])},
                    {'metric':'max_abs_annual_vs_reconstructed','value':float(np.abs(series.annual_esi-series.reconstructed_esi).max())},
                    {'metric':'annual_reconstructed_Pearson_r','value':float(pearsonr(series.annual_esi,series.reconstructed_esi).statistic)}]
    save(summary_values,'comparison_summary')
    checks=[]
    def check(name,passed):checks.append({'check':name,'passed':bool(passed)});assert passed,name
    check('annual_inputs_21_years_no_missing',len(data)==21 and not data.isna().any().any())
    check('descriptive_19_years',len(series)==19)
    check('same_release_five_epoch_control_19_years',len(freq)==19 and list(freq.index)==list(range(2005,2024)))
    check('same_release_control_preserves_five_anchors',all(np.allclose(freq.loc[y,['X3_草地占比%','X4_森林占比%','X5_水域占比%','X7_农田占比%']].to_numpy(float),
        hist.loc[y,['X3_草地占比%','X4_森林占比%','X5_水域占比%','X7_农田占比%']].to_numpy(float),rtol=0,atol=1e-12) for y in [2005,2010,2015,2020,2023]))
    check('sampling_control_changes_11_grades',int(frequency.loc[frequency.contrast.str.contains('sampling contrast'),'changed_grades'].iloc[0])==11)
    check('release_bridge_changes_one_grade',int(frequency.loc[frequency.contrast.str.contains('release bridge'),'changed_grades'].iloc[0])==1)
    check('fixed_scale_sampling_control_changes_seven_grades',fixed_summary['changed_grades']==7)
    check('fixed_scale_peaks_2010_to_2009',fixed_summary['peak_year_a']==2010 and fixed_summary['peak_year_b']==2009)
    check('origin_weights_sum_one',np.allclose(pd.DataFrame(weightrows).groupby('origin').combined.sum(),1))
    check('mixture_training_weights_sum_one',np.allclose(pd.DataFrame(fits).groupby('origin').mixture_weight.sum(),1))
    check('rolling1_has_12_origins',all(sm.loc[sm.scheme=='rolling1','n_origins']==12))
    check('rolling5_has_8_origins_and_40_records',all(sm.loc[sm.scheme=='rolling5','n_origins']==8) and all(sm.loc[sm.scheme=='rolling5','n_target_records']==40))
    changed_data=data.copy();changed_data.loc[2016:]=changed_data.loc[2016:]*10+100
    sa,pa,ma,wa,ba,ia=forecast_at(data,2015,5);sb,pb,mb,wb,bb,ib=forecast_at(changed_data,2015,5)
    check('future_perturbation_all_forecasts_exact',all(np.array_equal(pa[m],pb[m]) for m in pa))
    check('future_perturbation_all_training_weights_exact',np.array_equal(sa['weights'],sb['weights']) and np.array_equal(wa,wb))
    check('future_perturbation_training_ranges_exact',np.array_equal(sa['lo'],sb['lo']) and np.array_equal(sa['hi'],sb['hi']))
    expected=pd.read_csv(D/'r56_observed_series.csv').set_index('year')
    got=frozen_series.set_index('year')
    check('annual_2024_2025_same_release_bridge_reproduced',np.allclose(got.loc[[2024,2025],'affine_esi'],expected.loc[[2024,2025],'same_release_esi'],atol=1e-10,rtol=0))
    check('annual_2024_2025_clipping_reproduced',np.allclose(got.loc[[2024,2025],'clipped_esi'],expected.loc[[2024,2025],'clipped_esi'],atol=1e-10,rtol=0))
    save(checks,'analysis_checks')
    print(sm[['scheme','target_scaling','model','rmse','mae']].to_string(index=False),flush=True)
    print('SUMMARY',summary_values,'CHECKS',len(checks),'PASS',flush=True)
if __name__=='__main__':main()
