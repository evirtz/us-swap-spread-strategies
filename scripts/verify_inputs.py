"""Check workbook hashes and the statistical snapshot against the raw levels."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from raw_data import load_inputs

ROOT = Path(__file__).resolve().parents[1]


def verify_inputs():
    manifest = json.loads((ROOT / 'data/manifest.json').read_text(encoding='utf-8'))
    for item in manifest['workbooks']:
        path = ROOT / item['path']
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != item['sha256']:
            raise ValueError(f"Workbook differs from the recorded copy: {item['path']}")

    raw, _ = load_inputs(
        ROOT / 'data/raw/US_Daily_Raw_Final_Models_With Libor.xlsx',
        ROOT / 'data/raw/Rates_Swaps_Daily - With Libor.xlsx',
    )
    names = {
        '10yr swap spreads': 'Spread', 'Move': 'MOVE',
        '2yr_Basis_GBP_SOFR': 'GBP2Y', '5yr_Basis_GBP_SOFR': 'GBP5Y',
        '2yr_Basis_EU_SOFR': 'EUR2Y', '5yr_Basis_EU_SOFR': 'EUR5Y',
    }
    snapshot = pd.read_csv(
        ROOT / 'research/data/observations.csv', parse_dates=['Date'],
        float_precision='round_trip',
    ).set_index('Date')
    selected = raw[list(names)].rename(columns=names)[list(snapshot.columns)]
    if not selected.index.equals(snapshot.index):
        raise ValueError('Raw workbook and statistical snapshot have different observation dates.')
    if not np.array_equal(selected.to_numpy(), snapshot.to_numpy(), equal_nan=True):
        raise ValueError('Raw workbook and statistical snapshot have different observed values.')
    result = {
        'WorkbookHashesMatch': True,
        'StatisticalSnapshotMatchesRawLevels': True,
        'StatisticalObservations': len(snapshot),
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    verify_inputs()
