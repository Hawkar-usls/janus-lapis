#!/usr/bin/env python3
"""Observe receiver commits without mistaking inbox delivery for runtime uptake."""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import pathlib
import re
import urllib.error
import urllib.request

from beetle_mirror_router import load_json, atomic, safe_repo
from beetle_memory_receiver import INBOX_STATUS

ACK_PATH = 'beetle-memory/data/beetle-inbox/ACK.json'


def classify_missing_ack(repo: str) -> str:
    """Raw 404 cannot distinguish a missing ACK from a private repository.

    A publicly visible repository with a missing ACK is positive evidence of
    absence. A 404 on repository metadata (or unreadable metadata) is not.
    No cross-repository credentials are used or inferred.
    """
    req = urllib.request.Request(
        f'https://api.github.com/repos/{repo}',
        headers={'User-Agent': 'JANUS-Beetle-ACK-Visibility/1',
                 'Accept': 'application/vnd.github+json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read(100_001)
        if len(raw) > 100_000:
            return 'ACK_VISIBILITY_UNKNOWN'
        metadata = json.loads(raw)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
            ValueError, UnicodeError):
        return 'ACK_VISIBILITY_UNKNOWN'
    if (isinstance(metadata, dict) and metadata.get('full_name') == repo and
            metadata.get('private') is False):
        return 'NO_ACK'
    return 'ACK_VISIBILITY_UNKNOWN'


def fetch_ack(repo: str):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        return None, 'INVALID_REPO'
    url = f'https://raw.githubusercontent.com/{repo}/{ACK_PATH}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'JANUS-Beetle-Delivery-Health/1'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = resp.read(100_001)
        if len(data) > 100_000:
            return None, 'ACK_TOO_LARGE'
        return json.loads(data), None
    except urllib.error.HTTPError as exc:
        return None, (classify_missing_ack(repo) if exc.code == 404
                      else f'HTTP_{exc.code}')
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return None, f'ACK_UNAVAILABLE:{type(exc).__name__}'


def parse_time(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00'))


def inspect_queue(queue: dict, ack: dict | None, error: str | None,
                  observed_at: dt.datetime, stale_minutes: int) -> dict:
    repo = queue['target_repository']
    entries = queue['entries']
    if queue.get('schema') != 'janus.beetle.delivery_queue.v1' or queue.get('next_sequence') != len(entries) + 1:
        raise ValueError(f'invalid sender delivery manifest for {repo}')
    last = 0
    if ack is not None:
        last = ack.get('last_sequence')
        if (ack.get('schema') != 'janus.beetle.inbox_ack.v1' or
            ack.get('target_repository') != repo or
            ack.get('status') != INBOX_STATUS or
            type(last) is not int or last < 0 or last > len(entries) or
            (last and (ack.get('batch_id') != entries[last - 1]['batch_id'] or
                       ack.get('sha256') != entries[last - 1]['sha256']))):
            return {'status': 'ACK_CONFLICT', 'produced': len(entries), 'confirmed': 0,
                    'pending': len(entries), 'reason': 'invalid or mismatched receiver ACK'}
    pending = len(entries) - last
    result = {'status': 'UP_TO_DATE' if pending == 0 else 'PENDING',
              'produced': len(entries), 'confirmed': last, 'pending': pending}
    if ack is not None:
        result['last_confirmed_batch'] = ack.get('batch_id')
        result['last_acknowledged_at'] = ack.get('acknowledged_at')
    if pending:
        oldest = entries[last]['created_at']
        minutes = max(0, int((observed_at - parse_time(oldest)).total_seconds() // 60))
        result['oldest_pending_minutes'] = minutes
        if minutes >= stale_minutes:
            result['status'] = 'STALE'
        if error:
            result['ack_read_error'] = error
            # Inaccessible private ACK or transport errors cannot prove delivery
            # silence, even when the sender's queue is old. Preserve pending.
            if error != 'NO_ACK':
                result['status'] = 'ACK_UNAVAILABLE'
            elif minutes < stale_minutes:
                result['status'] = 'AWAITING_ACK'
    return result


def inspect(root: pathlib.Path, fetcher=fetch_ack, stale_minutes: int = 180,
            observed_at: dt.datetime | None = None) -> dict:
    observed_at = observed_at or dt.datetime.now(dt.timezone.utc)
    queues = {}
    for p in sorted((root / 'mirrors').glob('*/delivery.json')):
        q = load_json(p, None)
        if not isinstance(q, dict):
            raise ValueError(f'invalid queue: {p}')
        repo = q.get('target_repository')
        if not isinstance(repo, str) or safe_repo(repo) != p.parent.name or repo in queues:
            raise ValueError(f'invalid routing identity: {p}')
        queues[repo] = q
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        fetched = dict(zip(queues, pool.map(fetcher, queues)))
    result = {'schema': 'janus.beetle.delivery_health.v1',
              'at': observed_at.isoformat().replace('+00:00', 'Z'),
              'ack_semantics': 'INBOX_DURABLE_ONLY_NOT_RUNTIME_CONSUMPTION',
              'scientific_authority_delta': 0,
              'repositories': {}, 'total_pending': 0}
    for repo, q in queues.items():
        ack, error = fetched[repo]
        row = inspect_queue(q, ack, error, observed_at, stale_minutes)
        result['repositories'][repo] = row
        result['total_pending'] += row['pending']
    states = {r['status'] for r in result['repositories'].values()}
    result['status'] = ('ALERT' if states & {'STALE', 'ACK_CONFLICT'} else
                        'WARN' if states & {'ACK_UNAVAILABLE', 'AWAITING_ACK'} else 'PASS')
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--state-dir', required=True)
    p.add_argument('--stale-minutes', type=int, default=180)
    args = p.parse_args()
    if args.stale_minutes < 1:
        raise ValueError('stale threshold must be positive')
    root = pathlib.Path(args.state_dir)
    result = inspect(root, stale_minutes=args.stale_minutes)
    atomic(root / 'latest_delivery_health.json', result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    for repo, row in result['repositories'].items():
        if row['status'] in ('STALE', 'ACK_CONFLICT', 'ACK_UNAVAILABLE'):
            print(f'::warning::Beetle receiver {repo}: {row["status"]} ({row["pending"]} queued)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
