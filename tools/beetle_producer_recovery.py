#!/usr/bin/env python3
"""Bounded wake-up of the existing Universal Beetle; no external provider spend.

This only classifies the latest *GitHub-attested* producer runs. It cannot
change queues, read secrets, or authorize Rowan computations.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

WORKFLOW = ".github/workflows/universal-beetle-hourly.yml"
MIN_SUCCESS_AGE_SECONDS = 90 * 60
MIN_LAST_ATTEMPT_AGE_SECONDS = 75 * 60
ALLOW_EVENTS = frozenset({"schedule", "workflow_dispatch", "push"})
ALLOWED_STATUSES = frozenset({"queued", "in_progress", "waiting", "completed"})


class RecoveryHold(ValueError):
    pass


def timestamp(raw):
    if not isinstance(raw, str) or not raw.endswith("Z"):
        raise RecoveryHold("INVALID_RUN_TIMESTAMP")
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RecoveryHold("INVALID_RUN_TIMESTAMP") from exc
    if value.tzinfo is None:
        raise RecoveryHold("INVALID_RUN_TIMESTAMP")
    return value


def decide(data, now):
    if not isinstance(data, dict) or not isinstance(data.get("workflow_runs"), list):
        raise RecoveryHold("RUN_COLLECTION_UNVERIFIED")
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise RecoveryHold("CLOCK_UNVERIFIED")
    candidates = []
    for r in data["workflow_runs"]:
        if not isinstance(r, dict):
            raise RecoveryHold("INVALID_RUN_ENTRY")
        if (r.get("path") != WORKFLOW or r.get("head_branch") != "main"
                or r.get("event") not in ALLOW_EVENTS):
            continue
        if type(r.get("id")) is not int or r["id"] <= 0:
            raise RecoveryHold("INVALID_RUN_ID")
        if r.get("status") not in ALLOWED_STATUSES:
            raise RecoveryHold("INVALID_RUN_STATUS")
        age = (now - timestamp(r.get("created_at"))).total_seconds()
        if age < -60:
            raise RecoveryHold("RUN_CLOCK_IN_FUTURE")
        candidates.append((age, r))
    if not candidates:
        raise RecoveryHold("NO_VERIFIABLE_PRODUCER_HISTORY")
    if any(r["status"] in {"queued", "waiting", "in_progress"} for _, r in candidates):
        return {"action": "HOLD_ACTIVE_RUN", "dispatch": False}
    age_latest = min(age for age, _ in candidates)
    if age_latest < MIN_LAST_ATTEMPT_AGE_SECONDS:
        return {"action": "HOLD_RECENT_ATTEMPT", "dispatch": False}
    completed = [age for age, r in candidates
                 if r["status"] == "completed" and r.get("conclusion") == "success"]
    if completed and min(completed) < MIN_SUCCESS_AGE_SECONDS:
        return {"action": "HOLD_RECENT_SUCCESS", "dispatch": False}
    return {"action": "RECOVER_MISSED_PRODUCER", "dispatch": True}


def delivery_backpressure(health, now):
    """Never wake a producer into a verified backlog or stale ACK state."""
    if (not isinstance(health, dict) or
        health.get("schema") != "janus.beetle.delivery_health.v1" or
        not isinstance(health.get("repositories"), dict) or
        not health["repositories"] or
        type(health.get("total_pending")) is not int or
        health["total_pending"] < 0):
        raise RecoveryHold("DELIVERY_HEALTH_UNVERIFIED")
    age = (now - timestamp(health.get("at"))).total_seconds()
    if age < -60 or age > 6*60*60:
        raise RecoveryHold("DELIVERY_HEALTH_OUTSIDE_FRESHNESS")
    receivers = health["repositories"]
    if any(not isinstance(v, dict) or
           type(v.get("pending")) is not int or v["pending"] < 0
           for v in receivers.values()):
        raise RecoveryHold("DELIVERY_RECIPIENTS_INVALID")
    if any(v.get("status") == "STALE" for v in receivers.values()):
        return "HOLD_STALE_RECEIVER_ACK"
    if health["total_pending"] >= max(2, len(receivers) // 2):
        return "HOLD_DELIVERY_BACKPRESSURE"
    if sum(v["pending"] for v in receivers.values()) != health["total_pending"]:
        raise RecoveryHold("DELIVERY_PENDING_CONTRADICTION")
    return "CLEAR"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--delivery-health", required=True)
    args = parser.parse_args()
    try:
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)
        with open(args.delivery_health, encoding="utf-8") as f:
            health = json.load(f)
        now = datetime.now(timezone.utc)
        pressure = delivery_backpressure(health, now)
        result = ({"action": pressure, "dispatch": False}
                  if pressure != "CLEAR" else decide(data, now))
    except (RecoveryHold, OSError, ValueError, json.JSONDecodeError) as exc:
        reason = str(exc)
        if reason not in {
            "RUN_COLLECTION_UNVERIFIED", "CLOCK_UNVERIFIED", "INVALID_RUN_ENTRY",
            "INVALID_RUN_ID", "INVALID_RUN_STATUS", "INVALID_RUN_TIMESTAMP",
            "RUN_CLOCK_IN_FUTURE", "NO_VERIFIABLE_PRODUCER_HISTORY",
            "DELIVERY_HEALTH_UNVERIFIED", "DELIVERY_HEALTH_OUTSIDE_FRESHNESS",
            "DELIVERY_RECIPIENTS_INVALID", "DELIVERY_PENDING_CONTRADICTION",
        }:
            reason = "SOURCE_UNAVAILABLE"
        print("BEETLE_PRODUCER_RECOVERY=HOLD_" + reason)
        return 2
    print("BEETLE_PRODUCER_RECOVERY=" + result["action"])
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write("dispatch=" + ("true" if result["dispatch"] else "false") + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
