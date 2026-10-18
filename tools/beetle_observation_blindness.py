#!/usr/bin/env python3
"""Alert separately when JANUS watch telemetry is UNKNOWN for >=3 hours.

The durable streak evidence is GitHub's existing workflow run history and
status-named observer artifacts (not a runner's temporary filesystem).
No UNKNOWN can create or close a Beetle *delivery* incident.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re

from beetle_incident_issues import (GitHubIssues, INCIDENT_ASSIGNEE, REPOSITORY,
                                    assignee_present, parse_report)


BLIND_MARKER = '<!-- janus.beetle_home.observation_blindness.v1 -->'
BLIND_START = '<!-- JANUS_OBSERVATION_AUTO_START -->'
BLIND_END = '<!-- JANUS_OBSERVATION_AUTO_END -->'
BLIND_TITLE = '[JANUS/OBSERVER] Beetle/HOME telemetry unavailable'
WORKFLOW_PATH = '.github/workflows/janus-beetle-home-watchdog.yml'
ARTIFACT_NAME = re.compile(r'janus-watchdog-(PASS|WARN|ALERT|UNKNOWN)-([1-9][0-9]*)\Z')
MIN_UNKNOWN_SAMPLES = 3
MIN_UNKNOWN_MINUTES = 180
MAX_PRIOR_RUNS = 50
RUNS_PER_PAGE = 10  # GitHub embeds bulky repo metadata; stay within API size cap.


def parse_utc(value: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ValueError('GitHub run timestamp missing')
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('GitHub run timestamp is timezone naive')
    return parsed.astimezone(dt.timezone.utc)


def relevant_run(run: dict) -> bool:
    return (isinstance(run, dict) and run.get('head_branch') == 'main' and
            run.get('event') in ('schedule', 'push', 'workflow_dispatch') and
            str(run.get('path', '')).split('@')[0] == WORKFLOW_PATH and
            type(run.get('id')) is int and run['id'] > 0)


def recent_runs(api: GitHubIssues, current_run_id: int) -> list[dict]:
    found = []
    for page in range(1, 21):
        payload = api.request('GET', f'/repos/{REPOSITORY}/actions/runs'
                              f'?branch=main&per_page={RUNS_PER_PAGE}&page={page}')
        batch = payload.get('workflow_runs') if isinstance(payload, dict) else None
        if not isinstance(batch, list):
            raise ValueError('untrusted workflow run history')
        found.extend(run for run in batch if relevant_run(run))
        if len(found) >= MAX_PRIOR_RUNS + 1 or len(batch) < RUNS_PER_PAGE:
            break
    found.sort(key=lambda run: (parse_utc(run.get('created_at')), run['id']),
               reverse=True)
    ids = [run['id'] for run in found]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate workflow run identity')
    if current_run_id not in ids:
        raise ValueError('current trusted main run missing from GitHub history')
    index = ids.index(current_run_id)
    return found[index:index + MAX_PRIOR_RUNS + 1]


def prior_status(api: GitHubIssues, run_id: int) -> str | None:
    payload = api.request('GET', f'/repos/{REPOSITORY}/actions/runs/{run_id}/artifacts'
                          '?per_page=100')
    artifacts = payload.get('artifacts') if isinstance(payload, dict) else None
    if not isinstance(artifacts, list):
        raise ValueError('untrusted GitHub artifact list')
    matches = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ValueError('invalid GitHub artifact')
        name = artifact.get('name')
        match = ARTIFACT_NAME.fullmatch(name) if isinstance(name, str) else None
        if match is None:
            continue
        if int(match.group(2)) != run_id:
            raise ValueError('mismatched observer artifact identity')
        if artifact.get('expired') is True:
            return None  # Expired evidence is a gap, not proof of UNKNOWN.
        if artifact.get('expired') is not False:
            raise ValueError('observer artifact expiry is unknown')
        owner = artifact.get('workflow_run')
        if not isinstance(owner, dict) or owner.get('id') != run_id or \
                owner.get('head_branch') != 'main':
            raise ValueError('observer artifact provenance mismatch')
        matches.append(match.group(1))
    if len(matches) > 1:
        raise ValueError('ambiguous status-named observer artifacts')
    # A legacy/no-artifact run is a gap in evidence, not presumed UNKNOWN.
    return matches[0] if matches else None


def unknown_streak(api: GitHubIssues, current_run_id: int) -> dict:
    history = recent_runs(api, current_run_id)
    current = history[0]
    first_id = current_run_id
    oldest = newest = parse_utc(current.get('created_at'))
    count = 1
    for prior in history[1:]:
        if prior.get('status') != 'completed':
            break
        status = prior_status(api, prior['id'])
        if status != 'UNKNOWN':
            break
        at = parse_utc(prior.get('created_at'))
        if at > oldest:
            raise ValueError('workflow history is non-monotonic')
        first_id, oldest = prior['id'], at
        count += 1
        if count >= MIN_UNKNOWN_SAMPLES and \
                (newest - oldest).total_seconds() >= MIN_UNKNOWN_MINUTES * 60:
            break
    elapsed_seconds = (newest - oldest).total_seconds()
    minutes = round(elapsed_seconds / 60, 1)
    return {'count': count, 'minutes': minutes, 'first_run_id': first_id,
            'last_run_id': current_run_id,
            'escalate': count >= MIN_UNKNOWN_SAMPLES and
            elapsed_seconds >= MIN_UNKNOWN_MINUTES * 60}


def choose_blind_issue(issues: list) -> dict | None:
    matches = [issue for issue in issues if isinstance(issue, dict) and
               'pull_request' not in issue and
               BLIND_MARKER in str(issue.get('body') or '')]
    if len(matches) > 1:
        raise ValueError('multiple observation blindness issues; refusing write')
    return matches[0] if matches else None


def machine_block(status: str, run_id: int, streak: dict | None = None) -> str:
    run_url = f'https://github.com/{REPOSITORY}/actions/runs/{run_id}'
    lines = [BLIND_START, f'Current state: **{status}**',
             f'Latest verified workflow run: {run_url}', '']
    if status == 'OBSERVABILITY_LOST':
        lines.extend([
            f'Consecutive UNKNOWN samples: **{streak["count"]}**',
            f'Observed duration: **{streak["minutes"]} minutes**',
            f'First UNKNOWN run: https://github.com/{REPOSITORY}/actions/runs/'
            f'{streak["first_run_id"]}', '',
            'No conclusion about Beetle delivery, Genesis HOME, or recipient ACKs'
            ' is possible while observation is UNKNOWN.',
        ])
    else:
        lines.append('Observer telemetry has returned; this is not proof of delivery.')
    lines.extend(['', 'Discovery is not execution or scientific evidence.',
                  'Scientific/command/external-effect authority remains unchanged.',
                  BLIND_END])
    return '\n'.join(lines)


def replace_block(body: str, replacement: str) -> str:
    if not isinstance(body, str) or body.count(BLIND_MARKER) != 1 or \
            body.count(BLIND_START) != 1 or body.count(BLIND_END) != 1:
        raise ValueError('blindness issue has ambiguous ownership boundaries')
    before, rest = body.split(BLIND_START, 1)
    _, after = rest.split(BLIND_END, 1)
    return before + replacement + after


def synchronize(report: dict, current_run_id: int, api: GitHubIssues) -> dict:
    issue = choose_blind_issue(api.list_all())
    if report['status'] != 'UNKNOWN':
        if issue is None or issue.get('state') == 'closed':
            return {'action': 'OBSERVABLE_NO_WRITE', 'issue_number':
                    issue.get('number') if issue else None}
        if issue.get('state') != 'open':
            raise ValueError('invalid observation issue state')
        number = issue.get('number')
        if type(number) is not int or number <= 0:
            raise ValueError('invalid observation issue number')
        block = machine_block('OBSERVATION_RESTORED', current_run_id)
        api.request('PATCH', f'/repos/{REPOSITORY}/issues/{number}',
                    {'state': 'closed', 'body': replace_block(issue.get('body'), block)})
        return {'action': 'CLOSE_OBSERVABILITY_RESTORED', 'issue_number': number}

    streak = unknown_streak(api, current_run_id)
    if not streak['escalate']:
        return {'action': 'UNKNOWN_GRACE_NO_WRITE', 'streak': streak['count'],
                'issue_number': issue.get('number') if issue else None}
    if issue is not None and issue.get('state') == 'open':
        return {'action': 'REPEAT_BLINDNESS_NO_WRITE', 'issue_number': issue['number']}
    if issue is not None and issue.get('state') != 'closed':
        raise ValueError('invalid observation issue state')
    block = machine_block('OBSERVABILITY_LOST', current_run_id, streak)
    if issue is None:
        body = '\n'.join([BLIND_MARKER, '',
                          'Durable *observation-loss* journal, separate from delivery incidents.',
                          'Opening this issue does not mean any delivery SLO failed.',
                          '', block, ''])
        created = api.request('POST', f'/repos/{REPOSITORY}/issues',
                              {'title': BLIND_TITLE, 'body': body,
                               'assignees': [INCIDENT_ASSIGNEE]})
        if not assignee_present(created):
            raise ValueError('GitHub did not assign observation incident')
        return {'action': 'CREATE_OBSERVABILITY_LOSS', 'issue_number': created['number']}
    number = issue.get('number')
    if type(number) is not int or number <= 0:
        raise ValueError('invalid observation issue number')
    api.request('PATCH', f'/repos/{REPOSITORY}/issues/{number}',
                {'state': 'open', 'body': replace_block(issue.get('body'), block)})
    return {'action': 'REOPEN_OBSERVABILITY_LOSS', 'issue_number': number}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('GITHUB_EVENT_NAME') == 'pull_request':
        raise SystemExit('observation incident updates disabled for pull requests')
    if os.environ.get('GITHUB_REPOSITORY') != REPOSITORY:
        raise SystemExit('observation incident updates restricted to Beetle')
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    if not run_id.isdecimal() or int(run_id) < 1:
        raise ValueError('missing trusted workflow run identity')
    report = parse_report(args.report)
    result = synchronize(report, int(run_id), GitHubIssues(os.environ.get('GITHUB_TOKEN', '')))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
