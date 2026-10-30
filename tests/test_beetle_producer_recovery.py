"""Pure offline tests for independent, bounded Beetle producer wakeups."""
import importlib.util
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone

P=Path(__file__).resolve().parents[1]/"tools/beetle_producer_recovery.py"
s=importlib.util.spec_from_file_location("beetle_recovery",P)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
NOW=datetime(2026,10,28,13,0,tzinfo=timezone.utc)


def run(age, *, status="completed", conclusion="success", event="schedule",
        path=m.WORKFLOW, branch="main", num=1):
    return {"id":num,"path":path,"head_branch":branch,"event":event,
            "status":status,"conclusion":conclusion,
            "created_at":(NOW-timedelta(minutes=age)).strftime("%Y-%m-%dT%H:%M:%SZ")}


class RecoveryTests(unittest.TestCase):
    def test_recent_success_never_dispatches(self):
        self.assertFalse(m.decide({"workflow_runs":[run(15)]},NOW)["dispatch"])

    def test_missing_producer_recovers_once(self):
        r=m.decide({"workflow_runs":[run(240),run(600,num=2)]},NOW)
        self.assertTrue(r["dispatch"])
        self.assertEqual(r["action"],"RECOVER_MISSED_PRODUCER")

    def test_active_anywhere_blocks_duplicates(self):
        r=m.decide({"workflow_runs":[run(240),run(240,status="in_progress",num=2)]},NOW)
        self.assertEqual(r["action"],"HOLD_ACTIVE_RUN")

    def test_recent_failure_blocks_storm(self):
        r=m.decide({"workflow_runs":[run(60,conclusion="failure"),run(240,num=2)]},NOW)
        self.assertFalse(r["dispatch"])

    def test_recent_success_blocks_failed_retry(self):
        r=m.decide({"workflow_runs":[run(80,conclusion="failure"),run(89,num=2)]},NOW)
        self.assertFalse(r["dispatch"])

    def test_wrong_repo_or_branch_not_authority(self):
        with self.assertRaises(m.RecoveryHold):
            m.decide({"workflow_runs":[run(999,path="malicious.yml"),
                                     run(999,branch="feature",num=2)]},NOW)

    def test_untrusted_payload_fails_closed(self):
        for d in ({}, {"workflow_runs":"oops"}, {"workflow_runs":[]},
                  {"workflow_runs":[{"status":"completed","path":m.WORKFLOW}]}):
            with self.assertRaises(m.RecoveryHold):
                m.decide(d,NOW)

    def test_unsupported_event_does_not_wake(self):
        with self.assertRaises(m.RecoveryHold):
            m.decide({"workflow_runs":[run(999,event="pull_request")]},NOW)

    def test_future_timestamp_rejected(self):
        with self.assertRaises(m.RecoveryHold):
            m.decide({"workflow_runs":[run(-100)]},NOW)

    def test_delivery_backpressure_blocks_stale_and_excess_pending(self):
        now=NOW
        base={"schema":"janus.beetle.delivery_health.v1",
              "at":now.strftime("%Y-%m-%dT%H:%M:%SZ"),
              "status":"WARN",
              "repositories":{f"consumer-{i}":{"pending":0,"status":"UP_TO_DATE"}
                              for i in range(19)},
              "total_pending":0}
        self.assertEqual(m.delivery_backpressure(base,now),"CLEAR")
        v={**base, "repositories":dict(base["repositories"])}
        v["repositories"]["consumer-0"]={"pending":2,"status":"STALE"}
        v["total_pending"]=2
        self.assertEqual(m.delivery_backpressure(v,now),"HOLD_STALE_RECEIVER_ACK")
        v={**base, "repositories":dict(base["repositories"])}
        for i in range(14):
            v["repositories"][f"consumer-{i}"]={"pending":1,"status":"PENDING"}
        v["total_pending"]=14
        self.assertEqual(m.delivery_backpressure(v,now),"HOLD_DELIVERY_BACKPRESSURE")
        v["total_pending"]=1
        with self.assertRaises(m.RecoveryHold):
            m.delivery_backpressure(v,now)

    def test_missing_delivery_health_fails_closed(self):
        with self.assertRaises(m.RecoveryHold):
            m.delivery_backpressure(None,NOW)

    def test_receiver_health_recomputed_on_each_wakeup(self):
        workflow=(P.parent.parent / ".github/workflows/beetle-producer-bounded-recovery.yml").read_text()
        self.assertIn("ref: beetle-state", workflow)
        self.assertIn("from beetle_delivery_health import inspect", workflow)
        self.assertIn("health = inspect(root, stale_minutes=180)", workflow)
        self.assertNotIn("contents/data/beetle-state/latest_delivery_health.json", workflow)
        self.assertIn("persist-credentials: false", workflow)

    def test_stale_snapshot_not_required_for_recovery(self):
        source=(P.parent.parent / ".github/workflows/beetle-producer-bounded-recovery.yml").read_text()
        self.assertIn("delivery-health.json", source)
        self.assertIn("--delivery-health delivery-health.json", source)
        self.assertIn("BEETLE_RECOVERY_REFRESHED_PENDING=", source)

    def test_zero_science_authority(self):
        src=P.read_text(encoding="utf-8")
        for forbidden in ("ROWAN_API_KEY","submit_protein_cofolding_workflow",
                          "os.system(", "subprocess.run("):
            self.assertNotIn(forbidden,src)


    def test_receiver_wake_cannot_use_untrusted_or_failed_execution(self):
        workflow = (P.parent.parent / ".github/workflows/beetle-producer-bounded-recovery.yml").read_text()
        self.assertIn("workflow_run:", workflow)
        self.assertIn("workflows: ['JANUS Beetle Memory Receiver']", workflow)
        self.assertIn("types: [completed]", workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", workflow)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", workflow)
        self.assertIn("github.event.workflow_run.head_repository.full_name == github.repository", workflow)
        self.assertIn("github.event_name != 'pull_request'", workflow)
        self.assertIn("cron: '13,43 * * * *'", workflow)

if __name__=="__main__":unittest.main()
