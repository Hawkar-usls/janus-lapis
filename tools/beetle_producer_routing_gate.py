#!/usr/bin/env python3
"""Zero-spend, fail-closed preflight for the normal Universal Beetle router.

Worker and source-context projection may proceed. Only creation of NEW mirror
outbox packets is held when independent receiver ACKs are behind.
Never reads Rowan secrets, submits compute, edits ACKs, or deletes queues.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from beetle_delivery_health import inspect
from beetle_producer_recovery import RecoveryHold, delivery_backpressure

SCHEMA = "janus.beetle.producer_routing_gate.v1"
MAX_PER_REPO_PENDING = 2


def canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def classify(health: dict, now: datetime) -> tuple[bool, str]:
    """Share the recovery gate and additionally protect a single slow consumer."""
    try:
        pressure = delivery_backpressure(health, now)
    except (RecoveryHold, ValueError, TypeError):
        return False, "HOLD_UNVERIFIED_DELIVERY_HEALTH"
    if pressure != "CLEAR":
        return False, pressure
    if any(row.get("status") == "ACK_CONFLICT"
           for row in health["repositories"].values()):
        return False, "HOLD_ACK_CONFLICT"
    if any(row["pending"] >= MAX_PER_REPO_PENDING
           for row in health["repositories"].values()):
        return False, "HOLD_SINGLE_RECEIVER_BACKLOG"
    # Backpressure is an operational ACK gate only, never scientific approval.
    return True, "ROUTING_ALLOWED"


def evaluate(health: dict | None, *, now: datetime, run_id: str) -> dict:
    if not isinstance(run_id, str) or not run_id.isdecimal() or int(run_id) <= 0:
        raise ValueError("INVALID_ACTION_RUN")
    allowed, reason = classify(health, now) if health is not None else (
        False, "HOLD_UNVERIFIED_DELIVERY_HEALTH")
    safe_health = health if isinstance(health, dict) else None
    return {
        "schema": SCHEMA,
        "at": now.isoformat().replace("+00:00", "Z"),
        "action_run_id": int(run_id),
        "routing_allowed": allowed,
        "reason": reason,
        "total_pending_before_route": (
            safe_health["total_pending"] if safe_health and
            type(safe_health.get("total_pending")) is int else None),
        "receiver_count": (
            len(safe_health["repositories"]) if safe_health and
            isinstance(safe_health.get("repositories"), dict) else None),
        "delivery_health_sha256": (
            hashlib.sha256(canonical(safe_health)).hexdigest()
            if safe_health else None),
        "source": "DURABLE_BEETLE_STATE_QUEUES_AND_LIVE_RECEIVER_ACKS",
        "ack_semantics": "INBOX_DURABLE_ONLY_NOT_RUNTIME_CONSUMPTION",
        "rowan_credit_authority_delta": 0,
        "scientific_authority_delta": 0,
        "new_packet_queue_mutations_performed_by_gate": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    root = Path(args.state_dir)
    now = datetime.now(timezone.utc)
    try:
        current = inspect(root, stale_minutes=180, observed_at=now)
    except (OSError, ValueError, RuntimeError, TypeError):
        current = None
    receipt = evaluate(current, now=now, run_id=args.run_id)
    # Write only a summary. Existing candidate state, queues, and receiver ACKs
    # remain unchanged; the normal producer will persist this receipt.
    path = root / "latest_routing_gate.json"
    path.write_bytes(json.dumps(receipt, indent=2, sort_keys=True,
                                ensure_ascii=False, allow_nan=False).encode() + b"\n")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as f:
            f.write("routing_allowed=" + ("true" if receipt["routing_allowed"] else "false") + "\n")
    print("BEETLE_NORMAL_ROUTING=" + receipt["reason"])
    print("BEETLE_NORMAL_ROUTING_PENDING=" +
          str(receipt["total_pending_before_route"]))
    if not receipt["routing_allowed"]:
        print("::warning::Beetle new-packet routing held; worker discoveries remain durable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
