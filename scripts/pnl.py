"""Calculate market P&L, carry and rolldown for each strategy trade."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from valuation import configure_rates,setup_trade,marks

def clean(v):
    if isinstance(v,dict):return {k:clean(a) for k,a in v.items()}
    if isinstance(v,list):return [clean(a) for a in v]
    if isinstance(v,pd.Timestamp):return str(v.date())
    if isinstance(v,(np.integer,)):return int(v)
    if isinstance(v,(np.bool_,)):return bool(v)
    if isinstance(v,(np.floating,float)):return float(v) if np.isfinite(v) else None
    return v

def attribute_models(models,rate_frame,output_dir):
    W=Path(output_dir)
    W.mkdir(parents=True,exist_ok=True)
    configure_rates(rate_frame)
    summaries=[];alltrades=[];audits=[];daily_export=[];signal_export=[];mark_export=[]
    for m in models:
        d=m['daily'];df=m['df'];y=df.iloc[:,0 if m['maturity']==10 else 1].ffill();n=len(d)
        components=np.zeros((n,3));dailytrade=['']*n
        rows_by_idx={int(v):j for j,v in enumerate(d['Index'])}
        for tr in m['trades']:
            cfg=setup_trade(tr);previous=np.zeros(3);last=None
            for i in range(tr['EntryIndex'],tr['EndIndex']+1):
                date=df.index[i];vals=marks(tr,cfg,date,float(y.iloc[i]));curr=np.array([vals['Market'],vals['Carry'],vals['Rolldown']]);j=rows_by_idx[i]
                components[j]+=curr-previous
                previous=curr;dailytrade[j]=tr['Trade'];last=vals
                mark_export.append({'Model':m['id'],'Trade':tr['Trade'],'Date':date,'OriginalSpreadMark':float(y.iloc[i]),**vals,'Adjusted':sum(curr)})
            tr.update(last);tr['Adjusted']=tr['Market']+tr['Carry']+tr['Rolldown'];tr['Outcome']='Open' if tr['Status']=='Open' else ('Win' if tr['Adjusted']>1e-10 else 'Loss' if tr['Adjusted']< -1e-10 else 'Flat');alltrades.append(tr)
        cumulative=np.cumsum(components,axis=0);equity=cumulative.sum(axis=1);peak=np.maximum.accumulate(np.r_[0,equity])[1:];dd=peak-equity
        t=pd.DataFrame(m['trades']);completed=t[t.Status=='Completed'];open_=t[t.Status=='Open'];wins=int((completed.Adjusted>1e-10).sum());losses=int((completed.Adjusted< -1e-10).sum());flat=len(completed)-wins-losses
        totals=t[['Market','Carry','Rolldown','Adjusted']].sum()
        s={'Model':m['id'],'Regime':m['regime'],'Maturity':m['maturity'],'Currency':m['currency'],'BasisTenor':m['tenor'],'Window':m['window'],'FirstSignal':m['start'],'FinalClose':m['end'],'Market':float(totals.Market),'Carry':float(totals.Carry),'Rolldown':float(totals.Rolldown),'Adjusted':float(totals.Adjusted),'MaxDrawdown':float(dd.max()),'Completed':len(completed),'Open':len(open_),'TotalTrades':len(t),'Wins':wins,'Losses':losses,'Flat':flat,'WinPct':wins/len(completed) if len(completed) else None,'LossPct':losses/len(completed) if len(completed) else None,'MeanHoldingSessions':float(completed.HoldingSessions.mean()) if len(completed) else None,'MeanHoldingDays':float(completed.HoldingDays.mean()) if len(completed) else None,'CompletedAdjusted':float(completed.Adjusted.sum()),'OpenAdjusted':float(open_.Adjusted.sum()),'ReducedCurveTrades':int(t.ReducedUSTCurve.sum()),'MissingSignals':int((~d.SignalAvailable).sum()),'MissingSpreadCloses':int((~d.SpreadAvailable).sum()),'MaxDrawdownDate':d.iloc[int(np.argmax(dd))].Date}
        summaries.append(s)
        market_from_trades=sum(tr['Direction']*(tr['EndSpread']-tr['EntrySpread']) for tr in m['trades'])
        dif=cumulative[-1]-totals[['Market','Carry','Rolldown']].values.astype(float)
        assert np.max(np.abs(dif))<1e-8,(m['id'],dif)
        assert abs(s['Market']-market_from_trades)<1e-8
        assert abs(s['Adjusted']-equity[-1])<1e-8
        assert s['Open'] in [0,1] and (completed['EntryDate']<=completed['EndDate']).all()
        for j,r in d.iterrows():
            daily_export.append({'Model':m['id'],'Date':r.Date,'OriginalSpread':r.OriginalSpread,'SpreadMark':float(y.iloc[int(r.Index)]),'Z':r.Z,'Signal':r.Signal,'Execution':r.Execution,'Position':int(r.Position),'Trade':dailytrade[j],'MarketChange':float(components[j,0]),'CarryChange':float(components[j,1]),'RolldownChange':float(components[j,2]),'MarketCumulative':float(cumulative[j,0]),'CarryCumulative':float(cumulative[j,1]),'RolldownCumulative':float(cumulative[j,2]),'AdjustedEquity':float(equity[j]),'Peak':float(peak[j]),'Drawdown':float(dd[j]),'SpreadAvailable':r.SpreadAvailable,'SignalAvailable':r.SignalAvailable})
            signal_export.append({'Model':m['id'],**r.to_dict()})
        audits.append({'Model':m['id'],'MarketDifference':float(dif[0]),'CarryDifference':float(dif[1]),'RolldownDifference':float(dif[2]),'AdjustedDifference':float(equity[-1]-s['Adjusted']),'MarketTradeFormulaDifference':float(s['Market']-market_from_trades),'Rows':n,'TradeRows':len(t)})
        print(m['id'],'Adj',round(s['Adjusted'],2),'DD',round(s['MaxDrawdown'],2),'Trades',len(t),flush=True)
    for name,data in [('summary',summaries),('trades',alltrades),('daily',daily_export),('signals',signal_export),('trade_daily_marks',mark_export),('reconciliation',audits)]:
        pd.DataFrame(data).to_csv(W/f'{name}.csv',index=False)
        (W/f'{name}.json').write_text(json.dumps(clean(data),allow_nan=False,separators=(',',':')))
    print('Completed attribution',len(summaries),'models',len(alltrades),'trades',len(daily_export),'daily rows')
    print(pd.DataFrame(summaries).groupby('Regime').agg(MinAdjusted=('Adjusted','min'),MaxAdjusted=('Adjusted','max'),Positive=('Adjusted',lambda a:(a>0).sum())))

    return dict(summary=summaries,trades=alltrades,daily=daily_export,signals=signal_export,trade_marks=mark_export)
