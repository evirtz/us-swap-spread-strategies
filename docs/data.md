# Data and reproduction

## Workbooks

The original study used two supplied workbooks:

- **US_Daily_Raw_Final_Models_With Libor.xlsx** for original swap spreads, the named basis series and MOVE.
- **Rates_Swaps_Daily - With Libor.xlsx** for Treasury and IRS curve quotes, SOFRRATE, LIBOR fixings and Treasury bill yields.

The workbook contents were treated as observations. The underlying market-data workbooks and Excel result workbooks are kept outside the repository.

The included Python script starts one stage later, from **Swap_Spread_Rolling_Results.xlsx**. It needs the signed daily P&L components and the trade-entry Treasury notionals per DV01 that were calculated in the wider study. It does not regenerate those inputs from the original market data.

## Running the script

The local setup was checked with Python 3.12.14, NumPy 2.3.5 and openpyxl 3.1.5. The two packages are pinned in **requirements.txt**.

From the repository root, install the dependencies and run:

~~~bash
python -m pip install -r requirements.txt
python scripts/reproduce_sofr_gross_returns.py --source "data/Swap_Spread_Rolling_Results.xlsx" --reference "data/SOFR_Gross_Monthly_Cumulative_Calendar_1x_10x_20x_30x.xlsx" --output-dir "results/generated" --verify
~~~

Place the source and reference workbooks in **data/** first. The source workbook is required for the calculation. The reference workbook is required when using **--verify**. You can supply other local paths with the same arguments. Running without **--verify** still performs the source and internal arithmetic checks, but does not compare against the reference workbook.

The script writes daily capital marks, trade capital records, monthly returns, calendar-year returns, account summaries and a JSON verification report. It reads the input workbooks without editing them.

## Required source layout

Both source tables have their column headers in Excel row 5. The script locates fields by their header names.

| Sheet | Required fields |
| --- | --- |
| Daily SOFR | Model, Date, Marked trade, Market change (bp), Carry change (bp), Roll change (bp) |
| Trades | Model, Trade ID, Entry execution, Exit / final mark, Status, Treasury notional per DV01, Swap notional per DV01, Market P&L (bp), Net carry (bp), Net rolldown (bp) |

The reference comparison uses the known layout of the gross workbook: eight family sheets with four leverage blocks, plus **Monthly Marks**. It checks every selected monthly, cumulative and calendar-year cell, including inactive and unavailable periods.

openpyxl reads saved cell values when **data_only=True**. The workbooks therefore need populated values or formula caches. A missing expected numeric value causes a validation error or a comparison failure.

## Published result files

The checked CSV exports in **results/gross/** come from the gross reproduction run. The files in **results/net/** contain the already calculated 0.5 bp plus 1% haircut results. They have been arranged into the same monthly grid for comparison. No new strategy parameters were fitted when preparing these files.

The cost-adjusted files are checked outputs. The Python script included here reproduces the gross stage only. Reading the result CSVs does not require the input workbooks.

Verification reports retain the recorded counts, tolerances and input hashes. A later review found a different binary hash for the rates workbook, with matching numeric SOFR series over all 2,019 retained dates. The net verification file records both hashes and that comparison. Local input paths have been shortened to filenames. Workbook files and locally generated output are excluded by **.gitignore**.
