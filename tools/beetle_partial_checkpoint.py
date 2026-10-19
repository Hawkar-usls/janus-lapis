#!/usr/bin/env python3
"""Fail-closed, provenance-checked salvage of a crashed Beetle worker.

Only complete candidate+receipt pairs and hash-matched HTTP Range chunks
can become durable. The caller must NOT route new packets or advance ACKs.
Subprocess grazer output is excluded unless separately verified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from beetle_shard_store import iter_lines, seal

RECEIPT_SCHEMA = 'janus.universal_beetle.receipt.v1'
CANDIDATE_SCHEMA = 'janus.universal_beetle.candidate.v1'
PARTIAL_SCHEMA = 'janus.beetle.partial_checkpoint.v1'
TASK_ID = re.compile(r'[A-Za-z0-9_-]{1,80}\Z')
HASH = re.compile(r'[0-9a-f]{64}\Z')


def sha256_obj(obj: dict) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def item_id(source: str, url: str, title: str) -> str:
    return hashlib.sha256(f'{source}\n{url}\n{title}'.encode('utf-8', 'replace')).hexdigest()[:24]


def load_json(path: Path, default: dict) -> dict:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n',
                    encoding='utf-8')
    temp.replace(path)


def _receipts(root: Path) -> list[dict]:
    prev = None
    all_rows = []
    for line in iter_lines(root, 'receipts'):
        row = json.loads(line)
        digest = row.get('receipt_sha256') if isinstance(row, dict) else None
        content = {k: v for k, v in row.items() if k != 'receipt_sha256'}
        if (row.get('schema') != RECEIPT_SCHEMA or
            row.get('prev_receipt_sha256') != prev or
            not isinstance(digest, str) or HASH.fullmatch(digest) is None or
            digest != sha256_obj(content)):
            raise ValueError('unverified Beetle receipt hash chain')
        prev = digest
        all_rows.append(row)
    return all_rows


def snapshot(root: Path) -> dict:
    receipts = _receipts(root)
    seen = load_json(root / 'seen.json', {})
    cursors = load_json(root / 'cursors.json', {})
    if not isinstance(seen, dict) or not isinstance(cursors, dict):
        raise ValueError('malformed baseline Beetle state')
    return {'schema': PARTIAL_SCHEMA, 'receipt_head':
            receipts[-1]['receipt_sha256'] if receipts else None,
            'seen': seen, 'cursors': cursors}


def salvage(root: Path, baseline: dict, run_id: str) -> dict:
    if (not isinstance(baseline, dict) or baseline.get('schema') != PARTIAL_SCHEMA or
        not isinstance(baseline.get('seen'), dict) or
        not isinstance(baseline.get('cursors'), dict) or
        (baseline.get('receipt_head') is not None and
         (not isinstance(baseline['receipt_head'], str) or
          HASH.fullmatch(baseline['receipt_head']) is None)) or
        not re.fullmatch(r'[0-9]{1,20}', run_id)):
        raise ValueError('untrusted partial-checkpoint baseline')

    receipts = _receipts(root)
    old_head = baseline['receipt_head']
    old_index = next((i for i, row in enumerate(receipts)
                      if row['receipt_sha256'] == old_head), None) if old_head else -1
    if old_index is None or (old_head is None and receipts and
                             receipts[0]['prev_receipt_sha256'] is not None):
        raise ValueError('baseline receipt head lost or replaced')
    added = receipts[old_index + 1:]
    receipt_candidates = {row.get('payload', {}).get('candidate_id')
                          for row in added if row.get('event') == 'CANDIDATE_ADDED'
                          and isinstance(row.get('payload'), dict)}
    original_seen = baseline['seen']
    confirmed_seen = dict(original_seen)
    new_candidates = set()
    for line in iter_lines(root, 'candidates'):
        row = json.loads(line)
        if (not isinstance(row, dict) or row.get('schema') != CANDIDATE_SCHEMA or
            row.get('epistemic_status') !=
            'DISCOVERY_CANDIDATE__NOT_VERIFIED__NO_PROOF_AUTHORITY' or
            any(not isinstance(row.get(k), str) for k in
                ('candidate_id', 'source', 'url', 'title', 'direction_id', 'discovered_at')) or
            row['candidate_id'] != item_id(row['source'], row['url'], row['title'])):
            raise ValueError('invalid candidate in partial append-only ledger')
        cid = row['candidate_id']
        if cid not in original_seen:
            if cid in new_candidates or cid not in receipt_candidates:
                raise ValueError('unreceipted or duplicate new candidate')
            new_candidates.add(cid)
            confirmed_seen[cid] = {'first_seen_at': row['discovered_at'],
                                   'direction_id': row['direction_id'],
                                   'source': row['source'], 'url': row['url'],
                                   'score': row['score']}
    if receipt_candidates != new_candidates:
        raise ValueError('candidate receipt not matched by persisted ledger')

    # Rebuild from baseline rather than trusting an in-memory cursor advanced
    # before a crash. Each new byte offset requires an exact receipt and bytes.
    cursors = dict(baseline['cursors'])
    staged_chunks = []
    for receipt in added:
        if receipt.get('event') != 'GRAZER_BITE':
            continue
        payload = receipt.get('payload')
        if not isinstance(payload, dict) or payload.get('kind') != 'http_range_text':
            raise ValueError('unexpected grazer bite')
        task = payload.get('task_id')
        points = payload.get('range')
        digest = payload.get('sha256')
        if (not isinstance(task, str) or TASK_ID.fullmatch(task) is None or
            not isinstance(points, list) or len(points) != 2 or
            not all(type(v) is int for v in points) or
            points[0] < 0 or points[1] <= points[0] or
            payload.get('bytes') != points[1] - points[0] or
            not isinstance(digest, str) or HASH.fullmatch(digest) is None):
            raise ValueError('malformed grazer bite receipt')
        key = f'grazer:{task}:byte_offset'
        start, end = points
        if type(cursors.get(key, 0)) is not int or cursors.get(key, 0) != start:
            raise ValueError('non-contiguous grazer partial cursor')
        chunk = root / 'grazers' / task / 'chunks' / f'{start:012d}-{end:012d}.bin'
        if (chunk.is_symlink() or not chunk.is_file() or
            chunk.stat().st_size != payload['bytes'] or
            hashlib.sha256(chunk.read_bytes()).hexdigest() != digest):
            raise ValueError('missing or corrupt grazer chunk')
        cursors[key] = end
        staged_chunks.append(chunk.relative_to(root).as_posix())

    # Validate all prospective blobs and shard indexes *before* publishing.
    # A crash after these atomic local writes is still recoverable next tick.
    atomic_json(root / 'seen.json', confirmed_seen)
    atomic_json(root / 'cursors.json', cursors)
    summary = {'schema': PARTIAL_SCHEMA, 'run_id': run_id,
               'status': 'VALIDATED_PARTIAL_ONLY__WORKER_FAILED',
               'new_candidates': len(new_candidates),
               'validated_chunks': staged_chunks,
               'receipt_head': receipts[-1]['receipt_sha256'] if receipts else None,
               'queue_published': False, 'ack_advanced': False,
               'scientific_authority_delta': 0,
               'external_effect_authority_delta': 0}
    atomic_json(root / 'latest_partial_checkpoint.json', summary)
    seal(root)
    return summary


def live_checkpoint(root: Path, baseline: dict, run_id: str, git_root: Path) -> dict:
    """Commit a verified progress cut while the worker is STILL running.

    A later SIGKILL/runner disappearance cannot erase an earlier remote Git
    commit. Mirrored delivery queues and ACKs are never staged by this path.
    """
    repo = git_root.resolve(strict=True)
    if root.resolve(strict=True) != repo / 'data/beetle-state':
        raise ValueError('durable checkpoint root is outside Beetle state checkout')

    def git(*args: str) -> str:
        done = subprocess.run(['git', '-C', str(repo), *args], check=True,
                              text=True, capture_output=True)
        return done.stdout.strip()

    if git('rev-parse', '--abbrev-ref', 'HEAD') != 'beetle-state':
        raise ValueError('live checkpoint requires checked-out beetle-state branch')
    summary = salvage(root, baseline, run_id)
    summary['status'] = 'VALIDATED_MID_RUN__WORKER_STILL_ACTIVE'
    summary['worker_interrupted'] = False
    atomic_json(root / 'latest_partial_checkpoint.json', summary)
    seal(root)

    allowable = [
        'data/beetle-state/seen.json',
        'data/beetle-state/cursors.json',
        'data/beetle-state/latest_partial_checkpoint.json',
        'data/beetle-state/latest_storage_health.json',
    ]
    for ledger in ('candidates', 'receipts'):
        path = repo / 'data/beetle-state' / f'{ledger}.parts'
        if path.is_dir():
            allowable.append(f'data/beetle-state/{ledger}.parts')
    allowable.extend('data/beetle-state/' + name for name in summary['validated_chunks'])
    git('add', '-A', '--', *allowable)

    staged = git('diff', '--cached', '--name-only').splitlines()
    shard_pattern = re.compile(
        r'data/beetle-state/(candidates|receipts)\.parts/(part-[0-9]{6}\.jsonl|index\.json|migration\.json)\Z')
    flat = set(allowable[:4])
    chunks = {'data/beetle-state/' + name for name in summary['validated_chunks']}
    if any(path not in flat and path not in chunks and not shard_pattern.fullmatch(path)
           for path in staged):
        raise ValueError('live checkpoint attempted to stage unverified output')
    if not staged:
        return {**summary, 'remote_action': 'NO_CHANGE'}
    git('diff', '--cached', '--check')
    git('commit', '-m', f'beetle: verified mid-run checkpoint {run_id}')
    # Fail closed on failure to reach remote. Never silently claim a durable
    # checkpoint based only on local runner Git state.
    git('push', 'origin', 'HEAD:beetle-state')
    return {**summary, 'remote_action': 'PUSH_CONFIRMED', 'commit': git('rev-parse', 'HEAD')}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['snapshot', 'salvage', 'live'])
    p.add_argument('--state-dir', required=True, type=Path)
    p.add_argument('--baseline', required=True, type=Path)
    p.add_argument('--run-id', default='0')
    p.add_argument('--git-root', type=Path, default=None)
    args = p.parse_args()
    if args.action == 'snapshot':
        atomic_json(args.baseline, snapshot(args.state_dir))
        result = {'status': 'BASELINE_STORED'}
    elif args.action == 'salvage':
        result = salvage(args.state_dir, json.loads(args.baseline.read_text()), args.run_id)
    else:
        if args.git_root is None:
            p.error('--git-root is required for live durable checkpoint')
        result = live_checkpoint(args.state_dir,
                                 json.loads(args.baseline.read_text()),
                                 args.run_id, args.git_root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
