# SOFR Swap Spread Strategy

This project tests whether cross-currency basis and interest-rate volatility can help identify trading opportunities in US swap spreads. A rolling regression provides a reference spread. The strategy takes a position when the observed spread moves far enough from that reference and exits when the deviation crosses zero.

The backtest starts with two raw Excel workbooks and rebuilds the regressions, trades, market P&L, carry, rolldown and monthly returns. It reports gross returns and returns after bid/offer and repo-haircut funding costs. Swap-margin funding and constraints are outside this version.

## The study

The traded spreads are the 10-year and 30-year SOFR series. Each is paired with GBP or EUR basis at the 2-year or 5-year tenor, with MOVE included in every regression.

| Window | Training history | First eligible signal |
| --- | --- | --- |
| R1 | Previous calendar year | 22 February 2022 |
| R2 | Previous two calendar years | 21 February 2023 |
| R3 | Previous three calendar years | 21 February 2024 |

All periods end on 3 September 2026. There are 24 rolling strategies. Each has its own account at 1x, 10x, 20x and 30x leverage, giving 96 accounts for each cost assumption. These are overlapping strategies, not independent holdings in a combined portfolio.

## How a trade works

At each close, fit the regression to earlier complete observations in the relevant calendar window. The signal is the current residual divided by the training regression's residual standard error, using N minus 3 degrees of freedom.

- Enter a long spread when the signal is -1 or below, and a short spread when it is +1 or above.
- Exit a long when the signal reaches zero or higher, and a short when it reaches zero or lower.
- Execute orders at the next recorded spread close. Keep one position per strategy.

A long spread holds a Treasury and pays fixed on a swap, with equal entry DV01 on the two legs. Basis and MOVE are predictors; neither is traded. Treasury notional at entry equals leverage times account capital. Position size stays fixed during the trade, and the next trade uses the updated capital.

The cost-adjusted case charges 0.5 bp for a completed round trip and funds a 1% Treasury repo haircut at SOFR plus 5 bp. Carry already includes Treasury funding at SOFR, so the haircut charge adds only the incremental cost. The [methodology](docs/methodology.md) explains the pricing and return conventions.

## Results

The table shows annualized returns at **10x leverage**, calculated from account capital over each R period. R1, R2 and R3 cover different evaluation periods.

| Spread and basis | R1 gross | R1 after costs | R2 gross | R2 after costs | R3 gross | R3 after costs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 10Y / GBP2Y | 4.52% | 2.78% | 2.33% | 0.98% | 5.80% | 4.89% |
| 10Y / GBP5Y | 4.90% | 3.16% | 3.76% | 2.64% | 3.12% | 2.07% |
| 10Y / EUR2Y | 4.34% | 2.04% | 5.85% | 4.59% | 8.31% | 7.06% |
| 10Y / EUR5Y | 2.22% | -0.24% | 5.43% | 4.05% | 3.40% | 2.35% |
| 30Y / GBP2Y | 3.74% | 0.00% | 10.32% | 8.23% | 25.62% | 22.86% |
| 30Y / GBP5Y | -1.28% | -5.07% | 11.09% | 8.23% | 13.72% | 10.41% |
| 30Y / EUR2Y | 3.85% | -0.25% | 14.74% | 12.34% | 21.11% | 18.03% |
| 30Y / EUR5Y | -3.03% | -6.80% | 10.99% | 8.64% | 17.18% | 14.55% |

At higher leverage, some accounts lose their capital before the sample ends: two at 20x and four at 30x in both cases. All six are 30-year R1 accounts. The calculation retains the loss at the stopping close and leaves later returns unavailable.

The [gross](results/gross/) and [cost-adjusted](results/net/) folders contain every account, monthly return and calendar-year return. Returns are decimals, so `0.02` means 2%. The [results guide](docs/results.md) explains the other fields.

## Run the backtest

Use Python 3.12. From the repository root:

```bash
python -m pip install -r requirements.txt
python scripts/run_backtest.py
python scripts/verify_backtest.py --output-dir results/generated --reference-results results
```

Input and funding checks can also be run with `python scripts/verify_inputs.py` and `python -m unittest discover -s tests -v`.

The two input workbooks are in `data/raw/`. The run writes a fresh set of calculations to `results/generated/`; rerunning replaces files there. Input workbooks and the saved results used for comparison are left unchanged.

The final command checks regression samples, trade timing, carry, capital and the saved return tables. The raw-data rebuild reproduced all 323 trades and both sets of monthly results within floating-point rounding. Reproduction confirms that the code recovers this backtest; it does not establish that the trading assumptions hold in live markets.

For different input locations, pass `--regression-data`, `--rates-data` and `--output-dir` to the backtest. This is a fixed historical study, with its model choices and dates set in the code. Using later observations requires reviewing those choices rather than only replacing the workbooks.

## What the evidence supports

The results show that this particular trading rule produced positive returns for several specifications under the stated assumptions. The statistical tests give a less consistent picture of a stable relationship between spread and basis. Cointegration depends on the specification, and the rolling adjustment results are sensitive to multiple-comparison corrections.

Each signal excludes its own observation from training, but the models and evaluation dates have already been explored. The backtest is not an untouched final test. Carry and rolldown are modeled estimates, and high leverage can make modest spread losses large relative to capital.

The [statistical findings](docs/statistical_findings.md) discuss those qualifications. The separate [research code](research/README.md) reproduces the 10-year statistical study and uses its own pinned library environment.

## Files

| Location | Contents |
| --- | --- |
| `data/` | Original workbooks, column descriptions and input hashes |
| `scripts/` | Raw-data reader, signals, valuation, P&L, capital and verification |
| `results/` | Saved strategy, trade, account and monthly results |
| `research/` | Statistical tests, observation snapshot and historical comparisons |
| `docs/` | Methodology, results notes and statistical interpretation |

The [reproduction notes](docs/reproduction.md) record the checks and their limits.
