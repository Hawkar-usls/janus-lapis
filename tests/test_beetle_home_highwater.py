"""Independent high-water record, rollback and fork tests (offline)."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from beetle_home_highwater import advance, ancestry_url, check, parse_issue, verify_ancestry


def record(seq=101):
    return {'schema': 'janus.genesis.home.highwater.v1', 'sequence': seq,
            'receipt_sha256': 'a' * 64, 'home_commit_sha': 'b' * 40,
            'source_repository': 'Hawkar-usls/Janus_Genesis',
            'scientific_authority_delta': 0}


def issue(witness=None):
    return {'number': 21, 'state': 'open', 'body':
            '<!-- janus.genesis.home.highwater.v1 -->\nIndependent witness.\n'
            '```json\n' + json.dumps(witness or record()) + '\n```\nManual footer.'}


def report(seq, sha='a' * 64, commit='b' * 40, highwater='ADVANCE_PENDING'):
    return {'status': 'PASS', 'metrics': {
        'home_receipt_integrity': 'PASS', 'home_sequence_integrity': 'PASS',
        'home_highwater_history': 'PASS',
        'home_highwater_status': highwater, 'home_checkpoint': seq,
        'home_current_receipt_sha256': sha, 'home_current_commit_sha': commit,
    }}


class FakeGitHub:
    def __init__(self, witness=None):
        self.issue = issue(witness)
        self.writes = []

    def request(self, method, path, payload=None):
        if method == 'GET':
            return copy.deepcopy(self.issue)
        assert method == 'PATCH' and path.endswith('/issues/21')
        self.writes.append(payload)
        self.issue['body'] = payload['body']
        return copy.deepcopy(self.issue)


class HighwaterTests(unittest.TestCase):
    def test_watchdog_has_safe_event_wakeup_if_cron_is_skipped(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    '.github/workflows/janus-beetle-home-watchdog.yml').read_text()
        self.assertIn("workflows:\n      - 'JANUS Universal Beetle hourly'", workflow)
        self.assertIn("- 'JANUS Beetle Memory Receiver'", workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", workflow)
        self.assertIn('needs.observe.result != \'skipped\'', workflow)

    def test_anchor_ancestry_detects_complete_history_replacement(self):
        compare = {'status': 'ahead', 'ahead_by': 3,
                   'base_commit': {'sha': 'b' * 40},
                   'url': ancestry_url(record(), 'c' * 40).split('?', 1)[0],
                   'merge_base_commit': {'sha': 'b' * 40}}
        self.assertEqual(verify_ancestry(compare, record(), 'c' * 40), [])
        compare['merge_base_commit']['sha'] = 'd' * 40
        compare['status'] = 'diverged'
        self.assertEqual(verify_ancestry(compare, record(), 'c' * 40),
                         ['GENESIS_HOME_INDEPENDENT_HISTORY_REWRITE'])
    def test_record_is_readable_and_preserves_manual_text(self):
        witness, left, right = parse_issue(issue())
        self.assertEqual(witness['sequence'], 101)
        self.assertIn('Independent witness.', left)
        self.assertIn('Manual footer.', right)

    def test_independent_rollback_even_if_local_history_looks_good(self):
        alerts, metrics = check({'sequence': 98, 'last_receipt_sha256': 'c' * 64},
                                record(), 'd' * 40)
        self.assertEqual(alerts, ['GENESIS_HOME_INDEPENDENT_HIGHWATER_ROLLBACK'])
        self.assertEqual(metrics['home_highwater_status'], 'FAIL')

    def test_same_sequence_rewritten_hash_is_fork(self):
        for changed in ({'last_receipt_sha256': 'c' * 64}, {'sha': 'c' * 40}):
            alerts, _ = check({'sequence': 101,
                               'last_receipt_sha256': changed.get('last_receipt_sha256', 'a' * 64)},
                              record(), changed.get('sha', 'b' * 40))
            self.assertEqual(alerts, ['GENESIS_HOME_INDEPENDENT_HIGHWATER_FORK'])

    def test_monotonic_advance_and_idempotent_replay(self):
        api = FakeGitHub()
        result = advance(report(102, 'c' * 64, 'd' * 40), api)
        self.assertEqual(result, {'action': 'ADVANCED', 'sequence': 102})
        self.assertEqual(len(api.writes), 1)
        self.assertIn('Manual footer.', api.issue['body'])
        self.assertEqual(advance(report(102, 'c' * 64, 'd' * 40), api),
                         {'action': 'ALREADY_ANCHORED', 'sequence': 102})
        self.assertEqual(len(api.writes), 1)

    def test_no_mutation_on_rollback_or_fork(self):
        for seq, sha, commit in [(100, 'a' * 64, 'b' * 40),
                                 (101, 'c' * 64, 'b' * 40),
                                 (101, 'a' * 64, 'c' * 40)]:
            api = FakeGitHub()
            with self.assertRaisesRegex(ValueError, 'monotonic high-water violation'):
                advance(report(seq, sha, commit), api)
            self.assertEqual(api.writes, [])

    def test_unknown_failed_integrity_and_corrupt_issue_fail_closed(self):
        api = FakeGitHub()
        self.assertEqual(advance({'status': 'UNKNOWN'}, api)['action'],
                         'NO_VERIFIED_EVIDENCE')
        broken = report(104)
        broken['metrics']['home_receipt_integrity'] = 'FAIL'
        self.assertEqual(advance(broken, api)['action'], 'INTEGRITY_GUARD_NO_WRITE')
        self.assertEqual(api.writes, [])
        for mutation in [lambda x: x.update(state='closed'),
                         lambda x: x.update(body='someone deleted the marker')]:
            broken_issue = issue()
            mutation(broken_issue)
            with self.assertRaises(ValueError):
                parse_issue(broken_issue)


if __name__ == '__main__':
    unittest.main()
