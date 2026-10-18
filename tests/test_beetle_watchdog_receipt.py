"""A missing or corrupt watcher result must never be labeled healthy."""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from beetle_watchdog_receipt import normalize_receipt
from beetle_incident_issues import parse_report


class WatchdogReceiptTests(unittest.TestCase):
    def test_missing_file_is_normalized_to_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'missing.txt'
            self.assertEqual(normalize_receipt(path), 'UNKNOWN')
            self.assertEqual(parse_report(path)['status'], 'UNKNOWN')
            self.assertEqual(parse_report(path)['scientific_authority_delta'], 0)

    def test_invalid_or_forged_result_becomes_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'receipt.txt'
            for data in ['garbage\n', json.dumps({
                    'schema': 'janus.beetle_home_watchdog.v1',
                    'status': 'PASS', 'alerts': [], 'scientific_authority_delta': 1})]:
                with self.subTest(data=data):
                    path.write_text(data)
                    self.assertEqual(normalize_receipt(path), 'UNKNOWN')
                    self.assertEqual(parse_report(path)['status'], 'UNKNOWN')

    def test_valid_receipt_keeps_first_line_and_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'receipt.txt'
            content = json.dumps({'schema': 'janus.beetle_home_watchdog.v1',
                                  'status': 'ALERT', 'alerts': ['GENESIS_HOME_CHECKPOINT_STALE'],
                                  'scientific_authority_delta': 0}) + '\n### Human summary\n'
            path.write_text(content)
            self.assertEqual(normalize_receipt(path), 'ALERT')
            self.assertEqual(path.read_text(), content)


if __name__ == '__main__':
    unittest.main()
