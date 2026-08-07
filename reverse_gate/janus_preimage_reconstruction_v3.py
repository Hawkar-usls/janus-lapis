#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JANUS-LAPIS v0.3.2 — Prioritized Structured Preimage Reconstruction."""
from __future__ import annotations

import argparse, csv, json, sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

import janus_preimage_reconstruction as core
import janus_preimage_reconstruction_v2 as v2

VERSION="0.3.2-prioritized-structure"


def recover_pair(pair: core.Pair, all_pairs: Sequence[core.Pair], budget: int) -> core.Result:
    tested=0
    # 1) Strong structure FIRST. This is the main change from v0.3.1.
    schema_budget=min(30000,budget)
    for method,candidate in core.unique_candidates(v2.schema_candidates(pair),schema_budget):
        tested += 1
        if core.exact_witness(pair,candidate):
            return core.Result(0,pair.file,pair.hash_path,pair.source_path,pair.source_key,
                               pair.encoding,pair.target_sha256,True,method,candidate,
                               pair.plaintext,tested)
    # 2) General learned/template search only after structural hypotheses fail.
    fallback=core.recover_pair(pair,all_pairs,max(1,budget-tested))
    fallback.candidates_tested += tested
    return fallback


def run(meta_root:Path,outdir:Path,budget:int):
    outdir.mkdir(parents=True,exist_ok=True)
    pairs=core.discover_pairs(meta_root); uniq=[]; seen=set()
    for p in sorted(pairs,key=lambda x:(len(x.plaintext),x.target_sha256,x.file)):
        k=(p.target_sha256,p.plaintext,p.encoding)
        if k in seen: continue
        seen.add(k); uniq.append(p)
    con=sqlite3.connect(outdir/"janus.db")
    con.execute("CREATE TABLE IF NOT EXISTS truths(target_sha256 TEXT PRIMARY KEY,source_key TEXT,encoding TEXT,method TEXT,plaintext TEXT,file TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS graveyard(target_sha256 TEXT,candidates_tested INTEGER,source_key TEXT,file TEXT)")
    results=[]
    for i,p in enumerate(uniq,1):
        r=recover_pair(p,uniq,budget); r.index=i; results.append(r)
        if r.recovered: con.execute("INSERT OR REPLACE INTO truths VALUES(?,?,?,?,?,?)",(r.target_sha256,r.source_key,r.encoding,r.method,r.recovered_plaintext,r.file))
        else: con.execute("INSERT INTO graveyard VALUES(?,?,?,?)",(r.target_sha256,r.candidates_tested,r.source_key,r.file))
    con.commit(); con.close()
    with (outdir/"results.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(asdict(results[0]).keys())); w.writeheader(); [w.writerow(asdict(r)) for r in results]
    rec=[r for r in results if r.recovered]
    by={}
    for r in rec: by[r.method]=by.get(r.method,0)+1
    redundancy=[r for r in rec if r.method=="registry_serialization_genealogy"]
    strong=[r for r in rec if r.method!="registry_serialization_genealogy"]
    summary={"experiment":"JANUS prioritized structured preimage","version":VERSION,
             "verified_real_hash_plaintext_pairs":len(results),"exact_preimages_recovered":len(rec),
             "strong_structural_recoveries":len(strong),"redundancy_assisted_recoveries":len(redundancy),
             "exact_recovery_rate":len(rec)/len(results) if results else 0.0,"by_method":by,
             "admission_rule":"exact SHA256(candidate)==target only",
             "boundary":"Constrained reconstruction from registry side information; not general SHA-256 inversion."}
    (outdir/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),"utf-8")
    lines=["# JANUS-LAPIS v0.3.2 — Prioritized Structured Preimage Reconstruction","",
           f"Verified challenges: **{len(results)}**",f"Exact recovered: **{len(rec)}/{len(results)}**",
           f"Strong structural: **{len(strong)}**",f"Redundancy-assisted: **{len(redundancy)}**","","## Exact witnesses",""]
    for r in rec:
        label="REDUNDANCY-ASSISTED" if r.method=="registry_serialization_genealogy" else "STRUCTURAL"
        lines += [f"### {r.index:03d} — {r.method} [{label}]","",f"- File: `{r.file}`",f"- SHA: `{r.target_sha256}`",f"- Hash field: `{r.hash_path}`","","```text",r.recovered_plaintext,"```",""]
    (outdir/"REPORT.md").write_text("\n".join(lines),"utf-8")
    return summary


def selftest(outdir:Path):
    text="ERA — Ameno | Era I | 1996"
    p=core.Pair("x.json","sha256_song_identifier_utf8","sha256_song_identifier_utf8",core.sha256_bytes(text.encode()),"identifier","song_identifier",text,"utf8",[("artist","ERA"),("track","Ameno"),("album","Era I"),("year","1996")])
    r=recover_pair(p,[p],10000)
    assert r.recovered and r.method=="schema_song_identifier" and r.recovered_plaintext==text
    outdir.mkdir(parents=True,exist_ok=True); (outdir/"selftest_v3.json").write_text(json.dumps(asdict(r),ensure_ascii=False,indent=2),"utf-8")
    print(json.dumps({"selftest":"PASS","method":r.method,"plaintext":r.recovered_plaintext},ensure_ascii=False))


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--meta-root",type=Path); ap.add_argument("--outdir",type=Path,default=Path("reverse_gate_runs/preimage_v3")); ap.add_argument("--budget",type=int,default=180000); ap.add_argument("--selftest",action="store_true"); a=ap.parse_args()
    if a.selftest: selftest(a.outdir); return
    if not a.meta_root: ap.error("--meta-root required")
    print(json.dumps(run(a.meta_root,a.outdir,a.budget),ensure_ascii=False,indent=2))

if __name__=="__main__": main()
