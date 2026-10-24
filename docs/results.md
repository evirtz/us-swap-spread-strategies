# Reading the results

## What an account represents

An account is one spread maturity, one basis predictor, one regression window and one leverage setting. For example, SOFR_10Y_GBP2Y_R1 at 10x uses the 10-year spread, GBP 2-year basis and the preceding year's observations for each regression fit.

There are eight spread/basis families and three rolling models in each. The four leverage settings give 96 account paths for the gross version and another 96 for the cost-adjusted version. They are overlapping alternatives, not separate assets in a portfolio.

## Periods and units

R1 starts on 22 February 2022, R2 on 21 February 2023 and R3 on 21 February 2024. Their planned final recorded close is 3 September 2026. A cumulative R3 return therefore covers less time than an R1 return. Comparing the two without accounting for the investment horizon can be misleading.

Returns in the CSV files are decimals. A value of 0.02 means 2%. Capital and monetary P&L components use an index with starting capital of 100. The underlying spread P&L records are expressed in basis points per unit of matched entry DV01.

The monthly grid contains 56 calendar months for each account, from February 2022 through September 2026. Blank values before the eligible start have status **Not started**. A zero is a flat month. Blank values after a capital-exhaustion stop have status **After capital exhaustion**. The Excel reports display those later months as **n.a.**

First and final months are partial. The year at a capital-exhaustion stop is also partial. Calendar returns compound the months actually covered and show their first and last recorded closes. They are not annualized estimates.

## Gross and cost-adjusted returns

Gross P&L includes the original-spread market component, estimated carry and estimated rolldown. Baseline carry includes Treasury funding at SOFR.

The cost-adjusted version adds a 0.5 bp completed round trip, split equally between entry and exit, and funds the 1% Treasury haircut at SOFR + 5 bp. Both costs reduce the capital available at the next entry. Open positions at the final close pay only the entry half of the trading cost. Forced capital-exhaustion exits pay the exit half.

The funding and trading cost columns are positive expenses in capital-index units. For each available net monthly row:

~~~text
ClosingCapital = OpeningCapital + MarketPnL + CarryPnL + RolldownPnL
                 - HaircutFundingCost - TradingCost
MonthlyReturn = ClosingCapital / OpeningCapital - 1
~~~

**CarryPnL** remains the baseline carry component. It is not already reduced by the separately reported haircut funding cost.

## Leverage and capital exhaustion

The Treasury entry notional is 1x, 10x, 20x or 30x the account capital at that entry. Money DV01 stays fixed during each trade, including across month-end. Leverage effects therefore reflect the sequence of trades and reinvestment, rather than a multiple of a monthly return series.

Both the gross and cost-adjusted versions stop the following accounts:

| Account | Leverage | Last recorded close |
| --- | ---: | --- |
| SOFR_30Y_GBP2Y_R1 | 20x | 24 October 2022 |
| SOFR_30Y_GBP2Y_R1 | 30x | 27 September 2022 |
| SOFR_30Y_GBP5Y_R1 | 20x | 27 September 2022 |
| SOFR_30Y_GBP5Y_R1 | 30x | 23 September 2022 |
| SOFR_30Y_EUR2Y_R1 | 30x | 27 September 2022 |
| SOFR_30Y_EUR5Y_R1 | 30x | 27 September 2022 |

The actual deficit is retained. Returns can fall below -100%, and no recovery is assumed after the stopping date. These paths use a capital-exhaustion rule rather than the separate swap margin model.

## Verification

The recorded gross reproduction checked 5,376 monthly cells, 5,376 cumulative cells and 480 calendar-year cells, along with the 4,224 eligible monthly capital records. All 96 accounts passed. The cell checks include blanks and unavailable markers, so the counts are larger than the number of numeric returns.

The largest differences in decimal return units were 8.88e-16 for monthly returns, 8.44e-15 for cumulative returns and 7.99e-15 for calendar-year returns. The report records no mismatched cells. Daily P&L was also reconciled to trade totals and monthly capital.

The net calculation was checked independently for all 96 accounts and 3,937 available monthly returns. Every account that survives the full period has a lower final return after costs. The six stopped accounts should be compared with their stopping dates and deficits visible.

These checks establish agreement with the saved calculations. They do not remove uncertainty in the hypothetical instruments, curve interpolation, funding assumptions or already explored model choices.

## Files

| Data | Gross | Cost-adjusted |
| --- | --- | --- |
| Account summaries | [CSV](../results/gross/account_summary.csv) | [CSV](../results/net/account_summary.csv) |
| Monthly and cumulative returns | [CSV](../results/gross/monthly_returns.csv) | [CSV](../results/net/monthly_returns.csv) |
| Calendar-year returns | [CSV](../results/gross/calendar_year_returns.csv) | [CSV](../results/net/calendar_year_returns.csv) |
| Verification evidence | [JSON](../results/gross/verification_report.json) | [JSON](../results/net/verification_report.json) |
