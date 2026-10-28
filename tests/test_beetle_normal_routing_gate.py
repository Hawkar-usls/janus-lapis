"""No-provider, no-network adversarial checks for the normal Beetle producer gate."""
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location(
    "beetle_producer_routing_gate", TOOLS / "beetle_producer_routing_gate.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
NOW = dt.datetime(2026, 10, 28, 12, 0, tzinfo=dt.timezone.utc)


def health(*, count=19, pending=0, one=None, state="UP_TO_DATE"):
    repos = {f"receiver-{i}": {"pending": 0, "status": "UP_TO_DATE"}
             for i in range(count)}
    if pending:
        repos["receiver-0"] = {"pending": pending, "status": state}
    if one:
        repos["receiver-1"] = one
    total = sum(row["pending"] for row in repos.values())
    return {"schema": "janus.beetle.delivery_health.v1",
            "at": NOW.isoformat().replace("+00:00", "Z"),
            "repositories": repos,
            "total_pending": total,
            "ack_semantics": "INBOX_DURABLE_ONLY_NOT_RUNTIME_CONSUMPTION"}


class NormalProducerGateTest(unittest.TestCase):
    def test_no_backlog_allows_new_delivery(self):
        self.assertEqual(m.classify(health(), NOW), (True, "ROUTING_ALLOWED"))
        receipt = m.evaluate(health(), now=NOW, run_id="40704229012")
        self.assertTrue(receipt["routing_allowed"])
        self.assertEqual(receipt["new_packet_queue_mutations_performed_by_gate"], 0)
        self.assertEqual(receipt["scientific_authority_delta"], 0)
        self.assertEqual(receipt["rowan_credit_authority_delta"], 0)
        self.assertEqual(receipt["delivery_health_sha256"],
                         hashlib.sha256(m.canonical(health())).hexdigest())

    def test_global_pressure_blocks(self):
        h = health()
        for i in range(14):
            h["repositories"][f"receiver-{i}"]["pending"] = 1
        h["total_pending"] = 14
        self.assertEqual(m.classify(h, NOW),
                         (False, "HOLD_DELIVERY_BACKPRESSURE"))

    def test_single_slow_receiver_blocks_even_below_global_limit(self):
        self.assertEqual(m.classify(health(pending=2), NOW),
                         (False, "HOLD_SINGLE_RECEIVER_BACKLOG"))

    def test_stale_receiver_holds(self):
        self.assertEqual(m.classify(health(pending=1, state="STALE"), NOW),
                         (False, "HOLD_STALE_RECEIVER_ACK"))

    def test_private_unknown_one_packet_preserves_fail_closed_rate_cap(self):
        h = health(pending=1, state="ACK_UNAVAILABLE")
        self.assertEqual(m.classify(h, NOW), (True, "ROUTING_ALLOWED"))
        h["repositories"]["receiver-0"]["pending"] = 2
        h["total_pending"] = 2
        self.assertFalse(m.classify(h, NOW)[0])

    def test_corrupt_ack_halts(self):
        self.assertEqual(m.classify(health(pending=1, state="ACK_CONFLICT"), NOW),
                         (False, "HOLD_ACK_CONFLICT"))

    def test_missing_malformed_or_future_health_never_allows(self):
        for h in (None, {}, {"repositories": {}},
                  {"schema": "janus.beetle.delivery_health.v1",
                   "repositories": {"a": {"pending": 0, "status": "UP_TO_DATE"}},
                   "total_pending": 0, "at": "2099-01-01T00:00:00Z"}):
            r = m.evaluate(h, now=NOW, run_id="1")
            self.assertFalse(r["routing_allowed"])

    def test_no_auth_or_expensive_provider_api(self):
        s = (TOOLS/"beetle_producer_routing_gate.py").read_text()
        for forbidden in ("ROWAN_API_KEY", "submit_protein_cofolding_workflow(",
                          "gh api --method POST", "git push", "delete(", "os.system("):
            self.assertNotIn(forbidden, s)

    def test_workflow_gate_controls_router_not_worker_or_health(self):
        workflow=(TOOLS.parent / ".github/workflows/universal-beetle-hourly.yml").read_text()
        self.assertIn("id: delivery_gate", workflow)
        self.assertIn("python lapis/tools/beetle_producer_routing_gate.py", workflow)
        self.assertIn(
            "steps.delivery_gate.outputs.routing_allowed == 'true'", workflow)
        router=workflow.split("      - name: Route new mirror contexts into provenance-bound repo mirrors\n",1)[1]
        self.assertTrue(router.startswith("        if: "))
        self.assertIn("steps.delivery_gate.outputs.routing_allowed == 'true'",
                      router.split("run:",1)[0])
        observe=workflow.split("      - name: Observe persisted receiver ACKs and delivery lag\n",1)[1]
        self.assertIn("python lapis/tools/beetle_delivery_health.py",
                      observe.split("      - name:",1)[0])
        self.assertIn("beetle-memory/data/beetle-state/latest_routing_gate.json",workflow)
        self.assertIn("test_beetle_normal_routing_gate.py",workflow)

    def test_gate_writes_only_routing_receipt_and_output(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            state=root/"durable"
            state.mkdir()
            with mock.patch.object(m, "inspect", return_value=health()):
                with mock.patch.dict("os.environ", {"GITHUB_OUTPUT": str(root/"out.txt")}):
                    with mock.patch.object(sys, "argv", ["gate",
                        "--state-dir",str(state),"--run-id","40704229012"]):
                        self.assertEqual(m.main(),0)
            self.assertEqual(sorted(p.name for p in state.iterdir()),
                             ["latest_routing_gate.json"])
            self.assertIn("routing_allowed=true",(root/"out.txt").read_text())
            r=json.loads((state/"latest_routing_gate.json").read_text())
            self.assertTrue(r["routing_allowed"])

    def test_source_unavailable_holds_without_queue_changes(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            state=root/"durable"
            state.mkdir()
            marker=state/"do-not-alter.json"
            marker.write_text('{"immutable":true}\n')
            with mock.patch.object(m, "inspect", side_effect=ValueError("untrusted source")):
                with mock.patch.dict("os.environ", {"GITHUB_OUTPUT": str(root/"out.txt")}):
                    with mock.patch.object(sys,"argv",["gate",
                        "--state-dir",str(state),"--run-id","40704229012"]):
                        self.assertEqual(m.main(),0)
            r=json.loads((state/"latest_routing_gate.json").read_text())
            self.assertFalse(r["routing_allowed"])
            self.assertEqual(r["reason"],"HOLD_UNVERIFIED_DELIVERY_HEALTH")
            self.assertEqual(marker.read_text(),'{"immutable":true}\n')
            self.assertIn("routing_allowed=false",(root/"out.txt").read_text())


if __name__ == "__main__":
    unittest.main()
