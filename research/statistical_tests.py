"""Replicate the SOFR integration, cointegration, stability and adjustment tests.

Run: python research/statistical_tests.py from the repository root.
See README.md for setup, stage selection, inputs and interpretation.
Statistical functions retain the methods used in the earlier analysis.
No workbooks are modified. Outputs are newly fitted JSON and CSV files.
"""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import platform
import time
import warnings
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import openpyxl
import scipy.stats as st
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, kpss, zivot_andrews
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.ardl import UECM
from statsmodels.tsa.tsatools import add_trend
from statsmodels.tsa.vector_ar.var_model import VAR
from statsmodels.tsa.vector_ar.vecm import coint_johansen, select_order, select_coint_rank
from arch.unitroot import PhillipsPerron
from arch.unitroot.cointegration import engle_granger, phillips_ouliaris, DynamicOLS, FullyModifiedOLS

ROOT = Path(__file__).resolve().parent
WORK = ROOT/"results"/"raw"
OUT = ROOT/"results"/"tables"
FAMILIES = ["GBP2Y", "GBP5Y", "EUR2Y", "EUR5Y"]
COLS = ["Spread", "MOVE"] + FAMILIES
PERIODS = {
    "Full": ("2021-02-19", "2026-09-04"),
    "R1 first": ("2021-02-22", "2022-02-22"),
    "R1 final": ("2025-09-03", "2026-09-03"),
    "R2 first": ("2021-02-21", "2023-02-21"),
    "R2 final": ("2024-09-03", "2026-09-03"),
    "R3 first": ("2021-02-21", "2024-02-21"),
    "R3 final": ("2023-09-03", "2026-09-03"),
}

def jsonable(value):
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, (Path, pd.Timestamp)): return str(value)
    raise TypeError(type(value).__name__)

def save(name, value):
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (WORK/(name+".json")).write_text(json.dumps(value, indent=2, default=jsonable, allow_nan=False), encoding="utf-8")
    if isinstance(value,list) and value and isinstance(value[0],dict):
        fields=list(dict.fromkeys(key for r in value for key in r))
        with (OUT/(name+".csv")).open("w",newline="",encoding="utf-8-sig") as f:
            writer=csv.DictWriter(f,fieldnames=fields)
            writer.writeheader()
            writer.writerows([{k:json.dumps(v,default=jsonable) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in value])

def load_data(path):
    """Read the bundled observations, or sheet SOFR in the original raw workbook."""
    if path.suffix.lower() == ".csv":
        data=pd.read_csv(path,parse_dates=["Date"],float_precision="round_trip").set_index("Date")[COLS]
    elif path.suffix.lower() == ".xlsx":
        book=openpyxl.load_workbook(path,read_only=True,data_only=True)
        records=[]
        try:
            rows=book["SOFR"].iter_rows(values_only=True)
            headers=next(rows)
            names=['10yr swap spreads','Move','2yr_Basis_GBP_SOFR','5yr_Basis_GBP_SOFR','2yr_Basis_EU_SOFR','5yr_Basis_EU_SOFR']
            for name in names:
                if headers.count(name)!=1:
                    raise ValueError(f"Expected one {name!r} source column.")
            positions=[headers.index(name) for name in names]
            for row in rows:
                if isinstance(row[0],datetime):
                    records.append([row[0]]+[float(row[i]) if isinstance(row[i],(int,float)) and np.isfinite(row[i]) else np.nan for i in positions])
        finally:
            book.close()
        data=pd.DataFrame(records,columns=["Date"]+COLS).set_index("Date")
    else:
        raise ValueError("Input must be the observations CSV or the raw .xlsx workbook containing sheet SOFR.")
    data=data.sort_index()
    if not data.index.is_unique: raise ValueError("Duplicate observation dates.")
    if data.empty: raise ValueError("No observations read.")
    return data


def sample(data, period, cols):
    start,end = PERIODS[period]
    return data.loc[(data.index >= start) & (data.index < end),cols].dropna()

def integration(data):
    units=[]
    for period in PERIODS:
        for col in COLS:
            a=sample(data,period,[col])[col].to_numpy()
            for transform in ['level','difference']:
                x=a if transform=='level' else np.diff(a)
                for trend in (['c','ct'] if period=='Full' and transform=='level' else ['c']):
                    for selector in ['AIC','BIC']:
                        res=adfuller(x,maxlag=20,regression=trend,autolag=selector)
                        units.append(dict(period=period,series=col,transform=transform,test='ADF',trend=trend,selector=selector,n=len(x),stat=float(res[0]),p=float(res[1]),lag=int(res[2])))
                    res=kpss(x,regression=trend,nlags='auto')
                    units.append(dict(period=period,series=col,transform=transform,test='KPSS',trend=trend,selector='auto',n=len(x),stat=float(res[0]),p=float(res[1]),lag=int(res[2]),p_censored=res[1] in [.01,.1]))
                    res=PhillipsPerron(x,trend=trend)
                    units.append(dict(period=period,series=col,transform=transform,test='PP',trend=trend,selector='auto',n=len(x),stat=float(res.stat),p=float(res.pvalue),lag=int(res.lags)))
            if period=='Full':
                res=zivot_andrews(a,maxlag=20,regression='ct',autolag='AIC')
                dates=sample(data,period,[col]).index
                units.append(dict(period=period,series=col,transform='level',test='Zivot-Andrews',trend='ct',selector='AIC',n=len(a),stat=float(res[0]),p=float(res[1]),lag=int(res[3]),break_date=str(dates[res[4]].date())))
        print('Integration complete:',period,flush=True)
    save('integration',units)
    tests=[]
    for period in PERIODS:
        for family in FAMILIES:
            for spec in ['pair','with MOVE']:
                cols=['Spread',family] + (['MOVE'] if spec=='with MOVE' else [])
                sub=sample(data,period,cols)
                for trend in (['c','ct'] if period=='Full' else ['c']):
                    for selector in ['aic','bic']:
                        res=engle_granger(sub.Spread,sub[cols[1:]],trend=trend,max_lags=20,method=selector)
                        tests.append(dict(period=period,family=family,spec=spec,test='Engle-Granger',trend=trend,selector=selector,n=len(sub),stat=float(res.stat),p=float(res.pvalue),lag=int(res.lags)))
                    res=phillips_ouliaris(sub.Spread,sub[cols[1:]],trend=trend,test_type='Zt',kernel='bartlett',force_int=True)
                    tests.append(dict(period=period,family=family,spec=spec,test='Phillips-Ouliaris Zt',trend=trend,selector='auto bandwidth',n=len(sub),stat=float(res.stat),p=float(res.pvalue),bandwidth=float(res.bandwidth)))
        print('Cointegration complete:',period,flush=True)
    for period in PERIODS:
        for spec in ['pair','with MOVE']:
            ix=[i for i,r in enumerate(tests) if r['period']==period and r['spec']==spec and r['test']=='Engle-Granger' and r['trend']=='c' and r['selector']=='aic']
            adjusted=multipletests([tests[i]['p'] for i in ix],method='holm')[1]
            for i,p in zip(ix,adjusted): tests[i]['holm_p_4_families']=float(p)
    save('cointegration',tests)
    print(pd.DataFrame(units).query("period=='Full' and transform=='level' and trend=='c'")[['series','test','selector','stat','p','lag']].to_string(index=False),flush=True)
    print(pd.DataFrame(tests).query("period=='Full' and trend=='c'")[['family','spec','test','selector','stat','p']].to_string(index=False),flush=True)

def hac(X,u,L):
    inv=np.linalg.inv(X.T@X)
    scores=X*u[:,None]
    meat=scores.T@scores
    for j in range(1,L+1):
        term=scores[j:].T@scores[:-j]
        meat+=(1-j/(L+1))*(term+term.T)
    return inv@meat@inv * len(u)/(len(u)-X.shape[1])

def rolling(data):
    rows=[]; summaries=[]; comparisons=[]
    invbook=json.loads((WORK/'workbook_context.json').read_text(encoding='utf-8'))[0]
    for family in FAMILIES:
        sub=data[['Spread',family,'MOVE']].dropna()
        dates=sub.index
        for years,start in [(1,'2022-02-22'),(2,'2023-02-21'),(3,'2024-02-21')]:
            model_rows=[]
            for dt in dates[dates>=start]:
                training=sub.loc[(dates>=dt-pd.DateOffset(years=years))&(dates<dt)]
                y=training.Spread.to_numpy(); X=sm.add_constant(training[[family,'MOVE']].to_numpy())
                beta=np.linalg.lstsq(X,y,rcond=None)[0]; u=y-X@beta
                L=int(np.floor(4*(len(y)/100)**(2/9)))
                se=np.sqrt(hac(X,u,L)[1,1]); crit=st.t.ppf(.975,len(y)-3)
                current=sub.loc[dt]
                r=dict(family=family,R=years,date=str(dt.date()),n=len(y),intercept=float(beta[0]),beta=float(beta[1]),move_beta=float(beta[2]),hac_se=float(se),lower=float(beta[1]-crit*se),upper=float(beta[1]+crit*se),residual_se=float(np.sqrt(u@u/(len(y)-3))),z=float((current.Spread-beta@np.array([1,current[family],current.MOVE]))/np.sqrt(u@u/(len(y)-3))))
                rows.append(r); model_rows.append(r)
            vals=np.array([r['beta'] for r in model_rows])
            summaries.append(dict(family=family,R=years,fits=len(vals),first_beta=float(vals[0]),last_beta=float(vals[-1]),min_beta=float(vals.min()),max_beta=float(vals.max()),positive_share=float(np.mean(vals>0)),sign_changes=int(np.sum(np.sign(vals[1:])!=np.sign(vals[:-1]))),negative_ci_share=float(np.mean([r['upper']<0 for r in model_rows])),positive_ci_share=float(np.mean([r['lower']>0 for r in model_rows]))))
            cells=dict(sum(next(s for s in invbook['sheets'] if s['name']==family+' Regressions')['all_rows'],[]))
            for last,rr in [(False,8+(years-1)*50),(True,33+(years-1)*50)]:
                r=model_rows[-1 if last else 0]
                comparisons.append(abs(r['beta']-cells['G'+str(rr)]))
                comparisons.append(abs(r['hac_se']-cells['H'+str(rr)]))
            print('Rolling complete:',family,'R'+str(years),flush=True)
    assert max(comparisons)<1e-8
    save('rolling',rows);save('rolling_summary',summaries)
    save('rolling_checks',dict(max_endpoint_coefficient_or_HAC_SE_difference=max(comparisons),fits=len(rows)))
    print(pd.DataFrame(summaries).to_string(index=False),flush=True)

def adjustment(data):
    estimates=[]; bounds=[]; ecms=[]
    for period in ['Full','R1 final','R2 final','R3 final']:
        for family in FAMILIES:
            sub=sample(data,period,['Spread',family,'MOVE'])
            for spec in ['pair','with MOVE']:
                xs=[family]+(['MOVE'] if spec=='with MOVE' else [])
                X=sub[xs]
                ols=sm.OLS(sub.Spread,sm.add_constant(X)).fit(cov_type='HAC',cov_kwds={'maxlags':20,'use_correction':True})
                estimates.append(dict(period=period,family=family,spec=spec,method='OLS HAC20',beta=float(ols.params[family]),se=float(ols.bse[family]),n=len(sub)))
                for lag in [2,5]:
                    fit=DynamicOLS(sub.Spread,X,trend='c',lags=lag,leads=lag).fit(cov_type='kernel',kernel='bartlett',bandwidth=20,df_adjust=True)
                    estimates.append(dict(period=period,family=family,spec=spec,method='DOLS'+str(lag)+' HAC20',beta=float(fit.params[family]),se=float(fit.std_errors[family]),n=len(fit.resid)))
                fit=FullyModifiedOLS(sub.Spread,X,trend='c').fit(kernel='bartlett',bandwidth=None,df_adjust=True)
                estimates.append(dict(period=period,family=family,spec=spec,method='FMOLS auto Bartlett',beta=float(fit.params[family]),se=float(fit.std_errors[family]),n=len(fit.resid)))
            # Mixed I(0)/I(1) conditional levels model, contiguous lags chosen by BIC on a common holdback.
            best=None
            for p in range(1,6):
                for q in range(1,6):
                    for m in range(1,6):
                        model=UECM(sub.Spread,lags=p,exog=sub[[family,'MOVE']],order={family:q,'MOVE':m},trend='c',hold_back=5)
                        fit=model.fit()
                        if best is None or fit.bic<best[0]:best=(float(fit.bic),fit,(p,q,m))
            fit=best[1];bt=fit.bounds_test(case=3,asymptotic=True)
            robust=fit.model.fit(cov_type='HAC',cov_kwds={'maxlags':10,'use_correction':True})
            lam=float(fit.params['Spread.L1']); bcoef=float(fit.params[family+'.L1']);mcoef=float(fit.params['MOVE.L1'])
            bounds.append(dict(period=period,family=family,n=int(fit.nobs),orders=list(best[2]),F=float(bt.statistic),p_I0=float(bt.pvalue['lower']),p_I1=float(bt.pvalue['upper']),critical5_I0=float(bt.critical_values.loc[95.0,'lower']),critical5_I1=float(bt.critical_values.loc[95.0,'upper']),lambda_spread=lam,lambda_HAC10_se=float(robust.bse['Spread.L1']),lambda_HAC10_p_descriptive=float(robust.pvalues['Spread.L1']),implied_basis_beta=-bcoef/lam,implied_move_beta=-mcoef/lam,ljungbox20_p=float(acorr_ljungbox(fit.resid,lags=[20],return_df=True).lb_pvalue.iloc[0])))
            # Two-equation adjustment diagnostic using one fixed, within-period fitted residual.
            ols0=sm.OLS(sub.Spread,sm.add_constant(sub[[family,'MOVE']])).fit()
            e=ols0.resid.to_numpy(); levels=sub.to_numpy();d=np.diff(levels,axis=0)
            chosen=None
            for p in range(0,6):
                ids=np.arange(p,len(d))
                design=np.column_stack([np.ones(len(ids)),e[ids]]+[d[ids-j] for j in range(1,p+1)])
                f=sm.OLS(d[ids,0],design).fit()
                # BIC comparisons use the same observations for all lag candidates.
                ci=np.arange(5,len(d));cd=np.column_stack([np.ones(len(ci)),e[ci]]+[d[ci-j] for j in range(1,p+1)])
                bic=sm.OLS(d[ci,0],cd).fit().bic
                if chosen is None or bic<chosen[0]:chosen=(bic,p,ids,design)
            _,p,ids,design=chosen
            for col_idx,name in [(0,'Spread'),(1,'Basis'),(2,'MOVE')]:
                f=sm.OLS(d[ids,col_idx],design).fit(cov_type='HAC',cov_kwds={'maxlags':10,'use_correction':True})
                ecms.append(dict(period=period,family=family,adjusting_series=name,difference_lags=p,lambda_=float(f.params[1]),hac10_se=float(f.bse[1]),p_descriptive=float(f.pvalues[1]),n=len(ids)))
            print('Adjustment complete:',period,family,flush=True)
    save('long_run_estimators',estimates);save('bounds',bounds);save('ecm_adjustment',ecms)
    print(pd.DataFrame(bounds)[['period','family','orders','F','p_I0','p_I1','lambda_spread']].to_string(index=False),flush=True)

def fm_scores(sub,family,bandwidth):
    # Use the library's transformation and bias convention; verify our fit against its public estimator.
    b=(sub[[family]]-sub[family].mean())/sub[family].std(ddof=0)
    model=FullyModifiedOLS(sub.Spread,b,trend='c')
    cov,eta,_=model._common_fit('bartlett',bandwidth,True,False)
    omega=np.asarray(cov.cov.long_run); lam=np.asarray(cov.cov.one_sided)
    inv22=np.linalg.inv(omega[1:,1:])
    adj=omega[:1,1:]@inv22
    ydot=sub.Spread.to_numpy()[1:]-np.squeeze(eta[:,1:]@adj.T)
    z=np.asarray(add_trend(b,trend='c'))[1:]
    bias=np.zeros(z.shape[1]);bias[0]=float((lam[:1,1:]-adj@lam[1:,1:])[0,0])
    theta=np.linalg.solve(z.T@z,z.T@ydot-len(z)*bias)
    public=model.fit(kernel='bartlett',bandwidth=bandwidth,force_int=True)
    assert np.allclose(theta,public.params.to_numpy(),atol=1e-9)
    u=ydot-z@theta
    scores=z*u[:,None]-bias
    assert np.max(np.abs(scores.sum(axis=0)))<1e-6
    variance=float((omega[:1,:1]-adj@omega[1:,:1])[0,0])
    return z,scores,variance,float(cov.bandwidth),float(public.params[family])

def break_matrices(z):
    n=len(z); ids=np.arange(int(np.ceil(.15*n)),int(np.floor(.85*n))+1)
    sums=np.cumsum(z[:,:,None]*z[:,None,:],axis=0)
    m=sums[-1]; m1=sums[ids-1];m2=m-m1
    a=np.linalg.inv(m1)+np.linalg.inv(m2)
    return ids,a,sums,np.linalg.inv(m)

def sup_stats(z,scores,variance):
    ids,a,_,_=break_matrices(z)
    s=np.cumsum(scores,axis=0)[ids-1]
    joint=np.einsum('ni,nij,nj->n',s,a,s)/variance
    delta=np.einsum('ni,ni->n',a[:,0,:],s)
    beta=delta**2/(variance*a[:,0,0])
    return ids,a,joint,beta

def simulate_beta_critical(z,ids,a,replications=1999,seed=20261003):
    # Conditional Gaussian approximation to the fully modified score limit, retaining the observed I(1) regressor path.
    rng=np.random.default_rng(seed); _,_,sums,inv=break_matrices(z); m1=sums[ids-1]
    maxima=[]
    for start in range(0,replications,100):
        r=min(100,replications-start); u=rng.standard_normal((r,len(z)))
        score=np.cumsum(u[:,:,None]*z[None,:,:],axis=1)[:,ids-1,:]
        estimated=np.einsum('ij,rj->ri',inv,u@z)
        score-=np.einsum('nij,rj->rni',m1,estimated)
        delta=np.einsum('ni,rni->rn',a[:,0,:],score)
        maxima.extend(np.max(delta**2/a[None,:,0,0],axis=1).tolist())
    return np.asarray(maxima)

def stability(data):
    results=[];gh=[]
    for family in FAMILIES:
        sub=sample(data,'Full',['Spread',family])
        for band in [None,20,60,120]:
            z,s,v,bw,beta=fm_scores(sub,family,band)
            ids,a,joint,betastat=sup_stats(z,s,v)
            if band is None:
                draws=simulate_beta_critical(z,ids,a)
                np.save(WORK/(family+'_stability_null.npy'),draws)
            selected=int(np.argmax(betastat)); joint_id=int(np.argmax(joint))
            r=dict(family=family,period='Full',bandwidth=bw,bandwidth_setting='auto' if band is None else band,
                fmols_beta=beta,beta_supWald=float(betastat[selected]),beta_break_date=str(sub.index[1:][ids[selected]-1].date()),
                beta_conditional_simulation_p=float((1+np.sum(draws>=betastat[selected]))/(1+len(draws))),
                beta_critical95_conditional=float(np.quantile(draws,.95)),replications=len(draws),seed=20261003,
                joint_supF=float(joint[joint_id]),joint_break_date=str(sub.index[1:][ids[joint_id]-1].date()),
                joint_critical95_Hansen_m1_p0=14.8,joint_reject95=bool(joint[joint_id]>14.8))
            results.append(r)
        print('FMOLS stability complete:',family,flush=True)
        # Gregory-Hansen: no-cointegration null; intercept break (C) and intercept+slope break (C/S).
        y=sub.Spread.to_numpy();x=sub[family].to_numpy();n=len(y);date=sub.index
        candidates=np.arange(int(np.ceil(.15*n)),int(np.floor(.85*n))+1)
        for spec in ['C','C/S']:
            best={method:(np.inf,None,None,None) for method in ['AIC','BIC']}
            for k in candidates:
                dummy=(np.arange(n)>=k).astype(float)
                X=np.column_stack([np.ones(n),x,dummy]+([x*dummy] if spec=='C/S' else []))
                b=np.linalg.lstsq(X,y,rcond=None)[0];u=y-X@b
                for method in ['AIC','BIC']:
                    adf=adfuller(u,maxlag=20,regression='n',autolag=method)
                    if adf[0]<best[method][0]:best[method]=(float(adf[0]),int(k),int(adf[2]),b)
            for method,(stat,k,lag,b) in best.items():
                critical={'C':[-5.13,-4.61,-4.34],'C/S':[-5.47,-4.95,-4.68]}[spec]
                gh.append(dict(family=family,spec=spec,selector=method,stat=stat,break_date=str(date[k].date()),lag=lag,
                    critical1=critical[0],critical5=critical[1],critical10=critical[2],reject5=bool(stat<critical[1]),
                    beta_pre=float(b[1]),beta_post=float(b[1]+(b[3] if spec=='C/S' else 0))))
            print('Break cointegration complete:',family,spec,flush=True)
        save('stability',results);save('gregory_hansen',gh)
    ix=[i for i,r in enumerate(results) if r['bandwidth_setting']=='auto']
    for i,p in zip(ix,multipletests([results[i]['beta_conditional_simulation_p'] for i in ix],method='holm')[1]):
        results[i]['beta_sim_p_Holm4']=float(p)
    save('stability',results)
    print(pd.DataFrame(results).to_string(index=False),flush=True)
    print(pd.DataFrame(gh).to_string(index=False),flush=True)

def prospective(data):
    rolling=pd.DataFrame(json.loads((WORK/'rolling.json').read_text(encoding='utf-8')))
    rows=[];cross=[]
    for family in FAMILIES:
        sub=data[['Spread',family,'MOVE']]
        for R in [1,2,3]:
            path=rolling[(rolling.family==family)&(rolling.R==R)].copy()
            path['date']=pd.to_datetime(path.date);path=path.set_index('date')
            joined=sub.join(path[['intercept','beta','move_beta']],how='left')
            joined['e']=joined.Spread-joined.intercept-joined.beta*joined[family]-joined.move_beta*joined.MOVE
            # No bridging missing predictor dates: lags and horizons use the original recorded-date index.
            changes=sub.diff();candidate=[]
            for horizon in [1,5,20]:
                response=sub.shift(-horizon)-sub
                response.columns=['dS','dB','dM']
                response['dBasisComponent']=-joined.beta*response.dB
                response['dMoveComponent']=-joined.move_beta*response.dM
                response['dFrozen']=response.dS-joined.beta*response.dB-joined.move_beta*response.dM
                response['dRolling']=joined.e.shift(-horizon)-joined.e
                response['dRefit']=response.dRolling-response.dFrozen
                for p in range(0,6):
                    frame=pd.concat([joined.e.rename('e'),response]+[changes.shift(j).rename(columns=lambda c:'lag'+str(j)+'_'+c) for j in range(p)],axis=1)
                    # Same comparison sample across lag candidates; last five changes must all exist.
                    common=pd.concat([joined.e]+[changes.shift(j) for j in range(5)],axis=1).dropna().index
                    frame=frame.loc[frame.index.intersection(common)].dropna()
                    xcols=['e']+[c for c in frame.columns if c.startswith('lag')]
                    X=sm.add_constant(frame[xcols]);fit=sm.OLS(frame.dS,X).fit()
                    candidate.append((float(fit.bic),horizon,p,frame,X))
                chosen=min([r for r in candidate if r[1]==horizon],key=lambda r:r[0]);_,_,p,frame,X=chosen
                for bandwidth in [max(20,horizon-1),60]:
                    coefficients={}
                    for label in ['dS','dB','dM','dBasisComponent','dMoveComponent','dFrozen','dRolling','dRefit']:
                        f=sm.OLS(frame[label],X).fit(cov_type='HAC',cov_kwds={'maxlags':bandwidth,'use_correction':True})
                        coefficients[label]=float(f.params.e)
                        rows.append(dict(family=family,R=R,horizon=horizon,bandwidth=bandwidth,response=label,n=len(frame),difference_lags=p,
                            lambda_=float(f.params.e),hac_se=float(f.bse.e),p_descriptive=float(f.pvalues.e),first=str(frame.index.min().date()),last=str(frame.index.max().date())))
                    assert abs(coefficients['dRolling']-coefficients['dFrozen']-coefficients['dRefit'])<1e-10
                    assert abs(coefficients['dFrozen']-coefficients['dS']-coefficients['dBasisComponent']-coefficients['dMoveComponent'])<1e-10
            # One-day zero crossings: count how often a refit is required to get across zero.
            a=joined.e;b=joined.e.shift(-1)
            frozen=(joined.Spread.shift(-1)-joined.intercept-joined.beta*joined[family].shift(-1)-joined.move_beta*joined.MOVE.shift(-1))
            valid=a.notna()&b.notna()&frozen.notna()
            crossing=valid&(a*b<0);refit_required=crossing&(a*frozen>=0)
            total=int(crossing.sum());needed=int(refit_required.sum())
            cross.append(dict(family=family,R=R,all_daily_residual_crossings=total,refit_required_crossings=needed,
                refit_required_share=float(needed/total) if total else 0))
            print('Prospective adjustment complete:',family,'R'+str(R),flush=True)
    for h in [1,5,20]:
        ix=[i for i,r in enumerate(rows) if r['horizon']==h and r['bandwidth']==max(20,h-1) and r['response']=='dS']
        for i,p in zip(ix,multipletests([rows[i]['p_descriptive'] for i in ix],method='holm')[1]): rows[i]['p_Holm12_descriptive']=float(p)
    save('prospective',rows);save('refit_crossings',cross)
    print(pd.DataFrame(rows).query("horizon==1 and bandwidth==20 and response=='dS'").to_string(index=False),flush=True)
    print(pd.DataFrame(cross).to_string(index=False),flush=True)

def bounds_sensitivity(data):
    rows=[]
    for period in ['Full','R1 final','R2 final','R3 final']:
        for family in FAMILIES:
            sub=sample(data,period,['Spread',family,'MOVE'])
            # Expand short-run lag allowance; choose each regressor's lag count with coordinate descent then exhaustive local search.
            # Full 1..10 grid (1000 candidates) remains modest and avoids reliance on a search approximation.
            best=None
            for p in range(1,11):
                for q in range(1,11):
                    for m in range(1,11):
                        f=UECM(sub.Spread,lags=p,exog=sub[[family,'MOVE']],order={family:q,'MOVE':m},trend='c',hold_back=10).fit()
                        if best is None or f.bic<best[0]:best=(float(f.bic),f,(p,q,m))
            fit=best[1];bt=fit.bounds_test(case=3,asymptotic=True)
            robust=fit.model.fit(cov_type='HAC',cov_kwds={'maxlags':20,'use_correction':True})
            rows.append(dict(period=period,family=family,orders=list(best[2]),F=float(bt.statistic),p_I0=float(bt.pvalue['lower']),p_I1=float(bt.pvalue['upper']),
                lambda_spread=float(fit.params['Spread.L1']),lambda_HAC20_p_descriptive=float(robust.pvalues['Spread.L1']),
                ljungbox20_p=float(acorr_ljungbox(fit.resid,lags=[20],return_df=True).lb_pvalue.iloc[0]),n=int(fit.nobs)))
            print('Longer lag bounds complete:',period,family,flush=True)
            save('bounds_sensitivity',rows)
    print(pd.DataFrame(rows).to_string(index=False),flush=True)

def corrected_bounds(data):
    # PSS reconstructs and refits the selected lag model using its natural holdback.
    # Refit the reported adjustment coefficient on that same sample after common-sample BIC selection.
    for name,L in [('bounds',10),('bounds_sensitivity',20)]:
        rows=json.loads((WORK/(name+'.json')).read_text())
        for r in rows:
            sub=sample(data,r['period'],['Spread',r['family'],'MOVE']);p,q,m=r['orders'];family=r['family']
            fit=UECM(sub.Spread,lags=p,exog=sub[[family,'MOVE']],order={family:q,'MOVE':m},trend='c').fit()
            robust=fit.model.fit(cov_type='HAC',cov_kwds={'maxlags':L,'use_correction':True})
            r['n']=int(fit.nobs);r['lambda_spread']=float(fit.params['Spread.L1'])
            r['lambda_HAC'+str(L)+'_se']=float(robust.bse['Spread.L1'])
            r['lambda_HAC'+str(L)+'_p_descriptive']=float(robust.pvalues['Spread.L1'])
            r['ljungbox20_p']=float(acorr_ljungbox(fit.resid,lags=[20],return_df=True).lb_pvalue.iloc[0])
            r['implied_basis_beta']=-float(fit.params[family+'.L1'])/r['lambda_spread']
            r['implied_move_beta']=-float(fit.params['MOVE.L1'])/r['lambda_spread']
        # Familywise adjustment for the four choices in each period, using the conservative I(1) p bound.
        for period in ['Full','R1 final','R2 final','R3 final']:
            ix=[i for i,r in enumerate(rows) if r['period']==period]
            for i,p in zip(ix,multipletests([rows[i]['p_I1'] for i in ix],method='holm')[1]):rows[i]['p_I1_Holm4']=float(p)
        save(name,rows)
    fixed=[]
    for period in ['Full','R3 final']:
        for family in FAMILIES:
            sub=sample(data,period,['Spread',family,'MOVE'])
            for lag in [10,20]:
                fit=UECM(sub.Spread,lags=lag,exog=sub[[family,'MOVE']],order=lag,trend='c').fit()
                bt=fit.bounds_test(case=3)
                fixed.append(dict(period=period,family=family,lags=lag,F=float(bt.statistic),p_I0=float(bt.pvalue['lower']),p_I1=float(bt.pvalue['upper']),
                    lambda_spread=float(fit.params['Spread.L1']),ljungbox20_p=float(acorr_ljungbox(fit.resid,lags=[20],return_df=True).lb_pvalue.iloc[0]),n=int(fit.nobs)))
    save('bounds_fixed_lags',fixed)
    print(pd.DataFrame(fixed).to_string(index=False),flush=True)

def dols_frame(sub,family):
    dx=sub[[family,'MOVE']].diff()
    frame=pd.concat([sub]+[dx.shift(j).rename(columns=lambda c:c+'_D'+str(j)) for j in range(-5,6)],axis=1).dropna()
    X=sm.add_constant(frame.drop(columns='Spread'));f=sm.OLS(frame.Spread,X).fit()
    # Exact equivalence to arch's fixed five-lead, five-lag point estimate.
    public=DynamicOLS(sub.Spread,sub[[family,'MOVE']],trend='c',leads=5,lags=5).fit()
    assert abs(f.params[family]-public.params[family])<1e-8
    influence=(X.to_numpy()@np.linalg.inv(X.to_numpy().T@X.to_numpy())[:,list(X.columns).index(family)])*f.resid.to_numpy()
    influence*=np.sqrt(len(frame)/(len(frame)-X.shape[1]))
    return f,frame.index,influence

def endpoint_dols(data):
    rows=[]
    for family in FAMILIES:
        for R in [1,2,3]:
            a=sample(data,'R'+str(R)+' first',['Spread',family,'MOVE'])
            b=sample(data,'R'+str(R)+' final',['Spread',family,'MOVE'])
            f0,i0,w0=dols_frame(a,family);f1,i1,w1=dols_frame(b,family)
            # Align on original recorded dates; overlapping R3 windows have nonzero covariance.
            influence=pd.Series(0.0,index=data.index)
            influence.loc[i1]+=w1;influence.loc[i0]-=w0
            v=influence.to_numpy();delta=float(f1.params[family]-f0.params[family])
            for L in [20,60,120]:
                variance=float(v@v+2*sum((1-j/(L+1))*(v[j:]@v[:-j]) for j in range(1,L+1)))
                se=np.sqrt(variance);z=delta/se;p=2*st.norm.sf(abs(z))
                rows.append(dict(family=family,R=R,bandwidth=L,first_beta=float(f0.params[family]),last_beta=float(f1.params[family]),
                    difference=delta,se_difference=float(se),z=float(z),p_conditional=float(p),first_n=int(f0.nobs),last_n=int(f1.nobs),overlap_n=len(i0.intersection(i1))))
    for L in [20,60,120]:
        ix=[i for i,r in enumerate(rows) if r['bandwidth']==L]
        for i,p in zip(ix,multipletests([rows[i]['p_conditional'] for i in ix],method='holm')[1]):rows[i]['p_Holm12_conditional']=float(p)
    save('endpoint_dols_stability',rows)
    print(pd.DataFrame(rows).query('bandwidth==20').to_string(index=False),flush=True)

def rank_at(stats, criticals, column=1):
    rank = 0
    for statistic, row in zip(stats, criticals):
        if statistic > row[column]:
            rank += 1
        else:
            break
    return rank

def p_bracket(statistic, cv):
    # Critical-value brackets only; no interpolation or exact p-value claim.
    if statistic > cv[2]:
        return '<0.01 (critical-value bracket)'
    if statistic > cv[1]:
        return '0.01 to 0.05 (critical-value bracket)'
    if statistic > cv[0]:
        return '0.05 to 0.10 (critical-value bracket)'
    return '>=0.10 (critical-value bracket)'

def johansen(data):
    all_stats, models, lag_records, vectors = [], [], [], []
    checks = {'max_trace_formula_error': 0.0, 'max_eigenvalue_formula_error': 0.0,
              'max_column_order_stat_difference': 0.0, 'rank_selection_agreement': True,
              'max_eigenvalue_imaginary_part': 0.0, 'max_eigenvector_relative_imaginary_part': 0.0}
    warnings_seen = []

    def run_case(sub, period, family, spec, det_order, method, q):
        y = sub.to_numpy()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            result = coint_johansen(y, det_order=det_order, k_ar_diff=q)
        warnings_seen.extend(str(w.message) for w in caught)
        # NumPy can return complex-typed eigen arrays even when all imaginary parts are zero.
        # Check their imaginary parts explicitly before converting them for real arithmetic/JSON.
        imag_eig = float(np.max(np.abs(np.imag(result.eig))))
        imag_vec_relative = float(np.max(np.abs(np.imag(result.evec))) / max(1.0, float(np.max(np.abs(result.evec)))))
        checks['max_eigenvalue_imaginary_part'] = max(checks['max_eigenvalue_imaginary_part'], imag_eig)
        checks['max_eigenvector_relative_imaginary_part'] = max(checks['max_eigenvector_relative_imaginary_part'], imag_vec_relative)
        assert imag_eig < 1e-10 and imag_vec_relative < 1e-10, 'Unexpected non-real eigenvalues/vectors.'
        eigenvalues = np.real(result.eig)
        eigenvectors = np.real(result.evec)
        trace = result.trace_stat
        maximum = result.max_eig_stat
        trace_cv, maximum_cv = result.trace_stat_crit_vals, result.max_eig_stat_crit_vals
        T = int(result.rkt.shape[0])
        assert np.isfinite(eigenvalues).all() and (eigenvalues >= 0).all() and (eigenvalues < 1).all()
        contributions = -T * np.log1p(-eigenvalues)
        manual_trace = np.cumsum(contributions[::-1])[::-1]
        e_trace = float(np.max(np.abs(trace - manual_trace)))
        e_max = float(np.max(np.abs(maximum - contributions)))
        checks['max_trace_formula_error'] = max(checks['max_trace_formula_error'], e_trace)
        checks['max_eigenvalue_formula_error'] = max(checks['max_eigenvalue_formula_error'], e_max)
        assert e_trace < 1e-8 and e_max < 1e-8
        rt, rm = rank_at(trace, trace_cv), rank_at(maximum, maximum_cv)
        for test_name, expected_rank in [('trace', rt), ('maxeig', rm)]:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                library_rank = select_coint_rank(y, det_order, q, method=test_name, signif=.05).rank
            warnings_seen.extend(str(w.message) for w in caught)
            assert library_rank == expected_rank
        # Verify invariance to reordering the variables on the main full-sample cases.
        if period == 'Full' and method == 'AIC' and det_order == 0:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                reordered = coint_johansen(y[:, ::-1], det_order, q)
            warnings_seen.extend(str(w.message) for w in caught)
            error = max(float(np.max(np.abs(reordered.trace_stat - trace))),
                        float(np.max(np.abs(reordered.max_eig_stat - maximum))))
            checks['max_column_order_stat_difference'] = max(checks['max_column_order_stat_difference'], error)
            assert error < 1e-7
        # Check residual adequacy of the unrestricted lag model used by the rank analysis.
        trend = 'c' if det_order == 0 else 'ct'
        var_fit = VAR(y).fit(q + 1, trend=trend)
        whiteness_lags = max(20, q + 5)
        whiteness = var_fit.test_whiteness(nlags=whiteness_lags, adjusted=True)
        base = dict(period=period, family=family, spec=spec, n_variables=y.shape[1],
                    det_order=det_order, lag_rule=method, k_ar_diff=q, level_VAR_lags=q + 1,
                    complete_case_n=len(sub), effective_test_n=T,
                    first=str(sub.index.min().date()), last=str(sub.index.max().date()))
        m = dict(base, trace_rank5=rt, max_eig_rank5=rm,
                 trace_r0_stat=float(trace[0]), trace_r0_cv5=float(trace_cv[0, 1]),
                 max_eig_r0_stat=float(maximum[0]), max_eig_r0_cv5=float(maximum_cv[0, 1]),
                 trace_r0_p_bracket=p_bracket(float(trace[0]), trace_cv[0]),
                 max_eig_r0_p_bracket=p_bracket(float(maximum[0]), maximum_cv[0]),
                 VAR_whiteness_lags=whiteness_lags, VAR_whiteness_stat=float(whiteness.test_statistic),
                 VAR_whiteness_p=float(whiteness.pvalue),
                 exact_Johansen_p_value=None)
        models.append(m)
        for test_name, stats, criticals in [('trace', trace, trace_cv), ('max_eigenvalue', maximum, maximum_cv)]:
            for r, (stat, cv) in enumerate(zip(stats, criticals)):
                all_stats.append(dict(base, test=test_name, null_rank=r,
                                      null=f'rank <= {r}' if test_name == 'trace' else f'rank = {r} versus {r + 1}',
                                      statistic=float(stat), critical10=float(cv[0]), critical5=float(cv[1]), critical1=float(cv[2]),
                                      reject10=bool(stat > cv[0]), reject5=bool(stat > cv[1]), reject1=bool(stat > cv[2]),
                                      exact_p_value=None, critical_value_p_bracket=p_bracket(float(stat), cv)))
        vectors.append(dict(base, columns=list(sub.columns), eigenvalues=eigenvalues.tolist(),
                            eigenvectors_columns=eigenvectors.tolist()))

    for period, (start, end) in PERIODS.items():
        period_data = data.loc[(data.index >= start) & (data.index < end)]
        for family in FAMILIES:
            for spec in ['pair', 'with MOVE']:
                columns = ['Spread', family] + (['MOVE'] if spec == 'with MOVE' else [])
                sub = period_data[columns].dropna()
                det_orders = [0, 1] if period in ['Full', 'R3 final'] else [0]
                for det_order in det_orders:
                    deterministic = 'co' if det_order == 0 else 'colo'
                    selected = select_order(sub.to_numpy(), maxlags=20, deterministic=deterministic)
                    lag_records.append(dict(period=period, family=family, spec=spec, det_order=det_order,
                                            selection_deterministic=deterministic, max_difference_lags=20,
                                            complete_case_n=len(sub), excluded_missing_rows=len(period_data)-len(sub),
                                            selected_orders=selected.selected_orders,
                                            information_criteria=selected.ics))
                    for method in ['AIC', 'BIC']:
                        q = int(selected.selected_orders[method.lower()])
                        run_case(sub, period, family, spec, det_order, method, q)
                    if det_order == 0 and period in ['Full', 'R3 final']:
                        for q in [10, 20]:
                            run_case(sub, period, family, spec, det_order, f'Fixed {q}', q)
        print(f'Completed {period}: {len(models)} fitted rank analyses', flush=True)

    assert len(models) == 176 and len(all_stats) == 880
    save("johansen_models", models)
    save("johansen_statistics", all_stats)
    save("johansen_lag_selection", lag_records)
    save("johansen_vectors", vectors)
    save("johansen_numerical_checks", {**checks, "model_count":len(models), "statistic_rows":len(all_stats), "warnings":sorted(set(warnings_seen))})



def stability_reporting_units(data):
    """Apply the same unit conversion that was used when producing the report."""
    rows=json.loads((WORK/"stability.json").read_text(encoding="utf-8"))
    for r in rows:
        if "fmols_beta_units" not in r:
            r["fmols_beta"]=float(r["fmols_beta"]/data[r["family"]].dropna().std(ddof=0))
            r["fmols_beta_units"]="bp spread / bp Basis"
        r.setdefault("beta_sim_p_Holm4",None)
    save("stability",rows)

def regression_snapshots(data):
    """Refit the 24 endpoint regressions shown in the regression appendix."""
    models=[]; terms=[]
    for family in FAMILIES:
        for R in [1,2,3]:
            for endpoint in ["first","final"]:
                period=f"R{R} {endpoint}"
                sub=sample(data,period,["Spread",family,"MOVE"])
                X=sm.add_constant(sub[[family,"MOVE"]].to_numpy())
                y=sub.Spread.to_numpy(); n=len(y); df=n-3
                beta=np.linalg.lstsq(X,y,rcond=None)[0]
                residual=y-X@beta
                L=int(np.floor(4*(n/100)**(2/9)))
                V=hac(X,residual,L); se=np.sqrt(np.diag(V)); critical=st.t.ppf(.975,df)
                classical=sm.OLS(y,X).fit()
                joint=float(beta[1:]@np.linalg.solve(V[1:,1:],beta[1:])/2)
                start,end=PERIODS[period]
                raw_n=len(data.loc[(data.index>=start)&(data.index<end)])
                models.append(dict(family=family,R=R,endpoint=endpoint,n=n,excluded=raw_n-n,
                    calendar_start=start,signal_date=end,first=str(sub.index[0].date()),last=str(sub.index[-1].date()),
                    residual_df=df,HAC_lags=L,R_squared=float(classical.rsquared),adjusted_R_squared=float(classical.rsquared_adj),
                    residual_SE=float(np.sqrt(residual@residual/df)),Durbin_Watson=float(sm.stats.durbin_watson(residual)),
                    classical_F=float(classical.fvalue),classical_F_p=float(classical.f_pvalue),HAC_joint_F=joint,
                    HAC_joint_F_p=float(st.f.sf(joint,2,df))))
                for j,name in enumerate(["Intercept","Basis","MOVE"]):
                    statistic=float(beta[j]/se[j])
                    terms.append(dict(family=family,R=R,endpoint=endpoint,term=name,coefficient=float(beta[j]),
                        HAC_SE=float(se[j]),HAC_t=statistic,HAC_p=float(2*st.t.sf(abs(statistic),df)),
                        CI_lower=float(beta[j]-critical*se[j]),CI_upper=float(beta[j]+critical*se[j]),
                        classical_SE=float(classical.bse[j]),classical_t=float(classical.tvalues[j]),
                        classical_p=float(classical.pvalues[j]),n=n,reference_df=df))
    save("regression_models",models); save("regression_coefficients",terms)

def currency_corrections():
    """Retain Holm12 and the exploratory Holm6 correction within each currency."""
    source=json.loads((WORK/"prospective.json").read_text(encoding="utf-8"))
    rows=[dict(r) for r in source if r["response"]=="dS"]
    for horizon in [1,5,20]:
        for bandwidth in [20,60]:
            group=[r for r in rows if r["horizon"]==horizon and r["bandwidth"]==bandwidth]
            assert len(group)==12
            for r,p in zip(group,multipletests([r["p_descriptive"] for r in group],method="holm")[1]):
                r["p_Holm12_reproduced"]=float(p)
            for currency in ["GBP","EUR"]:
                group6=[r for r in group if r["family"].startswith(currency)]
                for r,p in zip(group6,multipletests([r["p_descriptive"] for r in group6],method="holm")[1]):
                    r["currency"]=currency; r["p_Holm6_currency"]=float(p)
                    r["significant_Holm6_5pct"]=bool(p<.05)
    save("currency_corrections",rows)

def compare_value(actual,expected,path="root",errors=None):
    """Compare the recomputed values against recorded results, not against invented targets."""
    if errors is None: errors=[]
    if isinstance(expected,dict):
        if not isinstance(actual,dict): errors.append(path+": not a dictionary"); return errors
        for key,value in expected.items():
            if key not in actual: errors.append(path+"."+key+": missing")
            else: compare_value(actual[key],value,path+"."+key,errors)
    elif isinstance(expected,list):
        if not isinstance(actual,list) or len(actual)!=len(expected):
            errors.append(path+": different row count"); return errors
        for i,(a,b) in enumerate(zip(actual,expected)): compare_value(a,b,f"{path}[{i}]",errors)
    elif isinstance(expected,(int,float)) and not isinstance(expected,bool):
        if not isinstance(actual,(int,float)) or not np.isclose(actual,expected,rtol=1e-7,atol=1e-7):
            errors.append(f"{path}: {actual!r} != {expected!r}")
    elif actual!=expected: errors.append(f"{path}: {actual!r} != {expected!r}")
    return errors

STAGE_RESULTS={
    "integration":["integration","cointegration"],
    "regressions":["regression_models","regression_coefficients"],
    "rolling":["rolling","rolling_summary","rolling_checks"],
    "adjustment":["long_run_estimators","bounds","bounds_sensitivity","bounds_fixed_lags","ecm_adjustment"],
    "stability":["stability","gregory_hansen"],
    "endpoints":["endpoint_dols_stability"],
    "prospective":["prospective","refit_crossings","currency_corrections"],
    "johansen":["johansen_models","johansen_statistics"],
}

def main():
    global WORK,OUT
    if not __debug__:
        raise RuntimeError('Run without -O so statistical verification assertions remain active.')
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source",type=Path,default=ROOT/"data"/"observations.csv",help="CSV snapshot or original raw workbook (sheet SOFR).")
    parser.add_argument("--out",type=Path,default=ROOT/"results",help="Results folder; workbooks are never overwritten.")
    parser.add_argument("--stages",nargs="+",choices=list(STAGE_RESULTS),default=list(STAGE_RESULTS),help="Run selected test groups; default runs every group.")
    parser.add_argument("--skip-reference-check",action="store_true",help="Skip historical output comparison (input must still match the reported observations).")
    args=parser.parse_args()
    if not args.skip_reference_check:
        requested=set(args.stages)
        if 'prospective' in requested:
            requested.add('rolling')
        for stage in requested:
            for name in STAGE_RESULTS[stage]:
                reference=ROOT/'reference_results'/(name+'.json')
                if not reference.is_file():
                    raise FileNotFoundError(f'Missing historical comparison: {reference}')
    WORK=args.out.resolve()/"raw"; OUT=args.out.resolve()/"tables"
    WORK.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter()
    input_hash=hashlib.sha256(args.source.read_bytes()).hexdigest()
    data=load_data(args.source)
    snapshot=load_data(ROOT/"data"/"observations.csv")
    matching=data.index.equals(snapshot.index) and np.allclose(data.to_numpy(),snapshot.to_numpy(),atol=0,rtol=0,equal_nan=True)
    if not matching and not args.skip_reference_check:
        raise ValueError("Data differ from the observations used in the report. This runner reproduces the reported dataset; update PERIODS and the endpoint references explicitly to analyze different observations.")
    # rolling() validates its first/final coefficients against saved workbook inputs.
    if matching:
        context=json.loads((ROOT/"data"/"endpoint_validation.json").read_text(encoding="utf-8"))
    else:
        raise ValueError("Rolling endpoint validation is fixed to the reported observations. To analyze different data, update the endpoint references and PERIODS explicitly.")
    (WORK/"workbook_context.json").write_text(json.dumps(context),encoding="utf-8")
    stages=[s for s in STAGE_RESULTS if s in args.stages]
    if "prospective" in stages and "rolling" not in stages:
        stages.insert(stages.index("prospective"),"rolling")
    completed=[]; comparisons=[]; durations={}
    for stage in stages:
        print(f"\nSTART {stage}",flush=True)
        tick=time.perf_counter()
        if stage=="integration": integration(data)
        elif stage=="regressions": regression_snapshots(data)
        elif stage=="rolling": rolling(data)
        elif stage=="adjustment":
            adjustment(data)
            bounds_sensitivity(data)
            corrected_bounds(data)
        elif stage=="stability":
            stability(data)
            stability_reporting_units(data)
        elif stage=="endpoints": endpoint_dols(data)
        elif stage=="prospective":
            prospective(data)
            currency_corrections()
        elif stage=="johansen": johansen(data)
        durations[stage]=round(time.perf_counter()-tick,3)
        completed.append(stage)
        if not args.skip_reference_check:
            for name in STAGE_RESULTS[stage]:
                ref=ROOT/"reference_results"/(name+".json")
                if not ref.is_file():
                    raise FileNotFoundError(f"Missing historical comparison: {ref}. Use --skip-reference-check only if comparisons are intentionally omitted.")
                actual=json.loads((WORK/(name+".json")).read_text(encoding="utf-8"))
                expected=json.loads(ref.read_text(encoding="utf-8"))
                differences=compare_value(actual,expected)
                comparisons.append(dict(result=name,matched=not differences,differences=differences[:20],rows=len(expected) if isinstance(expected,list) else None))
                if differences:
                    save("replication_checks",comparisons)
                    raise AssertionError(f"Historical result comparison failed for {name}: {differences[:3]}")
        print(f"COMPLETE {stage}: {durations[stage]} seconds",flush=True)
    assert hashlib.sha256(args.source.read_bytes()).hexdigest()==input_hash
    save("replication_checks",comparisons)
    save("run_metadata",dict(run_time_utc=datetime.now(__import__("datetime").timezone.utc).isoformat(),
        input_path=str(args.source.resolve()),input_sha256=input_hash,input_matches_reported_observations=matching,
        input_rows=len(data),first=str(data.index[0].date()),last=str(data.index[-1].date()),missing=data.isna().sum().to_dict(),
        period_boundaries=PERIODS,stages_completed=completed,stage_seconds=durations,total_seconds=round(time.perf_counter()-start,3),
        versions={p:importlib.metadata.version(p) for p in ["numpy","pandas","scipy","statsmodels","arch","openpyxl"]},
        python_version=platform.python_version(),reference_comparisons=not args.skip_reference_check,original_workbooks_modified=False))
    print(f"\nDone. CSV tables: {OUT}\nFull-precision JSON: {WORK}",flush=True)

if __name__=="__main__":
    main()
