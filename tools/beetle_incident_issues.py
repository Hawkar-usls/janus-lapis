#!/usr/bin/env python3
"""Idempotent GitHub Issues incident ledger for the read-only Beetle/HOME watch.

One reusable issue represents the delivery SLO.  A changed alert fingerprint
updates its machine-owned section; ordinary repeats are no-ops.  Recovered
incidents close the issue, and later alerts reopen the same issue.  UNKNOWN
telemetry never masquerades as either a confirmed failure or recovery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request


REPOSITORY = 'Hawkar-usls/janus-lapis'
# Repository owner is a GitHub user (not an organization). Assignment uses
# native GitHub inbox/email settings; no personal address or bot token needed.
INCIDENT_ASSIGNEE = 'Hawkar-usls'
MARKER = '<!-- janus.beetle_home.incident.v1 -->'
AUTO_START = '<!-- JANUS_WATCH_AUTO_START -->'
AUTO_END = '<!-- JANUS_WATCH_AUTO_END -->'
TITLE = '[JANUS/WATCH] Beetle delivery and Genesis HOME incident'
REPORT_SCHEMA = 'janus.beetle_home_watchdog.v1'


def parse_report(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) > 100_000 or not raw:
        raise ValueError('missing or oversized watchdog receipt')
    result = json.loads(raw.splitlines()[0])
    if not isinstance(result, dict) or result.get('schema') != REPORT_SCHEMA:
        raise ValueError('untrusted watchdog receipt schema')
    status = result.get('status')
    if status not in ('PASS', 'WARN', 'ALERT', 'UNKNOWN'):
        raise ValueError('invalid watchdog status')
    alerts = result.get('alerts', [])
    if not isinstance(alerts, list) or len(alerts) > 50:
        raise ValueError('invalid alert list')
    if any(not isinstance(x, str) or
           not re.fullmatch(r'[A-Za-z0-9_.:/ -]{1,160}', x) for x in alerts):
        raise ValueError('unsafe alert text')
    if (status == 'ALERT') != bool(alerts):
        raise ValueError('watchdog status and alerts disagree')
    if result.get('scientific_authority_delta') != 0:
        raise ValueError('unexpected research authority')
    return result


def fingerprint(report: dict) -> str:
    # Fingerprint the *causes*, not volatile ages, counts, timestamps or run IDs.
    unique = sorted(set(report.get('alerts', [])))
    return hashlib.sha256(json.dumps(unique, separators=(',', ':')).encode()).hexdigest()


def machine_block(report: dict, run_url: str) -> str:
    status = report['status']
    lines = [AUTO_START, f'Current state: **{status}**',
             f'Alert fingerprint: `{fingerprint(report)}`',
             f'Observed GitHub run: {run_url}', '']
    if status == 'ALERT':
        lines.append('Detected conditions:')
        lines.extend(f'- `{code}`' for code in sorted(set(report['alerts'])))
    else:
        lines.append('No currently confirmed delivery SLO violations.')
    lines.extend(['',
                  'An ACK means durable discovery inbox, **not** execution or proof.',
                  'Scientific/command/external-effect authority remains unchanged.',
                  AUTO_END])
    return '\n'.join(lines)


def replace_block(old_body: str, block: str) -> str:
    if not isinstance(old_body, str) or MARKER not in old_body:
        raise ValueError('issue body lacks ledger ownership marker')
    if old_body.count(AUTO_START) != 1 or old_body.count(AUTO_END) != 1:
        raise ValueError('issue machine-owned section is ambiguous')
    left, remainder = old_body.split(AUTO_START, 1)
    _, right = remainder.split(AUTO_END, 1)
    return left + block + right


def choose_issue(issues: list) -> dict | None:
    marked = [issue for issue in issues if isinstance(issue, dict) and
              'pull_request' not in issue and MARKER in str(issue.get('body') or '')]
    if len(marked) > 1:
        raise ValueError('multiple incident ledger issues; refusing ambiguous write')
    return marked[0] if marked else None


def assignee_present(issue: dict) -> bool:
    users = issue.get('assignees')
    if not isinstance(users, list):
        raise ValueError('GitHub did not return issue assignees')
    if any(not isinstance(user, dict) or not isinstance(user.get('login'), str)
           for user in users):
        raise ValueError('invalid GitHub issue assignees')
    return any(user['login'].casefold() == INCIDENT_ASSIGNEE.casefold()
               for user in users)


def decide(report: dict, issues: list) -> tuple[str, dict | None]:
    issue = choose_issue(issues)
    status = report['status']
    if status == 'UNKNOWN':
        return 'UNKNOWN_NO_WRITE', issue
    if status == 'ALERT':
        if issue is None:
            return 'CREATE', None
        if issue.get('state') == 'closed':
            return 'REOPEN', issue
        if issue.get('state') != 'open':
            raise ValueError('unknown GitHub issue state')
        body = str(issue.get('body') or '')
        if f'Alert fingerprint: `{fingerprint(report)}`' in body:
            return 'REPEAT_NO_WRITE', issue
        return 'UPDATE_ALERT_SET', issue
    if issue is not None and issue.get('state') == 'open':
        return 'CLOSE_RECOVERED', issue
    return 'HEALTHY_NO_WRITE', issue


class GitHubIssues:
    def __init__(self, token: str):
        if not token:
            raise ValueError('missing scoped GITHUB_TOKEN')
        self.token = token

    def request(self, method: str, path: str, payload: dict | None = None):
        if not path.startswith(f'/repos/{REPOSITORY}/'):
            raise ValueError('GitHub API path outside JANUS incident scope')
        url = 'https://api.github.com' + path
        data = (json.dumps(payload).encode('utf-8') if payload is not None else None)
        req = urllib.request.Request(url, data=data, method=method, headers={
            'Authorization': 'Bearer ' + self.token,
            'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json',
            'User-Agent': 'JANUS-Beetle-Incident-Ledger/1',
            'X-GitHub-Api-Version': '2022-11-28',
        })
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read(500_001)
        if len(raw) > 500_000:
            raise ValueError('GitHub issue API response too large')
        return json.loads(raw)

    def list_all(self) -> list:
        found = []
        for page in range(1, 11):
            batch = self.request('GET',
                                 f'/repos/{REPOSITORY}/issues?state=all&per_page=100&page={page}')
            if not isinstance(batch, list):
                raise ValueError('invalid GitHub issue list')
            found.extend(batch)
            if len(batch) < 100:
                return found
        raise ValueError('too many issues to safely deduplicate')


def synchronize(report: dict, run_url: str, api: GitHubIssues) -> dict:
    action, issue = decide(report, api.list_all())
    if action.endswith('NO_WRITE'):
        return {'action': action, 'issue_number': issue.get('number') if issue else None}
    block = machine_block(report, run_url)
    if action == 'CREATE':
        body = '\n'.join([MARKER, '',
                          'Durable JANUS Beetle → Genesis delivery incident ledger.',
                          'This is a liveness alert, not admission of research evidence.',
                          'Assigned at creation to the repository owner for native GitHub notifications.',
                          'Email delivery depends on the owner\'s GitHub notification preferences.',
                          '', block, ''])
        created = api.request('POST', f'/repos/{REPOSITORY}/issues',
                              {'title': TITLE, 'body': body,
                               'assignees': [INCIDENT_ASSIGNEE]})
        # GitHub can silently ignore invalid issue assignees. Fail visibly
        # instead of claiming a personal notification that was not configured.
        if not assignee_present(created):
            raise ValueError('GitHub did not assign incident to repository owner')
        return {'action': action, 'issue_number': created['number']}
    number = issue.get('number')
    if type(number) is not int or number < 1:
        raise ValueError('invalid existing incident issue number')
    body = replace_block(issue.get('body'), block)
    payload = {'body': body}
    if action == 'REOPEN':
        payload['state'] = 'open'
    elif action == 'CLOSE_RECOVERED':
        payload['state'] = 'closed'
    elif action != 'UPDATE_ALERT_SET':
        raise ValueError('unsupported issue state transition')
    # Deliberately leave assignees unchanged after creation: a maintainer can
    # opt out by unassigning themselves; repeated SLO polls must not override it.
    api.request('PATCH', f'/repos/{REPOSITORY}/issues/{number}', payload)
    return {'action': action, 'issue_number': number}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    # The PR workflow must never gain a path to user-visible mutations.
    if os.environ.get('GITHUB_EVENT_NAME') == 'pull_request':
        raise SystemExit('incident updates are disabled for pull requests')
    if os.environ.get('GITHUB_REPOSITORY') != REPOSITORY:
        raise SystemExit('incident updates are restricted to JANUS Beetle')
    report = parse_report(args.report)
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    if not run_id.isdecimal():
        raise ValueError('missing GitHub workflow run identity')
    run_url = f'https://github.com/{REPOSITORY}/actions/runs/{run_id}'
    api = GitHubIssues(os.environ.get('GITHUB_TOKEN', ''))
    result = synchronize(report, run_url, api)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
