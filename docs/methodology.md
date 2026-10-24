# Methodology

## Reference spread and signal

For each traded tenor and basis series, the model regresses the original swap spread in basis points on an intercept, the selected basis and MOVE. The training sample contains complete observations in the preceding one, two or three calendar years. It includes the lower date boundary and excludes the signal date.

The signal is the current regression residual divided by the training residual standard error, calculated as the square root of SSE divided by N minus 3. It is not normalized by a separate rolling standard deviation of spreads.

A signal of -1 or lower triggers a long spread; +1 or higher triggers a short. A long exits at zero or higher, and a short exits at zero or lower. The fit changes each day, so a signal can cross zero because the reference moved, the spread moved, or both.

## Execution and missing observations

Orders execute at the next recorded close with an original spread quote. Execution happens before a new signal is considered at that close. Only one position can be open per strategy. Positions still open at the final close are marked there.

A missing basis or MOVE observation prevents a new signal. It does not cancel a previously signaled order or remove an existing spread mark. The missing EUR 5-year basis observation on 20 March 2026 is included in the verification checks.

## Instruments and P&L

A long spread is a long Treasury paired with a pay-fixed, receive-floating swap. Shorts reverse the signs. The two legs have equal money DV01 at entry.

Market P&L comes from the change in the original swap-spread column. Treasury and IRS quotes are used to estimate the legs' notionals, carry and rolldown. They are not used to replace the original spread series with a newly constructed one.

The Treasury is a hypothetical par instrument with semiannual payments. Coupon accrual uses ACT/365.25, and the swap fixed leg uses ACT/360. The observed SOFRRATE fixings determine floating receipts and baseline Treasury funding. Rates quoted as percentages are divided by 100 before compounding over calendar-day intervals using ACT/360.

Carry comprises Treasury coupon accrual, Treasury funding, swap floating receipts and swap fixed payments. Payment-day differences are calculated directly from timestamps to avoid dependence on their internal storage units.

For rolldown, Treasury and IRS curves are frozen at entry. Natural cubic splines interpolate the 7-, 10-, 20- and 30-year quotes. Remaining maturity decreases by elapsed calendar days divided by 365.25. The mis-mapped IRS 5-year column is excluded.

Discounting and DV01 retain the study's flat-yield approximations. This is a modeled backtest rather than a reconstruction of settled cash flows for identified securities.

## Capital and leverage

Each account begins with capital of 100. Treasury entry notional equals the selected leverage times capital at entry. The swap notional is matched by DV01. Money DV01 stays fixed within a trade; profits and losses affect the size of the next trade.

Daily capital combines scaled market P&L, carry and rolldown, less any added costs. Accounts stop at the first nonpositive capital close. The actual deficit is retained, including the exit charge if a cost-adjusted position must be closed. Later returns are unavailable rather than zero.

## Costs

The gross case includes baseline Treasury funding at SOFR within carry. The cost-adjusted case also charges 0.25 bp at entry and 0.25 bp at a completed exit, per unit of matched spread DV01. A final open trade pays only its entry charge.

A 1% repo haircut is funded at SOFR plus 5 bp. The incremental cumulative charge per unit of DV01 is:

```text
0.01 × Treasury notional per DV01
     × (compounded SOFR+5bp factor − compounded SOFR factor)
```

The daily change in that amount is scaled by the trade's fixed money DV01. This avoids charging baseline SOFR funding twice. Swap initial margin, variation-margin constraints and their borrowing facility are excluded. There is no separate idle-cash interest credit.

## Returns

Monthly return equals closing capital divided by opening capital minus one. Cumulative and calendar-year returns compound the relevant monthly returns. First and final months can be partial.

CAGR for an account that completes its period is:

```text
(final capital / 100) ** (365.25 / elapsed calendar days) − 1
```

An exhausted account has no CAGR over the planned full period. R1, R2 and R3 begin on different dates, so their annualized returns are not comparisons over a common sample.
