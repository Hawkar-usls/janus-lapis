#!/usr/bin/env python3
"""Acquire exact, page-discovered P. vanderplanki Pv0.9/Pv0.91 MidgeBase files
from the Internet Archive and preserve byte-level provenance.

The filenames below were discovered from the archived MidgeBase download page;
they are not inferred from naming patterns. No retrieved payload is scientifically
admitted until its contents are validated against expected PvScaf/PvG identifiers.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

OUT = Path(os.environ.get("JANUS_PV09_EXACT_OUT", "pv09_exact_archives")).resolve()
OUT.mkdir(parents=True, exist_ok=True)
UA = "JANUS-LONGEVITY-SURVIVOR/1.0 exact-Pv09-MidgeBase-acquisition"
TIMEOUT = 45

# Evidence origin: hrefs extracted from archived MidgeBase page snapshot 20200217020915.
ORIGINALS = {
    "pv09_genome": "http://bertone.nises-f.affrc.go.jp/files/pv/assembly/PvScaf_v0.9.fasta.zip",
    "pv091_gene_model": "http://bertone.nises-f.affrc.go.jp/files/pv/genemodel/PvGeneModel_v0.91.tar.gz",
    "pv091_gene_model_gff": "http://bertone.nises-f.affrc.go.jp/files/pv/genemodel/PvGeneModel_v0.91.gff.tar.gz",
    "pv20121018_nt": "http://bertone.nises-f.affrc.go.jp/files/pv/genemodel/Pv20121018.all.fa.tar.gz",
    "pv20121018_aa": "http://bertone.nises-f.affrc.go.jp/files/pv/genemodel/Pv20121018.all.aa.tar.gz",
}
TIMESTAMPS = ["20220405", "20200301", "20180101", "20150101", "20240101"]


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def get(url: str, timeout: int = TIMEOUT) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.geturl(), r.headers.get("Content-Type", "")


def availability(original: str, timestamp: str) -> dict:
    api = "https://archive.org/wayback/available?" + urllib.parse.urlencode({"url": original, "timestamp": timestamp})
    try:
        b, final, ctype = get(api, 20)
        obj = json.loads(b)
        closest = ((obj.get("archived_snapshots") or {}).get("closest") or {})
        return {
            "status": "PASS",
            "api_url": api,
            "api_final_url": final,
            "api_content_type": ctype,
            "api_sha256": sha256(b),
            "requested_timestamp": timestamp,
            "closest": closest,
        }
    except Exception as e:
        return {"status": "FAIL", "api_url": api, "requested_timestamp": timestamp, "error": f"{type(e).__name__}: {e}"}


def classify(b: bytes) -> str:
    if b[:4] == b"PK\x03\x04": return "ZIP"
    if b[:2] == b"\x1f\x8b": return "GZIP"
    if b.lstrip().startswith(b">"): return "FASTA"
    if b[:200].lstrip().lower().startswith((b"<!doctype html", b"<html")): return "HTML"
    return "OTHER"


def acquire_one(label: str, original: str) -> dict:
    av = [availability(original, ts) for ts in TIMESTAMPS]
    candidates = []
    seen = set()
    for x in av:
        c = x.get("closest") or {}
        u = c.get("url")
        ts = c.get("timestamp")
        if u and u not in seen:
            candidates.append(("closest", u)); seen.add(u)
        # Raw replay is useful for archived binary payloads and avoids HTML rewriting.
        if ts:
            raw = f"https://web.archive.org/web/{ts}id_/{original}"
            if raw not in seen:
                candidates.append(("raw_replay", raw)); seen.add(raw)
    attempts = []
    accepted = None
    for route, url in candidates:
        try:
            b, final, ctype = get(url)
            kind = classify(b)
            rec = {"route": route, "url": url, "status": "PASS", "final_url": final, "content_type": ctype,
                   "bytes": len(b), "sha256": sha256(b), "payload_kind": kind, "prefix_hex": b[:16].hex()}
            attempts.append(rec)
            if kind in {"ZIP", "GZIP", "FASTA"}:
                ext = ".zip" if kind == "ZIP" else ".tar.gz" if kind == "GZIP" else ".fasta"
                path = OUT / f"{label}{ext}"
                path.write_bytes(b)
                accepted = rec | {"saved_as": path.name}
                break
        except Exception as e:
            attempts.append({"route": route, "url": url, "status": "FAIL", "error": f"{type(e).__name__}: {e}"})
    return {
        "label": label,
        "original_url": original,
        "availability": av,
        "download_attempts": attempts,
        "retrieved_binary_candidate": accepted,
        "admission": "RETRIEVED_NOT_YET_CONTENT_VALIDATED" if accepted else "NOT_RETRIEVED",
    }


def main() -> int:
    results = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = {ex.submit(acquire_one, label, url): label for label, url in ORIGINALS.items()}
        for fut in as_completed(futs):
            results.append(fut.result())
    results.sort(key=lambda x: x["label"])
    summary = {
        "artifact_id": "JANUS-PV09-EXACT-MIDGEBASE-ARCHIVE-ACQUISITION-V1",
        "source_discovery": {
            "archived_midgebase_page_timestamp": "20200217020915",
            "rule": "ONLY_EXACT_HREFS_DISCOVERED_ON_ARCHIVED_MIDGEBASE_PAGE_ARE_PROBED"
        },
        "results": results,
        "retrieved_count": sum(bool(x.get("retrieved_binary_candidate")) for x in results),
        "old_sequence_admission": "PENDING_CONTENT_VALIDATION",
        "hard_boundaries": [
            "WAYBACK_CAPTURE_NE_AUTOMATIC_BIOLOGICAL_IDENTITY",
            "RETRIEVED_BYTES_MUST_BE_HASHED_AND_CONTENT_VALIDATED",
            "PvScaf_HEADERS_REQUIRED_FOR_GENOME_ADMISSION",
            "PvG_IDENTIFIERS_REQUIRED_FOR_OLD_GENE_MODEL_SEQUENCE_ADMISSION",
            "MISSING_DATA_STAYS_MISSING"
        ]
    }
    (OUT / "exact_archive_acquisition.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("PV09_EXACT_ARCHIVE", json.dumps({"retrieved_count": summary["retrieved_count"],
                                            "labels": {x["label"]: x["admission"] for x in results}}, sort_keys=True), flush=True)
    # Acquisition probe succeeds even if archival bytes are unavailable; absence is a result.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
