"""Simulate gross and cost-adjusted accounts with fixed sizing within each trade."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from functools import lru_cache
import csv,json,math,bisect
import numpy as np
import pandas as pd

def run_capital(daily_records,trade_records,rate_frame,output_dir,with_costs=False,reference_dir=None):
    cost_case=with_costs
    D=Path(output_dir)
    D.mkdir(parents=True,exist_ok=True)
    reference_dir=Path(reference_dir) if reference_dir is not None else None
    families = [f'SOFR_{m}Y_{c}{t}Y' for m in [10, 30] for c in ['GBP', 'EUR'] for t in [2, 5]]
    models = [f'{f}_R{r}' for f in families for r in [1, 2, 3]]
    levels = [1, 10, 20, 30]
    months = [str(x.date()) for x in pd.date_range('2022-02-01', '2026-09-01', freq='MS')]
    settings = {'RoundtripBp': .5, 'EntryBp': .25, 'ExitBp': .25, 'Haircut': .01, 'FundingPremium': .0005, 'DayBasis': 360} if cost_case else None
    if cost_case:
        fixings=sorted((pd.Timestamp(day),float(value)/100)
                       for day,value in rate_frame.Floating.dropna().items())
        fixdates=[x[0] for x in fixings]
        assert len(set(fixdates))==len(fixdates)
        @lru_cache(None)
        def factors(start,end):
            i = bisect.bisect_right(fixdates,start)-1
            assert i >= 0 and start <= end <= fixdates[-1]
            base = funded = 1.0
            cursor = start
            while cursor < end:
                nextdate = min(end, fixdates[i+1] if i+1 < len(fixdates) else end)
                fraction = (nextdate-cursor).days/settings['DayBasis']
                base *= 1 + fixings[i][1]*fraction
                funded *= 1 + (fixings[i][1]+settings['FundingPremium'])*fraction
                cursor = nextdate
                i += 1
            return base-1, funded-1
    daily,trades=defaultdict(list),defaultdict(dict)
    for row in daily_records:
        if row["Model"] in models:
            daily[row["Model"]].append({
                "Date":pd.Timestamp(row["Date"]),"Trade":row["Trade"] or None,
                "Market":row["MarketChange"],"Carry":row["CarryChange"],
                "Roll":row["RolldownChange"],
            })
    for row in trade_records:
        if row["Model"] in models:
            trades[row["Model"]][row["Trade"]]={
                "Entry":pd.Timestamp(row["EntryDate"]),"End":pd.Timestamp(row["EndDate"]),
                "Status":row["Status"],"TreasuryNotionalPerDV01":row["TreasuryNotionalPerDV01"],
                "SwapNotionalPerDV01":row["SwapNotionalPerDV01"],
                "Market":row["Market"],"Carry":row["Carry"],"Roll":row["Rolldown"],
                "TreasuryFunding":row["TreasuryFundingCarry"],
            }
    assert set(daily)==set(models) and set(trades)==set(models)
    marks, accounts, calendar, audits, trade_ledger = [], [], [], [], []
    max_trade_bp_error = 0
    cost_bp = {}
    capital_daily=[]
    capital_trades=[]
    for mid in models:
        source = sorted(daily[mid], key=lambda x: x['Date'])
        assert source[0]['Date'] == datetime.fromisoformat({1: '2022-02-22', 2: '2023-02-21', 3: '2024-02-21'}[int(mid[-1])])
        assert source[-1]['Date'] == datetime(2026, 9, 3)
        for tid, t in trades[mid].items():
            td = [r for r in source if r['Trade'] == tid]
            assert td[0]['Date'] == t['Entry'] and td[-1]['Date'] == t['End']
            for k in ['Market', 'Carry', 'Roll']:
                error = abs(math.fsum(r[k] for r in td) - t[k])
                max_trade_bp_error = max(max_trade_bp_error, error)
                assert error < 1e-8, (mid, tid, k, error)
            if cost_case:
                f0, f1 = factors(t['Entry'],t['End'])
                assert abs(abs(t['TreasuryFunding'])-t['TreasuryNotionalPerDV01']*f0) < 1e-8
                previous = 0.0
                for day in td:
                    f0, f1 = factors(t['Entry'],day['Date'])
                    cumulative_hc = settings['Haircut']*t['TreasuryNotionalPerDV01']*(f1-f0)
                    haircut_bp = cumulative_hc - previous
                    assert haircut_bp >= -1e-10
                    previous = cumulative_hc
                    fee_bp = settings['EntryBp']*int(day['Date']==t['Entry']) + settings['ExitBp']*int(t['Status']=='Completed' and day['Date']==t['End'])
                    cost_bp[(mid,day['Date'])] = (haircut_bp, fee_bp)
                assert abs(sum(cost_bp[(mid,d['Date'])][0] for d in td)-cumulative_hc) < 1e-8
        for L in levels:
            capital = 100.0
            records, sizes, entry_capital = [], {}, {}
            for day in source:
                tid = day['Trade']
                opening = capital
                if tid:
                    t = trades[mid][tid]
                    if tid not in sizes:
                        assert day['Date'] == t['Entry'] and opening > 0
                        entry_capital[tid] = opening
                        sizes[tid] = L * opening / t['TreasuryNotionalPerDV01']
                    scale = sizes[tid]
                else:
                    scale = 0.0
                    assert max(abs(day[k]) for k in ['Market', 'Carry', 'Roll']) < 1e-9
                parts = np.array([day[k] for k in ['Market', 'Carry', 'Roll']]) * scale
                hc_bp, fee_bp = cost_bp.get((mid,day['Date']), (0.0,0.0))
                hc_cost, fee_cost = hc_bp*scale, fee_bp*scale
                capital += float(parts.sum()) - hc_cost - fee_cost
                normal_exit = bool(tid and t['Status']=='Completed' and day['Date']==t['End'])
                forced_exit = settings['ExitBp']*scale if cost_case and capital<=0 and tid and not normal_exit else 0.0
                fee_cost += forced_exit
                capital -= forced_exit
                records.append({'Date': day['Date'], 'Trade': tid, 'Opening': opening, 'Closing': capital,
                                'Market': float(parts[0]), 'Carry': float(parts[1]), 'Roll': float(parts[2]),
                                'MarketBp': day['Market'], 'CarryBp': day['Carry'], 'RollBp': day['Roll'],
                                'Haircut': hc_cost, 'Trading': fee_cost, 'HaircutBp': hc_bp,
                                'TradingBp': fee_bp+(forced_exit/scale if forced_exit else 0.0), 'ForcedExit': forced_exit})
                if capital <= 0:
                    break
            exhausted = capital <= 0
            assert all(r['Closing'] > 0 for r in records[:-1])
            independent = 100.0
            grouped_trade = defaultdict(list)
            for r in records:
                if r['Trade']:
                    grouped_trade[r['Trade']].append(r)
            for tid, group in grouped_trade.items():
                t = trades[mid][tid]
                assert abs(independent - entry_capital[tid]) < 1e-7
                before_trade_capital = independent
                bp = math.fsum(math.fsum(r[k] for r in group) for k in ['MarketBp', 'CarryBp', 'RollBp'])
                bp -= math.fsum(r['HaircutBp']+r['TradingBp'] for r in group)
                independent *= 1 + L * bp / t['TreasuryNotionalPerDV01']
                assert abs(independent - group[-1]['Closing']) < 1e-7
                if cost_case:
                    complete = t['Status']=='Completed' and group[-1]['Date']==t['End']
                    trading_bp = math.fsum(r['TradingBp'] for r in group)
                    expected_fee = settings['RoundtripBp'] if complete or exhausted and group[-1]['Date']==records[-1]['Date'] else settings['EntryBp']
                    assert abs(trading_bp-expected_fee)<1e-9
                    trade_ledger.append({'Model': mid, 'Leverage': L, 'Trade': tid, 'Entry': str(t['Entry'].date()),
                        'End': str(group[-1]['Date'].date()), 'EntryCapital': before_trade_capital, 'FinalCapital': independent,
                        'MoneyDV01': sizes[tid], 'NetBp': bp, 'TradingBp': trading_bp,
                        'HaircutBp': math.fsum(r['HaircutBp'] for r in group), 'Status': 'Completed' if complete else 'Stopped' if exhausted else 'Open'})
            assert abs(independent-capital) < 1e-7
            peak=100.0
            for record in records:
                peak=max(peak,record['Closing'])
                tid=record['Trade']
                units=sizes[tid] if tid else 0.0
                capital_daily.append({
                    'Model':mid,'Leverage':L,'Date':str(record['Date'].date()),'Trade':tid,
                    'OpeningCapital':record['Opening'],'ClosingCapital':record['Closing'],
                    'DailyReturn':record['Closing']/record['Opening']-1,
                    'MoneyDV01PerBp':units,
                    'MarketPnL':record['Market'],'CarryPnL':record['Carry'],'RolldownPnL':record['Roll'],
                    'HaircutFundingCost':record['Haircut'],'TradingCost':record['Trading'],
                    'ForcedExitCost':record['ForcedExit'],'PeakCapital':peak,
                    'DrawdownPct':(peak-record['Closing'])/peak,
                })
            for tid,group in grouped_trade.items():
                t=trades[mid][tid]
                completed=t['Status']=='Completed' and group[-1]['Date']==t['End']
                status='Completed' if completed else 'Stopped: capital exhausted' if exhausted else 'Open at final close'
                capital_trades.append({
                    'Model':mid,'Leverage':L,'Trade':tid,'Status':status,
                    'EntryDate':str(t['Entry'].date()),'EndDate':str(group[-1]['Date'].date()),
                    'EntryCapital':entry_capital[tid],'ClosingCapital':group[-1]['Closing'],
                    'MoneyDV01PerBp':sizes[tid],'HoldingSessions':len(group)-1,
                    'HoldingDays':(group[-1]['Date']-t['Entry']).days,
                    'MarketPnL':math.fsum(r['Market'] for r in group),
                    'CarryPnL':math.fsum(r['Carry'] for r in group),
                    'RolldownPnL':math.fsum(r['Roll'] for r in group),
                    'HaircutFundingCost':math.fsum(r['Haircut'] for r in group),
                    'TradingCost':math.fsum(r['Trading'] for r in group),
                    'TradePnL':group[-1]['Closing']-entry_capital[tid],
                    'TradeReturn':group[-1]['Closing']/entry_capital[tid]-1,
                })
            account = {'Model': mid, 'Leverage': L, 'FirstClose': str(source[0]['Date'].date()),
                'FinalClose': str(records[-1]['Date'].date()), 'PlannedFinalClose': '2026-09-03',
                'FinalCapital': capital, 'CumulativeReturn': capital/100-1,
                'Status': 'Capital exhausted' if exhausted else 'Full period', 'ExhaustionDate': str(records[-1]['Date'].date()) if exhausted else None}
            if cost_case:
                account['HaircutCost'] = math.fsum(r['Haircut'] for r in records)
                account['TradingCost'] = math.fsum(r['Trading'] for r in records)
            accounts.append(account)
            active, planned = defaultdict(list), defaultdict(list)
            for r in records:
                active[r['Date'].strftime('%Y-%m-01')].append(r)
            for r in source:
                planned[r['Date'].strftime('%Y-%m-01')].append(r)
            growth = 1.0
            for month in months:
                if month not in planned:
                    continue
                rows = active[month]
                p = planned[month]
                mark = {'Model': mid, 'Leverage': L, 'Month': month, 'Opening': None, 'Market': None,
                    'Carry': None, 'Roll': None, 'Haircut': None, 'Trading': None, 'Closing': None, 'Return': None, 'Cumulative': None,
                    'FirstClose': str(rows[0]['Date'].date()) if rows else None,
                    'LastClose': str(rows[-1]['Date'].date()) if rows else None,
                    'Status': 'After capital exhaustion' if not rows else ('Capital exhausted' if rows[-1]['Closing']<=0 else 'Available'),
                    'Partial': bool(month in [source[0]['Date'].strftime('%Y-%m-01'), '2026-09-01'] or (rows and len(rows)<len(p))),
                    'Sessions': len(rows), 'PlannedSessions': len(p)}
                if rows:
                    mark.update(Opening=rows[0]['Opening'], Closing=rows[-1]['Closing'],
                        Market=math.fsum(r['Market'] for r in rows), Carry=math.fsum(r['Carry'] for r in rows), Roll=math.fsum(r['Roll'] for r in rows),
                        Haircut=math.fsum(r['Haircut'] for r in rows), Trading=math.fsum(r['Trading'] for r in rows))
                    mark['Return'] = mark['Closing']/mark['Opening']-1
                    assert abs(mark['Opening'] + mark['Market'] + mark['Carry'] + mark['Roll'] - mark['Haircut'] - mark['Trading'] - mark['Closing']) < 1e-7
                    growth *= 1+mark['Return']
                    mark['Cumulative'] = growth-1
                    assert abs(growth - mark['Closing']/100) < 1e-9
                marks.append(mark)
            assert abs(growth-capital/100) < 1e-9
            for year in range(2022, 2027):
                yr = [r for r in marks if r['Model']==mid and r['Leverage']==L and r['Month'].startswith(str(year)) and r['Return'] is not None]
                unavailable = year > int(account['FinalClose'][:4])
                cy = {'Model': mid, 'Leverage': L, 'Year': year, 'Return': None, 'Status': 'After exhaustion' if unavailable else 'Not started', 'FirstClose': None, 'LastClose': None}
                if yr:
                    cy.update(Return=math.prod(1+r['Return'] for r in yr)-1,
                        FirstClose=yr[0]['FirstClose'], LastClose=yr[-1]['LastClose'], Status='Full year')
                    if cy['FirstClose'][:4] == account['FirstClose'][:4]:
                        cy['Status'] = f"From {account['FirstClose']}"
                    if cy['LastClose'] == account['FinalClose']:
                        cy['Status'] = f"To {account['FinalClose']}" + ('; exhausted' if exhausted else '')
                calendar.append(cy)
            audits.append({'Model': mid, 'Leverage': L, 'DailyVsTradeFinalError': abs(independent-capital),
                           'MonthlyVsDailyFinalError': abs(growth-capital/100),
                           'DailyRecords': len(records)})


    assert len(accounts) == 96 and len(calendar) == 480 and len(marks) == 4224

    # Export the full common month grid, including pre-start and exhausted months.
    mark_map = {(r['Model'],r['Leverage'],r['Month']):r for r in marks}
    monthly_csv = []
    for mid in models:
        for L in levels:
            for month in months:
                row = mark_map.get((mid,L,month))
                item = {
                    'Model':mid,'Leverage':L,'Month':month,
                    'Status':row['Status'] if row else 'Not started',
                    'MonthlyReturn':row['Return'] if row else None,
                    'CumulativeReturn':row['Cumulative'] if row else None,
                    'OpeningCapital':row['Opening'] if row else None,
                    'ClosingCapital':row['Closing'] if row else None,
                    'MarketPnL':row['Market'] if row else None,
                    'CarryPnL':row['Carry'] if row else None,
                    'RolldownPnL':row['Roll'] if row else None,
                    'FirstClose':row['FirstClose'] if row else None,
                    'LastClose':row['LastClose'] if row else None,
                    'PartialMonth':row['Partial'] if row else False,
                    'IncludedSessions':row['Sessions'] if row else 0,
                    'PlannedSessions':row['PlannedSessions'] if row else 0,
                }
                if cost_case:
                    item.update(HaircutFundingCost=row['Haircut'] if row else None,
                                TradingCost=row['Trading'] if row else None)
                monthly_csv.append(item)

    audit_map = {(r['Model'],r['Leverage']):r for r in audits}
    account_csv = []
    for row in accounts:
        item = dict(Model=row['Model'],Leverage=row['Leverage'],FirstClose=row['FirstClose'],
            LastClose=row['FinalClose'],PlannedLastClose=row['PlannedFinalClose'],
            Status=row['Status'],ExhaustionDate=row['ExhaustionDate'],
            FinalCapital=row['FinalCapital'],CumulativeReturn=row['CumulativeReturn'])
        if cost_case:
            item.update(HaircutFundingCost=row['HaircutCost'],TradingCost=row['TradingCost'])
        else:
            item['TradeCapitalError'] = audit_map[row['Model'],row['Leverage']]['DailyVsTradeFinalError']
        account_csv.append(item)

    annual_csv = []
    for row in calendar:
        status = row['Status'].replace('After exhaustion','After capital exhaustion')
        if not cost_case:
            status = status.replace('; exhausted','; capital exhausted')
        annual_csv.append(dict(Model=row['Model'],Leverage=row['Leverage'],Year=row['Year'],
            CalendarReturn=row['Return'],FirstClose=row['FirstClose'],LastClose=row['LastClose'],Status=status))

    tables = {
        'account_summary.csv':(account_csv,('Model','Leverage')),
        'monthly_returns.csv':(monthly_csv,('Model','Leverage','Month')),
        'calendar_year_returns.csv':(annual_csv,('Model','Leverage','Year')),
    }
    numeric = {
        'Leverage','Year','FinalCapital','CumulativeReturn','TradeCapitalError',
        'MonthlyReturn','CalendarReturn','OpeningCapital','ClosingCapital',
        'MarketPnL','CarryPnL','RolldownPnL','IncludedSessions','PlannedSessions',
        'HaircutFundingCost','TradingCost',
    }
    checks = 0
    max_return_error = 0.0
    max_capital_error = 0.0
    if reference_dir:
        for filename,(rows,key_fields) in tables.items():
            def key(r):
                return tuple(str(r[k]) for k in key_fields)
            with (reference_dir/filename).open(encoding='utf-8-sig',newline='') as handle:
                expected = list(csv.DictReader(handle))
            actual_map = {key(r):r for r in rows}
            assert len(actual_map)==len(rows)==len(expected),filename
            assert set(actual_map)=={key(r) for r in expected},filename
            for wanted in expected:
                actual = actual_map[key(wanted)]
                for field,value in wanted.items():
                    got = actual[field]
                    label = f"{filename}, {key(wanted)}, {field}"
                    if value == '':
                        assert got is None or got == '',(label,got,value)
                    elif field in numeric:
                        difference = abs(float(got)-float(value))
                        tolerance = 1e-9 if field in {'MonthlyReturn','CumulativeReturn','CalendarReturn'} else 1e-7
                        assert math.isfinite(float(got)) and difference<=tolerance,(label,got,value)
                        if field in {'MonthlyReturn','CumulativeReturn','CalendarReturn'}:
                            max_return_error = max(max_return_error,difference)
                        else:
                            max_capital_error = max(max_capital_error,difference)
                    else:
                        assert str(got)==value,(label,got,value)
                    checks += 1

    for filename,(rows,_) in tables.items():
        with (D/filename).open('w',encoding='utf-8-sig',newline='') as handle:
            writer = csv.DictWriter(handle,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    for filename,rows in (('daily_capital.csv',capital_daily),('trade_capital.csv',capital_trades)):
        with (D/filename).open('w',encoding='utf-8-sig',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    data = dict(Families=families,Levels=levels,Months=months,Marks=marks,Accounts=accounts,
                Calendar=calendar,CostSettings=settings)
    (D/'calculation_records.json').write_text(json.dumps(data,allow_nan=False),encoding='utf-8')
    counts = {str(L):sum(a['Leverage']==L and a['Status']=='Capital exhausted' for a in accounts) for L in levels}
    report = dict(InternalStatus='PASS',ReferenceStatus='PASS' if reference_dir else 'NOT REQUESTED',
        Case='net' if cost_case else 'gross',Accounts=len(accounts),MonthlyRows=len(monthly_csv),
        EligibleMonthlyMarks=len(marks),AvailableMonthlyReturns=sum(r['MonthlyReturn'] is not None for r in monthly_csv),
        CalendarRows=len(annual_csv),ReferenceCellsChecked=checks,
        MaximumReferenceReturnError=max_return_error,MaximumReferenceCapitalError=max_capital_error,
        MaximumSourceTradeBpError=max_trade_bp_error,
        MaximumTradeCapitalError=max(r['DailyVsTradeFinalError'] for r in audits),
        MaximumMonthlyCapitalError=max(r['MonthlyVsDailyFinalError'] for r in audits),
        CapitalExhaustion=counts)
    (D/'verification_report.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    if cost_case:
        (D/'trade_ledger.json').write_text(json.dumps(trade_ledger,allow_nan=False),encoding='utf-8')
        (D/'funding_fixings.json').write_text(json.dumps(
            [{'Date':str(d.date()),'SOFR':r} for d,r in fixings]),encoding='utf-8')
    print(json.dumps(report,indent=2))

    return report
