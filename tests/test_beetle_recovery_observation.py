"""Offline tests: recovery telemetry is observation, never routing authority."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import beetle_recovery_observation as m

NOW = datetime(2026, 11, 17, 20, 0, tzinfo=timezone.utc)
def at(t):
    return t.isoformat().replace("+00:00", "Z")

def fixture(pending=0, status="UP_TO_DATE"):
    health = {"schema": "janus.beetle.delivery_health.v1",
              "at": at(NOW), "status": "PASS" if not pending else "WARN",
              "repositories": {f"not-for-output-{i}": {"pending": pending if i == 1 else 0,
                                 "status": status if i == 1 else "UP_TO_DATE"}
                               for i in range(19)},
              "total_pending": pending}
    gate = {"schema": "janus.beetle.producer_routing_gate.v1", "at": at(NOW - timedelta(hours=3)),
            "action_run_id": 123, "routing_allowed": False}
    return health, gate

def invoke(health, gate):
    return m.build(json.dumps(health).encode(),
                   None if gate is None else json.dumps(gate).encode(),
                   source_sha="a"*40, run_id=456, attempt=1, now=NOW)

class Tests(unittest.TestCase):
    def test_clear_observation_is_not_permission_or_replacement(self):
        h, g = fixture()
        r = invoke(h, g)
        self.assertEqual(r["preflight_observation"], "CLEAR_OBSERVATION_ONLY")
        self.assertFalse(r["routing_authority"])
        self.assertFalse(r["persisted_gate_replaced"])
        self.assertFalse(r["persisted_routing_gate"]["routing_allowed"])
        self.assertEqual(r["persisted_routing_gate"]["age_minutes"], 180)
        self.assertEqual(r["persisted_routing_gate"]["action_run_id"], 123)
        self.assertEqual(r["source_commit_sha"], "a"*40)
        self.assertNotIn("not-for-output", json.dumps(r))
        self.assertEqual(r["queue_mutations"], 0)

    def test_existing_hold_preserved(self):
        h, g = fixture(2, "ACK_UNAVAILABLE")
        r = invoke(h, g)
        self.assertEqual(r["preflight_observation"], "HOLD_SINGLE_RECEIVER_BACKLOG")
        self.assertEqual(r["total_pending"], 2)
        self.assertEqual(r["receiver_states"], {"UP_TO_DATE":18, "ACK_UNAVAILABLE":1})
        self.assertFalse(r["routing_authority"])

    def test_missing_prior_gate_is_unknown_not_fresh(self):
        h, _ = fixture()
        self.assertEqual(invoke(h, None)["persisted_routing_gate"], {"status":"UNKNOWN"})
        self.assertEqual(invoke(h, {"at":"bad"})["persisted_routing_gate"], {"status":"UNKNOWN"})

    def test_invalid_and_old_health_rejected(self):
        h, g = fixture()
        with self.assertRaises(ValueError):
            invoke(dict(h,total_pending=1),g)
        with self.assertRaises(ValueError):
            invoke(dict(h,at=at(NOW-timedelta(minutes=121))),g)

    def test_existing_workflow_emits_only_observation(self):
        w = (Path(__file__).resolve().parents[1] /
             ".github/workflows/beetle-producer-bounded-recovery.yml").read_text()
        self.assertIn("tools/beetle_recovery_observation.py",w)
        self.assertIn("git -C beetle-durable rev-parse HEAD",w)
        self.assertNotIn("contents: write",w)

if __name__ == "__main__":
    unittest.main()
