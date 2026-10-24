"""Treasury/swap carry and rolldown under the study's pricing assumptions."""
import numpy as np
import pandas as pd
from functools import lru_cache
series={}
def configure_rates(rate_frame):
    global series
    series={"SOFR":{c:rate_frame[c].dropna() for c in rate_frame}}
    compound.cache_clear()

class CubicSpline:
    def __init__(self,x,y,bc_type='natural'):
        assert bc_type=='natural'
        self.x=np.array(x,dtype=float);self.y=np.array(y,dtype=float);h=np.diff(self.x);n=len(x)
        matrix=np.zeros((n,n));rhs=np.zeros(n);matrix[0,0]=1;matrix[-1,-1]=1
        for j in range(1,n-1):
            matrix[j,j-1]=h[j-1];matrix[j,j]=2*(h[j-1]+h[j]);matrix[j,j+1]=h[j]
            rhs[j]=6*((self.y[j+1]-self.y[j])/h[j]-(self.y[j]-self.y[j-1])/h[j-1])
        self.second=np.linalg.solve(matrix,rhs)
        assert np.max(np.abs(self(self.x)-self.y))<1e-12
    def __call__(self,t):
        t=np.asarray(t);i=np.clip(np.searchsorted(self.x,t,side='right')-1,0,len(self.x)-2);h=self.x[i+1]-self.x[i]
        a=(self.x[i+1]-t)/h;b=(t-self.x[i])/h
        return a*self.y[i]+b*self.y[i+1]+((a**3-a)*self.second[i]+(b**3-b)*self.second[i+1])*h*h/6

def asof(g,col,date):
    s=series[g][col];i=s.index.searchsorted(date,side='right')-1
    if i<0:return np.nan,None
    return float(s.iloc[i])/100,s.index[i]

def discount(y,t):return np.power(1+y/2,-2*np.asarray(t))

@lru_cache(maxsize=200000)
def compound(g,start,end):
    if end==start:return 0.0
    s=series[g]['Floating'];ix=s.index;first=ix.searchsorted(start,side='right')-1;last=ix.searchsorted(end,side='left')
    assert first>=0
    factor=1.0
    for j in range(first,last):
        a=max(start,ix[j]);b=min(end,ix[j+1] if j+1<len(ix) else end)
        days=(b-a).days
        if days:factor*=1+float(s.iloc[j])/100*days/360
    return factor-1

def setup_trade(trade):
    g=trade['Regime'];date=trade['EntryDate'];T=trade['Maturity'];ust=[];irs=[];ages=[];ustnodes=[]
    for n in [7,10,20,30]:
        a,ad=asof(g,f'UST_{n}yrs',date)
        if np.isfinite(a):
            age=(date-ad).days
            if age<=7:ustnodes.append(n);ust.append(a);ages.append(age)
        c=f'IRS_{n}yrs_SOFR' if g=='SOFR' else f'IRS_{n}y_LIBOR';b,bd=asof(g,c,date)
        assert np.isfinite(b) and (date-bd).days<=7,(g,date,c)
        irs.append(b);ages.append((date-bd).days)
    assert ustnodes in [[7,10,20,30],[7,10,30]],(g,date,ustnodes)
    if g=='SOFR':assert ustnodes==[7,10,20,30]
    tc=CubicSpline(ustnodes,ust,bc_type='natural');sc=CubicSpline([7,10,20,30],irs,bc_type='natural')
    yt=float(tc(T));k=float(sc(T));payments=pd.DatetimeIndex([date+pd.DateOffset(months=6*j) for j in range(1,T*2+1)])
    # Timestamp.value is nanoseconds while DatetimeIndex.asi8 may be microseconds.
    # Subtract timestamps directly so payment accruals are independent of storage units.
    daylength=np.array([(b-a).days for a,b in zip([date]+list(payments[:-1]),payments)],dtype=float);tt=(payments-date).days.values/365.25
    assert (daylength>0).all() and (daylength<190).all(),(date,daylength)
    at=daylength/365.25;ass=daylength/360
    ds=discount(k*365.25/360,tt);ann=float(ass@ds)
    d=discount(yt,tt);coupon=(1-d[-1])/float(at@d)
    cash=coupon*at;cash[-1]+=1
    treasury_dv01=float(cash@(discount(yt-.0001,tt)-discount(yt+.0001,tt)))/2
    swap_dv01=ann*.0001
    nt=1/treasury_dv01;ns=1/swap_dv01
    assert coupon>0 and treasury_dv01>0 and swap_dv01>0 and nt>0 and ns>0,(date,coupon,treasury_dv01,swap_dv01)
    trade.update({'EntryUST':yt,'EntryIRS':k,'TreasuryCoupon':coupon,'TreasuryNotionalPerDV01':nt,'SwapNotionalPerDV01':ns,'USTNodes':','.join(map(str,ustnodes)),'ReducedUSTCurve':ustnodes==[7,10,30],'MaxQuoteAgeDays':max(ages),'EntryTreasuryDV01PerNotional':treasury_dv01,'EntrySwapDV01PerNotional':swap_dv01})
    return tc,sc,yt,k,payments,cash,nt,ns

def marks(trade,setup,date,spread):
    tc,sc,yt,k,payments,cash,nt,ns=setup;days=(date-trade['EntryDate']).days;side=trade['Direction'];h=days/365.25
    market=side*(spread-trade['EntrySpread'])
    funding=compound(trade['Regime'],trade['EntryDate'],date)
    floating=funding
    coupons=nt*trade['TreasuryCoupon']*days/365.25;fund=-nt*funding;recv=ns*floating;fixed=-ns*k*days/360
    carry=side*(coupons+fund+recv+fixed)
    remain=trade['Maturity']-h;yr=float(tc(remain));kr=float(sc(remain))
    alive=payments>date;p=payments[alive];ct=cash[alive];tt=(p-date).days.values/365.25
    tr=nt*float(ct@(discount(yr,tt)-discount(yt,tt)))
    accr=np.array([(b-a).days for a,b in zip([date]+list(p[:-1]),p)],dtype=float)/360
    assert (accr>0).all() and (accr<.53).all(),(date,accr)
    a=float(accr@discount(kr*365.25/360,tt))
    sr=ns*(kr-k)*a;roll=side*(tr+sr)
    return {'Market':market,'Carry':carry,'Rolldown':roll,'TreasuryCouponCarry':side*coupons,'TreasuryFundingCarry':side*fund,'SwapFloatingCarry':side*recv,'SwapFixedCarry':side*fixed,'TreasuryRolldown':side*tr,'SwapRolldown':side*sr,'RolledUST':yr,'RolledIRS':kr}
