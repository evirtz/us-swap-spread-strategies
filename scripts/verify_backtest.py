"""Independently check a completed raw rebuild; comparisons never feed the strategy."""
from pathlib import Path
from collections import defaultdict
from datetime import date
import argparse,csv,json,math
import numpy as np
import pandas as pd

def verify_rebuild(output_dir,reference_results=None):
    if not __debug__:
        raise RuntimeError('Run without -O so verification assertions remain active.')
    out=Path(output_dir)
    report=json.loads((out/"rebuild_verification.json").read_text())
    assert report["InputsOnlyTwoRawWorkbooks"] and report["InputFilesUnchanged"]
    raw=pd.read_csv(out/"normalized_inputs/signals_SOFR.csv",parse_dates=["Date"]).set_index("Date")
    rates=pd.read_csv(out/"normalized_inputs/rates_SOFR.csv",parse_dates=["Date"]).set_index("Date")
    fits=pd.read_csv(out/"strategy/signals.csv",parse_dates=["Date","TrainingStart"])
    trades=pd.read_csv(out/"strategy/trades.csv",parse_dates=["EntrySignal","EntryDate","ExitSignal","EndDate"])
    assert fits.Model.nunique()==24 and len(trades)==323
    ols_samples=0
    for mid,rows in fits.groupby("Model"):
        parts=mid.split("_")
        maturity=int(parts[1][:-1])
        currency=parts[2][:3]
        tenor=int(parts[2][3:-1])
        window=int(parts[3][1:])
        ycol="10yr swap spreads" if maturity==10 else "30yr swap spreads"
        basis=f"{tenor}yr_Basis_{'EU' if currency=='EUR' else currency}_SOFR"
        for index in sorted({0,len(rows)//2,len(rows)-1}):
            r=rows.iloc[index]
            lower=r.Date-pd.DateOffset(years=window)
            sample=raw.loc[(raw.index>=lower)&(raw.index<r.Date),[ycol,basis,"Move"]].dropna()
            X=np.column_stack([np.ones(len(sample)),sample[basis],sample.Move])
            y=sample[ycol].to_numpy()
            beta=np.linalg.solve(X.T@X,X.T@y)
            se=np.sqrt(np.sum((y-X@beta)**2)/(len(y)-3))
            assert len(y)==r.TrainingN and r.TrainingStart==lower
            assert np.allclose(beta,[r.Intercept,r.BasisBeta,r.MOVEBeta],atol=1e-8,rtol=1e-8)
            assert abs(se-r.Sigma)<1e-8
            ols_samples+=1
        assert rows.loc[~rows.SignalAvailable,"Signal"].isna().all()
        relevant=trades[trades.Model==mid].sort_values("EntryDate")
        previous_end=None
        valid=raw[ycol].dropna().index
        for t in relevant.itertuples():
            assert t.EntryDate==valid[valid>t.EntrySignal][0]
            if t.Status=="Completed":
                assert t.EndDate==valid[valid>t.ExitSignal][0]
            else:
                assert t.EndDate==pd.Timestamp("2026-09-03")
            if previous_end is not None:
                assert t.EntryDate>previous_end
            previous_end=t.EndDate
    missing=fits[(fits.Model.str.contains("EUR5Y"))&(fits.Date==pd.Timestamp("2026-03-20"))]
    assert len(missing)==6 and not missing.SignalAvailable.any() and missing.SpreadAvailable.all()
    assert missing.Signal.isna().all()
    for r in missing.itertuples():
        prior=fits[(fits.Model==r.Model)&(fits.Date==pd.Timestamp("2026-03-19"))].iloc[0]
        if pd.notna(prior.Signal):
            assert r.Execution==prior.Signal

    # Independent ordinal-day intersections for all holding-period SOFR factors.
    fix=rates.Floating.dropna()
    days=np.array([d.toordinal() for d in fix.index])
    values=fix.to_numpy()/100
    max_carry=0.0
    for t in trades.itertuples():
        begin=t.EntryDate.toordinal()
        end=t.EndDate.toordinal()
        nextdays=np.r_[days[1:],end]
        fractions=np.maximum(0,np.minimum(nextdays,end)-np.maximum(days,begin))/360
        factor=float(np.prod(1+values*fractions)-1)
        length=end-begin
        legs=t.Direction*np.array([
            t.TreasuryNotionalPerDV01*t.TreasuryCoupon*length/365.25,
            -t.TreasuryNotionalPerDV01*factor,
            t.SwapNotionalPerDV01*factor,
            -t.SwapNotionalPerDV01*t.EntryIRS*length/360,
        ])
        expected=np.array([t.TreasuryCouponCarry,t.TreasuryFundingCarry,t.SwapFloatingCarry,t.SwapFixedCarry])
        max_carry=max(max_carry,float(np.max(np.abs(legs-expected))),abs(float(legs.sum())-t.Carry))
        assert np.max(np.abs(legs-expected))<1e-8 and abs(float(legs.sum())-t.Carry)<1e-8
        assert abs(t.Market-t.Direction*(t.EndSpread-t.EntrySpread))<1e-10
        assert abs(t.Rolldown-t.TreasuryRolldown-t.SwapRolldown)<1e-8
        assert t.TreasuryCoupon>0 and .98<t.TreasuryCoupon/t.EntryUST<1.02
        assert not t.ReducedUSTCurve and t.MaxQuoteAgeDays<=7

    case_reports={}
    numeric={"Leverage","Year","FinalCapital","CumulativeReturn","TradeCapitalError",
        "MonthlyReturn","CalendarReturn","OpeningCapital","ClosingCapital","MarketPnL",
        "CarryPnL","RolldownPnL","IncludedSessions","PlannedSessions","HaircutFundingCost","TradingCost"}
    def read(path):
        with path.open(encoding="utf-8-sig",newline="") as handle:
            return list(csv.DictReader(handle))
    for case in ("gross","net"):
        dd=read(out/case/"daily_capital.csv")
        tt=read(out/case/"trade_capital.csv")
        accounts=read(out/case/"account_summary.csv")
        monthly=read(out/case/"monthly_returns.csv")
        assert len(accounts)==96 and len(monthly)==5376
        daily_groups=defaultdict(list)
        trade_groups=defaultdict(list)
        for row in dd:
            daily_groups[row["Model"],row["Leverage"]].append(row)
        for row in tt:
            trade_groups[row["Model"],row["Leverage"]].append(row)
        for a in accounts:
            key=a["Model"],a["Leverage"]
            rows=daily_groups[key]
            assert rows[0]["OpeningCapital"]=="100.0"
            assert abs(float(rows[-1]["ClosingCapital"])-float(a["FinalCapital"]))<1e-7
            assert all(float(r["ClosingCapital"])>0 for r in rows[:-1])
            for r in rows:
                net=sum(float(r[k]) for k in ("MarketPnL","CarryPnL","RolldownPnL"))
                net-=float(r["HaircutFundingCost"])+float(r["TradingCost"])
                assert abs(float(r["OpeningCapital"])+net-float(r["ClosingCapital"]))<1e-7
            total=math.fsum(float(t["TradePnL"]) for t in trade_groups[key])
            assert abs(100+total-float(a["FinalCapital"]))<1e-7
        checked=0
        max_return=max_capital=0.0
        if reference_results:
            for filename,keys in (("account_summary.csv",("Model","Leverage")),
                                  ("monthly_returns.csv",("Model","Leverage","Month")),
                                  ("calendar_year_returns.csv",("Model","Leverage","Year"))):
                actual=read(out/case/filename)
                expected=read(Path(reference_results)/case/filename)
                key=lambda r:tuple(r[k] for k in keys)
                lookup={key(r):r for r in actual}
                assert len(lookup)==len(actual)==len(expected)
                assert set(lookup)=={key(r) for r in expected}
                for wanted in expected:
                    got=lookup[key(wanted)]
                    for field,value in wanted.items():
                        if value=="":
                            assert got[field]=="",(filename,key(wanted),field,got[field])
                        elif field in numeric:
                            error=abs(float(got[field])-float(value))
                            is_return=field in {"MonthlyReturn","CumulativeReturn","CalendarReturn"}
                            assert math.isfinite(float(got[field])) and error<=(1e-9 if is_return else 1e-7),(case,filename,key(wanted),field,error)
                            if is_return:
                                max_return=max(max_return,error)
                            else:
                                max_capital=max(max_capital,error)
                        else:
                            assert got[field]==value,(case,filename,key(wanted),field,got[field],value)
                        checked+=1
        case_reports[case]=dict(Accounts=96,MonthlyRows=5376,
            NumericMonthlyReturns=sum(r["MonthlyReturn"]!="" for r in monthly),
            DailyCapitalRows=len(dd),CapitalTrades=len(tt),ReferenceFieldsChecked=checked,
            MaximumReferenceReturnError=max_return,MaximumReferenceCapitalError=max_capital)
    result=dict(Status="PASS",RollingModels=24,RegressionSamples=ols_samples,
        TradesChecked=len(trades),MissingPredictorCasesChecked=len(missing),
        MaximumIndependentCarryDifferenceBp=max_carry,Cases=case_reports,
        CalculationUsedOnlyRawWorkbooks=True,
        SavedResultsUsedForVerificationOnly=bool(reference_results))
    (out/"independent_verification.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",required=True,type=Path)
    parser.add_argument("--reference-results",type=Path)
    args=parser.parse_args()
    print(json.dumps(verify_rebuild(args.output_dir,args.reference_results),indent=2))
