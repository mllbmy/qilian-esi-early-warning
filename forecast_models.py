"""Canonical grey response functions with consecutive observation/forecast indices.

The accumulated response A(t) uses t=0 for the first observation. Fitted levels
are A(t)-A(t-1), t=1,...,n-1; forecasts start at t=n. Gamma=1 is singular in the
Bernoulli formulation and is excluded from its selection grid.
"""
from __future__ import annotations
import numpy as np

GAMMA_GRID=np.round(np.arange(.05,1.96,.05),2)
GAMMA_GRID=GAMMA_GRID[~np.isclose(GAMMA_GRID,1.)]

def ngbm(x,gamma,n_pred=5):
    x=np.asarray(x,dtype=float)
    if len(x)<4 or not np.all(np.isfinite(x)) or np.any(x<=0):
        raise ValueError('NGBM requires at least four finite positive observations')
    g=float(gamma)
    if abs(g-1.)<1e-9:raise ValueError('gamma=1 is singular')
    z=.5*(np.cumsum(x)[1:]+np.cumsum(x)[:-1])
    a,b=np.linalg.lstsq(np.column_stack([-z,z**g]),x[1:],rcond=None)[0]
    if abs(a)<1e-12:raise ValueError('degenerate grey parameter')
    with np.errstate(over='raise',invalid='raise',divide='raise'):
        t=np.arange(len(x)+n_pred,dtype=float)
        base=(x[0]**(1-g)-b/a)*np.exp(-a*(1-g)*t)+b/a
        if np.any(base<=0):raise ValueError('nonpositive accumulated response')
        acc=base**(1/(1-g))
        restored=np.r_[x[0],np.diff(acc)]
    if not np.all(np.isfinite(restored)):raise ValueError('nonfinite grey response')
    return restored[len(x):],restored[:len(x)],(float(a),float(b),g)

def gm11(x,n_pred=5):
    future,fit,_=ngbm(x,0.,n_pred)
    return future,fit

def select_gamma(x):
    best=None
    for g in GAMMA_GRID:
        try:
            f,fit,_=ngbm(x,g,1)
        except (ValueError,FloatingPointError,OverflowError,np.linalg.LinAlgError):continue
        loss=float(np.sum((np.asarray(x)[1:]-fit[1:])**2))
        if best is None or loss<best[0]:best=(loss,float(g))
    if best is None:raise ValueError('no admissible NGBM fit')
    return best[1]

def grey_accuracy(x,fit):
    x=np.asarray(x);e=x-np.asarray(fit)
    s=x.std(ddof=0)
    return {'rmse':float(np.sqrt(np.mean(e**2))),'mae':float(np.mean(np.abs(e))),
            'C':float(e.std(ddof=0)/s),'P':float(np.mean(np.abs(e-e.mean())<.6745*s))}

def fit_forecast(x,model,n_pred=5):
    x=np.asarray(x,float)
    if model=='GM(1,1)':
        f,fit=gm11(x,n_pred);return f,fit,{'gamma':np.nan}
    if model=='NGBM':
        g=select_gamma(x);f,fit,_=ngbm(x,g,n_pred);return f,fit,{'gamma':g}
    if model=='ARIMA(0,1,1)':
        from statsmodels.tsa.arima.model import ARIMA
        result=ARIMA(x,order=(0,1,1)).fit(method_kwargs={'warn_convergence':False})
        fit=np.asarray(result.fittedvalues,float).copy()
        fit[0]=x[0]
        return np.asarray(result.forecast(n_pred),float),fit,{'gamma':np.nan,
            'converged':bool(result.mle_retvals.get('converged',True))}
    if model=='Naive':return np.repeat(x[-1],n_pred),np.r_[x[0],x[:-1]],{'gamma':np.nan}
    if model=='Drift':
        delta=(x[-1]-x[0])/(len(x)-1)
        return x[-1]+np.arange(1,n_pred+1)*delta,np.r_[x[0],x[:-1]+delta],{'gamma':np.nan}
    raise ValueError(model)
