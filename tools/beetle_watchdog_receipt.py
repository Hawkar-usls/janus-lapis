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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    print(normalize_receipt(args.report))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
