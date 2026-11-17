#!/usr/bin/env python3
"""Read-only, aggregate recovery observation; never a producer routing permit."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from beetle_producer_recovery import delivery_backpressure, timestamp
from beetle_producer_routing_gate import classify as classify_routing

GIT_SHA = re.compile(r"[0-9a-f]{40}")
STATES = frozenset({"UP_TO_DATE", "PENDING", "STALE", "ACK_CONFLICT",
                    "ACK_UNAVAILABLE", "AWAITING_ACK"})
HEALTH_STATES = frozenset({"PASS", "WARN", "ALERT"})
REASONS = frozenset({"ROUTING_ALLOWED", "HOLD_UNVERIFIED_DELIVERY_HEALTH",
                     "HOLD_ACK_CONFLICT", "HOLD_STALE_RECEIVER_ACK",
                     "HOLD_DELIVERY_BACKPRESSURE", "HOLD_SINGLE_RECEIVER_BACKLOG"})


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def build(health_raw: bytes, gate_raw: bytes | None, *,
          source_sha: str, run_id: int, attempt: int, now: datetime) -> dict:
    if (not isinstance(source_sha, str) or not GIT_SHA.fullmatch(source_sha)
            or type(run_id) is not int or run_id < 1
            or type(attempt) is not int or attempt < 1
            or not isinstance(now, datetime) or now.tzinfo is None):
        raise ValueError("UNVERIFIED_OBSERVER_IDENTITY")
    health = json.loads(health_raw)
    delivery_backpressure(health, now)  # verifies schema, timestamps, sums, rows
    observed = timestamp(health["at"])
    age = (now - observed).total_seconds()
    if not -60 <= age <= 120 * 60:
        raise ValueError("OBSERVATION_OUTSIDE_FRESHNESS")
    counts = Counter(row.get("status") for row in health["repositories"].values())
    if set(counts) - STATES or health.get("status") not in HEALTH_STATES:
        raise ValueError("UNVERIFIED_HEALTH_STATES")
    allowed, reason = classify_routing(health, observed)
    if reason not in REASONS:
        raise ValueError("UNVERIFIED_PREFLIGHT_REASON")
    # Separate the prior actual producer decision from the live advisory.
    persisted = {"status": "UNKNOWN"}
    if gate_raw is not None:
        try:
            gate = json.loads(gate_raw)
            gate_at = timestamp(gate["at"])
            if (gate.get("schema") == "janus.beetle.producer_routing_gate.v1"
                    and type(gate.get("action_run_id")) is int
                    and gate["action_run_id"] > 0
                    and type(gate.get("routing_allowed")) is bool
                    and (observed - gate_at).total_seconds() >= -60):
                persisted = {"status": "PRIOR_PRODUCER_SNAPSHOT",
                             "sha256": digest(gate_raw), "at": gate["at"],
                             "action_run_id": gate["action_run_id"],
                             "age_minutes": max(0, int((observed - gate_at).total_seconds() // 60)),
                             "routing_allowed": gate["routing_allowed"]}
        except (ValueError, TypeError, KeyError, AttributeError):
            pass
    return {
        "schema": "janus.beetle.recovery_observation.v1",
        "source_branch": "beetle-state", "source_commit_sha": source_sha,
        "observer_run_id": run_id, "observer_attempt": attempt,
        "observed_at": health["at"], "health_input_sha256": digest(health_raw),
        "health_status": health["status"], "receiver_states": dict(sorted(counts.items())),
        "total_pending": health["total_pending"],
        "preflight_observation": "CLEAR_OBSERVATION_ONLY" if allowed else reason,
        "persisted_routing_gate": persisted,
        "routing_authority": False, "persisted_gate_replaced": False,
        "queue_mutations": 0, "scientific_authority_delta": 0,
        "ack_semantics": "INBOX_DURABLE_ONLY_NOT_RUNTIME_CONSUMPTION",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--health", type=Path, required=True)
    ap.add_argument("--prior-gate", type=Path, required=True)
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--run-id", type=int, required=True)
    ap.add_argument("--attempt", type=int, required=True)
    args = ap.parse_args()
    try:
        try:
            gate_raw = args.prior_gate.read_bytes()
        except OSError:
            gate_raw = None
        receipt = build(args.health.read_bytes(), gate_raw, source_sha=args.source_sha,
                        run_id=args.run_id, attempt=args.attempt,
                        now=datetime.now(timezone.utc))
    except (ValueError, TypeError, OSError, KeyError, AttributeError):
        print("BEETLE_RECOVERY_OBSERVATION=UNKNOWN")
        return 2
    # Only aggregate values, no repo names, ACK identifiers, raw content or tokens.
    print("BEETLE_RECOVERY_OBSERVATION=" + json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
