# Reading the results

The saved results cover 24 SOFR strategies and four leverage levels under gross and cost-adjusted assumptions. R1 begins on 22 February 2022, R2 on 21 February 2023 and R3 on 21 February 2024. The planned final close is 3 September 2026.

## Monthly and account tables

Each case contains `monthly_returns.csv`, `account_summary.csv` and `calendar_year_returns.csv`. The common monthly grid has 5,376 rows, including months before a strategy starts and months after an account exhausts its capital. There are 3,937 numeric monthly returns in each case.

Returns are decimals. Capital and P&L amounts use a starting capital index of 100. A blank return before inception means the account has not started. A blank after capital exhaustion means trading has stopped. The `Status` field distinguishes them from a real zero-return month.

`MarketPnL`, `CarryPnL` and `RolldownPnL` sum to the gross capital change. The cost-adjusted case also reports `HaircutFundingCost` and `TradingCost`, which are subtracted. `PartialMonth` identifies the first, final or shortened stopping month. Calendar returns compound available monthly returns, with the dates shown in each row.

`account_summary.csv` records final capital, cumulative return, the final recorded close and any capital-exhaustion date. Six accounts stop early in each case: two at 20x and four at 30x. They are all 30-year R1 accounts. A surviving account's positive return does not imply that another leverage level follows the same path.

`cagr_10x.csv` supplies the README's annualized-return table. It uses the actual account dates and capital values. A displayed 0.00% is rounded, not a claim of an exactly zero return.

## Strategy and trade tables

`strategy_summary.csv` reports the underlying strategy in basis points per unit of matched spread DV01, before capital scaling. It includes market P&L, carry, rolldown, drawdown and trade counts. Its drawdown is in those fixed-DV01 P&L units, not a percentage loss on an account.

`trades.csv` gives the 323 strategy trades, their signal and execution dates, original spread changes, matched notionals and carry/rolldown components. These trades are shared across leverage levels in this version; account sizing and capital exhaustion are simulated separately.

Running the backtest creates the full daily records under `results/generated/`, including regression fits, daily strategy marks, daily account capital and account-level trade returns. Those larger files are generated locally rather than stored alongside the final monthly tables.

## Interpretation

The results describe the chosen historical rule and modeled execution costs. The reference spread can change when the regression refits, so an exit need not mean that the observed spread returned to an unchanged equilibrium.

Different strategies share dates, instruments and predictors. Adding their P&Ls would require an explicit portfolio allocation and funding model. This repository evaluates the accounts separately.
