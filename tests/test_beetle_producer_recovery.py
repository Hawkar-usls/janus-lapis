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

    def test_zero_science_authority(self):
        src=P.read_text(encoding="utf-8")
        for forbidden in ("ROWAN_API_KEY","submit_protein_cofolding_workflow",
                          "os.system(", "subprocess.run("):
            self.assertNotIn(forbidden,src)


if __name__=="__main__":unittest.main()
