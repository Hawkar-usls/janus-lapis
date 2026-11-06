#!/usr/bin/env python3
"""Emit an honest UNKNOWN receipt if the read-only watchdog produced none.

Used by an always() step after the observer, before uploading a status-named
artifact.  A malformed or absent receipt must never be labeled PASS/ALERT.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from beetle_incident_issues import REPORT_SCHEMA, parse_report


def normalize_receipt(path: Path) -> str:
    try:
        return parse_report(path)['status']
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        # The observer did not provide trustworthy telemetry. A synthesized
        # receipt reports only that fact, not any delivery or HOME failure.
        path.write_text(json.dumps({
            'schema': REPORT_SCHEMA,
            'status': 'UNKNOWN',
            'reason': 'MISSING_OR_INVALID_WATCHDOG_RECEIPT',
            'scientific_authority_delta': 0,
        }, sort_keys=True) + '\n', encoding='utf-8')
        return 'UNKNOWN'


def verify_observer_exit(report_path: Path, exit_code_path: Path) -> str:
    """Verify a complete observation without confusing ALERT with runner failure.

    The watchdog exits 0 for PASS/WARN, 1 for an observed SLO ALERT, and
    2 for source/transport UNKNOWN. All three are legitimate completed
    observations, but only when a trustworthy JSON receipt matches the
    captured exit code. A synthetic UNKNOWN from a missing/corrupt receipt
    must fail closed rather than falsely prove schedule liveness.
    """
    report = parse_report(report_path)
    if report.get('reason') == 'MISSING_OR_INVALID_WATCHDOG_RECEIPT':
        raise ValueError('missing or corrupt watchdog receipt cannot prove liveness')
    raw_code = exit_code_path.read_text(encoding='utf-8').strip()
    expected = {
        '0': {'PASS', 'WARN'},
        '1': {'ALERT'},
        '2': {'UNKNOWN'},
    }
    if raw_code not in expected or report['status'] not in expected[raw_code]:
        raise ValueError('observer exit code and trusted receipt status disagree')
    return report['status']


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--exit-code-file', type=Path)
    args = parser.parse_args()
    if args.exit_code_file is not None:
        print(verify_observer_exit(args.report, args.exit_code_file))
    else:
        print(normalize_receipt(args.report))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
