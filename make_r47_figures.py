"""Current 2.2 figures from r47 results; previews are confined to QILIAN_WORK."""
from pathlib import Path
import os
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import jms_style as J
from current_release import PACKAGE as P,WORK as W

D=P/'data';F=P/'figures';PRE=W/'figure_previews';PRE.mkdir(parents=True,exist_ok=True)
def read(n):return pd.read_csv(D/n,encoding='utf-8-sig')
def save(fig,name):
    fig.savefig(F/(name+'.pdf'),dpi=300)
    fig.savefig(PRE/(name+'.png'),dpi=170)
    plt.close(fig)

def forecast():
    hist=read('r28_deredundancy_series.csv');fc=read('r47_forecast.csv');bt=read('r47_bootstrap.csv')
    fig,ax=J.subplots(height_cm=10.6,layout='constrained')
    for lo,hi,c in [(0,.2,'#b2182b'),(.2,.4,'#e07b39'),(.4,.6,'#f4d03f'),(.6,.8,'#7dcea0'),(.8,1,'#1b7837')]:
        ax.axhspan(lo,hi,color=c,alpha=.055,zorder=0)
    for y in [.2,.4,.6,.8]:ax.axhline(y,color='#b7bdc4',lw=.5,ls=(0,(3,3)),zorder=0)
    ax.plot(hist.year,hist.esi_drop_X9,'-o',color='#2166ac',ms=3,lw=1.5,label='Reconstructed ESI')
    z=bt[bt.model=='Mixture'];ax.fill_between(z.year,z.lo,z.hi,color='#687581',alpha=.18,label='Mixture bootstrap envelope',linewidth=0)
    for m,c,mark,style in [('GM(1,1)','#238c91','s','--'),('NGBM','#d57a35','^','-.'),('ARIMA(0,1,1)','#7561a8','v',':'),('Mixture','#202020','o','--')]:
        g=fc[fc.model==m];ax.plot(g.year,g.value,linestyle=style,marker=mark,color=c,ms=3,
            lw=1.5 if m=='Mixture' else 1.1,label=m,zorder=4 if m=='Mixture' else 3)
    ax.axvline(2023.5,color='#555555',lw=.8,ls='--');ax.set(xlim=(2004,2029),ylim=(0,1),
        xlabel='Year',ylabel='Ecological security index')
    ax.set_xticks([2005,2010,2015,2020,2024,2028]);ax.legend(loc='upper left',ncol=2,frameon=False,fontsize=8,
        handlelength=2.5,columnspacing=1.5,labelspacing=.45)
    ax.text(2026,.85,'2023-origin forecasts',ha='center',va='center',fontsize=8,color='#4a5056')
    ax.spines[['top','right']].set_visible(False)
    save(fig,'fig3_esi_timeseries')

def spatial():
    pts=read('spatial_samples.csv').merge(read('spatial_esi_points.csv'),on=['lat','lon'])
    lat=np.sort(pts.lat.unique());lon=np.sort(pts.lon.unique())
    rings=[]
    gj=json.loads((D/'qmn_park_digitized.geojson').read_text(encoding='utf-8'))
    for item in gj['features']:
        g=item['geometry'];polys=g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]
        rings.extend(np.asarray(poly[0]) for poly in polys)
    fig,axes=J.subplots(height_cm=15.0,nrows=3,ncols=2,layout='constrained')
    for ax,field,title,cmap,binary in zip(axes.flat,['precip','temp','grass','forest','barren','esi'],
            ['(a) Precipitation (mm/year)','(b) Temperature (degrees C)',
             '(c) Grassland dominant class','(d) Forest dominant class',
             '(e) CLCD barren dominant class','(f) Six-indicator point index'],
             ['Blues','coolwarm','Greens','Greens','YlOrBr','viridis'],[False,False,True,True,True,False]):
        matrix=pts.pivot(index='lat',columns='lon',values=field).reindex(index=lat,columns=lon).values
        im=ax.pcolormesh(lon,lat,matrix,shading='nearest',cmap=cmap,vmin=0 if binary else None,vmax=1 if binary else None)
        for ring in rings:ax.plot(ring[:,0],ring[:,1],color='#c53a32',lw=.45,ls='--')
        cb=fig.colorbar(im,ax=ax,shrink=.88,pad=.02)
        if binary:cb.set_ticks([0,1]);cb.set_ticklabels(['0','1'])
        cb.ax.tick_params(labelsize=8);ax.set_title(title,fontsize=8.5)
        ax.set(xlim=(93.5,103.5),ylim=(36,40.5));ax.set_xticks([94,98,102]);ax.set_yticks([36,38,40])
    for ax in axes[-1,:]:ax.set_xlabel('Longitude (degrees E)',fontsize=8)
    for ax in axes[:,0]:ax.set_ylabel('Latitude (degrees N)',fontsize=8)
    save(fig,'fig_spatial_maps')

def factor():
    fig,axes=J.subplots(height_cm=9.5,nrows=2,ncols=1,layout='constrained')
    for ax,title,names,values in [(axes[0],'(a) Factors overlapping index inputs',
        ['Barren/degraded','Grassland','Precipitation','Temperature'],'primary'),
        (axes[1],'(b) Climate and terrain factors',['Precipitation','Temperature','Elevation','Slope'],None)]:
        if values is None:
            ex=read('results_geodetector_exogenous.csv')
            # Terrain values are taken from their archived source table.
            factors=['precip','temp','elev','slope']
            values=[float(ex.loc[ex.factor==f,'q'].iloc[0]) for f in factors]
        else:
            rr=read('r47_shift_reference.csv').set_index('factor')
            values=[float(rr.loc[f,'q']) for f in ['barren','grass','precip','temp']]
        y=np.arange(len(names));ax.hlines(y,0,values,color='#a9c4d3',lw=2);ax.plot(values,y,'o',color='#2166ac',ms=4)
        for yy,v in zip(y,values):ax.text(v+.022,yy,f'{v:.3f}',va='center',fontsize=8,color='#30363b')
        ax.set_yticks(y);ax.set_yticklabels(names);ax.set_ylim(len(names)-.55,-.45);ax.set_xlim(0,1)
        ax.set_title(title,fontsize=9,loc='left',pad=7);ax.grid(axis='x',color='#dce2e8',lw=.5,alpha=.7)
        ax.spines[['top','right']].set_visible(False);ax.tick_params(axis='y',length=0,pad=6)
        ax.set_axisbelow(True)
    axes[-1].set_xlabel('q statistic');save(fig,'fig_geodetector_q')

def obstacle():
    annual=read('r47_obstacle_annual.csv');phase=read('r47_obstacle_phase.csv')
    en={'X1_降水mm':'Precipitation','X2_气温C':'Temperature','X3_草地占比%':'Grassland',
        'X4_森林占比%':'Forest','X5_水域占比%':'Water','X6_裸地荒漠%':'Barren/degraded',
        'X7_农田占比%':'Cropland','X8_草地变化率':'Grassland change rate'}
    colors=['#1f6f9f','#74b7c9','#14532d','#2e8b57','#52b788','#a52633','#df4866','#b06c1f']
    fig,axes=J.subplots(height_cm=13.2,nrows=2,ncols=1,gridspec_kw={'height_ratios':[1.6,1]})
    fig.subplots_adjust(left=.125,right=.98,bottom=.075,top=.88,hspace=.43)
    a=annual[annual.scheme=='Combined'];ax=axes[0]
    styles=['-','--','-','--',':','-.','-','-']
    for (name,label),c,style in zip(en.items(),colors,styles):
        z=a[a.indicator==name];ax.plot(z.year,z.value,lw=1.35 if name=='X8_草地变化率' else 1.1,
            linestyle=style,color=c,label=label)
    ax.axvline(2010.5,color='#555555',lw=.7,ls='--');ax.set(xlabel='Year',ylabel='Normalized obstacle degree',ylim=(0,.55))
    ax.set_xticks([2005,2010,2015,2020,2023])
    ax.set_title('(a) Primary eight-indicator combined weights',fontsize=9)
    handles,labels=ax.get_legend_handles_labels()
    fig.legend(handles,labels,fontsize=8,ncol=4,loc='upper center',bbox_to_anchor=(.53,.995),
        frameon=False,columnspacing=.8,handlelength=1.9,handletextpad=.5,labelspacing=.55)
    ax=axes[1];names=['X8_草地变化率','X7_农田占比%','X5_水域占比%']
    x=np.arange(4);schemes=['Combined','Entropy','AHP','Equal']
    for j,name in enumerate(names):
        vals=[float(phase[(phase.phase=='2011-2023')&(phase.scheme==sc)&(phase.indicator==name)].value.iloc[0]) for sc in schemes]
        ax.bar(x+(j-1)*.23,vals,width=.23,label=en[name],color=dict(zip(en,colors))[name])
    ax.set_xticks(x);ax.set_xticklabels(schemes);ax.set_ylabel('Phase-mean degree')
    ax.set_title('(b) Weight sensitivity, 2011-2023',fontsize=9);ax.set_ylim(0,.5)
    for ax in axes:
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',color='#dde3e9',lw=.5,alpha=.65);ax.set_axisbelow(True)
    save(fig,'fig_obstacle')

if __name__=='__main__':
    forecast();spatial();factor();obstacle()
    import runpy
    runpy.run_path(str(P/'make_fig2_redesign.py'),run_name='__main__')
    print('Updated figures 2, 4, 7, 8 and 10; PNG previews:',PRE)
