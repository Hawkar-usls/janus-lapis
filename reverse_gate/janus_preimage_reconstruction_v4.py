#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JANUS-LAPIS v0.3.3 — Provenance-Aware Structured Preimage Reconstruction.

Adds generic extraction of explicit source provenance embedded in allowed context
strings. Candidate plaintext remains hidden; every extracted hypothesis must hash
exactly to the target.
"""
from __future__ import annotations

import argparse, csv, json, re, sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Iterator, Sequence, Tuple

import janus_preimage_reconstruction as core
import janus_preimage_reconstruction_v2 as v2
import janus_preimage_reconstruction_v3 as v3

VERSION="0.3.3-provenance-aware"

MARKER_PATTERNS=[
    re.compile(r"(?i)calculated\s+from\s+(?:utf-?8\s+)?string\s*:\s*(.+)$"),
    re.compile(r"(?i)(?:source|original|input|identifier|text|payload)\s*(?:string|text)?\s*[:=]\s*(.+)$"),
    re.compile(r"(?i)sha-?256\s*\([^)]*\)\s*(?:of|from)?\s*[:=]\s*(.+)$"),
]
QUOTED=[re.compile(r'"([^"\n]{1,10000})"'),re.compile(r"'([^'\n]{1,10000})'"),re.compile(r"`([^`\n]{1,10000})`")]


def provenance_candidates(pair:core.Pair)->Iterator[str]:
    seen=set()
    for path,value in pair.context:
        if not isinstance(value,str) or not value or len(value)>20000:continue
        raw=value.strip()
        candidates=[raw]
        # Whole lines and paragraphs are legitimate source hypotheses.
        candidates.extend(x.strip() for x in raw.splitlines() if x.strip())
        for pat in MARKER_PATTERNS:
            m=pat.search(raw)
            if m:candidates.append(m.group(1).strip())
        for pat in QUOTED:
            candidates.extend(m.group(1) for m in pat.finditer(raw))
        # Generic final field after colon/equal, but only for descriptive provenance-like strings.
        low=raw.lower()
        if any(k in low for k in ("calculated","source","original","identifier","hash","utf-8","utf8")):
            for sep in (": "," = "," -> "):
                if sep in raw:candidates.append(raw.rsplit(sep,1)[-1].strip())
        for c in candidates:
            # Strip prose wrappers, preserving actual punctuation inside payload.
            c=c.strip().strip('"').strip("'").strip('`').strip()
            if c and c not in seen:
                seen.add(c);yield c


def recover_pair(pair:core.Pair,all_pairs:Sequence[core.Pair],budget:int)->core.Result:
    tested=0
    # Explicit provenance is the highest-information source and costs almost no ATP.
    for candidate in provenance_candidates(pair):
        tested+=1
        if core.exact_witness(pair,candidate):
            return core.Result(0,pair.file,pair.hash_path,pair.source_path,pair.source_key,pair.encoding,
                               pair.target_sha256,True,"explicit_provenance_extraction",candidate,pair.plaintext,tested)
        if tested>=budget:break
    # Then use the existing prioritized structural engine.
    fallback=v3.recover_pair(pair,all_pairs,max(1,budget-tested))
    fallback.candidates_tested += tested
    return fallback


def run(meta_root:Path,outdir:Path,budget:int):
    outdir.mkdir(parents=True,exist_ok=True);pairs=core.discover_pairs(meta_root);uniq=[];seen=set()
    for p in sorted(pairs,key=lambda x:(len(x.plaintext),x.target_sha256,x.file)):
        k=(p.target_sha256,p.plaintext,p.encoding)
        if k in seen:continue
        seen.add(k);uniq.append(p)
    results=[];con=sqlite3.connect(outdir/"janus.db")
    con.execute("CREATE TABLE IF NOT EXISTS truths(target_sha256 TEXT PRIMARY KEY,source_key TEXT,encoding TEXT,method TEXT,plaintext TEXT,file TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS graveyard(target_sha256 TEXT,candidates_tested INTEGER,source_key TEXT,file TEXT)")
    for i,p in enumerate(uniq,1):
        r=recover_pair(p,uniq,budget);r.index=i;results.append(r)
        if r.recovered:con.execute("INSERT OR REPLACE INTO truths VALUES(?,?,?,?,?,?)",(r.target_sha256,r.source_key,r.encoding,r.method,r.recovered_plaintext,r.file))
        else:con.execute("INSERT INTO graveyard VALUES(?,?,?,?)",(r.target_sha256,r.candidates_tested,r.source_key,r.file))
    con.commit();con.close()
    with (outdir/"results.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(asdict(results[0]).keys()));w.writeheader();[w.writerow(asdict(r)) for r in results]
    rec=[r for r in results if r.recovered];by={}
    for r in rec:by[r.method]=by.get(r.method,0)+1
    unique_plaintexts=len({r.recovered_plaintext for r in rec})
    summary={"experiment":"JANUS Provenance-Aware Structured Preimage","version":VERSION,
             "verified_real_hash_plaintext_pairs":len(results),"exact_hash_challenges_recovered":len(rec),
             "unique_plaintexts_recovered":unique_plaintexts,"recovery_rate":len(rec)/len(results) if results else 0.0,
             "by_method":by,"admission_rule":"exact SHA256(candidate bytes)==target",
             "boundary":"Explicit provenance and structured side information are allowed; not SHA-only inversion."}
    (outdir/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),"utf-8")
    lines=["# JANUS-LAPIS v0.3.3 — Provenance-Aware Structured Preimage","",f"Verified real challenges: **{len(results)}**",f"Exact hash challenges recovered: **{len(rec)}/{len(results)}**",f"Unique plaintexts recovered: **{unique_plaintexts}**","","## Exact witnesses",""]
    for r in rec:
        lines += [f"### {r.index:03d} — {r.method}","",f"- File: `{r.file}`",f"- SHA: `{r.target_sha256}`",f"- Source key: `{r.source_key}`","","```text",r.recovered_plaintext,"```",""]
    (outdir/"REPORT.md").write_text("\n".join(lines),"utf-8")
    return summary


def selftest(outdir:Path):
    text="ERA — Ameno | Era I | 1996";target=core.sha256_bytes(text.encode())
    p=core.Pair("x.json","h","sha",target,"song_identifier","song_identifier",text,"utf8",[("hash_policy","Calculated from UTF-8 string: ERA — Ameno | Era I | 1996")])
    r=recover_pair(p,[p],1000);assert r.recovered and r.recovered_plaintext==text and r.method=="explicit_provenance_extraction"
    outdir.mkdir(parents=True,exist_ok=True);(outdir/"selftest.json").write_text(json.dumps(asdict(r),ensure_ascii=False,indent=2),"utf-8");print(json.dumps({"selftest":"PASS","plaintext":text},ensure_ascii=False))


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--meta-root",type=Path);ap.add_argument("--outdir",type=Path,default=Path("reverse_gate_runs/preimage_v4"));ap.add_argument("--budget",type=int,default=180000);ap.add_argument("--selftest",action="store_true");a=ap.parse_args()
    if a.selftest:selftest(a.outdir);return
    if not a.meta_root:ap.error("--meta-root required")
    print(json.dumps(run(a.meta_root,a.outdir,a.budget),ensure_ascii=False,indent=2))

if __name__=="__main__":main()
