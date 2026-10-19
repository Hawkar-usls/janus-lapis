"""Crash-salvage contract: only verified partial records survive (offline)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from beetle_partial_checkpoint import item_id, salvage, snapshot, sha256_obj
from beetle_shard_store import append


class InterruptedBeetleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'beetle-state'
        self.root.mkdir()
        (self.root / 'seen.json').write_text('{}\n')
        (self.root / 'cursors.json').write_text('{}\n')
        self.baseline = snapshot(self.root)

    def receipt(self, event, payload):
        head = snapshot(self.root)['receipt_head']
        row = {'schema': 'janus.universal_beetle.receipt.v1',
               'tool_version': '1.0.0', 'at': '2026-10-19T12:00:00Z',
               'event': event, 'payload': payload, 'prev_receipt_sha256': head}
        append(self.root, 'receipts', {'receipt_sha256': sha256_obj(row), **row})

    def add_candidate(self):
        self.receipt('RUN_START', {'mode': 'both'})
        cid = item_id('arxiv', 'https://arxiv.org/abs/abc', 'Ocean mechanics')
        append(self.root, 'candidates', {
            'schema': 'janus.universal_beetle.candidate.v1',
            'candidate_id': cid, 'epistemic_status':
            'DISCOVERY_CANDIDATE__NOT_VERIFIED__NO_PROOF_AUTHORITY',
            'source': 'arxiv', 'url': 'https://arxiv.org/abs/abc',
            'title': 'Ocean mechanics', 'direction_id': 'test',
            'discovered_at': '2026-10-19T12:00:00Z', 'score': 3.0})
        self.receipt('CANDIDATE_ADDED', {'candidate_id': cid})
        # The worker dies before State.save(); seen.json remains its old value.
        self.assertEqual(json.loads((self.root / 'seen.json').read_text()), {})

    def test_candidate_is_recovered_with_no_queue_or_ack_advancement(self):
        self.add_candidate()
        result = salvage(self.root, self.baseline, '123')
        self.assertEqual(result['new_candidates'], 1)
        self.assertFalse(result['ack_advanced'])
        self.assertFalse(result['queue_published'])
        self.assertEqual(len(json.loads((self.root / 'seen.json').read_text())), 1)
        self.assertFalse((self.root / 'mirrors').exists())
        self.assertEqual(result['validated_chunks'], [])

    def test_verified_range_chunk_recovers_cursor(self):
        body = b'ocean-bite'
        chunk = self.root / 'grazers' / 'test_task' / 'chunks' / f'{0:012d}-{len(body):012d}.bin'
        chunk.parent.mkdir(parents=True)
        chunk.write_bytes(body)
        self.receipt('GRAZER_BITE', {'task_id': 'test_task',
                           'kind': 'http_range_text', 'range': [0, len(body)],
                           'sha256': hashlib.sha256(body).hexdigest(),
                           'bytes': len(body)})
        result = salvage(self.root, self.baseline, '124')
        self.assertEqual(json.loads((self.root / 'cursors.json').read_text())
                         ['grazer:test_task:byte_offset'], len(body))
        self.assertEqual(len(result['validated_chunks']), 1)

    def test_corrupt_or_missing_chunk_never_advances_cursor(self):
        self.receipt('GRAZER_BITE', {'task_id': 'test_task',
                           'kind': 'http_range_text', 'range': [0, 4],
                           'sha256': 'f' * 64, 'bytes': 4})
        with self.assertRaisesRegex(ValueError, 'missing or corrupt'):
            salvage(self.root, self.baseline, '125')
        self.assertEqual(json.loads((self.root / 'cursors.json').read_text()), {})

    def test_unreceipted_candidate_does_not_survive(self):
        append(self.root, 'candidates', {'schema': 'janus.universal_beetle.candidate.v1',
               'candidate_id': 'bad', 'epistemic_status':
               'DISCOVERY_CANDIDATE__NOT_VERIFIED__NO_PROOF_AUTHORITY'})
        with self.assertRaisesRegex(ValueError, 'invalid candidate'):
            salvage(self.root, self.baseline, '126')

    def test_hash_tampered_receipt_fails_closed(self):
        self.receipt('RUN_START', {'mode': 'both'})
        path = next((self.root / 'receipts.parts').glob('part-*.jsonl'))
        raw = path.read_text()
        path.write_text(raw.replace('RUN_START', 'RUN_BREAK'))
        with self.assertRaisesRegex(ValueError, 'hash chain'):
            salvage(self.root, self.baseline, '127')

    def test_prior_receipt_head_cannot_disappear(self):
        self.receipt('RUN_START', {'mode': 'both'})
        other_baseline = snapshot(self.root)
        (self.root / 'receipts.parts' / 'part-000001.jsonl').write_text('')
        with self.assertRaisesRegex(ValueError, 'baseline receipt head lost'):
            salvage(self.root, other_baseline, '128')

    def test_invalid_run_identity_rejected(self):
        with self.assertRaisesRegex(ValueError, 'baseline'):
            salvage(self.root, self.baseline, 'unsafe/checkout')


if __name__ == '__main__':
    unittest.main()
