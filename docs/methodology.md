# Methodology

## Regression and signal

For each spread/basis pair, estimate:

$$s_t = \alpha + \beta_b b_t + \beta_m MOVE_t + \varepsilon_t$$

Here, $s_t$ is the original 10-year or 30-year swap-spread observation in basis points. The selected cross-currency basis and MOVE are explanatory variables. The model includes an intercept.

At signal close $t$, R1, R2 and R3 use the preceding one, two or three calendar years. The lower date boundary is included and the signal date is excluded. Each fit uses complete observations for that particular model. The coefficients and residual standard error are recalculated at every eligible close.

With three estimated coefficients, the residual standard error is:

$$\hat\sigma_t = \sqrt{\frac{\sum_{i\in W_t}\hat\varepsilon_i^2}{n_t-3}}$$

The current deviation is:

$$z_t = \frac{s_t-\hat s_t}{\hat\sigma_t}$$

This compares the current spread with a conditional fitted value. It is not a direct forecast of the next day's spread change.

## Orders and exits

| Position at the signal close | Condition | Order |
| --- | --- | --- |
| Flat | $z_t \leq -1$ | Enter long spread |
| Flat | $z_t \geq +1$ | Enter short spread |
| Long spread | $z_t \geq 0$ | Exit |
| Short spread | $z_t \leq 0$ | Exit |

Orders execute at the next recorded close with an original spread quote. Pending orders execute before that close's new signal is evaluated. There is at most one position in each model. An exit can be followed by a new entry signal for the following close, without an immediate reversal at the same close.

If a predictor is missing, the model generates no new signal. Existing positions are still marked and a pending order can execute if the spread quote is available. In particular, the missing EUR 5-year basis observation on 20 March 2026 does not remove that day's spread mark.

The last recorded SOFR close is 3 September 2026. Any remaining position is marked at that close. It is not counted as a completed trade.

## Position and market P&L

A long spread is a long Treasury and a pay-fixed, receive-floating swap. A short reverses both legs. Each trade starts with equal absolute money DV01 on the two legs. Both notionals remain fixed over the trade.

Market P&L uses the original swap-spread series:

$$P\&L_{market} = d(s_{mark}-s_{entry})$$

Here, $d$ is +1 for long spreads and -1 for short spreads. The result is in basis points per unit of matched entry spread DV01. The market component is not replaced with IRS minus Treasury quotes from the rates workbook. Basis and MOVE are not traded hedges.

## Carry

The attribution uses a hypothetical par Treasury with a semiannual schedule and ACT/365.25 coupon accrual. Swap fixed accrual uses ACT/360. The Treasury coupon is chosen to price the bond at par under the entry yield approximation.

For SOFR trades, the observed **SOFRRATE** column supplies both the floating receipt and generic Treasury funding proxies. Rate quotes are divided by 100 before use. Fixings compound over their covered calendar-day intervals using ACT/360, including weekends and holidays. The compounding spans the actual holding period. These are attribution estimates rather than a reconstruction of settled coupon cash flows.

The long-spread carry estimate is Treasury coupon accrual, less Treasury funding, plus swap floating receipts, less swap fixed payments. A short reverses these amounts. SOFR fixings observed during a trade are used after the fact for P&L attribution, not for entry or exit signals.

The discounting and DV01 calculations use flat-yield approximations at each quoted maturity. They do not bootstrap full instrument-specific zero curves.

## Rolldown

Freeze the Treasury and IRS curves at trade entry. At each subsequent mark, reduce maturity by actual calendar days divided by 365.25 and interpolate the frozen curves with natural cubic splines through 7-, 10-, 20- and 30-year quotes.

Treasury rolldown compares the remaining cash flows valued at the shortened-maturity frozen-curve yield with their value at the unchanged entry yield. Swap rolldown uses the change in the interpolated IRS par rate and the remaining fixed-leg annuity. Daily rolldown P&L is the change in the cumulative estimate from entry.

The known mis-mapped 5-year IRS quote is excluded. The 2-year and 5-year labels in the current results refer to the basis predictor, while the traded spreads remain 10-year and 30-year.

The marked gross P&L used in the return calculation is:

$$P\&L_{gross} = P\&L_{market} + Carry + Rolldown$$

The market component follows a constant-maturity spread series. Carry and rolldown are added under the study's modeling conventions, so the total should be read as a modeled spread strategy result rather than executable instrument cash P&L.

## Capital, leverage and reinvestment

Each model and leverage setting starts with a capital index of 100. At entry, the absolute Treasury notional equals the leverage multiple times available account capital. The matched money DV01 is:

$$DV01_{money} = \frac{L\,C_{entry}}{N_{Treasury\ per\ DV01}}$$

The same money DV01 scales daily signed market, carry and rolldown changes for the entire trade. It is fixed across month-end. The next trade is sized from the updated capital. Monthly returns are therefore not obtained by multiplying the 1x monthly series by the leverage multiple.

There is no additional interest on idle account cash. The gross version includes the baseline funding already in carry and adds no bid/offer, haircut or swap margin costs.

## Trading cost and Treasury haircut

The cost-adjusted results use the same signal sequence as the gross version, subject to stopping when account capital is exhausted. They charge 0.25 bp per unit of matched spread DV01 at entry and another 0.25 bp at exit. A position still open at the final close incurs only its entry cost. Capital-exhaustion liquidation incurs the exit half as well.

The repo assumption funds 99% of the absolute Treasury notional at SOFR and the remaining 1% at SOFR + 5 bp. Since baseline funding already charges SOFR on the full notional, the incremental haircut cost is:

$$Cost_{haircut} = 0.01\,N_T\,[F_{SOFR+5bp}-F_{SOFR}]$$

Each $F$ is the compounded holding-period factor using the observed SOFR fixing intervals and ACT/360. The haircut cost is applied to absolute Treasury notional for both directions. A haircut is collateral support rather than a 1% trading loss.

Costs reduce the capital available at the next trade entry. The cost-adjusted account paths are simulated with this reinvestment effect, rather than deducting a single cost estimate from the final gross return.

## Reporting periods and stopping rules

Monthly return is closing capital divided by opening capital minus one. Cumulative and calendar-year returns compound the eligible monthly growth factors. First and final months are partial. Calendar-year tables label the dates actually covered.

Stop an account at its first nonpositive recorded capital close. Keep the actual closing deficit, even when the resulting loss exceeds 100%. Later returns are unavailable, and the account does not restart. Cumulative plots stop at that date. This stopping convention is separate from the swap margin constraints described below.

For fixed-DV01 P&L, drawdown is measured from the daily adjusted marked equity path beginning at zero. For capital-return reports, drawdown is measured from daily account capital beginning at 100. Trade win rates and average holding sessions use completed trades only. Open positions contribute to marked P&L but not to wins or losses.

## Earlier LIBOR and 1-year basis work

The broader analysis contained 72 rolling specifications: SOFR and LIBOR, 10-year and 30-year spreads, GBP and EUR basis at 1-, 2- and 5-year tenors, and three regression windows. The current result folders retain the 24 SOFR specifications using 2-year and 5-year basis inputs.

LIBOR first eligible signals were 4 May 2012 for R1, 6 May 2013 for R2 and 5 May 2014 for R3. Its stated end date was 12 December 2021, with final marks at the last recorded close, 10 December 2021.

The LIBOR carry proxy used observed 3-month LIBOR for floating receipts, fixed at entry and at unadjusted three-month reset dates, with ACT/360 accrual. Treasury funding used a generic compounded LIBOR proxy. Before the 20-year Treasury quote was available, the approved rolldown fallback used the observed 7-, 10- and 30-year Treasury quotes and flagged those reduced curves.

## Margin and statistical extensions

Separate margin scenarios added swap initial margin and variation-margin funding to the trading cost and repo assumptions. The modeled base initial margin was 5% of swap notional for 10-year swaps and 10% for 30-year swaps. These were analysis assumptions, not exchange margin quotations. The borrowing case used account capital first and then a facility capped at 100% of starting capital, priced at SOFR + 50 bp. A cash-only comparison removed that borrowing facility for the four selected 10-year basis families.

Margin limits could reject an entry or close a position early. That changes the executed trades, so the difference from a gross backtest can include changes in market exposure as well as financing charges. The gross and cost-adjusted datasets included here impose no swap margin constraint.

The later 10-year reports also calculated risk statistics using average 3-month Treasury bill yields over the respective R1, R2 and R3 evaluation periods. First and final regression fits were reported with Newey-West HAC standard errors. The covariance calculation used Bartlett weights, $\lfloor4(n/100)^{2/9}\rfloor$ lags and an $n/(n-3)$ correction. The t-tests used an approximate Student-t reference with $n-3$ degrees of freedom. Those regression statistics describe the training fits.

The included monthly-return script does not rerun these extensions.

## Validation

Trading signals use only earlier observations for each regression fit and execute at a later recorded close. They form rolling out-of-sample backtests. Previously tested observations can later enter a training window, which is part of the rolling procedure.

The evaluation periods and candidate models were already explored. Picking a preferred specification after reviewing the results can still introduce selection bias. Cost and leverage variants reuse the same history and do not supply independent holdout samples. Significant regression coefficients or positive trading P&L alone do not establish cointegration.

Method references: [Bailey et al., The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf), [New York Fed reference-rate conventions](https://www.newyorkfed.org/markets/reference-rates/additional-information-about-reference-rates), and [statsmodels HAC covariance documentation](https://www.statsmodels.org/stable/generated/statsmodels.stats.sandwich_covariance.cov_hac.html). The numerical choices above describe this analysis.
