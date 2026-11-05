"""Fail-closed tests for independent, bounded local Beetle receiver recovery."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import beetle_local_receiver_recovery as m

NOW = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)
SHA1 = "a" * 64
SHA2 = "b" * 64


def fixture(count=2, seq=1):
    entries = [{"batch_id": f"batch-{i}", "sequence": i,
                "sha256": SHA1 if i == 1 else SHA2}
               for i in range(1, count + 1)]
    queue = {"schema": "janus.beetle.delivery_queue.v1",
             "target_repository": m.REPOSITORY,
             "entries": entries, "next_sequence": count + 1}
    ack = {"schema": "janus.beetle.inbox_ack.v1",
           "target_repository": m.REPOSITORY,
           "status": m.ACK_STATUS,
           "scientific_authority_delta": 0,
           "last_sequence": seq,
           "sha256": entries[seq - 1]["sha256"],
           "batch_id": entries[seq - 1]["batch_id"]}
    return queue, ack


def run(age=240, *, status="completed", conclusion="success",
        event="schedule", branch="main"):
    return {"id": 12345, "path": m.WORKFLOW,
            "head_branch": branch,
            "head_repository": {"full_name": m.REPOSITORY},
            "event": event, "status": status, "conclusion": conclusion,
            "created_at": (NOW - timedelta(minutes=age)).strftime("%Y-%m-%dT%H:%M:%SZ")}


class LocalReceiverWakeTests(unittest.TestCase):
    def test_valid_pending_and_old_success_issues_one_wake(self):
        q, a = fixture()
        d = m.decide(q, a, {"workflow_runs": [run()]}, NOW)
        self.assertEqual(d["action"], "RECOVER_MISSED_RECEIVER")
        self.assertTrue(d["dispatch"])
        self.assertEqual(d["pending"], 1)

    def test_current_ack_never_dispatches(self):
        q, a = fixture(seq=2)
        self.assertEqual(m.decide(q, a, {"workflow_runs": []}, NOW)["action"], "CURRENT_ACK")

    def test_active_recent_attempt_and_recent_success_block_duplicates(self):
        q, a = fixture()
        for row, decision in [(run(status="in_progress"), "HOLD_ACTIVE_RECEIVER"),
                              (run(age=10), "HOLD_RECENT_RECEIVER_ATTEMPT"),
                              (run(age=85), "HOLD_RECENT_RECEIVER_SUCCESS")]:
            with self.subTest(decision=decision):
                self.assertEqual(m.decide(q, a, {"workflow_runs": [row]}, NOW)["action"], decision)

    def test_broken_ack_fork_or_queue_holds(self):
        q, a = fixture()
        variants = [({**q, "next_sequence": 11}, a),
                    (q, {**a, "sha256": SHA2}),
                    (q, {**a, "last_sequence": 5}),
                    (q, {**a, "scientific_authority_delta": 1}),
                    ({**q, "target_repository": "untrusted/repo"}, a)]
        for qq, aa in variants:
            with self.subTest(variant=str(qq.get("next_sequence"))):
                with self.assertRaises(m.Hold):
                    m.decide(qq, aa, {"workflow_runs": [run()]}, NOW)

    def test_unverified_runs_do_not_dispatch(self):
        q, a = fixture()
        for rows in [{"workflow_runs": []},
                     {"workflow_runs": [run(event="pull_request")]},
                     {"workflow_runs": [run(branch="untrusted")]},
                     {"workflow_runs": [run(status="unexpected")]},
                     {"workflow_runs": [run(age=-100)]}]:
            with self.assertRaises(m.Hold):
                m.decide(q, a, rows, NOW)

    def test_contract_wakes_existing_receiver_not_sender_while_hold(self):
        root = Path(__file__).resolve().parents[1]
        w = (root / ".github/workflows/beetle-producer-bounded-recovery.yml").read_text()
        watchdog = (root / ".github/workflows/janus-beetle-home-watchdog.yml").read_text()
        self.assertIn("tools/beetle_local_receiver_recovery.py", w)
        self.assertIn("ref: beetle-memory", w)
        self.assertIn("steps.local_receiver_gate.outputs.dispatch == 'true'", w)
        self.assertIn("janus-beetle-memory-receiver.yml/dispatches", w)
        self.assertIn("steps.gate.outputs.dispatch == 'true' && steps.local_receiver_gate.outputs.dispatch != 'true'", w)
        self.assertIn("github.event_name != 'pull_request'", w)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", watchdog)
        self.assertIn("JANUS Beetle producer bounded recovery", watchdog)
        self.assertNotIn("ROWAN_API_KEY", w)


if __name__ == "__main__":
    unittest.main()
