"""Fit rolling regressions and execute residual signals at the next close."""
import numpy as np
import pandas as pd

def generate_models(raw):
    starts={'SOFR':{1:'2022-02-22',2:'2023-02-21',3:'2024-02-21'},'LIBOR':{1:'2012-05-04',2:'2013-05-06',3:'2014-05-05'}}
    end={'SOFR':'2026-09-03','LIBOR':'2021-12-12'}
    models=[]
    for regime in ['SOFR']:
        df=raw.copy().loc[:end[regime]]
        move='Move' if regime=='SOFR' else 'Move Index'
        for maturity,ycol in [(10,df.columns[0]),(30,df.columns[1])]:
            for currency in ['GBP','EUR']:
                for tenor in [2,5]:
                    basis=f'{tenor}yr_Basis_{"EU" if currency=="EUR" else currency}_{regime}'
                    X=np.column_stack([np.ones(len(df)),df[basis].values,df[move].values]);y=df[ycol].values
                    complete=np.isfinite(X).all(axis=1)&np.isfinite(y)
                    for window in [1,2,3]:
                        mid=f'{regime}_{maturity}Y_{currency}{tenor}Y_R{window}'
                        begin=np.searchsorted(df.index,pd.Timestamp(starts[regime][window])); daily=[];trades=[];pos=0;pending=None;active=None;seq=0
                        for i in range(begin,len(df)):
                            date=df.index[i];valid_quote=np.isfinite(y[i]);execaction='';execid=None
                            # A row with no original spread quote is not an executable spread close.
                            if pending is not None and valid_quote:
                                action,sdate,sz=pending
                                if action in ['Long','Short']:
                                    assert pos==0;pos=1 if action=='Long' else -1;seq+=1;execid=f'{mid}_T{seq:03}'
                                    active={'Model':mid,'Trade':execid,'Regime':regime,'Maturity':maturity,'Currency':currency,'BasisTenor':tenor,'Window':window,'Direction':pos,'EntrySignal':sdate,'EntryZ':sz,'EntryDate':date,'EntryIndex':i,'EntrySpread':float(y[i])}
                                else:
                                    assert active is not None;execid=active['Trade'];active.update({'ExitSignal':sdate,'ExitZ':sz,'EndDate':date,'EndIndex':i,'EndSpread':float(y[i]),'Status':'Completed','HoldingSessions':i-active['EntryIndex'],'HoldingDays':(date-active['EntryDate']).days})
                                    trades.append(active);active=None;pos=0
                                execaction=action;pending=None
                            lower=date-pd.DateOffset(years=window);lo=np.searchsorted(df.index,lower);ix=np.arange(lo,i)[complete[lo:i]]
                            xtrain=X[ix];yt=y[ix];beta,res,rank,sv=np.linalg.lstsq(xtrain,yt,rcond=None)
                            assert len(ix)>3 and rank==3
                            resid=yt-xtrain@beta;sigma=np.sqrt(resid@resid/(len(ix)-3))
                            fitted=float(X[i]@beta) if np.isfinite(X[i]).all() else np.nan
                            z=float((y[i]-fitted)/sigma) if complete[i] and sigma>0 else np.nan
                            action=''
                            if pending is None and np.isfinite(z) and i<len(df)-1:
                                if pos==0 and z>=1:action='Short'
                                elif pos==0 and z<=-1:action='Long'
                                elif pos==1 and z>=0:action='Exit'
                                elif pos==-1 and z<=0:action='Exit'
                                if action:pending=(action,date,z)
                            daily.append({'Date':date,'Index':i,'OriginalSpread':float(y[i]) if valid_quote else np.nan,'Basis':float(X[i,1]),'MOVE':float(X[i,2]),'TrainingStart':lower,'TrainingN':len(ix),'Intercept':float(beta[0]),'BasisBeta':float(beta[1]),'MOVEBeta':float(beta[2]),'Sigma':float(sigma),'FittedSpread':fitted,'Z':z,'Signal':action,'Execution':execaction,'ExecutionTrade':execid,'Position':pos,'ActiveTrade':active['Trade'] if active else None,'SignalAvailable':bool(complete[i]),'SpreadAvailable':bool(valid_quote)})
                        if active:
                            active.update({'ExitSignal':None,'ExitZ':np.nan,'EndDate':df.index[-1],'EndIndex':len(df)-1,'EndSpread':float(y[-1]),'Status':'Open','HoldingSessions':len(df)-1-active['EntryIndex'],'HoldingDays':(df.index[-1]-active['EntryDate']).days});trades.append(active)
                        models.append({'id':mid,'regime':regime,'maturity':maturity,'currency':currency,'tenor':tenor,'window':window,'start':df.index[begin],'end':df.index[-1],'df':df,'daily':pd.DataFrame(daily),'trades':trades,'pending_final':pending})
        print('Completed regressions',regime,flush=True)
    return models
