#!/usr/bin/env python3
"""Independent GitHub Issues witness for Genesis Cloud HOME sequence.

This witness lives in janus-lapis Issues, outside Genesis' mutable Git
history. It is not a claim about model consumption or scientific validity.
Only the trusted main-branch watchdog may advance it after receipt checks.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re

from beetle_incident_issues import GitHubIssues, REPOSITORY, parse_report


ISSUE_NUMBER = 21
SCHEMA = 'janus.genesis.home.highwater.v1'
MARKER = '<!-- janus.genesis.home.highwater.v1 -->'
FENCE = '```json\n'
END_FENCE = '\n```'
SOURCE = 'Hawkar-usls/Janus_Genesis'
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
COMMIT = re.compile(r'[0-9a-f]{40}\Z')


def validate_record(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) != {
        'schema', 'sequence', 'receipt_sha256', 'home_commit_sha',
        'source_repository', 'scientific_authority_delta',
    }:
        raise ValueError('malformed high-water record')
    if (value['schema'] != SCHEMA or type(value['sequence']) is not int or
        value['sequence'] < 1 or value['source_repository'] != SOURCE or
        value['scientific_authority_delta'] != 0 or
        not isinstance(value['receipt_sha256'], str) or
        SHA256.fullmatch(value['receipt_sha256']) is None or
        not isinstance(value['home_commit_sha'], str) or
        COMMIT.fullmatch(value['home_commit_sha']) is None):
        raise ValueError('untrusted high-water witness')
    return value


def parse_issue(issue: dict) -> tuple[dict, str, str]:
    if (not isinstance(issue, dict) or issue.get('number') != ISSUE_NUMBER or
        issue.get('state') != 'open'):
        raise ValueError('high-water issue missing or closed')
    body = issue.get('body')
    if not isinstance(body, str) or body.count(MARKER) != 1 or body.count(FENCE) != 1:
        raise ValueError('high-water issue marker missing or ambiguous')
    before, after = body.split(FENCE, 1)
    if after.count(END_FENCE) != 1:
        raise ValueError('ambiguous high-water JSON section')
    raw, suffix = after.split(END_FENCE, 1)
    if len(raw) > 2000:
        raise ValueError('oversized high-water record')
    return validate_record(json.loads(raw)), before + FENCE, END_FENCE + suffix


def check(home: dict, record: dict, commit_sha: str) -> tuple[list[str], dict]:
    """Detect rollback even when the two latest Git commits look consistent."""
    validate_record(record)
    sequence = home.get('sequence')
    receipt_sha = home.get('last_receipt_sha256')
    if (type(sequence) is not int or sequence < 1 or
        not isinstance(receipt_sha, str) or SHA256.fullmatch(receipt_sha) is None or
        not isinstance(commit_sha, str) or COMMIT.fullmatch(commit_sha) is None):
        raise ValueError('untrusted HOME evidence for high-water comparison')
    alerts = []
    if sequence < record['sequence']:
        alerts.append('GENESIS_HOME_INDEPENDENT_HIGHWATER_ROLLBACK')
    if sequence == record['sequence'] and (
        receipt_sha != record['receipt_sha256'] or
        commit_sha != record['home_commit_sha']
    ):
        alerts.append('GENESIS_HOME_INDEPENDENT_HIGHWATER_FORK')
    return alerts, {
        'home_highwater_sequence': record['sequence'],
        'home_highwater_status': ('FAIL' if alerts else
                                  'ADVANCE_PENDING' if sequence > record['sequence'] else 'MATCH'),
        'home_current_commit_sha': commit_sha,
        'home_current_receipt_sha256': receipt_sha,
    }


def ancestry_url(record: dict, commit_sha: str) -> str:
    validate_record(record)
    if not isinstance(commit_sha, str) or COMMIT.fullmatch(commit_sha) is None:
        raise ValueError('malformed Git commit for ancestry check')
    return ('https://api.github.com/repos/Hawkar-usls/Janus_Genesis/compare/' +
            record['home_commit_sha'] + '...' + commit_sha + '?per_page=1')


def verify_ancestry(compare: dict, record: dict, commit_sha: str) -> list[str]:
    """A higher sequence must DESCEND from the previously witnessed commit."""
    if (not isinstance(compare, dict) or
        not isinstance(compare.get('base_commit'), dict) or
        not isinstance(compare.get('merge_base_commit'), dict)):
        raise ValueError('no trustworthy Git comparison data')
    if (compare['base_commit'].get('sha') != record['home_commit_sha'] or
        compare.get('url') != ancestry_url(record, commit_sha).split('?', 1)[0]):
        raise ValueError('Git comparison is not pinned to witnessed commits')
    if (compare.get('status') != 'ahead' or
        type(compare.get('ahead_by')) is not int or compare['ahead_by'] < 1 or
        compare['merge_base_commit'].get('sha') != record['home_commit_sha']):
        return ['GENESIS_HOME_INDEPENDENT_HISTORY_REWRITE']
    return []


def advance(report: dict, api: GitHubIssues) -> dict:
    """Never advance from UNKNOWN or from a failed cryptographic/history check."""
    metrics = report.get('metrics')
    if not isinstance(metrics, dict) or report['status'] == 'UNKNOWN':
        return {'action': 'NO_VERIFIED_EVIDENCE'}
    if (metrics.get('home_receipt_integrity') != 'PASS' or
        metrics.get('home_sequence_integrity') != 'PASS' or
        metrics.get('home_highwater_history') != 'PASS' or
        metrics.get('home_highwater_status') not in ('ADVANCE_PENDING', 'MATCH')):
        return {'action': 'INTEGRITY_GUARD_NO_WRITE'}
    home = {'sequence': metrics.get('home_checkpoint'),
            'last_receipt_sha256': metrics.get('home_current_receipt_sha256')}
    commit_sha = metrics.get('home_current_commit_sha')
    issue = api.request('GET', f'/repos/{REPOSITORY}/issues/{ISSUE_NUMBER}')
    witness, left, right = parse_issue(issue)
    alerts, _ = check(home, witness, commit_sha)
    if alerts:
        raise ValueError('monotonic high-water violation; refusing write')
    if home['sequence'] == witness['sequence']:
        return {'action': 'ALREADY_ANCHORED', 'sequence': witness['sequence']}
    newer = {**witness, 'sequence': home['sequence'],
             'receipt_sha256': home['last_receipt_sha256'],
             'home_commit_sha': commit_sha}
    # Serialized watchdog jobs prevent concurrent machine writers. The Issue
    # API has no compare-and-swap; manual administrator edits remain possible.
    api.request('PATCH', f'/repos/{REPOSITORY}/issues/{ISSUE_NUMBER}',
                {'body': left + json.dumps(newer, sort_keys=True,
                                           separators=(',', ':')) + right})
    persisted = api.request('GET', f'/repos/{REPOSITORY}/issues/{ISSUE_NUMBER}')
    saved, _, _ = parse_issue(persisted)
    if saved != newer:
        raise ValueError('high-water writeback was not durably confirmed')
    return {'action': 'ADVANCED', 'sequence': newer['sequence']}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    if (os.environ.get('GITHUB_EVENT_NAME') == 'pull_request' or
        os.environ.get('GITHUB_REF') != 'refs/heads/main' or
        os.environ.get('GITHUB_REPOSITORY') != REPOSITORY):
        raise SystemExit('high-water updates restricted to trusted main')
    result = advance(parse_report(args.report), GitHubIssues(os.environ.get('GITHUB_TOKEN', '')))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
