"""Adversarial and normal-delivery SLO tests; never contact GitHub."""
from __future__ import annotations

import contextlib
import copy
import datetime as dt
import hashlib
import io
import json
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from beetle_home_watchdog import (evaluate, elapsed_minutes, main,
                                  predecessor_state_url, receipt_url,
                                  reconcile_stale, verify_checkpoint_progress,
                                  verify_receipt)


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
        'checkpoint_head': 'state/habitat_cloud_home/receipts/00000091-123-1.json',
        'handoff_head': 'state/habitat_cloud_home/receipts/00000091-123-1.json',
        'last_run_id': '123', 'last_event': 'schedule',
        'last_worker': 'github-actions:123:worker-a',
        'source_main_sha': 'e' * 40,
        'state_id': 'JANUS-HABITAT-CLOUD-HOME',
        'durable_identity': 'JANUS_HABITAT_RESIDENT_V1',
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
    commits = [
        {'sha': 'f' * 40, 'commit': {
            'committer': {'date': '2026-10-17T22:20:00Z'},
            'message': 'JANUS cloud HOME checkpoint 123/1'}},
        {'sha': 'd' * 40, 'commit': {
            'committer': {'date': '2026-10-17T21:20:00Z'},
            'message': 'JANUS cloud HOME checkpoint 122/1'}},
    ]
    return health, home, cursor, ack, commits


def sample_predecessor():
    home = copy.deepcopy(sample()[1])
    home.update(sequence=90, last_run_id='122')
    home['checkpoint_head'] = 'state/habitat_cloud_home/receipts/00000090-122-1.json'
    home['handoff_head'] = home['checkpoint_head']
    home['beetle_memory']['cursor_sequence'] = 5
    return home


def sample_receipt(home):
    event_id = (f'{home["last_run_id"]}:1:{home["last_event"]}:'
                f'{home["source_main_sha"]}:{home["sequence"]}')
    receipt = {
        'schema': 'JANUS_HABITAT_CLOUD_HOME_RECEIPT_V1',
        'state_id': home['state_id'], 'sequence': home['sequence'],
        'run_id': home['last_run_id'], 'event': home['last_event'],
        'worker': home['last_worker'], 'source_main_sha': home['source_main_sha'],
        'resident_identity': home['durable_identity'],
        'run_attempt': 1, 'event_id': event_id,
        'dedupe_key': hashlib.sha256(event_id.encode()).hexdigest(),
        'beetle_memory': home['beetle_memory'], 'authority_delta': 0,
        'admission_status': 'ADMITTED_BOUNDED_CLOUD_HOME_TICK',
        'parse_status': 'PARSED', 'execute_status': 'CHECKPOINT_ONLY',
        'load_status': 'CONTEXT_STAGED_NOT_MODEL_LOADED',
        'pc_dependency_observed': False, 'remote_desktop_dependency_observed': False,
        'nas_dependency_observed': False, 'hidden_session_context_used': False,
        'source_writeback_observed': False, 'destructive_action': False,
    }
    raw = (json.dumps(receipt, sort_keys=True) + '\n').encode()
    home['last_receipt_sha256'] = hashlib.sha256(raw).hexdigest()
    return receipt, raw


def sample_highwater(home):
    record = {'schema': 'janus.genesis.home.highwater.v1',
              'sequence': home['sequence'],
              'receipt_sha256': home['last_receipt_sha256'],
              'home_commit_sha': 'f' * 40,
              'source_repository': 'Hawkar-usls/Janus_Genesis',
              'scientific_authority_delta': 0}
    return {'number': 21, 'state': 'open', 'body':
            '<!-- janus.genesis.home.highwater.v1 -->\n```json\n' +
            json.dumps(record) + '\n```'}


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

    def stale_snapshot_and_live_queue(self, *, correct_ack=True):
        health = copy.deepcopy(self.sources[0])
        health['repositories']['Hawkar-usls/Echo-Pyramid'].update(
            status='STALE', produced=2, confirmed=1, pending=1,
            oldest_pending_minutes=240)
        health['total_pending'] = 2
        queue = {'schema': 'janus.beetle.delivery_queue.v1',
                 'target_repository': 'Hawkar-usls/Echo-Pyramid',
                 'next_sequence': 3,
                 'entries': [
                     {'sequence': 1, 'batch_id': 'a' * 20, 'sha256': 'a' * 64,
                      'created_at': '2026-10-17T17:00:00Z'},
                     {'sequence': 2, 'batch_id': 'b' * 20, 'sha256': 'b' * 64,
                      'created_at': '2026-10-17T18:00:00Z'},
                 ]}
        ack = {'schema': 'janus.beetle.inbox_ack.v1',
               'target_repository': 'Hawkar-usls/Echo-Pyramid',
               'status': 'INBOX_DURABLE_UNVERIFIED__NOT_RUNTIME_CONSUMPTION',
               'last_sequence': 2 if correct_ack else 1,
               'batch_id': 'b' * 20 if correct_ack else 'a' * 20,
               'sha256': 'b' * 64 if correct_ack else 'a' * 64,
               'scientific_authority_delta': 0,
               'acknowledged_at': '2026-10-17T22:55:00Z'}
        return health, queue, ack

    def test_live_ack_resolves_cron_race_without_faking_progress(self):
        health, queue, ack = self.stale_snapshot_and_live_queue()
        fetch = mock.Mock(side_effect=[queue, ack])
        current = reconcile_stale(health, NOW, fetcher=fetch)
        self.assertEqual(current['repositories']['Hawkar-usls/Echo-Pyramid']['status'],
                         'UP_TO_DATE')
        self.assertEqual(current['total_pending'], 1)
        self.assertEqual(current['live_rechecked_recipients'], ['Hawkar-usls/Echo-Pyramid'])
        self.assertEqual(health['repositories']['Hawkar-usls/Echo-Pyramid']['status'], 'STALE')
        sources = [current, *self.sources[1:]]
        self.assertEqual(self.check(sources)['status'], 'PASS')
        self.assertEqual(fetch.call_count, 2)

    def test_live_old_ack_does_not_suppress_real_stale_alert(self):
        health, queue, ack = self.stale_snapshot_and_live_queue(correct_ack=False)
        current = reconcile_stale(health, NOW, fetcher=mock.Mock(side_effect=[queue, ack]))
        self.assertEqual(current['repositories']['Hawkar-usls/Echo-Pyramid']['status'], 'STALE')
        self.assertIn('Hawkar-usls/Echo-Pyramid: STALE',
                      self.check([current, *self.sources[1:]])['alerts'])

    def test_live_mismatched_ack_sha_fails_conflict_not_silent_clear(self):
        health, queue, ack = self.stale_snapshot_and_live_queue()
        ack['sha256'] = 'f' * 64
        current = reconcile_stale(health, NOW, fetcher=mock.Mock(side_effect=[queue, ack]))
        self.assertEqual(current['repositories']['Hawkar-usls/Echo-Pyramid']['status'],
                         'ACK_CONFLICT')

    def test_live_authority_claim_cannot_clear_old_alarm(self):
        health, queue, ack = self.stale_snapshot_and_live_queue()
        ack['scientific_authority_delta'] = 1
        current = reconcile_stale(health, NOW, fetcher=mock.Mock(side_effect=[queue, ack]))
        self.assertEqual(current['repositories']['Hawkar-usls/Echo-Pyramid']['status'],
                         'ACK_CONFLICT')

    def test_no_suspected_lag_never_makes_extra_requests(self):
        fetch = mock.Mock(side_effect=AssertionError('unexpected network request'))
        current = reconcile_stale(self.sources[0], NOW, fetcher=fetch)
        self.assertEqual(current['live_rechecked_recipients'], [])
        fetch.assert_not_called()

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

    def test_home_receipt_sha_and_provenance_match(self):
        home = self.sources[1]
        _, raw = sample_receipt(home)
        self.assertEqual(verify_receipt(home, raw), [])
        self.assertTrue(receipt_url(home).endswith('/receipts/00000091-123-1.json'))

    def test_home_receipt_hash_mismatch_is_confirmed_integrity_alert(self):
        home = self.sources[1]
        _, raw = sample_receipt(home)
        self.assertEqual(verify_receipt(home, raw + b' '),
                         ['GENESIS_HOME_RECEIPT_SHA256_MISMATCH'])

    def test_home_receipt_matching_hash_but_wrong_state_is_alert(self):
        home = self.sources[1]
        receipt, _ = sample_receipt(home)
        receipt['sequence'] = 90
        raw = json.dumps(receipt).encode()
        home['last_receipt_sha256'] = hashlib.sha256(raw).hexdigest()
        self.assertEqual(verify_receipt(home, raw),
                         ['GENESIS_HOME_RECEIPT_STATE_MISMATCH'])

    def test_home_receipt_event_identity_is_bound_to_checkpoint(self):
        home = self.sources[1]
        receipt, _ = sample_receipt(home)
        receipt['event_id'] = 'forged'
        raw = json.dumps(receipt).encode()
        home['last_receipt_sha256'] = hashlib.sha256(raw).hexdigest()
        self.assertEqual(verify_receipt(home, raw),
                         ['GENESIS_HOME_RECEIPT_STATE_MISMATCH'])

    def test_home_receipt_authority_guard_is_alert(self):
        home = self.sources[1]
        receipt, _ = sample_receipt(home)
        receipt['source_writeback_observed'] = True
        raw = json.dumps(receipt).encode()
        home['last_receipt_sha256'] = hashlib.sha256(raw).hexdigest()
        self.assertEqual(verify_receipt(home, raw),
                         ['GENESIS_HOME_RECEIPT_AUTHORITY_GUARD'])

    def test_home_receipt_path_cannot_escape_expected_branch(self):
        home = self.sources[1]
        home['checkpoint_head'] = 'state/habitat_cloud_home/receipts/../STATE.json'
        home['handoff_head'] = home['checkpoint_head']
        with self.assertRaisesRegex(ValueError, 'untrusted HOME receipt path'):
            receipt_url(home)

    def test_home_receipt_path_sequence_and_run_id_are_bound(self):
        home = self.sources[1]
        home['checkpoint_head'] = 'state/habitat_cloud_home/receipts/00000092-123-1.json'
        home['handoff_head'] = home['checkpoint_head']
        with self.assertRaisesRegex(ValueError, 'sequence disagreement'):
            receipt_url(home)
        home['checkpoint_head'] = 'state/habitat_cloud_home/receipts/00000091-124-1.json'
        home['handoff_head'] = home['checkpoint_head']
        with self.assertRaisesRegex(ValueError, 'run disagreement'):
            receipt_url(home)

    def test_home_checkpoint_history_advances_once_and_cursor_never_regresses(self):
        url = predecessor_state_url(self.sources[1], self.sources[4])
        self.assertIn('d' * 40, url)
        self.assertTrue(url.endswith('/state/habitat_cloud_home/STATE.json'))
        alerts, metrics = verify_checkpoint_progress(self.sources[1], sample_predecessor())
        self.assertEqual(alerts, [])
        self.assertEqual(metrics['home_previous_checkpoint'], 90)
        self.assertEqual(metrics['home_previous_cursor_sequence'], 5)

    def test_home_history_snapshot_race_is_unknown_not_rollback_claim(self):
        commits = copy.deepcopy(self.sources[4])
        commits[0]['commit']['message'] = 'JANUS cloud HOME checkpoint 124/1'
        with self.assertRaisesRegex(ValueError, 'not yet synchronized'):
            predecessor_state_url(self.sources[1], commits)

    def test_home_sequence_rollback_and_reuse_detected(self):
        old = sample_predecessor()
        old['sequence'] = 92
        alerts, _ = verify_checkpoint_progress(self.sources[1], old)
        self.assertIn('GENESIS_HOME_SEQUENCE_ROLLBACK', alerts)
        old['sequence'] = 91
        alerts, _ = verify_checkpoint_progress(self.sources[1], old)
        self.assertIn('GENESIS_HOME_SEQUENCE_REUSED', alerts)

    def test_home_sequence_gap_detected(self):
        old = sample_predecessor()
        old['sequence'] = 88
        alerts, _ = verify_checkpoint_progress(self.sources[1], old)
        self.assertIn('GENESIS_HOME_SEQUENCE_GAP', alerts)

    def test_home_beetle_cursor_rollback_detected(self):
        old = sample_predecessor()
        old['beetle_memory']['cursor_sequence'] = 7
        alerts, _ = verify_checkpoint_progress(self.sources[1], old)
        self.assertIn('GENESIS_HOME_BEETLE_CURSOR_ROLLBACK', alerts)

    def test_home_run_attempt_reuse_detected(self):
        old = sample_predecessor()
        old['last_run_id'] = self.sources[1]['last_run_id']
        old['checkpoint_head'] = 'state/habitat_cloud_home/receipts/00000090-123-1.json'
        alerts, _ = verify_checkpoint_progress(self.sources[1], old)
        self.assertIn('GENESIS_HOME_RUN_ATTEMPT_REUSED', alerts)

    def test_legitimate_github_rerun_higher_attempt_does_not_alert(self):
        home = copy.deepcopy(self.sources[1])
        home['checkpoint_head'] = 'state/habitat_cloud_home/receipts/00000091-123-2.json'
        old = sample_predecessor()
        old['last_run_id'] = home['last_run_id']
        old['checkpoint_head'] = 'state/habitat_cloud_home/receipts/00000090-123-1.json'
        alerts, _ = verify_checkpoint_progress(home, old)
        self.assertEqual(alerts, [])

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

    def test_receipt_transport_failure_is_unknown_not_delivery_alert(self):
        sources = self.sources
        with mock.patch('beetle_home_watchdog.fetch_json',
                        side_effect=[*sources, sample_predecessor()]), \
                mock.patch('beetle_home_watchdog.fetch_receipt_bytes',
                           side_effect=OSError('GitHub unavailable')):
            with mock.patch.object(sys, 'argv', ['watch']):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    code = main(now=NOW)
        self.assertEqual(code, 2)
        self.assertIn('"status": "UNKNOWN"', output.getvalue())

    def test_alert_result_produces_nonzero_status(self):
        sources = self.mutate(0, lambda h: h.update(at='2026-10-17T18:00:00Z'))
        _, raw = sample_receipt(sources[1])
        with mock.patch('beetle_home_watchdog.fetch_json',
                        side_effect=[*sources, sample_predecessor(), sample_highwater(sources[1])]), \
                mock.patch('beetle_home_watchdog.fetch_receipt_bytes', return_value=raw):
            with mock.patch.object(sys, 'argv', ['watch']):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = main(now=NOW)
        self.assertEqual(code, 1)

    def test_receipt_mismatch_turns_otherwise_pass_into_alert(self):
        sources = copy.deepcopy(self.sources)
        _, raw = sample_receipt(sources[1])
        with mock.patch('beetle_home_watchdog.fetch_json',
                        side_effect=[*sources, sample_predecessor(), sample_highwater(sources[1])]), \
                mock.patch('beetle_home_watchdog.fetch_receipt_bytes',
                           return_value=raw + b'corrupted'):
            with mock.patch.object(sys, 'argv', ['watch']):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    code = main(now=NOW)
        self.assertEqual(code, 1)
        self.assertIn('GENESIS_HOME_RECEIPT_SHA256_MISMATCH', output.getvalue())

    def test_predecessor_fetch_failure_is_unknown(self):
        sources = copy.deepcopy(self.sources)
        _, raw = sample_receipt(sources[1])
        with mock.patch('beetle_home_watchdog.fetch_json',
                        side_effect=[*sources, OSError('commit 404')]), \
                mock.patch('beetle_home_watchdog.fetch_receipt_bytes', return_value=raw):
            with mock.patch.object(sys, 'argv', ['watch']):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    code = main(now=NOW)
        self.assertEqual(code, 2)
        self.assertIn('"status": "UNKNOWN"', output.getvalue())


if __name__ == '__main__':
    unittest.main()
