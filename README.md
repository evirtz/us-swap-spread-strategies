# US Swap Spread Strategy

This project tests a trading rule for US Treasury-swap spreads. A rolling regression on cross-currency basis swaps and the MOVE index provides a fitted spread, and the strategy trades large deviations from that fitted value.

The analysis separates changes in the original swap spread from estimated carry and rolldown. It then asks how the returns change when trading costs, repo funding and leverage are included.

## Scope

The results here cover 10-year and 30-year SOFR swap spreads, with GBP and EUR basis at the 2-year and 5-year tenors. Each specification uses three rolling regression windows:

| Window | Training history | First eligible signal |
| --- | --- | --- |
| R1 | Previous calendar year | 22 February 2022 |
| R2 | Previous two calendar years | 21 February 2023 |
| R3 | Previous three calendar years | 21 February 2024 |

All three periods end on 3 September 2026. The eight spread/basis combinations give 24 rolling models. Applying 1x, 10x, 20x and 30x leverage gives 96 separate account paths for each cost assumption.

The wider study also covered LIBOR spreads, 1-year basis inputs, swap margin constraints and regression inference with HAC standard errors. The [methodology](docs/methodology.md) explains where those fit into the analysis.

## Trading rule

At each close, estimate the regression using earlier complete observations. Divide the current residual by the training regression's residual standard error. Go long the spread at -1 or below and short at +1 or above. Exit when the current rolling deviation crosses zero. Orders execute at the next recorded close.

A long spread holds a Treasury and pays fixed on a swap, with equal entry DV01 on the two legs. Basis and MOVE are signal inputs. Positions are sized at entry and held at that size until exit. The next trade is sized from the remaining account capital.

## Results

The table shows cumulative returns at 10x leverage. Each R column covers its own period above, so these are different investment horizons. The first and final calendar years are partial.

| Spread and basis | R1 gross | R1 after costs | R2 gross | R2 after costs | R3 gross | R3 after costs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 10Y / GBP2Y | 22.16% | 13.20% | 8.48% | 3.52% | 15.34% | 12.86% |
| 10Y / GBP5Y | 24.20% | 15.11% | 13.93% | 9.64% | 8.09% | 5.32% |
| 10Y / EUR2Y | 21.23% | 9.56% | 22.23% | 17.17% | 22.42% | 18.85% |
| 10Y / EUR5Y | 10.48% | -1.06% | 20.52% | 15.06% | 8.84% | 6.05% |
| 30Y / GBP2Y | 18.09% | 0.02% | 41.45% | 32.22% | 78.19% | 68.42% |
| 30Y / GBP5Y | -5.68% | -21.00% | 44.96% | 32.22% | 38.49% | 28.52% |
| 30Y / EUR2Y | 18.64% | -1.14% | 62.54% | 50.83% | 62.42% | 52.17% |
| 30Y / EUR5Y | -13.01% | -27.31% | 44.54% | 33.98% | 49.42% | 41.06% |

The cost-adjusted version charges 0.5 bp for a completed round trip and funds a 1% Treasury repo haircut at SOFR + 5 bp. Baseline carry already includes Treasury funding at SOFR, so the haircut calculation adds the incremental funding cost. Swap margin costs are assessed separately.

Leverage increases losses as well as gains. In both versions, two 20x accounts and four 30x accounts exhaust their capital. All six are 30-year R1 models. The files retain the actual loss at the stopping close and leave subsequent returns unavailable.

The [results notes](docs/results.md) explain the units and stopping rules. The [gross](results/gross/) and [cost-adjusted](results/net/) folders contain all leverage levels, monthly returns, calendar-year returns and verification reports.

## Reproducing the gross returns

The Python script starts from the existing trade and daily P&L records in **Swap_Spread_Rolling_Results.xlsx**. It rebuilds the capital paths, monthly returns and calendar-year returns. Its verification option compares them with the gross results workbook.

~~~bash
python -m pip install -r requirements.txt
python scripts/reproduce_sofr_gross_returns.py --source "data/Swap_Spread_Rolling_Results.xlsx" --reference "data/SOFR_Gross_Monthly_Cumulative_Calendar_1x_10x_20x_30x.xlsx" --output-dir "results/generated" --verify
~~~

The input workbooks stay in the local **data/** folder. See [data and reproduction](docs/data.md) for the required files and columns. The script covers the gross return calculation. The regression fitting, carry estimation and cost-adjusted simulation are documented here but are not rerun by that script.

The recorded Excel comparison passed for all 96 accounts, with no mismatched monthly, cumulative or calendar-year return cells. The largest return difference was 8.44e-15 in decimal units. This checks the reproduction against the workbook. It does not independently validate the upstream pricing assumptions.

Run the verification tests from the repository root:

~~~bash
python -m unittest discover -s tests -v
~~~

The tests use temporary workbooks and do not require the analysis inputs. They check that swapped, missing or unexpected model labels fail verification in the monthly, cumulative and calendar-year tables.

## Reading the backtest

Each trading signal is out of sample relative to its rolling regression fit. The evaluation periods and model choices have already been explored, however, so the results are not an untouched final holdout. Selecting a preferred model after reviewing these tables can introduce selection bias.

These are modeled spread returns with estimated carry and rolldown. They do not establish cointegration or a stable equilibrium. The account paths overlap and should be assessed separately rather than added together as independent strategies.
