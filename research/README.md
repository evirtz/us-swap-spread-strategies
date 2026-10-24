# Statistical study of the SOFR 10-year spread

This folder contains the integration, cointegration, stability, regression and error-correction work discussed in the report. It covers the 10-year spread against GBP/EUR 2-year and 5-year basis, with MOVE where specified. The trading backtest also includes 30-year spreads; this statistical study does not.

The runner refits the tests from `data/observations.csv`, which preserves all 1,353 original observations and their missing values. `reference_results/` contains historical estimates used only for comparisons after refitting. `data/endpoint_validation.json` supplies the saved coefficient checks for the rolling fits. The snapshot and source hashes are recorded in `data/provenance.json`.

## Run

The statistical code uses different pinned library versions from the trading backtest. Use a separate Python 3.12 environment and install `research/requirements.txt` there. The original validation used Python 3.12.14.

From the repository root, with that environment active:

```bash
python -m pip install -r research/requirements.txt
python research/statistical_tests.py
```

The full study includes exhaustive lag and break searches. To run selected groups:

```bash
python research/statistical_tests.py --stages integration johansen
python research/statistical_tests.py --stages regressions
python research/statistical_tests.py --stages prospective
```

`prospective` also runs the rolling fits it needs. Outputs go to `research/results/`, which is excluded from Git. `saved_results/` contains selected tables from the original validated study. `VERIFICATION.md` records the historical full-suite validation; it should not be read as a claim that each test was newly rerun when preparing this repository.

The dataset, evaluation periods and comparison references are fixed to this study. Changing them requires reviewing the specifications and endpoint checks. `--skip-reference-check` skips output comparisons; it does not permit arbitrary new observations.

## Included work

| Group | Tests or calculations |
| --- | --- |
| Integration | ADF, Phillips–Perron, KPSS and Zivot–Andrews |
| Cointegration | Engle–Granger, Phillips–Ouliaris and Johansen |
| Long-run models | OLS, DOLS, FMOLS and conditional UECM bounds |
| Stability | Fully modified stability diagnostics, Gregory–Hansen breaks and endpoint comparisons |
| Regressions | First/final fits, HAC uncertainty and joint tests |
| Adjustment | Fixed-residual and rolling-gap responses at one, five and twenty recorded closes |

The original full validation matched twenty result files covering 13,045 records. The fully modified stability simulation is a conditional approximation. It uses an internal arch fitting method, which is one reason to retain the pinned library version.

P-values are raw unless a correction is explicitly named. KPSS probabilities at its table limits are bounds. Gregory–Hansen and Johansen use their published/tabulated critical values; exact p-values are not supplied. The currency-specific Holm correction is exploratory and does not control both currencies or the wider model search jointly.

See [statistical findings](../docs/statistical_findings.md) for the interpretation. A significant regression coefficient, a cointegration rejection or a negative adjustment coefficient answers a different question from whether the implemented strategy earns positive returns after entry and costs.
