"""Input and day-count cases that can otherwise change trades or carry silently."""

from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

import numpy as np
import openpyxl
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from raw_data import read_sofr
from valuation import compound, configure_rates


class InputValidation(unittest.TestCase):
    def write_input(self, directory, headers, rows):
        path = Path(directory) / 'input.xlsx'
        book = openpyxl.Workbook()
        sheet = book.active
        sheet.title = 'SOFR'
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        book.save(path)
        book.close()
        return path

    def test_duplicate_dates_are_rejected(self):
        day = pd.Timestamp('2026-03-20').to_pydatetime()
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_input(directory, ['Date', 'Spread'], [[day, 1], [day, 2]])
            with self.assertRaisesRegex(ValueError, 'duplicate source dates'):
                read_sofr(path, ['Spread'])

    def test_missing_or_duplicate_headers_are_rejected(self):
        for headers in (['Date', 'Other'], ['Date', 'Spread', 'Spread']):
            with self.subTest(headers=headers), tempfile.TemporaryDirectory() as directory:
                path = self.write_input(directory, headers, [])
                with self.assertRaisesRegex(ValueError, 'exactly one'):
                    read_sofr(path, ['Spread'])

    def test_missing_predictor_is_preserved(self):
        day = pd.Timestamp('2026-03-20').to_pydatetime()
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_input(directory, ['Date', 'Basis'], [[day, None]])
            frame = read_sofr(path, ['Basis'])
            self.assertTrue(np.isnan(frame.iloc[0, 0]))


class FundingAccrual(unittest.TestCase):
    def test_friday_fixing_covers_three_calendar_days(self):
        friday = pd.Timestamp('2026-03-20')
        monday = pd.Timestamp('2026-03-23')
        configure_rates(pd.DataFrame({'Floating': [5.0, 6.0]}, index=[friday, monday]))
        self.assertAlmostEqual(compound('SOFR', friday, monday), 0.05 * 3 / 360, places=14)

    def test_same_day_holding_has_no_funding_accrual(self):
        day = pd.Timestamp('2026-03-20')
        configure_rates(pd.DataFrame({'Floating': [5.0]}, index=[day]))
        self.assertEqual(compound('SOFR', day, day), 0.0)


class ExecutionGuards(unittest.TestCase):
    def test_optimized_execution_cannot_report_a_pass(self):
        root = Path(__file__).resolve().parents[1]
        commands = [
            [root / 'scripts/run_backtest.py'],
            [root / 'scripts/verify_backtest.py', '--output-dir', root / 'results/generated'],
        ]
        for command in commands:
            with self.subTest(script=str(command[0])):
                result = subprocess.run(
                    [sys.executable, '-B', '-O', *map(str, command)],
                    capture_output=True, text=True, check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Run without -O', result.stderr)


if __name__ == '__main__':
    unittest.main()
