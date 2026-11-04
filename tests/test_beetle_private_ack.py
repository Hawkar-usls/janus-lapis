"""Offline privacy/security tests for scoped private ACK visibility."""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import pathlib
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from beetle_delivery_health import (
    PRIVATE_ACK_REPOSITORY, PRIVATE_ACK_TOKEN_ENV, fetch_scoped_private_ack,
    inspect, inspect_queue,
)
from beetle_mirror_router import safe_repo

TOKEN = "READ_ONLY_TEST_TOKEN_DO_NOT_PUBLISH"
DIGEST = "a" * 64
BATCH = "f" * 20
TIME = dt.datetime(2026, 11, 4, 12, 0, tzinfo=dt.timezone.utc)


def ack():
    return {
        "schema": "janus.beetle.inbox_ack.v1",
        "target_repository": PRIVATE_ACK_REPOSITORY,
        "status": "INBOX_DURABLE_UNVERIFIED__NOT_RUNTIME_CONSUMPTION",
        "last_sequence": 1, "batch_id": BATCH, "sha256": DIGEST,
        "acknowledged_at": "2026-11-04T10:00:00Z",
        "scientific_authority_delta": 0,
    }


def queue():
    return {"schema": "janus.beetle.delivery_queue.v1",
            "target_repository": PRIVATE_ACK_REPOSITORY, "next_sequence": 2,
            "entries": [{"sequence": 1, "batch_id": BATCH, "sha256": DIGEST,
                         "created_at": "2026-11-04T09:00:00Z"}]}


class Response:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _cap):
        return self.data


class FakeOpener:
    def __init__(self, body=None, error=None):
        self.body, self.error = body, error
        self.requests = []

    def open(self, req, timeout=None):
        self.requests.append(req)
        if self.error:
            raise self.error
        return Response(self.body)


def body(value):
    raw = json.dumps(value).encode()
    return json.dumps({"type": "file", "encoding": "base64", "size": len(raw),
                       "content": base64.b64encode(raw).decode()}).encode()


class PrivateAckTests(unittest.TestCase):
    def test_private_ack_fetched_only_from_fixed_endpoint(self):
        opener = FakeOpener(body(ack()))
        result, error = fetch_scoped_private_ack(PRIVATE_ACK_REPOSITORY, TOKEN, opener=opener)
        self.assertIsNone(error)
        self.assertEqual(result["last_sequence"], 1)
        self.assertEqual(len(opener.requests), 1)
        self.assertIn("/Hawkar-usls/SkinGPT/contents/data/beetle-inbox/ACK.json",
                      opener.requests[0].full_url)
        self.assertEqual(opener.requests[0].get_header("Authorization"),
                         "Bearer " + TOKEN)
        self.assertEqual(inspect_queue(queue(), result, None, TIME, 180)["status"],
                         "UP_TO_DATE")

    def test_unapproved_private_repo_is_never_fetched(self):
        opener = FakeOpener(body(ack()))
        self.assertEqual(fetch_scoped_private_ack("Hawkar-usls/Janus-Demiurge",
                         TOKEN, opener=opener)[1], "ACK_PRIVATE_SCOPE_DENIED")
        self.assertEqual(opener.requests, [])

    def test_unauthorized_private_read_does_not_forge_ack(self):
        err = urllib.error.HTTPError("url", 403, "Forbidden", None, None)
        result, error = fetch_scoped_private_ack(PRIVATE_ACK_REPOSITORY,
                                                 TOKEN, opener=FakeOpener(error=err))
        self.assertIsNone(result)
        self.assertEqual(error, "ACK_PRIVATE_READ_UNAVAILABLE")
        self.assertEqual(inspect_queue(queue(), result, error, TIME, 180)["status"],
                         "ACK_UNAVAILABLE")

    def test_private_ack_sha_mismatch_remains_conflict(self):
        altered = ack()
        altered["sha256"] = "b" * 64
        result, error = fetch_scoped_private_ack(PRIVATE_ACK_REPOSITORY,
                                                 TOKEN, opener=FakeOpener(body(altered)))
        self.assertIsNone(error)
        self.assertEqual(inspect_queue(queue(), result, error, TIME, 180)["status"],
                         "ACK_CONFLICT")

    def test_malformed_base64_cannot_ack_sender(self):
        bad = json.dumps({"type": "file", "encoding": "base64", "size": 7,
                          "content": "not==valid"}).encode()
        result, error = fetch_scoped_private_ack(PRIVATE_ACK_REPOSITORY,
                                                 TOKEN, opener=FakeOpener(body=bad))
        self.assertIsNone(result)
        self.assertEqual(error, "ACK_PRIVATE_READ_UNAVAILABLE")

    def test_public_health_redacts_private_ack_timestamp_and_batch(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(os.environ,
                                                                    {PRIVATE_ACK_TOKEN_ENV: TOKEN}):
            root = pathlib.Path(temp)
            folder = root / "mirrors" / safe_repo(PRIVATE_ACK_REPOSITORY)
            folder.mkdir(parents=True)
            (folder / "delivery.json").write_text(json.dumps(queue()), encoding="utf-8")
            result = inspect(root, fetcher=lambda repo: (ack(), None),
                             observed_at=TIME, stale_minutes=180)
            row = result["repositories"][PRIVATE_ACK_REPOSITORY]
            self.assertEqual(row["status"], "UP_TO_DATE")
            self.assertEqual(result["total_pending"], 0)
            self.assertNotIn("last_acknowledged_at", row)
            self.assertNotIn("last_confirmed_batch", row)
            self.assertNotIn(TOKEN, json.dumps(result))
            self.assertEqual(row["ack_evidence_scope"], "SCOPED_PRIVATE_READ_INBOX_ONLY")


if __name__ == "__main__":
    unittest.main()
