#!/usr/bin/env python3
"""
JANUS UNIVERSAL BEETLE v1.0

A bounded, resumable, provenance-first research scout for large/public data.
It is intentionally split into two roles:

  SCOUT  -> discover small metadata records from configured public sources
  GRAZER -> keep consuming already-approved large targets in bounded bites

State is external to the code and is designed to live on a dedicated Git branch.
The runner can die after every invocation; the next run resumes from receipts and
checkpoints.

Core law:
    DIRECTION -> DISCOVER -> SCORE -> DEDUPE -> BITE -> RECEIPT -> CHECKPOINT -> NEXT

This tool does NOT promote discoveries to truth. All discovered items are candidates.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, Iterable

import requests

VERSION = "1.0.0"
UA = "JANUS-Universal-Beetle/1.0 (+https://github.com/Hawkar-usls/janus-lapis)"
DEFAULT_TIMEOUT = 45


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_obj(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj)).hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", "replace")).hexdigest()


def load_json(path: pathlib.Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: pathlib.Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: pathlib.Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def safe_https(url: str) -> str:
    p = urllib.parse.urlparse(url)
    if p.scheme != "https" or not p.netloc:
        raise ValueError(f"Only absolute HTTPS URLs are allowed: {url!r}")
    return url


def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def item_id(source: str, url: str, title: str = "") -> str:
    return sha256_text(f"{source}\n{url}\n{title}")[:24]


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "*/*"})
    return s


@dataclasses.dataclass
class Budget:
    max_requests: int = 24
    max_new_items: int = 40
    max_metadata_bytes: int = 4_000_000
    requests: int = 0
    new_items: int = 0
    metadata_bytes: int = 0

    def can_request(self) -> bool:
        return self.requests < self.max_requests and self.metadata_bytes < self.max_metadata_bytes

    def note_request(self, nbytes: int = 0) -> None:
        self.requests += 1
        self.metadata_bytes += max(0, nbytes)

    def can_add(self) -> bool:
        return self.new_items < self.max_new_items

    def note_add(self) -> None:
        self.new_items += 1


class State:
    def __init__(self, root: pathlib.Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.seen_path = root / "seen.json"
        self.cursor_path = root / "cursors.json"
        self.candidates_path = root / "candidates.jsonl"
        self.receipts_path = root / "receipts.jsonl"
        self.latest_path = root / "latest_run.json"
        self.seen: dict[str, dict[str, Any]] = load_json(self.seen_path, {})
        self.cursors: dict[str, Any] = load_json(self.cursor_path, {})
        self.prev_receipt = self._last_receipt_hash()

    def _last_receipt_hash(self) -> str | None:
        if not self.receipts_path.exists():
            return None
        last = None
        with self.receipts_path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.strip():
                    last = line
        if not last:
            return None
        try:
            return json.loads(last).get("receipt_sha256")
        except Exception:
            return None

    def receipt(self, event: str, payload: dict[str, Any]) -> str:
        body = {
            "schema": "janus.universal_beetle.receipt.v1",
            "tool_version": VERSION,
            "at": now(),
            "event": event,
            "prev_receipt_sha256": self.prev_receipt,
            "payload": payload,
        }
        digest = sha256_obj(body)
        row = {"receipt_sha256": digest, **body}
        append_jsonl(self.receipts_path, row)
        self.prev_receipt = digest
        return digest

    def save(self) -> None:
        atomic_json(self.seen_path, self.seen)
        atomic_json(self.cursor_path, self.cursors)


def keyword_score(direction: dict[str, Any], title: str, summary: str, tags: Iterable[str] = ()) -> tuple[float, list[str]]:
    hay = " ".join([title, summary, " ".join(tags)]).lower()
    hits: list[str] = []
    score = 0.0
    for kw in direction.get("keywords", []):
        k = str(kw).strip().lower()
        if k and k in hay:
            hits.append(k)
            score += 1.0 + min(2.0, len(k) / 24.0)
    for kw in direction.get("priority_keywords", []):
        k = str(kw).strip().lower()
        if k and k in hay:
            hits.append(k)
            score += 3.0
    return score, sorted(set(hits))


def record_candidate(state: State, budget: Budget, direction: dict[str, Any], item: dict[str, Any]) -> bool:
    iid = item_id(item["source"], item["url"], item.get("title", ""))
    if iid in state.seen:
        return False
    score, hits = keyword_score(direction, item.get("title", ""), item.get("summary", ""), item.get("tags", []))
    threshold = float(direction.get("min_score", 1.0))
    if score < threshold or not budget.can_add():
        return False
    row = {
        "schema": "janus.universal_beetle.candidate.v1",
        "candidate_id": iid,
        "discovered_at": now(),
        "direction_id": direction["id"],
        "direction_title": direction.get("title", direction["id"]),
        "score": round(score, 4),
        "keyword_hits": hits,
        "epistemic_status": "DISCOVERY_CANDIDATE__NOT_VERIFIED__NO_PROOF_AUTHORITY",
        **item,
    }
    append_jsonl(state.candidates_path, row)
    state.seen[iid] = {
        "first_seen_at": row["discovered_at"],
        "direction_id": direction["id"],
        "source": item["source"],
        "url": item["url"],
        "score": row["score"],
    }
    budget.note_add()
    state.receipt("CANDIDATE_ADDED", {"candidate_id": iid, "direction_id": direction["id"], "score": score, "url": item["url"]})
    return True


def _get(sess: requests.Session, budget: Budget, url: str, **kwargs: Any) -> requests.Response:
    if not budget.can_request():
        raise RuntimeError("request budget exhausted")
    safe_https(url)
    r = sess.get(url, timeout=DEFAULT_TIMEOUT, **kwargs)
    budget.note_request(len(r.content))
    r.raise_for_status()
    return r


def scout_arxiv(sess: requests.Session, state: State, budget: Budget, direction: dict[str, Any], source_cfg: dict[str, Any]) -> None:
    terms = source_cfg.get("query") or " OR ".join(f'all:"{k}"' for k in direction.get("keywords", [])[:6])
    max_results = int(source_cfg.get("max_results", 12))
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"search_query": terms, "start": 0, "max_results": max_results, "sortBy": "submittedDate", "sortOrder": "descending"})
    r = _get(sess, budget, url)
    root = ET.fromstring(r.content)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for e in root.findall("a:entry", ns):
        title = norm_text(e.findtext("a:title", default="", namespaces=ns))
        summary = norm_text(e.findtext("a:summary", default="", namespaces=ns))
        link = e.findtext("a:id", default="", namespaces=ns)
        if not link:
            continue
        tags = [c.attrib.get("term", "") for c in e.findall("a:category", ns)]
        record_candidate(state, budget, direction, {"source": "arxiv", "url": link.replace("http://", "https://"), "title": title, "summary": summary[:4000], "tags": tags, "published": e.findtext("a:published", default=None, namespaces=ns), "updated": e.findtext("a:updated", default=None, namespaces=ns)})


def scout_zenodo(sess: requests.Session, state: State, budget: Budget, direction: dict[str, Any], source_cfg: dict[str, Any]) -> None:
    query = source_cfg.get("query") or " ".join(direction.get("keywords", [])[:5])
    size = int(source_cfg.get("max_results", 12))
    url = "https://zenodo.org/api/records?" + urllib.parse.urlencode({"q": query, "size": size, "sort": "mostrecent"})
    r = _get(sess, budget, url)
    for rec in r.json().get("hits", {}).get("hits", []):
        meta = rec.get("metadata", {})
        rid = rec.get("id")
        if not rid:
            continue
        title = norm_text(meta.get("title", ""))
        desc = re.sub(r"<[^>]+>", " ", meta.get("description", "") or "")
        record_candidate(state, budget, direction, {"source": "zenodo", "url": f"https://zenodo.org/records/{rid}", "title": title, "summary": norm_text(desc)[:4000], "tags": list(meta.get("keywords", []) or []), "published": meta.get("publication_date"), "record_id": rid, "files": [{"key": f.get("key"), "size": f.get("size"), "checksum": f.get("checksum")} for f in rec.get("files", [])[:20]]})


def scout_github(sess: requests.Session, state: State, budget: Budget, direction: dict[str, Any], source_cfg: dict[str, Any]) -> None:
    query = source_cfg.get("query") or " ".join(direction.get("keywords", [])[:4])
    per_page = min(20, int(source_cfg.get("max_results", 12)))
    url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode({"q": query, "sort": "updated", "order": "desc", "per_page": per_page})
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = _get(sess, budget, url, headers=headers)
    for repo in r.json().get("items", []):
        record_candidate(state, budget, direction, {"source": "github_repository_search", "url": repo.get("html_url"), "title": repo.get("full_name", ""), "summary": norm_text(repo.get("description") or "")[:4000], "tags": repo.get("topics", []) or [], "updated": repo.get("updated_at"), "stars": repo.get("stargazers_count"), "language": repo.get("language")})


def scout_feed(sess: requests.Session, state: State, budget: Budget, direction: dict[str, Any], source_cfg: dict[str, Any]) -> None:
    url = safe_https(source_cfg["url"])
    r = _get(sess, budget, url)
    root = ET.fromstring(r.content)
    if root.tag.endswith("feed"):
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for e in root.findall("a:entry", ns)[: int(source_cfg.get("max_results", 20))]:
            title = norm_text(e.findtext("a:title", default="", namespaces=ns))
            summary = norm_text(e.findtext("a:summary", default="", namespaces=ns) or e.findtext("a:content", default="", namespaces=ns))
            href = ""
            for link in e.findall("a:link", ns):
                if link.attrib.get("rel", "alternate") in {"alternate", ""} and link.attrib.get("href"):
                    href = link.attrib["href"]
                    break
            if href.startswith("http://"):
                href = "https://" + href[len("http://"):]
            if href:
                record_candidate(state, budget, direction, {"source": "feed", "url": href, "title": title, "summary": summary[:4000], "tags": []})
    else:
        for e in root.findall(".//item")[: int(source_cfg.get("max_results", 20))]:
            title = norm_text(e.findtext("title", default=""))
            summary = norm_text(re.sub(r"<[^>]+>", " ", e.findtext("description", default="") or ""))
            link = norm_text(e.findtext("link", default=""))
            if link.startswith("http://"):
                link = "https://" + link[len("http://"):]
            if link:
                record_candidate(state, budget, direction, {"source": "feed", "url": link, "title": title, "summary": summary[:4000], "tags": []})


SCOUTERS = {"arxiv": scout_arxiv, "zenodo": scout_zenodo, "github": scout_github, "feed": scout_feed}


def run_scout(config: dict[str, Any], state: State, only_direction: str | None) -> dict[str, Any]:
    g = config.get("global_budget", {})
    budget = Budget(max_requests=int(g.get("max_requests_per_run", 24)), max_new_items=int(g.get("max_new_candidates_per_run", 40)), max_metadata_bytes=int(g.get("max_metadata_bytes_per_run", 4_000_000)))
    sess = session()
    errors: list[dict[str, str]] = []
    started = now()
    for d in config.get("directions", []):
        if not d.get("enabled", True) or (only_direction and d.get("id") != only_direction):
            continue
        for src in d.get("sources", []):
            if not src.get("enabled", True):
                continue
            fn = SCOUTERS.get(src.get("kind"))
            if not fn:
                errors.append({"direction": d.get("id", "?"), "source": str(src.get("kind")), "error": "unsupported source kind"})
                continue
            if not budget.can_request() or not budget.can_add():
                break
            try:
                fn(sess, state, budget, d, src)
            except Exception as exc:
                err = {"direction": d.get("id", "?"), "source": str(src.get("kind")), "error": f"{type(exc).__name__}: {exc}"}
                errors.append(err)
                state.receipt("SCOUT_SOURCE_ERROR", err)
    summary = {"started_at": started, "finished_at": now(), "requests": budget.requests, "metadata_bytes": budget.metadata_bytes, "new_candidates": budget.new_items, "errors": errors}
    state.receipt("SCOUT_RUN_COMPLETE", summary)
    state.save()
    return summary


def run_grazers(config: dict[str, Any], state: State, repo_root: pathlib.Path, only_task: str | None) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for task in config.get("grazer_tasks", []):
        if not task.get("enabled", True):
            continue
        tid = task.get("id")
        if only_task and tid != only_task:
            continue
        kind = task.get("kind")
        if kind == "uwa_hdf5_channel":
            src = safe_https(task["url"])
            out_dir = state.root / "grazers" / tid
            cmd = [sys.executable, str(repo_root / "tools" / "ocean_beetle.py"), "uwa-channel", src, "--bite", str(int(task.get("bite", 64))), "--max-bites", str(int(task.get("max_bites_per_run", 1))), "--include-tracking", "--block-size", str(int(task.get("block_size", 1_048_576))), "--max-cache-blocks", str(int(task.get("max_cache_blocks", 8))), "--out-dir", str(out_dir)]
            try:
                p = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, timeout=int(task.get("timeout_seconds", 900)))
                payload = {"task_id": tid, "kind": kind, "returncode": p.returncode, "stdout_tail": p.stdout[-5000:], "stderr_tail": p.stderr[-3000:]}
                state.receipt("GRAZER_RUN", payload)
                results.append(payload)
            except Exception as exc:
                payload = {"task_id": tid, "kind": kind, "error": f"{type(exc).__name__}: {exc}"}
                state.receipt("GRAZER_ERROR", payload)
                results.append(payload)
        elif kind == "http_range_text":
            url = safe_https(task["url"])
            cursor_key = f"grazer:{tid}:byte_offset"
            start = int(state.cursors.get(cursor_key, 0))
            bite_bytes = int(task.get("bite_bytes", 262_144))
            end = start + bite_bytes - 1
            try:
                r = requests.get(url, headers={"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"}, timeout=DEFAULT_TIMEOUT)
                if r.status_code not in (200, 206):
                    r.raise_for_status()
                if r.status_code == 200 and start > 0:
                    raise RuntimeError("server ignored Range on a resumed task")
                body = r.content
                if r.status_code == 200 and len(body) > bite_bytes:
                    raise RuntimeError("server ignored bounded byte request; refusing oversized body")
                actual_end = start + len(body)
                digest = hashlib.sha256(body).hexdigest()
                chunk_dir = state.root / "grazers" / tid / "chunks"
                chunk_dir.mkdir(parents=True, exist_ok=True)
                (chunk_dir / f"{start:012d}-{actual_end:012d}.bin").write_bytes(body)
                state.cursors[cursor_key] = actual_end
                payload = {"task_id": tid, "kind": kind, "range": [start, actual_end], "sha256": digest, "bytes": len(body), "http_status": r.status_code}
                state.receipt("GRAZER_BITE", payload)
                results.append(payload)
            except Exception as exc:
                payload = {"task_id": tid, "kind": kind, "error": f"{type(exc).__name__}: {exc}"}
                state.receipt("GRAZER_ERROR", payload)
                results.append(payload)
        else:
            payload = {"task_id": tid, "kind": str(kind), "error": "unsupported grazer kind"}
            state.receipt("GRAZER_ERROR", payload)
            results.append(payload)
    state.save()
    return {"finished_at": now(), "tasks": results}


def main() -> int:
    ap = argparse.ArgumentParser(description="JANUS Universal Beetle")
    ap.add_argument("--config", default="data/beetle/directions.json")
    ap.add_argument("--state-dir", default="beetle-state")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--direction", default=None)
    ap.add_argument("--grazer-task", default=None)
    ap.add_argument("--mode", choices=["scout", "graze", "both"], default="both")
    args = ap.parse_args()

    repo_root = pathlib.Path(args.repo_root).resolve()
    config_path = pathlib.Path(args.config)
    if not config_path.is_absolute():
        config_path = repo_root / config_path
    state_dir = pathlib.Path(args.state_dir)
    if not state_dir.is_absolute():
        state_dir = repo_root / state_dir

    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema") != "janus.universal_beetle.directions.v1":
        raise SystemExit("Unsupported or missing config schema")
    state = State(state_dir)
    state.receipt("RUN_START", {"mode": args.mode, "direction": args.direction, "grazer_task": args.grazer_task, "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest()})

    out: dict[str, Any] = {"tool": "JANUS UNIVERSAL BEETLE", "version": VERSION, "started_at": now(), "mode": args.mode}
    if args.mode in {"scout", "both"}:
        out["scout"] = run_scout(config, state, args.direction)
    if args.mode in {"graze", "both"}:
        out["graze"] = run_grazers(config, state, repo_root, args.grazer_task)
    out["finished_at"] = now()
    out["receipt_head"] = state.prev_receipt
    atomic_json(state.latest_path, out)
    state.receipt("RUN_COMPLETE", {"finished_at": out["finished_at"], "receipt_head_before_complete": out["receipt_head"]})
    state.save()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
