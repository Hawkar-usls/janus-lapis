"""A missing or corrupt watcher result must never be labeled healthy."""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from beetle_watchdog_receipt import normalize_receipt, verify_observer_exit
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


    def test_observed_alert_counts_as_completed_schedule_not_healthy_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'receipt.txt'
            exit_file = pathlib.Path(directory) / 'exit.txt'
            path.write_text(json.dumps({
                'schema': 'janus.beetle_home_watchdog.v1',
                'status': 'ALERT',
                'alerts': ['Hawkar-usls/AIFC: STALE'],
                'scientific_authority_delta': 0,
            }) + '\n', encoding='utf-8')
            exit_file.write_text('1\n', encoding='utf-8')
            self.assertEqual(verify_observer_exit(path, exit_file), 'ALERT')
            self.assertEqual(parse_report(path)['alerts'],
                             ['Hawkar-usls/AIFC: STALE'])

    def test_known_observation_exit_codes_require_matching_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'receipt.txt'
            exit_file = pathlib.Path(directory) / 'exit.txt'
            for status, code, alerts in [
                ('PASS', '0', []), ('WARN', '0', []),
                ('ALERT', '1', ['GENESIS_HOME_CHECKPOINT_STALE']),
                ('UNKNOWN', '2', []),
            ]:
                with self.subTest(status=status):
                    body = {'schema': 'janus.beetle_home_watchdog.v1',
                            'status': status, 'alerts': alerts,
                            'scientific_authority_delta': 0}
                    if status == 'UNKNOWN':
                        body['reason'] = 'OSError'
                    path.write_text(json.dumps(body) + '\n', encoding='utf-8')
                    exit_file.write_text(code + '\n', encoding='utf-8')
                    self.assertEqual(verify_observer_exit(path, exit_file), status)
                    wrong_code = '1' if code != '1' else '0'
                    exit_file.write_text(wrong_code + '\n', encoding='utf-8')
                    with self.assertRaisesRegex(ValueError, 'disagree'):
                        verify_observer_exit(path, exit_file)

    def test_synthetic_unknown_missing_output_never_proves_schedule_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'receipt.txt'
            exit_file = pathlib.Path(directory) / 'exit.txt'
            self.assertEqual(normalize_receipt(path), 'UNKNOWN')
            exit_file.write_text('2\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'cannot prove liveness'):
                verify_observer_exit(path, exit_file)

    def test_missing_exit_code_and_unknown_process_failure_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'receipt.txt'
            exit_file = pathlib.Path(directory) / 'exit.txt'
            path.write_text(json.dumps({
                'schema': 'janus.beetle_home_watchdog.v1',
                'status': 'PASS', 'alerts': [],
                'scientific_authority_delta': 0,
            }) + '\n', encoding='utf-8')
            with self.assertRaises(OSError):
                verify_observer_exit(path, exit_file)
            exit_file.write_text('137\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'disagree'):
                verify_observer_exit(path, exit_file)


if __name__ == '__main__':
    unittest.main()
