"""Rebuild the historical SOFR backtest from the two raw workbooks."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import pandas as pd
from raw_data import load_inputs
from signals import generate_models
from pnl import attribute_models
from capital import run_capital

REPOSITORY = Path(__file__).resolve().parents[1]

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    if not __debug__:
        raise RuntimeError("Run without -O: calculation validation must stay active.")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regression-data",type=Path,
                        default=REPOSITORY/"data/raw/US_Daily_Raw_Final_Models_With Libor.xlsx")
    parser.add_argument("--rates-data",type=Path,
                        default=REPOSITORY/"data/raw/Rates_Swaps_Daily - With Libor.xlsx")
    parser.add_argument("--output-dir",type=Path,default=REPOSITORY/"results/generated")
    parser.add_argument("--verify-results",type=Path,
                        help="Optional saved gross/net CSV folders, used only for comparison.")
    args=parser.parse_args()
    paths=(args.regression_data,args.rates_data)
    for path in paths:
        if not path.is_file():
            parser.error(f"Input workbook not found: {path}")
    hashes={str(path.resolve()):sha256(path) for path in paths}
    out=args.output_dir
    out.mkdir(parents=True,exist_ok=True)
    raw,rates=load_inputs(*paths)
    normalized=out/"normalized_inputs"
    normalized.mkdir(exist_ok=True)
    raw.to_csv(normalized/"signals_SOFR.csv",index_label="Date")
    rates.to_csv(normalized/"rates_SOFR.csv",index_label="Date")
    # Retain the original preparation-stage CSV round trip for numerical
    # consistency. These files are freshly created from the supplied workbooks.
    raw=pd.read_csv(normalized/"signals_SOFR.csv",parse_dates=["Date"]).set_index("Date")
    rates=pd.read_csv(normalized/"rates_SOFR.csv",parse_dates=["Date"]).set_index("Date")
    print("Recalculating rolling fits and signals from raw observations.",flush=True)
    models=generate_models(raw)
    assert len(models)==24
    # The current SOFR snapshot has original spread quotes at its final close.
    for m in models:
        assert m["end"]==pd.Timestamp("2026-09-03")
        assert np.isfinite(m["df"].iloc[-1,0 if m["maturity"]==10 else 1])
    print("Repricing all generated trades and daily marks.",flush=True)
    records=attribute_models(models,rates,out/"strategy")
    references=args.verify_results
    reports={}
    for case in ("gross","net"):
        reports[case]=run_capital(records["daily"],records["trades"],rates,out/case,
            with_costs=case=="net",
            reference_dir=references/case if references is not None else None)
    for filename,before in hashes.items():
        if sha256(filename)!=before:
            raise RuntimeError(f"Input file changed during the run: {filename}")
    report=dict(Status="PASS",InputsOnlyTwoRawWorkbooks=True,InputFilesUnchanged=True,
        InputSHA256={Path(name).name:value for name,value in hashes.items()},RollingModels=len(models),Trades=len(records["trades"]),
        DailyMarks=len(records["daily"]),Gross=reports["gross"],Net=reports["net"],
        Scope="SOFR 10Y/30Y, GBP/EUR 2Y/5Y basis, R1/R2/R3, 1x/10x/20x/30x",
        FinalClose="2026-09-03")
    (out/"rebuild_verification.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="InputSHA256"},indent=2))

if __name__=="__main__":
    main()
