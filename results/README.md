# Result files

**gross/** contains the checked SOFR results before added trading, haircut and swap margin costs. Baseline carry still includes Treasury funding at SOFR.

**net/** contains the same selected models with a 0.5 bp completed round-trip cost and a 1% Treasury haircut funded at SOFR + 5 bp. Swap margin costs and constraints are assessed separately from these files.

Each folder contains account summaries, monthly returns including cumulative returns, calendar-year returns and a verification report. Both monthly files use the same 5,376-row model/leverage/month grid. Return fields are decimals, and missing values should be read together with **Status**.

The CSVs preserve full stored precision. Percentages in the main README are rounded to two decimal places. See [results notes](../docs/results.md) for the dates, units and treatment of stopped accounts.
