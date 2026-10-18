#!/usr/bin/env python3
"""Read-only SLO watch over Beetle delivery and Genesis durable HOME.

Unlike the producer's informational health report, this process exits nonzero
when an independently observed GitHub checkpoint has stopped progressing.  It
never changes a repository, authorizes research claims, or advances an ACK.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import urllib.request


HEALTH_URL = ('https://raw.githubusercontent.com/Hawkar-usls/janus-lapis/'
              'beetle-state/data/beetle-state/latest_delivery_health.json')
HOME_BASE = ('https://raw.githubusercontent.com/Hawkar-usls/Janus_Genesis/'
             'janus/habitat-cloud-state/state/habitat_cloud_home')
STATE_URL = HOME_BASE + '/STATE.json'
CURSOR_URL = HOME_BASE + '/memory/beetle/CURSOR.json'
ACK_URL = ('https://raw.githubusercontent.com/Hawkar-usls/Janus_Genesis/'
           'beetle-memory/data/beetle-inbox/ACK.json')
HOME_COMMIT_URL = ('https://api.github.com/repos/Hawkar-usls/Janus_Genesis/commits'
                   '?sha=janus%2Fhabitat-cloud-state&'
                   'path=state%2Fhabitat_cloud_home%2FSTATE.json&per_page=1')


def fetch_json(url: str, max_bytes: int = 500_000):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'JANUS-Beetle-HOME-SLO/1',
        'Accept': 'application/vnd.github+json',
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError('telemetry payload exceeds limit')
    return json.loads(raw)


def elapsed_minutes(value: str, now: dt.datetime) -> float:
    if not isinstance(value, str):
        raise ValueError('missing timestamp')
    timestamp = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if timestamp.utcoffset() is None or now.utcoffset() is None:
        raise ValueError('timezone missing from timestamp')
    minutes = (now - timestamp).total_seconds() / 60
    if minutes < -10:
        raise ValueError('telemetry timestamp unexpectedly in future')
    return max(0.0, minutes)


def evaluate(health: dict, home: dict, cursor: dict, ack: dict,
             commits: list, now: dt.datetime, *,
             max_heartbeat_minutes: int = 240,
             max_genesis_lag_minutes: int = 180) -> dict:
    """Return a bounded report; time gaps are observations, not proof claims."""
    alerts: list[str] = []
    warnings: list[str] = []
    metrics: dict = {}

    def require(condition: bool, message: str):
        if not condition:
            raise ValueError(message)

    require(health.get('schema') == 'janus.beetle.delivery_health.v1',
            'unexpected Beetle health schema')
    require(health.get('scientific_authority_delta') == 0,
            'Beetle health claims scientific authority')
    rows = health.get('repositories')
    require(isinstance(rows, dict) and rows, 'missing routed repositories')
    metrics['recipient_count'] = len(rows)
    metrics['beetle_health_age_minutes'] = round(elapsed_minutes(health.get('at'), now), 1)
    if metrics['beetle_health_age_minutes'] >= max_heartbeat_minutes:
        alerts.append('BEETLE_HEARTBEAT_STALE')

    total_pending = 0
    for repo, row in sorted(rows.items()):
        require(bool(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo)),
                'invalid recipient identity')
        require(isinstance(row, dict), f'{repo}: malformed delivery row')
        produced, confirmed, pending = (row.get(k) for k in ('produced', 'confirmed', 'pending'))
        require(all(type(v) is int for v in (produced, confirmed, pending)) and
                0 <= confirmed <= produced and pending == produced - confirmed,
                f'{repo}: inconsistent counts')
        total_pending += pending
        status = row.get('status')
        if status in ('STALE', 'ACK_CONFLICT'):
            alerts.append(f'{repo}: {status}')
        elif status in ('PENDING', 'UP_TO_DATE', 'AWAITING_ACK', 'ACK_UNAVAILABLE'):
            if status in ('AWAITING_ACK', 'ACK_UNAVAILABLE'):
                warnings.append(f'{repo}: {status}')
        else:
            raise ValueError(f'{repo}: unknown delivery state')
    require(health.get('total_pending') == total_pending,
            'Beetle health pending count mismatch')
    metrics['pending_batches'] = total_pending

    require(home.get('schema') == 'JANUS_HABITAT_CLOUD_HOME_STATE_V1' and
            home.get('status') == 'CLOUD_HOME_ACTIVE', 'HOME state not active')
    require(type(home.get('sequence')) is int and home['sequence'] >= 1,
            'HOME checkpoint sequence invalid')
    require(home.get('authority_delta') == 0, 'HOME authority escalation')
    memory = home.get('beetle_memory')
    require(isinstance(memory, dict) and
            memory.get('scientific_authority_delta') == 0 and
            memory.get('command_authority') is False and
            memory.get('external_effect_authority') is False,
            'HOME memory authority guard invalid')
    require(cursor.get('schema') == 'janus.genesis.beetle_context_cursor.v1' and
            cursor.get('unverified_research_only') is True and
            cursor.get('scientific_authority_delta') == 0,
            'HOME cursor is not discovery-only')
    require(type(cursor.get('last_sequence')) is int and cursor['last_sequence'] >= 1,
            'HOME cursor sequence invalid')
    require(memory.get('cursor_sequence') == cursor['last_sequence'] and
            memory.get('context_sha256') == cursor.get('context_sha256'),
            'HOME state and durable cursor disagree')
    require(ack.get('schema') == 'janus.beetle.inbox_ack.v1' and
            ack.get('target_repository') == 'Hawkar-usls/Janus_Genesis' and
            ack.get('status') == 'INBOX_DURABLE_UNVERIFIED__NOT_RUNTIME_CONSUMPTION' and
            ack.get('scientific_authority_delta') == 0 and
            type(ack.get('last_sequence')) is int and ack['last_sequence'] >= 1,
            'Genesis durable ACK is invalid')
    require(isinstance(commits, list) and len(commits) >= 1 and
            isinstance(commits[0], dict) and isinstance(commits[0].get('commit'), dict),
            'missing HOME GitHub commit evidence')
    committed = commits[0]['commit'].get('committer')
    require(isinstance(committed, dict), 'missing HOME commit metadata')
    metrics['home_commit_age_minutes'] = round(elapsed_minutes(committed.get('date'), now), 1)
    metrics['home_checkpoint'] = home['sequence']
    metrics['genesis_ack_sequence'] = ack['last_sequence']
    metrics['home_cursor_sequence'] = cursor['last_sequence']
    if metrics['home_commit_age_minutes'] >= max_heartbeat_minutes:
        alerts.append('GENESIS_HOME_CHECKPOINT_STALE')
    if cursor['last_sequence'] > ack['last_sequence']:
        alerts.append('GENESIS_CURSOR_AHEAD_OF_RECEIVER_ACK')
    elif cursor['last_sequence'] < ack['last_sequence']:
        lag = round(elapsed_minutes(ack.get('acknowledged_at'), now), 1)
        metrics['genesis_unconsumed_ack_age_minutes'] = lag
        if lag >= max_genesis_lag_minutes:
            alerts.append('GENESIS_HOME_ACK_LAG_STALE')
        else:
            warnings.append('GENESIS_ACK_AHEAD_OF_HOME_WITHIN_GRACE')
    require(home.get('checkpoint_head') == home.get('handoff_head') and
            isinstance(home.get('checkpoint_head'), str) and
            home['checkpoint_head'].startswith('state/habitat_cloud_home/receipts/'),
            'HOME checkpoint head is not durable receipt')
    return {'schema': 'janus.beetle_home_watchdog.v1',
            'status': 'ALERT' if alerts else 'WARN' if warnings else 'PASS',
            'alerts': alerts, 'warnings': warnings, 'metrics': metrics,
            'scientific_authority_delta': 0}


def main(now: dt.datetime | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--max-heartbeat-minutes', type=int, default=240)
    p.add_argument('--max-genesis-lag-minutes', type=int, default=180)
    args = p.parse_args()
    if min(args.max_heartbeat_minutes, args.max_genesis_lag_minutes) < 1:
        p.error('SLO thresholds must be positive')
    sources = [HEALTH_URL, STATE_URL, CURSOR_URL, ACK_URL, HOME_COMMIT_URL]
    try:
        values = [fetch_json(url) for url in sources]
        result = evaluate(*values, now or dt.datetime.now(dt.timezone.utc),
                          max_heartbeat_minutes=args.max_heartbeat_minutes,
                          max_genesis_lag_minutes=args.max_genesis_lag_minutes)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        # A transport error cannot establish a delivery failure; flag separately.
        print(json.dumps({'schema': 'janus.beetle_home_watchdog.v1', 'status': 'UNKNOWN',
                          'reason': type(exc).__name__, 'scientific_authority_delta': 0}))
        print(f'::error::JANUS Beetle/HOME telemetry UNKNOWN: {type(exc).__name__}')
        return 2
    print(json.dumps(result, sort_keys=True))
    metrics = result['metrics']
    print('### JANUS Beetle → Genesis durable HOME watch')
    print(f"- Status: **{result['status']}**")
    print(f"- Routes: {metrics['recipient_count']}; pending packets: {metrics['pending_batches']}")
    print(f"- Beetle heartbeat: {metrics['beetle_health_age_minutes']} min ago")
    print(f"- HOME checkpoint #{metrics['home_checkpoint']} / Beetle cursor "
          f"{metrics['home_cursor_sequence']} / receiver ACK {metrics['genesis_ack_sequence']}")
    print(f"- HOME Git commit: {metrics['home_commit_age_minutes']} min ago")
    for warning in result['warnings']:
        print(f'::warning::{warning}')
    for alert in result['alerts']:
        print(f'::error::{alert}')
    return 1 if result['alerts'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
