"""Adversarial and normal-delivery SLO tests; never contact GitHub."""
from __future__ import annotations

import contextlib
import copy
import datetime as dt
import io
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from beetle_home_watchdog import evaluate, elapsed_minutes, main


NOW = dt.datetime(2026, 10, 17, 23, 0, tzinfo=dt.timezone.utc)


def sample():
    health = {
        'schema': 'janus.beetle.delivery_health.v1',
        'scientific_authority_delta': 0,
        'at': '2026-10-17T22:00:00Z',
        'repositories': {
            'Hawkar-usls/Janus_Genesis': {
                'status': 'PENDING', 'produced': 7, 'confirmed': 6, 'pending': 1,
                'oldest_pending_minutes': 30,
            },
            'Hawkar-usls/Echo-Pyramid': {
                'status': 'UP_TO_DATE', 'produced': 2, 'confirmed': 2, 'pending': 0,
            },
        },
        'total_pending': 1,
    }
    home = {
        'schema': 'JANUS_HABITAT_CLOUD_HOME_STATE_V1',
        'status': 'CLOUD_HOME_ACTIVE', 'sequence': 91, 'authority_delta': 0,
        'checkpoint_head': 'state/habitat_cloud_home/receipts/00000091.json',
        'handoff_head': 'state/habitat_cloud_home/receipts/00000091.json',
        'beetle_memory': {
            'cursor_sequence': 6, 'context_sha256': 'a' * 64,
            'scientific_authority_delta': 0, 'command_authority': False,
            'external_effect_authority': False,
        },
    }
    cursor = {
        'schema': 'janus.genesis.beetle_context_cursor.v1',
        'last_sequence': 6, 'context_sha256': 'a' * 64,
        'unverified_research_only': True, 'scientific_authority_delta': 0,
    }
    ack = {
        'schema': 'janus.beetle.inbox_ack.v1',
        'target_repository': 'Hawkar-usls/Janus_Genesis',
        'status': 'INBOX_DURABLE_UNVERIFIED__NOT_RUNTIME_CONSUMPTION',
        'last_sequence': 6, 'acknowledged_at': '2026-10-17T22:00:00Z',
        'scientific_authority_delta': 0,
    }
    commits = [{'commit': {'committer': {'date': '2026-10-17T22:20:00Z'}}}]
    return health, home, cursor, ack, commits


class BeetleHomeWatchdogTests(unittest.TestCase):
    def setUp(self):
        self.sources = sample()

    def check(self, sources=None):
        return evaluate(*(sources or self.sources), NOW)

    def mutate(self, slot, fn):
        sources = copy.deepcopy(self.sources)
        fn(sources[slot])
        return sources

    def test_normal_scheduled_pending_does_not_alert(self):
        result = self.check()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['metrics']['pending_batches'], 1)
        self.assertEqual(result['metrics']['home_checkpoint'], 91)

    def test_recent_genesis_ack_ahead_is_grace_warning(self):
        sources = self.mutate(3, lambda ack: ack.update(
            last_sequence=7, acknowledged_at='2026-10-17T22:00:00Z'))
        result = self.check(sources)
        self.assertEqual(result['status'], 'WARN')
        self.assertEqual(result['alerts'], [])

    def test_old_genesis_ack_ahead_is_alarm(self):
        sources = self.mutate(3, lambda ack: ack.update(
            last_sequence=7, acknowledged_at='2026-10-17T19:00:00Z'))
        self.assertIn('GENESIS_HOME_ACK_LAG_STALE', self.check(sources)['alerts'])

    def test_producer_heartbeat_stale(self):
        sources = self.mutate(0, lambda h: h.update(at='2026-10-17T18:00:00Z'))
        self.assertIn('BEETLE_HEARTBEAT_STALE', self.check(sources)['alerts'])

    def test_home_durable_commit_stale_despite_recent_ack(self):
        sources = self.mutate(4, lambda commits: commits[0]['commit']['committer'].update(
            date='2026-10-17T18:00:00Z'))
        self.assertIn('GENESIS_HOME_CHECKPOINT_STALE', self.check(sources)['alerts'])

    def test_one_stale_recipient_triggers_alarm(self):
        sources = self.mutate(0, lambda h: h['repositories']['Hawkar-usls/Echo-Pyramid'].update(
            status='STALE', produced=3, confirmed=2, pending=1))
        sources[0]['total_pending'] = 2
        self.assertIn('Hawkar-usls/Echo-Pyramid: STALE', self.check(sources)['alerts'])

    def test_conflicting_ack_triggers_alarm(self):
        sources = self.mutate(0, lambda h: h['repositories']['Hawkar-usls/Janus_Genesis'].update(
            status='ACK_CONFLICT'))
        self.assertIn('Hawkar-usls/Janus_Genesis: ACK_CONFLICT', self.check(sources)['alerts'])

    def test_recent_missing_ack_is_not_false_failure(self):
        sources = self.mutate(0, lambda h: h['repositories']['Hawkar-usls/Janus_Genesis'].update(
            status='AWAITING_ACK'))
        self.assertEqual(self.check(sources)['status'], 'WARN')

    def test_cursor_ahead_of_receiver_is_alarm(self):
        sources = self.mutate(3, lambda ack: ack.update(last_sequence=5))
        self.assertIn('GENESIS_CURSOR_AHEAD_OF_RECEIVER_ACK', self.check(sources)['alerts'])

    def test_home_checkpoint_and_cursor_mismatch_is_unknown_not_pass(self):
        sources = self.mutate(2, lambda cursor: cursor.update(last_sequence=5))
        with self.assertRaisesRegex(ValueError, 'HOME state and durable cursor disagree'):
            self.check(sources)

    def test_invalid_authority_not_accepted_as_healthy(self):
        sources = self.mutate(1, lambda home: home['beetle_memory'].update(
            external_effect_authority=True))
        with self.assertRaisesRegex(ValueError, 'authority'):
            self.check(sources)

    def test_tampered_pending_counts_rejected(self):
        sources = self.mutate(0, lambda h: h['repositories']['Hawkar-usls/Echo-Pyramid'].update(
            pending=True))
        with self.assertRaisesRegex(ValueError, 'inconsistent counts'):
            self.check(sources)

    def test_future_timestamp_not_silently_clamped(self):
        with self.assertRaisesRegex(ValueError, 'in future'):
            elapsed_minutes('2026-10-18T00:00:00Z', NOW)

    def test_failure_to_fetch_is_unknown_and_nonzero(self):
        with mock.patch('beetle_home_watchdog.fetch_json', side_effect=OSError('offline')):
            with mock.patch.object(sys, 'argv', ['watch']):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    code = main()
        self.assertEqual(code, 2)
        self.assertIn('"status": "UNKNOWN"', output.getvalue())

    def test_alert_result_produces_nonzero_status(self):
        sources = self.mutate(0, lambda h: h.update(at='2026-10-17T18:00:00Z'))
        with mock.patch('beetle_home_watchdog.fetch_json', side_effect=sources):
            with mock.patch.object(sys, 'argv', ['watch']):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = main(now=NOW)
        self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
