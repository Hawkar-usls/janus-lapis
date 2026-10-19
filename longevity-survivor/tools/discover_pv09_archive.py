#!/usr/bin/env python3
"""Discover archival/public acquisition routes for the original PvScaf0.9/0.91
P. vanderplanki assembly without treating raw PRJDB1558 reads as the assembly.

Discovery is deliberately bounded: finite public endpoints, short network deadlines,
and no filename guessing promoted as evidence. Every attempt is recorded.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

OUT = Path(os.environ.get("JANUS_PV09_DISCOVERY_OUT", "pv09_archive_discovery")).resolve()
OUT.mkdir(parents=True, exist_ok=True)
UA = "JANUS-LONGEVITY-SURVIVOR/1.0 PvScaf0.9 archival-discovery"
NETWORK_TIMEOUT = 12
MAX_DISCOVERED_PROBES = 30

ROOTS = [
    "http://bertone.nises-f.affrc.go.jp/midgebase/",
    "https://bertone.nises-f.affrc.go.jp/midgebase/",
    "http://bertone.nises-f.affrc.go.jp/cgi-bin/gb2/gbrowse/pv091",
    "https://bertone.nises-f.affrc.go.jp/cgi-bin/gb2/gbrowse/pv091",
]
ARCHIVE_TARGETS = [
    "http://bertone.nises-f.affrc.go.jp/midgebase/",
    "http://bertone.nises-f.affrc.go.jp/cgi-bin/gb2/gbrowse/pv091",
]
CANDIDATE_RE = re.compile(
    r"(?:pv(?:scaf|ander|091|09)|vanderplanki|genom|assembl|download|dump|fasta|fa(?:sta)?(?:\.gz)?|fna|seq|gbrowse|gff|gtf|tar|zip)",
    re.I,
)
HREF_RE = re.compile(r'''href\s*=\s*["']([^"']+)["']''', re.I)
SEQ_EXT_RE = re.compile(r"\.(?:fa|fasta|fna|fas|seq)(?:\.gz)?(?:$|[?#])|\.(?:tar\.gz|tgz|zip)(?:$|[?#])", re.I)


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def get(url: str, timeout: int = NETWORK_TIMEOUT) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.geturl(), r.headers.get("Content-Type", "")


def attempt(url: str, label: str) -> dict:
    try:
        b, final, ctype = get(url)
        rec = {
            "label": label,
            "url": url,
            "status": "PASS",
            "final_url": final,
            "content_type": ctype,
            "bytes": len(b),
            "sha256": sha256(b),
            "prefix_hex": b[:16].hex(),
        }
        if b.lstrip().startswith(b">"):
            rec["payload_hint"] = "FASTA_LIKE"
        elif b[:2] == b"\x1f\x8b":
            rec["payload_hint"] = "GZIP_LIKE"
        elif b[:4] == b"PK\x03\x04":
            rec["payload_hint"] = "ZIP_LIKE"
        elif b[:200].lstrip().lower().startswith((b"<!doctype html", b"<html")):
            rec["payload_hint"] = "HTML"
        else:
            rec["payload_hint"] = "OTHER"
        return rec | {"_bytes": b}
    except Exception as e:
        return {"label": label, "url": url, "status": "FAIL", "error": f"{type(e).__name__}: {e}"}


def cdx_query(target: str) -> dict:
    params = {
        "url": target,
        "output": "json",
        "fl": "timestamp,original,mimetype,statuscode,digest,length",
        "filter": "statuscode:200",
        "collapse": "urlkey",
        "from": "2013",
        "to": "2023",
        "limit": "5000",
    }
    url = "https://web.archive.org/cdx/search/cdx?" + urllib.parse.urlencode(params)
    rec = attempt(url, "WAYBACK_CDX")
    if rec.get("status") != "PASS":
        return {k: v for k, v in rec.items() if k != "_bytes"}
    b = rec.pop("_bytes")
    try:
        rows = json.loads(b)
    except Exception as e:
        rec["parse_error"] = f"{type(e).__name__}: {e}"
        rec["body_preview"] = b[:2000].decode("utf-8", "replace")
        return rec
    header = rows[0] if rows else []
    entries = [dict(zip(header, r)) for r in rows[1:] if isinstance(r, list)] if header else []
    candidates = [x for x in entries if CANDIDATE_RE.search(x.get("original", ""))]
    strong = [x for x in candidates if SEQ_EXT_RE.search(x.get("original", ""))]
    rec.update({"rows": len(entries), "candidate_rows": candidates, "strong_sequence_rows": strong})
    return rec


def availability(target: str) -> dict:
    url = "https://archive.org/wayback/available?" + urllib.parse.urlencode({"url": target, "timestamp": "20200301"})
    rec = attempt(url, "WAYBACK_AVAILABILITY")
    if rec.get("status") != "PASS":
        return {k: v for k, v in rec.items() if k != "_bytes"}
    b = rec.pop("_bytes")
    try:
        rec["json"] = json.loads(b)
    except Exception as e:
        rec["parse_error"] = f"{type(e).__name__}: {e}"
        rec["body_preview"] = b[:2000].decode("utf-8", "replace")
    return rec


def extract_links(base: str, body: bytes) -> list[str]:
    text = body.decode("utf-8", "replace")
    out = []
    for raw in HREF_RE.findall(text):
        raw = html.unescape(raw.strip())
        if raw.startswith(("javascript:", "mailto:", "#")):
            continue
        u = urllib.parse.urljoin(base, raw)
        if CANDIDATE_RE.search(u):
            out.append(u)
    return sorted(set(out))


def main() -> int:
    report = {
        "artifact_id": "JANUS-PV09-ARCHIVE-DISCOVERY-V1_1",
        "status": "DISCOVERY_ONLY",
        "network_timeout_seconds": NETWORK_TIMEOUT,
        "max_discovered_candidate_probes": MAX_DISCOVERED_PROBES,
        "forbidden_substitute": "PRJDB1558_RAW_READ_REASSEMBLY_AS_PvScaf0.9",
        "direct_attempts": [],
        "wayback_availability": [],
        "wayback_cdx": [],
        "discovered_links": [],
        "candidate_payloads": [],
    }

    discovered = set()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(attempt, root, "LIVE_ORIGINAL"): root for root in ROOTS}
        for fut in as_completed(futs):
            root = futs[fut]
            r = fut.result(); b = r.pop("_bytes", None)
            report["direct_attempts"].append(r)
            if b is not None and r.get("payload_hint") == "HTML":
                discovered.update(extract_links(r.get("final_url", root), b))

    for target in ARCHIVE_TARGETS:
        av = availability(target)
        report["wayback_availability"].append(av)
        snap = (((av.get("json") or {}).get("archived_snapshots") or {}).get("closest") or {}).get("url")
        if snap:
            r = attempt(snap, "WAYBACK_CLOSEST_PAGE"); b = r.pop("_bytes", None)
            report["direct_attempts"].append(r)
            if b is not None:
                discovered.update(extract_links(r.get("final_url", snap), b))
        report["wayback_cdx"].append(cdx_query(target.rstrip("/") + "/*"))

    strong_discovered = sorted(u for u in discovered if SEQ_EXT_RE.search(u) or "download" in u.lower() or "genome" in u.lower())[:MAX_DISCOVERED_PROBES]
    report["discovered_links"] = sorted(discovered)
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(attempt, u, "DISCOVERED_CANDIDATE"): u for u in strong_discovered}
        for fut in as_completed(futs):
            r = fut.result(); b = r.pop("_bytes", None)
            if b is not None and r.get("payload_hint") in {"FASTA_LIKE", "GZIP_LIKE", "ZIP_LIKE"}:
                name = f"candidate_{len(report['candidate_payloads'])+1:03d}.bin"
                (OUT / name).write_bytes(b); r["saved_as"] = name
            report["candidate_payloads"].append(r)

    cdx_strong = []
    for block in report["wayback_cdx"]:
        cdx_strong.extend(block.get("strong_sequence_rows", []))
    report["cdx_strong_sequence_candidates"] = cdx_strong
    report["old_assembly_admission"] = "NOT_ADMITTED_DISCOVERY_REQUIRES_CONTENT_VALIDATION"
    (OUT / "archive_discovery.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("PV09_ARCHIVE_DISCOVERY", json.dumps({
        "direct_passes": sum(x.get("status") == "PASS" for x in report["direct_attempts"]),
        "discovered_links": len(report["discovered_links"]),
        "cdx_strong_candidates": len(cdx_strong),
        "candidate_payloads_probed": len(report["candidate_payloads"]),
        "saved_binary_candidates": sum(bool(x.get("saved_as")) for x in report["candidate_payloads"]),
        "old_assembly_admission": report["old_assembly_admission"],
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
