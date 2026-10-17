"""Offline storage and Genesis inbox compatibility tests for Universal Beetle."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from beetle_shard_store import append, iter_lines, latest_row, migrate, seal  # noqa: E402


def serialize(rows: list[dict]) -> bytes:
    return b"".join((json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8") for row in rows)


class BeetleShardedStorageTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="janus-beetle-test-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_lossless_migration_and_continued_append(self):
        historical = [{"candidate_id": f"c{i:04d}", "title": f"Мем {i}"} for i in range(90)]
        original = serialize(historical)
        (self.root / "contexts.jsonl").write_bytes(original)
        result = migrate(self.root, "contexts", limit=1024)
        self.assertEqual(result["sha256"], hashlib.sha256(original).hexdigest())
        self.assertFalse((self.root / "contexts.jsonl").exists())
        parts = sorted((self.root / "contexts.parts").glob("part-*.jsonl"))
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(p.stat().st_size <= 1024 for p in parts))
        self.assertEqual(b"".join(p.read_bytes() for p in parts), original)
        frozen = [(p.name, hashlib.sha256(p.read_bytes()).hexdigest()) for p in parts]
        append(self.root, "contexts", {"candidate_id": "NEW", "title": "новая находка"}, limit=1024)
        for p, digest in zip(parts, [x[1] for x in frozen]):
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), digest)
        rows = [json.loads(row) for row in iter_lines(self.root, "contexts")]
        self.assertEqual(rows[:-1], historical)
        self.assertEqual(rows[-1]["candidate_id"], "NEW")
        self.assertEqual(seal(self.root)["ledgers"]["contexts"]["lines"], 91)

    def test_interrupted_rename_can_safely_finish(self):
        original = serialize([{"id": i} for i in range(3)])
        (self.root / "receipts.jsonl").write_bytes(original)
        migrate(self.root, "receipts")
        (self.root / "receipts.jsonl").write_bytes(original)  # Crash immediately before legacy removal.
        self.assertEqual(migrate(self.root, "receipts")["mode"], "sharded")
        self.assertFalse((self.root / "receipts.jsonl").exists())
        self.assertEqual(b"".join(p.read_bytes() for p in (self.root / "receipts.parts").glob("part-*.jsonl")), original)

    def test_corrupted_historical_shard_fails_closed(self):
        (self.root / "contexts.jsonl").write_bytes(serialize([{"id": "old"}]))
        migrate(self.root, "contexts")
        shard = self.root / "contexts.parts" / "part-000001.jsonl"
        shard.write_bytes(serialize([{"id": "tampered"}]))
        with self.assertRaisesRegex(ValueError, "historical shard integrity"):
            seal(self.root)

    def test_ambiguous_legacy_and_shards_refuses_loss(self):
        (self.root / "candidates.jsonl").write_bytes(serialize([{"id": "old"}]))
        migrate(self.root, "candidates")
        (self.root / "candidates.jsonl").write_bytes(serialize([{"id": "different"}]))
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            migrate(self.root, "candidates")
        self.assertTrue((self.root / "candidates.jsonl").exists())

    def test_oversize_row_is_rejected_before_write(self):
        with self.assertRaisesRegex(ValueError, "single record"):
            append(self.root, "contexts", {"text": "x" * 2000}, limit=1024)
        self.assertEqual(list(iter_lines(self.root, "contexts")), [])

    def test_github_file_ceiling_applies_to_other_files(self):
        (self.root / "seen.json").write_text("x" * 1024, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Git blob guard"):
            seal(self.root, max_file_bytes=1024)

    def test_legacy_receipt_tail_is_still_available(self):
        (self.root / "receipts.jsonl").write_bytes(serialize([{"receipt_sha256": "aaa"}, {"receipt_sha256": "bbb"}]))
        self.assertEqual(latest_row(self.root, "receipts")["receipt_sha256"], "bbb")
        migrate(self.root, "receipts")
        self.assertEqual(latest_row(self.root, "receipts")["receipt_sha256"], "bbb")

    def test_genesis_receiver_batch_contract_after_projection_and_routing(self):
        candidate = {"candidate_id": "candidate-1", "title": "inverse problem", "summary": "verified provenance needed",
                     "tags": ["research"], "source": "arxiv", "url": "https://arxiv.org/abs/test"}
        append(self.root, "candidates", candidate)
        cfg = self.root / "directions.json"
        cfg.write_text(json.dumps({"directions": [{"id": lens.lower(), "enabled": True, "keywords": ["inverse"],
                   "priority_keywords": [], "min_score": 1, "mirror_lens": lens,
                   "target_repositories": ["Hawkar-usls/Janus_Genesis"]}
                   for lens in ("FORWARD", "REVERSE", "COUNTEREVIDENCE", "CONTROL")]}, indent=2), encoding="utf-8")
        project = subprocess.run([sys.executable, str(TOOLS / "beetle_context_projector.py"),
                    "--state-dir", str(self.root), "--effective-config", str(cfg)], capture_output=True, text=True)
        self.assertEqual(project.returncode, 0, project.stderr)
        self.assertEqual(json.loads(project.stdout)["new_contexts"], 4)
        route = subprocess.run([sys.executable, str(TOOLS / "beetle_mirror_router.py"),
                    "--state-dir", str(self.root), "--effective-config", str(cfg)], capture_output=True, text=True)
        self.assertEqual(route.returncode, 0, route.stderr)
        path = self.root / "mirrors" / "Hawkar-usls__Janus_Genesis" / "latest.json"
        packet = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(packet["schema"], "janus.beetle.repo_memory_batch.v1")
        self.assertEqual(packet["target_repository"], "Hawkar-usls/Janus_Genesis")
        self.assertEqual(packet["claim_ceiling"], "DISCOVERY_MEMORY_ONLY__TARGET_REPO_MUST_VERIFY_INDEPENDENTLY")
        self.assertEqual({item["mirror_lens"] for item in packet["items"]},
                         {"FORWARD", "REVERSE", "COUNTEREVIDENCE", "CONTROL"})
        # Repeating a scheduled run with identical state must remain idempotent.
        subprocess.run([sys.executable, str(TOOLS / "beetle_context_projector.py"),
                        "--state-dir", str(self.root), "--effective-config", str(cfg)], check=True, capture_output=True)
        self.assertEqual(len(list(iter_lines(self.root, "contexts"))), 4)


if __name__ == "__main__":
    unittest.main()
