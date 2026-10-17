#!/usr/bin/env python3
"""Bounded, idempotent consumer for the JANUS Beetle discovery-only outbox.

Run inside a target repository's beetle-memory checkout.  The workflow commits
the staged inbox and ACK atomically: an ACK is not visible until git push.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import time
import urllib.error
import urllib.request
from typing import Callable

SOURCE = 'https://raw.githubusercontent.com/Hawkar-usls/janus-lapis/beetle-state/data/beetle-state/mirrors'
INBOX_STATUS = 'INBOX_DURABLE_UNVERIFIED__NOT_RUNTIME_CONSUMPTION'
CLAIM_CEILING = 'DISCOVERY_MEMORY_ONLY__TARGET_REPO_MUST_VERIFY_INDEPENDENTLY'
MAX_QUEUE_BYTES = 32_000_000
MAX_BATCH_BYTES = 4_000_000


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def fetch_url(url: str, max_bytes: int) -> bytes:
    error = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'JANUS-Beetle-Receiver/1'})
            with urllib.request.urlopen(req, timeout=15) as response:
                data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ValueError(f'remote data exceeds {max_bytes} bytes: {url}')
            return data
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise FileNotFoundError(url) from exc
            if exc.code not in (429, 500, 502, 503, 504):
                raise
            error = exc
        except (urllib.error.URLError, TimeoutError) as exc:
            error = exc
        if attempt < 3:
            time.sleep(1 + attempt)
    raise RuntimeError(f'failed to fetch {url}: {error}')


def read_json(path: pathlib.Path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def atomic_bytes(path: pathlib.Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_bytes(data)
    tmp.replace(path)


def atomic_json(path: pathlib.Path, data: dict) -> None:
    atomic_bytes(path, (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode('utf-8'))


def stage(inbox: pathlib.Path, repo: str, fetch: Callable[[str, int], bytes] = fetch_url,
          max_batches: int = 96, source: str = SOURCE) -> dict:
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('invalid recipient repository name')
    if not 1 <= max_batches <= 256:
        raise ValueError('max_batches must be 1..256')
    slug = repo.replace('/', '__')
    base = f'{source}/{slug}'
    try:
        queue = json.loads(fetch(f'{base}/delivery.json', MAX_QUEUE_BYTES))
    except FileNotFoundError:
        return {'status': 'NO_DELIVERY_QUEUE', 'repository': repo, 'new_batches': 0}
    if queue.get('schema') != 'janus.beetle.delivery_queue.v1' or queue.get('target_repository') != repo:
        raise ValueError('wrong or invalid sender queue')
    entries = queue.get('entries')
    if not isinstance(entries, list) or queue.get('next_sequence') != len(entries) + 1:
        raise ValueError('invalid sender queue length')
    for seq, entry in enumerate(entries, 1):
        if (entry.get('sequence') != seq or
            not re.fullmatch(r'[0-9a-f]{20}', str(entry.get('batch_id', ''))) or
            not re.fullmatch(r'[0-9a-f]{64}', str(entry.get('sha256', '')))):
            raise ValueError(f'broken sender queue at sequence {seq}')
    ack_path = inbox / 'ACK.json'
    ack = read_json(ack_path, {})
    if ack:
        if ack.get('schema') != 'janus.beetle.inbox_ack.v1' or ack.get('target_repository') != repo or ack.get('status') != INBOX_STATUS:
            raise ValueError('untrusted or incompatible existing ACK')
    current = ack.get('last_sequence', 0)
    if not isinstance(current, int) or isinstance(current, bool) or current < 0 or current > len(entries):
        raise ValueError('ACK sequence outside sender queue')
    if current:
        previous = entries[current - 1]
        if ack.get('batch_id') != previous['batch_id'] or ack.get('sha256') != previous['sha256']:
            raise ValueError('ACK does not match immutable sender queue')
        previous_path = inbox / 'batches' / f"{previous['batch_id']}.json"
        if not previous_path.is_file() or hashlib.sha256(previous_path.read_bytes()).hexdigest() != previous['sha256']:
            raise ValueError('ACK points to missing or corrupted durable batch')
    if current == len(entries):
        return {'status': 'UP_TO_DATE', 'repository': repo, 'new_batches': 0, 'last_sequence': current}
    selected = entries[current:current + max_batches]
    records = []
    for entry in selected:
        data = fetch(f"{base}/batches/{entry['batch_id']}.json", MAX_BATCH_BYTES)
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError(f"sender batch checksum mismatch: {entry['batch_id']}")
        packet = json.loads(data)
        if (packet.get('schema') != 'janus.beetle.repo_memory_batch.v1' or
            packet.get('target_repository') != repo or
            packet.get('batch_id') != entry['batch_id'] or
            packet.get('claim_ceiling') != CLAIM_CEILING or
            not isinstance(packet.get('items'), list)):
            raise ValueError(f"invalid addressed discovery batch {entry['batch_id']}")
        for item in packet['items']:
            if item.get('target_repository') != repo or item.get('epistemic_status') != 'DISCOVERY_INBOX__UNVERIFIED__NO_PROOF_AUTHORITY':
                raise ValueError(f"unsafe item in batch {entry['batch_id']}")
        target = inbox / 'batches' / f"{entry['batch_id']}.json"
        if target.exists() and target.read_bytes() != data:
            raise ValueError(f"existing batch differs: {entry['batch_id']}")
        records.append((entry, data, target))
    # Validate the whole bounded window before writing anything.  A failure
    # must not advance the durable ACK or become a partial git commit.
    for _, data, target in records:
        if not target.exists():
            atomic_bytes(target, data)
    final_entry, final_data, _ = records[-1]
    atomic_bytes(inbox / 'LATEST.json', final_data)
    readme = inbox / 'README.md'
    if not readme.exists():
        atomic_bytes(readme, b'# JANUS Beetle discovery inbox\n\nUnverified research only. ACK proves inbox durability, NOT runtime ingestion or scientific evidence.\n')
    atomic_json(ack_path, {
        'schema': 'janus.beetle.inbox_ack.v1',
        'target_repository': repo,
        'status': INBOX_STATUS,
        'last_sequence': final_entry['sequence'],
        'batch_id': final_entry['batch_id'],
        'sha256': final_entry['sha256'],
        'acknowledged_at': utc_now(),
        'scientific_authority_delta': 0,
    })
    return {'status': 'STAGED_NOT_YET_PUSHED', 'repository': repo,
            'new_batches': len(records), 'last_sequence': final_entry['sequence'],
            'remaining': len(entries) - final_entry['sequence']}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--inbox-dir', required=True)
    p.add_argument('--target-repository', required=True)
    p.add_argument('--max-batches', type=int, default=96)
    args = p.parse_args()
    result = stage(pathlib.Path(args.inbox_dir), args.target_repository, max_batches=args.max_batches)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
