#!/usr/bin/env python3
"""Bounded, lossless JSONL storage for JANUS Beetle's append-only ledgers.

Existing Git history preserves the original single-file ledgers.  Migration
copies their *exact bytes* into ordered shards, checks the SHA-256 and byte
count, then removes only the now-redundant worktree copy.  A frozen migration
receipt protects those historical shards from future modifications.

The code intentionally does not interpret candidate rows or promote them to
scientific evidence.  It only preserves and verifies their transport bytes.
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterator

LEDGERS = ("candidates", "contexts", "receipts")
PART_BYTES = 16_000_000  # Conservative headroom below GitHub's 100 MiB cap.
MAX_GIT_FILE_BYTES = 80_000_000
SCHEMA = "janus.beetle.sharded_jsonl.v1"
_READY: set[tuple[Path, str]] = set()


def _parts(root: Path, name: str) -> Path:
    if name not in LEDGERS:
        raise ValueError(f"unknown Beetle ledger: {name}")
    return root / f"{name}.parts"


def _legacy(root: Path, name: str) -> Path:
    return root / f"{name}.jsonl"


def _files(root: Path, name: str) -> list[Path]:
    directory = _parts(root, name)
    files = sorted(directory.glob("part-*.jsonl")) if directory.exists() else []
    if files != [directory / f"part-{i:06d}.jsonl" for i in range(1, len(files) + 1)]:
        raise ValueError(f"non-contiguous or unexpected shard sequence: {directory}")
    return files


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _describe(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = count = 0
    with path.open("rb") as stream:
        for line in stream:
            if not line.endswith(b"\n"):
                raise ValueError(f"unterminated JSONL record in {path}")
            size += len(line)
            count += 1
            digest.update(line)
    return {"name": path.name, "bytes": size, "lines": count, "sha256": digest.hexdigest()}


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def _verify_migration(root: Path, name: str) -> dict[str, Any] | None:
    marker = _parts(root, name) / "migration.json"
    if not marker.exists():
        return None
    receipt = json.loads(marker.read_text(encoding="utf-8"))
    if receipt.get("schema") != SCHEMA or receipt.get("ledger") != name:
        raise ValueError(f"invalid migration receipt: {marker}")
    sha = hashlib.sha256()
    size = count = 0
    for recorded in receipt["original_parts"]:
        filename = recorded["name"]
        if not filename.startswith("part-") or "/" in filename or "\\" in filename:
            raise ValueError("invalid historical shard name")
        path = _parts(root, name) / filename
        actual = _describe(path)
        if actual != recorded:
            raise ValueError(f"historical shard integrity failed: {path}")
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                sha.update(block)
        size += actual["bytes"]
        count += actual["lines"]
    original = receipt["original"]
    if (sha.hexdigest(), size, count) != (original["sha256"], original["bytes"], original["lines"]):
        raise ValueError(f"original byte-for-byte reconstruction failed: {name}")
    return receipt


def migrate(root: Path, name: str, limit: int = PART_BYTES) -> dict[str, Any]:
    """Migrate legacy log without losing a byte, or resume a completed rename."""
    if not 1_024 <= limit < MAX_GIT_FILE_BYTES:
        raise ValueError("invalid shard limit")
    root.mkdir(parents=True, exist_ok=True)
    original = _legacy(root, name)
    target = _parts(root, name)
    if target.exists():
        files = _files(root, name)
        frozen = _verify_migration(root, name)
        if original.exists():
            if frozen is None or file_digest(original) != frozen["original"]["sha256"] or original.stat().st_size != frozen["original"]["bytes"]:
                raise ValueError(f"refusing ambiguous legacy + shards state: {name}")
            original.unlink()  # Exact copy verified; recoverable from previous Git commit.
        return {"ledger": name, "mode": "sharded", "parts": len(files)}
    if not original.exists():
        return {"ledger": name, "mode": "empty", "parts": 0}

    stage = Path(tempfile.mkdtemp(prefix=f".{name}-migration-", dir=root))
    original_hash = hashlib.sha256()
    nbytes = lines = 0
    try:
        with original.open("rb") as source:
            index, shard_size = 0, 0
            output = None
            for row in source:
                if not row.endswith(b"\n") or len(row) > limit:
                    raise ValueError(f"record too large or unterminated in {original}")
                if output is None or shard_size + len(row) > limit:
                    if output:
                        output.close()
                    index += 1
                    output = (stage / f"part-{index:06d}.jsonl").open("wb")
                    shard_size = 0
                output.write(row)
                shard_size += len(row)
                original_hash.update(row)
                nbytes += len(row)
                lines += 1
            if output:
                output.close()
        if original.stat().st_size != nbytes or file_digest(original) != original_hash.hexdigest():
            raise ValueError("source changed during migration; refusing to remove legacy")
        originals = [_describe(path) for path in sorted(stage.glob("part-*.jsonl"))]
        receipt = {
            "schema": SCHEMA,
            "ledger": name,
            "shard_limit_bytes": limit,
            "original": {"sha256": original_hash.hexdigest(), "bytes": nbytes, "lines": lines},
            "original_parts": originals,
            "authority": "STORAGE_REENCODING_ONLY__NO_EVIDENCE_PROMOTION",
        }
        _atomic_json(stage / "migration.json", receipt)
        os.replace(stage, target)
        _verify_migration(root, name)
        original.unlink()  # A verified exact copy is present and Git history has the source.
        return {"ledger": name, "mode": "migrated", "parts": len(originals), **receipt["original"]}
    finally:
        if stage.exists():
            shutil.rmtree(stage)  # Only this invocation's private incomplete staging dir.


def append(root: Path, name: str, row: dict[str, Any], limit: int = PART_BYTES) -> None:
    key = (root.resolve(), name)
    if key not in _READY:
        migrate(root, name, limit)
        _READY.add(key)
    if not 1_024 <= limit < MAX_GIT_FILE_BYTES:
        raise ValueError("invalid shard limit")
    data = (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    if len(data) > limit:
        raise ValueError("a single record exceeds the shard size ceiling")
    folder = _parts(root, name)
    folder.mkdir(parents=True, exist_ok=True)
    files = _files(root, name)
    migration_file = folder / "migration.json"
    protected_count = (len(json.loads(migration_file.read_text(encoding="utf-8"))["original_parts"])
                       if migration_file.exists() else 0)
    last = files[-1] if len(files) > protected_count else None
    if last is None or last.stat().st_size + len(data) > limit:
        last = folder / f"part-{len(files) + 1:06d}.jsonl"
    with last.open("ab") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def iter_lines(root: Path, name: str) -> Iterator[str]:
    legacy = _legacy(root, name)
    files = _files(root, name)
    if legacy.exists() and files:
        raise ValueError(f"ambiguous legacy + shards state: {name}")
    paths = files if files else [legacy] if legacy.exists() else []
    for path in paths:
        with path.open("r", encoding="utf-8") as stream:
            yield from stream


def latest_row(root: Path, name: str) -> dict[str, Any] | None:
    result = deque((line for line in iter_lines(root, name) if line.strip()), maxlen=1)
    return json.loads(result[0]) if result else None


def seal(root: Path, max_file_bytes: int = MAX_GIT_FILE_BYTES) -> dict[str, Any]:
    """Validate all prospective Git blobs and write bounded provenance indexes."""
    if not 1_024 <= max_file_bytes < 100_000_000:
        raise ValueError("invalid Git blob ceiling")
    ledgers: dict[str, Any] = {}
    for name in LEDGERS:
        migrate(root, name)
        files = _files(root, name)
        if not files:
            continue
        _verify_migration(root, name)
        parts = [_describe(path) for path in files]
        if any(x["bytes"] > PART_BYTES for x in parts):
            raise ValueError(f"oversized JSONL shard in {name}")
        info = {"schema": SCHEMA, "ledger": name, "parts": parts,
                "total_bytes": sum(x["bytes"] for x in parts),
                "total_lines": sum(x["lines"] for x in parts)}
        _atomic_json(_parts(root, name) / "index.json", info)
        ledgers[name] = {"parts": len(parts), "bytes": info["total_bytes"], "lines": info["total_lines"]}
    largest: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if path.name.startswith(".contexts-migration-") or path.name.startswith(".candidates-migration-") or path.name.startswith(".receipts-migration-"):
            raise ValueError(f"unfinished migration staging directory must be investigated: {path}")
        if path.is_symlink():
            raise ValueError(f"refusing symlink inside Beetle state: {path}")
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size >= max_file_bytes:
            raise ValueError(f"Git blob guard: {path} is {size} bytes, limit {max_file_bytes}")
        largest.append({"path": str(path.relative_to(root)), "bytes": size})
    summary = {"schema": "janus.beetle.storage_health.v1", "status": "PASS",
               "max_file_bytes": max_file_bytes, "ledgers": ledgers,
               "largest_files": sorted(largest, key=lambda x: x["bytes"], reverse=True)[:8],
               "scientific_authority_delta": 0}
    _atomic_json(root / "latest_storage_health.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Lossless sharded Beetle memory")
    parser.add_argument("action", choices=["migrate", "seal"])
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--max-file-bytes", type=int, default=MAX_GIT_FILE_BYTES)
    options = parser.parse_args()
    if options.action == "migrate":
        result = [migrate(options.state_dir, name) for name in LEDGERS]
    else:
        result = seal(options.state_dir, options.max_file_bytes)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
