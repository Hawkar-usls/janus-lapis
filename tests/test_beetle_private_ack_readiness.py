"""P0.3 SkinGPT private-readiness: never expose private content or fake its ACK."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import beetle_private_ack_readiness as m


def valid_queue():
    return {"schema":"janus.beetle.delivery_queue.v1",
            "target_repository":m.PRIVATE_ACK_REPOSITORY,
            "entries":[
                {"sequence":1,"batch_id":"a"*20,"sha256":"1"*64,
                 "created_at":"2026-11-23T09:00:00Z"},
                {"sequence":2,"batch_id":"b"*20,"sha256":"2"*64,
                 "created_at":"2026-11-23T09:01:00Z"},
            ],"next_sequence":3}


def valid_ack():
    return {"schema":"janus.beetle.inbox_ack.v1",
            "target_repository":m.PRIVATE_ACK_REPOSITORY,
            "status":"INBOX_DURABLE_UNVERIFIED__NOT_RUNTIME_CONSUMPTION",
            "last_sequence":2,"batch_id":"b"*20,"sha256":"2"*64}


class AckReadinessTests(unittest.TestCase):
    def test_without_secret_never_contacts_private_receiver(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/m.QUEUE
            file.parent.mkdir(parents=True)
            file.write_text(json.dumps(valid_queue()))
            def fail_fetch(*_):
                self.fail("network must not be called without secret")
            with patch.dict(os.environ,{m.PRIVATE_ACK_TOKEN_ENV:""},clear=False):
                r=m.check(Path(td),fetcher=fail_fetch)
            self.assertEqual(r["status"],"HOLD_READ_CREDENTIAL_NOT_CONFIGURED")
            self.assertEqual(r["pending"],2)
            self.assertEqual(r["confirmed"],0)
            self.assertFalse(r["p03_phase_admitted"])

    def test_valid_receiver_side_ack_matches_both_packets(self):
        r=m.assess(valid_queue(),True,valid_ack())
        self.assertEqual(r["status"],"INBOX_DURABLE_ACK_MATCHED__NOT_CONSUMED")
        self.assertEqual((r["produced"],r["confirmed"],r["pending"]),(2,2,0))
        self.assertFalse(r["receipt_or_model_consumption_attested"])
        self.assertFalse(r["external_custodian_attested"])
        self.assertNotIn("batch_id",r)
        self.assertNotIn("sha256",r)

    def test_malformed_ack_or_wrong_sha_never_clear_backpressure(self):
        ack=valid_ack()
        ack["sha256"]="f"*64
        r=m.assess(valid_queue(),True,ack)
        self.assertEqual(r["status"],"HOLD_PRIVATE_ACK_CONFLICT")
        self.assertEqual(r["pending"],2)

    def test_missing_or_invalid_credential_fails_closed(self):
        r=m.assess(valid_queue(),True,None,"ACK_PRIVATE_READ_UNAVAILABLE")
        self.assertEqual(r["status"],"HOLD_PRIVATE_ACK_UNAVAILABLE")
        self.assertEqual(r["pending"],2)

    def test_partial_ack_still_has_backlog(self):
        ack=valid_ack()
        ack.update(last_sequence=1,batch_id="a"*20,sha256="1"*64)
        r=m.assess(valid_queue(),True,ack)
        self.assertEqual(r["status"],"HOLD_PRIVATE_ACK_PENDING")
        self.assertEqual(r["pending"],1)

    def test_wrong_repo_and_invalid_queue_rejected(self):
        for mutate in (
            lambda q:q.update(target_repository="someone/else"),
            lambda q:q.update(next_sequence=9),
            lambda q:q["entries"][0].update(sequence=2),
            lambda q:q["entries"][0].update(sha256="notSHA"),
        ):
            q=valid_queue();mutate(q)
            with self.assertRaises(ValueError):
                m.assess(q,False,None)

    def test_no_batch_identifiers_or_tokens_in_output(self):
        r=m.assess(valid_queue(),True,valid_ack())
        raw=json.dumps(r)
        self.assertNotIn("a"*20,raw)
        self.assertNotIn("b"*20,raw)
        self.assertNotIn("2"*64,raw)
        self.assertFalse(r["private_ack_contents_output"])
        self.assertFalse(r["routing_or_queue_modified"])

    def test_replay_is_deterministic(self):
        a=m.assess(valid_queue(),True,valid_ack())
        b=m.assess(valid_queue(),True,valid_ack())
        self.assertEqual(a,b)


if __name__=="__main__":
    unittest.main()
