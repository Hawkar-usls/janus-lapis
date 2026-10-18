"""Test GitHub incident state transitions without network calls or real writes."""
from __future__ import annotations

import copy
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from beetle_incident_issues import (AUTO_START, MARKER, TITLE,
                                    choose_issue, decide, parse_report,
                                    replace_block, synchronize)


RUN = 'https://github.com/Hawkar-usls/janus-lapis/actions/runs/12345'


def report(status='ALERT', alerts=None):
    if alerts is None:
        alerts = (['Hawkar-usls/Janus_Genesis: STALE'] if status == 'ALERT' else [])
    return {'schema': 'janus.beetle_home_watchdog.v1', 'status': status,
            'alerts': alerts, 'warnings': [], 'metrics': {'recipient_count': 16},
            'scientific_authority_delta': 0}


class FakeGitHubIssues:
    def __init__(self):
        self.issues = []
        self.calls = []

    def list_all(self):
        return copy.deepcopy(self.issues)

    def request(self, method, path, payload=None):
        self.calls.append((method, path, copy.deepcopy(payload)))
        if method == 'POST':
            issue = {'number': 17, 'state': 'open', 'title': payload['title'],
                     'body': payload['body']}
            self.issues.append(issue)
            return copy.deepcopy(issue)
        if method == 'PATCH':
            number = int(path.rsplit('/', 1)[1])
            issue = next(v for v in self.issues if v['number'] == number)
            issue.update(payload)
            return copy.deepcopy(issue)
        raise AssertionError(f'unexpected API request: {method}')


class IssueLedgerTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeGitHubIssues()

    def test_alert_creates_one_issue_then_repeat_does_not_write(self):
        first = synchronize(report(), RUN, self.api)
        self.assertEqual(first, {'action': 'CREATE', 'issue_number': 17})
        self.assertEqual(self.api.issues[0]['title'], TITLE)
        self.assertIn(MARKER, self.api.issues[0]['body'])
        before = len(self.api.calls)
        duplicate = synchronize(report(), RUN, self.api)
        self.assertEqual(duplicate['action'], 'REPEAT_NO_WRITE')
        self.assertEqual(len(self.api.calls), before)

    def test_distinct_alert_set_updates_instead_of_new_issue(self):
        synchronize(report(), RUN, self.api)
        fresh = report(alerts=['Hawkar-usls/Janus_Genesis: ACK_CONFLICT'])
        updated = synchronize(fresh, RUN, self.api)
        self.assertEqual(updated['action'], 'UPDATE_ALERT_SET')
        self.assertEqual(len(self.api.issues), 1)
        self.assertEqual(self.api.calls[-1][0], 'PATCH')
        self.assertIn('ACK_CONFLICT', self.api.issues[0]['body'])

    def test_recovery_closes_then_later_failure_reopens_same_issue(self):
        synchronize(report(), RUN, self.api)
        recovered = synchronize(report('WARN'), RUN, self.api)
        self.assertEqual(recovered['action'], 'CLOSE_RECOVERED')
        self.assertEqual(self.api.issues[0]['state'], 'closed')
        before = len(self.api.calls)
        self.assertEqual(synchronize(report('PASS'), RUN, self.api)['action'],
                         'HEALTHY_NO_WRITE')
        self.assertEqual(len(self.api.calls), before)
        recurred = synchronize(report(), RUN, self.api)
        self.assertEqual(recurred['action'], 'REOPEN')
        self.assertEqual(self.api.issues[0]['state'], 'open')
        self.assertEqual(len(self.api.issues), 1)

    def test_unknown_never_opens_or_closes_an_incident(self):
        self.assertEqual(synchronize(report('UNKNOWN'), RUN, self.api)['action'],
                         'UNKNOWN_NO_WRITE')
        self.assertEqual(self.api.calls, [])
        synchronize(report(), RUN, self.api)
        before = len(self.api.calls)
        self.assertEqual(synchronize(report('UNKNOWN'), RUN, self.api)['action'],
                         'UNKNOWN_NO_WRITE')
        self.assertEqual(self.api.issues[0]['state'], 'open')
        self.assertEqual(len(self.api.calls), before)

    def test_machine_owned_block_preserves_human_notes(self):
        synchronize(report(), RUN, self.api)
        self.api.issues[0]['body'] += '\n## Maintainer notes\nKeep this note!\n'
        synchronize(report(alerts=['Hawkar-usls/janus-lapis: STALE']), RUN, self.api)
        self.assertIn('Keep this note!', self.api.issues[0]['body'])

    def test_foreign_issue_or_pr_is_not_reused(self):
        self.api.issues.append({'number': 4, 'state': 'open', 'body': 'unrelated'})
        self.api.issues.append({'number': 5, 'state': 'open',
                                'pull_request': {}, 'body': MARKER})
        self.assertIsNone(choose_issue(self.api.list_all()))
        self.assertEqual(synchronize(report(), RUN, self.api)['action'], 'CREATE')
        self.assertEqual(len(self.api.issues), 3)

    def test_duplicate_markers_cause_no_ambiguous_mutation(self):
        synchronize(report(), RUN, self.api)
        self.api.issues.append({'number': 18, 'state': 'closed', 'body': MARKER})
        before = len(self.api.calls)
        with self.assertRaisesRegex(ValueError, 'multiple incident'):
            synchronize(report(), RUN, self.api)
        self.assertEqual(len(self.api.calls), before)

    def test_corrupt_machine_block_cannot_overwrite_human_issue(self):
        synchronize(report(), RUN, self.api)
        self.api.issues[0]['body'] = MARKER + '\nNo machine block'
        with self.assertRaisesRegex(ValueError, 'machine-owned'):
            synchronize(report(alerts=['Hawkar-usls/Janus_Genesis: ACK_CONFLICT']),
                        RUN, self.api)
        self.assertEqual(len(self.api.calls), 1)

    def test_cannot_replace_nonledger_issue_body(self):
        with self.assertRaises(ValueError):
            replace_block('A human issue', AUTO_START + '\nignore\n')

    def test_status_validation_rejects_inconsistent_or_unsafe_receipt(self):
        for bad in [report('PASS', alerts=['Fake: STALE']),
                    report('ALERT', alerts=[]),
                    report(alerts=['bad\nline']),
                    {**report(), 'scientific_authority_delta': 1}]:
            with self.subTest(bad=bad):
                with tempfile.TemporaryDirectory() as temp:
                    path = pathlib.Path(temp) / 'receipt.txt'
                    import json
                    path.write_text(json.dumps(bad) + '\n::error::annotation\n')
                    with self.assertRaises(ValueError):
                        parse_report(path)

    def test_first_line_json_receipt_with_following_summary_is_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / 'receipt.txt'
            import json
            path.write_text(json.dumps(report('WARN')) + '\n### Human summary\n')
            self.assertEqual(parse_report(path)['status'], 'WARN')


if __name__ == '__main__':
    unittest.main()
