"""End-to-end queue/receiver/ACK tests, with no external network or Git writes."""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

TOOLS = pathlib.Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
from beetle_mirror_router import canon, queue_batch, queue_snapshot, safe_repo, to_item
from beetle_memory_receiver import stage, INBOX_STATUS
from beetle_delivery_health import classify_missing_ack, inspect

REPO = 'Hawkar-usls/Janus_Genesis'
TIME = '2026-10-17T00:00:00Z'


def packet(index):
    bid = f'{index:020x}'
    return {'schema': 'janus.beetle.repo_memory_batch.v1', 'target_repository': REPO,
            'batch_id': bid, 'claim_ceiling': 'DISCOVERY_MEMORY_ONLY__TARGET_REPO_MUST_VERIFY_INDEPENDENTLY',
            'items': [{'target_repository': REPO,
                       'epistemic_status': 'DISCOVERY_INBOX__UNVERIFIED__NO_PROOF_AUTHORITY',
                       'context_id': f'context_{index}'}]}


class DeliveryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.mirror = self.root / 'mirrors' / safe_repo(REPO)
        self.inbox = self.root / 'target' / 'data' / 'beetle-inbox'

    def send(self, index, created_at=TIME):
        return queue_batch(self.mirror, REPO, packet(index), created_at)

    def fetch(self, url, max_bytes):
        path = self.mirror / url.rsplit('/', 1)[-1]
        if '/batches/' in url:
            path = self.mirror / 'batches' / url.rsplit('/', 1)[-1]
        if not path.exists():
            raise FileNotFoundError(url)
        data = path.read_bytes()
        self.assertLessEqual(len(data), max_bytes)
        return data

    def receive(self, max_batches=96, fetch=None):
        return stage(self.inbox, REPO, fetch=fetch or self.fetch, max_batches=max_batches)

    def test_monotone_queue_preserves_hourly_intermediate_batches(self):
        for i in range(1, 5):
            self.assertEqual(self.send(i), i)
        result = self.receive()
        self.assertEqual(result['new_batches'], 4)
        self.assertEqual(result['last_sequence'], 4)
        self.assertEqual(len(list((self.inbox / 'batches').glob('*.json'))), 4)
        self.assertEqual(json.loads((self.inbox / 'LATEST.json').read_text())['batch_id'], packet(4)['batch_id'])
        self.assertEqual(json.loads((self.inbox / 'ACK.json').read_text())['status'], INBOX_STATUS)

    def test_repeated_producer_run_never_requeues_same_batch(self):
        self.assertEqual(self.send(1), 1)
        self.assertEqual(self.send(1), 1)
        self.assertEqual(json.loads((self.mirror / 'delivery.json').read_text())['next_sequence'], 2)

    def test_receiver_idempotent_and_resumes_bounded_backlog(self):
        for i in range(1, 7):
            self.send(i)
        self.assertEqual(self.receive(max_batches=2)['last_sequence'], 2)
        ack_hash = hashlib.sha256((self.inbox / 'ACK.json').read_bytes()).hexdigest()
        self.assertEqual(self.receive(max_batches=2)['last_sequence'], 4)
        self.assertNotEqual(ack_hash, hashlib.sha256((self.inbox / 'ACK.json').read_bytes()).hexdigest())
        self.assertEqual(self.receive(max_batches=2)['last_sequence'], 6)
        before = hashlib.sha256((self.inbox / 'ACK.json').read_bytes()).hexdigest()
        self.assertEqual(self.receive()['status'], 'UP_TO_DATE')
        self.assertEqual(before, hashlib.sha256((self.inbox / 'ACK.json').read_bytes()).hexdigest())

    def test_failed_download_does_not_advance_ack_or_commit_partial_window(self):
        for i in range(1, 3):
            self.send(i)
        def broken(url, cap):
            if packet(2)['batch_id'] in url:
                raise ConnectionError('down')
            return self.fetch(url, cap)
        with self.assertRaises(ConnectionError):
            self.receive(fetch=broken)
        self.assertFalse((self.inbox / 'ACK.json').exists())
        self.assertEqual(self.receive()['last_sequence'], 2)

    def test_sha256_corruption_and_address_mismatch_are_rejected(self):
        self.send(1)
        path = self.mirror / 'batches' / f"{packet(1)['batch_id']}.json"
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.receive()
        self.assertFalse((self.inbox / 'ACK.json').exists())

    def test_sender_queue_collision_and_receiver_ack_conflict_fail_closed(self):
        self.send(1)
        altered = packet(1)
        altered['items'].append({'target_repository': REPO})
        with self.assertRaisesRegex(ValueError, 'collision'):
            queue_batch(self.mirror, REPO, altered, TIME)
        self.receive()
        ack_path = self.inbox / 'ACK.json'
        ack = json.loads(ack_path.read_text())
        ack['sha256'] = 'f' * 64
        ack_path.write_text(json.dumps(ack))
        with self.assertRaisesRegex(ValueError, 'ACK does not match'):
            self.receive()

    def test_status_is_inbox_only_and_stale_detection_works(self):
        self.send(1)
        observed = dt.datetime.fromisoformat('2026-10-17T04:00:00+00:00')
        health = inspect(self.root, fetcher=lambda repo: (None, 'NO_ACK'), observed_at=observed)
        self.assertEqual(health['status'], 'ALERT')
        self.assertEqual(health['repositories'][REPO]['status'], 'STALE')
        self.receive()
        ack = json.loads((self.inbox / 'ACK.json').read_text())
        health = inspect(self.root, fetcher=lambda repo: (ack, None), observed_at=observed)
        self.assertEqual(health['status'], 'PASS')
        self.assertEqual(health['repositories'][REPO]['pending'], 0)
        self.assertEqual(health['ack_semantics'], 'INBOX_DURABLE_ONLY_NOT_RUNTIME_CONSUMPTION')

    def test_private_or_inaccessible_ack_keeps_pending_without_false_stale(self):
        self.send(1)
        observed = dt.datetime.fromisoformat('2026-10-17T04:00:00+00:00')
        health = inspect(self.root, fetcher=lambda repo: (None, 'ACK_VISIBILITY_UNKNOWN'),
                         observed_at=observed)
        row = health['repositories'][REPO]
        self.assertEqual(health['status'], 'WARN')
        self.assertEqual(row['status'], 'ACK_UNAVAILABLE')
        self.assertEqual(row['pending'], 1)
        self.assertEqual(row['confirmed'], 0)
        self.assertEqual(row['oldest_pending_minutes'], 240)

    def test_transient_ack_transport_error_never_proves_stale(self):
        self.send(1)
        observed = dt.datetime.fromisoformat('2026-10-17T04:00:00+00:00')
        health = inspect(self.root, fetcher=lambda repo: (None, 'HTTP_503'),
                         observed_at=observed)
        self.assertEqual(health['repositories'][REPO]['status'], 'ACK_UNAVAILABLE')
        self.assertEqual(health['status'], 'WARN')

    def test_public_repo_metadata_proves_missing_ack_when_404(self):
        metadata = json.dumps({'full_name': REPO, 'private': False}).encode()
        with mock.patch('beetle_delivery_health.urllib.request.urlopen',
                        return_value=io.BytesIO(metadata)):
            self.assertEqual(classify_missing_ack(REPO), 'NO_ACK')
        with mock.patch('beetle_delivery_health.urllib.request.urlopen',
                        side_effect=urllib.error.HTTPError('https://api.github.com',
                                                           404, 'not found', None, None)):
            self.assertEqual(classify_missing_ack(REPO), 'ACK_VISIBILITY_UNKNOWN')

    def test_old_ack_cannot_skip_newly_queued_batches(self):
        self.send(1)
        self.receive()
        for i in range(2, 5):
            self.send(i)
        old = json.loads((self.inbox / 'ACK.json').read_text())
        h = inspect(self.root, fetcher=lambda repo: (old, None))
        self.assertEqual(h['repositories'][REPO]['pending'], 3)
        self.assertEqual(self.receive()['new_batches'], 3)

    def test_missing_sender_manifest_never_advances_ack(self):
        r = self.receive()
        self.assertEqual(r['status'], 'NO_DELIVERY_QUEUE')
        self.assertFalse((self.inbox / 'ACK.json').exists())

    def test_same_context_id_with_updated_metadata_gets_new_immutable_batch(self):
        first = {'target_repository': REPO, 'epistemic_status': 'DISCOVERY_INBOX__UNVERIFIED__NO_PROOF_AUTHORITY',
                 'context_id': 'stable-context-id', 'mirror_lens': 'FORWARD',
                 'summary': 'old summary'}
        one = queue_snapshot(self.mirror, REPO, [first], 48, TIME)
        again = queue_snapshot(self.mirror, REPO, [first], 48, TIME)
        self.assertEqual(one[0][0]['batch_id'], again[0][0]['batch_id'])
        self.assertEqual(one[0][1], again[0][1])
        changed = dict(first, summary='updated independently published summary')
        two = queue_snapshot(self.mirror, REPO, [changed], 48, TIME)
        self.assertNotEqual(one[0][0]['batch_id'], two[0][0]['batch_id'])
        self.assertEqual(two[0][1], 2)
        self.assertEqual(self.receive()['last_sequence'], 2)
        self.assertEqual(len(list((self.inbox / 'batches').glob('*.json'))), 2)

    def test_large_mirror_snapshot_is_split_losslessly_and_replayed(self):
        selected = [{'target_repository': REPO,
                     'epistemic_status': 'DISCOVERY_INBOX__UNVERIFIED__NO_PROOF_AUTHORITY',
                     'context_id': f'context-{n}', 'mirror_lens': 'FORWARD',
                     'summary': 'observational metadata ' * 22}
                    for n in range(12)]
        parts = queue_snapshot(self.mirror, REPO, selected, 48, TIME, max_bytes=1400)
        self.assertGreater(len(parts), 1)
        self.assertEqual(sum(len(packet['items']) for packet, _ in parts), len(selected))
        self.assertEqual([seq for _, seq in parts], list(range(1, len(parts) + 1)))
        self.assertTrue(all(len((self.mirror / 'batches' / f"{packet['batch_id']}.json").read_bytes()) <= 1400
                            for packet, _ in parts))
        self.assertEqual(self.receive()['new_batches'], len(parts))
        recovered = []
        for packet, _ in parts:
            recovered.extend(json.loads((self.inbox / 'batches' / f"{packet['batch_id']}.json").read_bytes())['items'])
        self.assertEqual(recovered, selected)

    def test_unshardable_single_discovery_never_creates_partial_queue(self):
        selected = [{'target_repository': REPO,
                     'epistemic_status': 'DISCOVERY_INBOX__UNVERIFIED__NO_PROOF_AUTHORITY',
                     'context_id': 'oversize', 'mirror_lens': 'FORWARD', 'summary': 'X' * 4000}]
        with self.assertRaisesRegex(ValueError, 'single Beetle discovery'):
            queue_snapshot(self.mirror, REPO, selected, 48, TIME, max_bytes=700)
        self.assertFalse((self.mirror / 'delivery.json').exists())
        self.assertFalse((self.mirror / 'batches').exists())

    def test_untrusted_large_source_yields_bounded_preview_with_source_hash(self):
        source = {'context_id': 'abcd' * 6, 'candidate_id': 'efgh' * 6,
                  'direction_id': 'forward', 'mirror_lens': 'FORWARD',
                  'source': 'arxiv', 'url': 'https://example.com/' + 'x' * 8000,
                  'title': 'T' * 9000, 'summary': 'S' * 5_000_000,
                  'tags': ['tag' * 100] * 400}
        item = to_item(source, REPO)
        self.assertEqual(item['source_context_sha256'], hashlib.sha256(canon(source)).hexdigest())
        self.assertTrue(item['delivery_preview_only'])
        self.assertTrue(item['delivery_preview_truncated'])
        self.assertEqual(len(item['summary']), 6000)
        self.assertEqual(len(item['title']), 300)
        self.assertEqual(len(item['tags']), 32)
        self.assertLess(len(json.dumps(item).encode()), 25_000)
        packet, seq = queue_snapshot(self.mirror, REPO, [item], 48, TIME)[0]
        self.assertEqual(seq, 1)
        self.assertEqual(self.receive()['last_sequence'], 1)
        self.assertEqual(packet['items'][0]['source_context_sha256'], item['source_context_sha256'])


if __name__ == '__main__':
    unittest.main()
