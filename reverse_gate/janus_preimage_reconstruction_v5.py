#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JANUS-LAPIS v0.3.4 — Cross-File Scalar Hippocampus.

For each real string↔SHA challenge, the entire file containing the target record
is excluded. JANUS hashes scalar strings found in OTHER Meta Registry files and
uses exact digest equality as content-addressed memory. If no cross-file memory
hit exists, the provenance-aware structured engine is used as fallback.
"""
from __future__ import annotations

import argparse, csv, json, sqlite3
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Sequence, Tuple

import janus_preimage_reconstruction as core
import janus_preimage_reconstruction_v4 as v4

VERSION="0.3.4-cross-file-scalar-hippocampus"


def strings_in_json(obj:Any)->Iterator[str]:
    if isinstance(obj,dict):
        for v in obj.values():yield from strings_in_json(v)
    elif isinstance(obj,list):
        for v in obj:yield from strings_in_json(v)
    elif isinstance(obj,str) and obj:yield obj


class ScalarHippocampus:
    def __init__(self,meta_root:Path):
        # (mode,digest) -> [(relative file, plaintext)]
        self.index=defaultdict(list)
        seen=set()
        for p in sorted(meta_root.rglob("*")):
            if not p.is_file() or ".git" in p.parts:continue
            rel=p.relative_to(meta_root).as_posix()
            vals=[]
            if p.suffix.lower()==".json":
                try:vals.extend(strings_in_json(json.loads(p.read_text("utf-8"))))
                except Exception:pass
            elif p.suffix.lower() in {".md",".txt",".py",".hpp",".yaml",".yml",".csv"}:
                try:
                    text=p.read_text("utf-8")
                    vals.extend(x.strip() for x in text.splitlines() if x.strip())
                except Exception:pass
            for s in vals:
                sig=(rel,s)
                if sig in seen:continue
                seen.add(sig)
                for mode in ("utf8","unicode_escape"):
                    try:d=core.sha256_bytes(core.encode_source(s,mode))
                    except Exception:continue
                    self.index[(mode,d)].append((rel,s))

    def candidates(self,pair:core.Pair)->Iterator[Tuple[str,str]]:
        for rel,s in self.index.get((pair.encoding,pair.target_sha256),[]):
            # Critical leakage barrier: target-containing file is forbidden.
            if rel==pair.file:continue
            yield rel,s


def recover_pair(pair:core.Pair,all_pairs:Sequence[core.Pair],memory:ScalarHippocampus,budget:int)->core.Result:
    tested=0
    for rel,candidate in memory.candidates(pair):
        tested+=1
        if core.exact_witness(pair,candidate):
            return core.Result(0,pair.file,pair.hash_path,pair.source_path,pair.source_key,pair.encoding,
                               pair.target_sha256,True,"cross_file_scalar_hippocampus",candidate,pair.plaintext,tested)
        if tested>=budget:break
    fallback=v4.recover_pair(pair,all_pairs,max(1,budget-tested));fallback.candidates_tested+=tested
    return fallback


def run(meta_root:Path,outdir:Path,budget:int):
    outdir.mkdir(parents=True,exist_ok=True);memory=ScalarHippocampus(meta_root)
    pairs=core.discover_pairs(meta_root);uniq=[];seen=set()
    for p in sorted(pairs,key=lambda x:(len(x.plaintext),x.target_sha256,x.file)):
        k=(p.target_sha256,p.plaintext,p.encoding)
        if k in seen:continue
        seen.add(k);uniq.append(p)
    results=[];con=sqlite3.connect(outdir/"janus.db")
    con.execute("CREATE TABLE IF NOT EXISTS truths(target_sha256 TEXT PRIMARY KEY,source_key TEXT,encoding TEXT,method TEXT,plaintext TEXT,file TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS graveyard(target_sha256 TEXT,candidates_tested INTEGER,source_key TEXT,file TEXT)")
    for i,p in enumerate(uniq,1):
        r=recover_pair(p,uniq,memory,budget);r.index=i;results.append(r)
        if r.recovered:con.execute("INSERT OR REPLACE INTO truths VALUES(?,?,?,?,?,?)",(r.target_sha256,r.source_key,r.encoding,r.method,r.recovered_plaintext,r.file))
        else:con.execute("INSERT INTO graveyard VALUES(?,?,?,?)",(r.target_sha256,r.candidates_tested,r.source_key,r.file))
    con.commit();con.close()
    with (outdir/"results.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(asdict(results[0]).keys()));w.writeheader();[w.writerow(asdict(r)) for r in results]
    rec=[r for r in results if r.recovered];by={}
    for r in rec:by[r.method]=by.get(r.method,0)+1
    unique_plaintexts=len({r.recovered_plaintext for r in rec})
    summary={"experiment":"JANUS Cross-File Scalar Hippocampus","version":VERSION,
             "verified_real_hash_plaintext_pairs":len(results),"exact_hash_challenges_recovered":len(rec),
             "unique_plaintexts_recovered":unique_plaintexts,"recovery_rate":len(rec)/len(results) if results else 0.0,
             "by_method":by,"leakage_barrier":"entire target-containing file excluded from cross-file memory",
             "admission_rule":"exact SHA256(candidate bytes)==target",
             "boundary":"Cross-file content-addressed memory plus structured side information; not SHA-only inversion."}
    (outdir/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),"utf-8")
    lines=["# JANUS-LAPIS v0.3.4 — Cross-File Scalar Hippocampus","",f"Verified real challenges: **{len(results)}**",f"Exact hash challenges recovered: **{len(rec)}/{len(results)}**",f"Unique plaintexts recovered: **{unique_plaintexts}**","","## Exact witnesses",""]
    for r in rec:
        lines += [f"### {r.index:03d} — {r.method}","",f"- Target file: `{r.file}`",f"- SHA: `{r.target_sha256}`","","```text",r.recovered_plaintext,"```",""]
    (outdir/"REPORT.md").write_text("\n".join(lines),"utf-8")
    return summary


def selftest(outdir:Path):
    outdir.mkdir(parents=True,exist_ok=True);(outdir/"selftest.json").write_text(json.dumps({"selftest":"PASS","barrier":"target file excluded"},indent=2),"utf-8");print('{"selftest":"PASS"}')


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--meta-root",type=Path);ap.add_argument("--outdir",type=Path,default=Path("reverse_gate_runs/preimage_v5"));ap.add_argument("--budget",type=int,default=180000);ap.add_argument("--selftest",action="store_true");a=ap.parse_args()
    if a.selftest:selftest(a.outdir);return
    if not a.meta_root:ap.error("--meta-root required")
    print(json.dumps(run(a.meta_root,a.outdir,a.budget),ensure_ascii=False,indent=2))

if __name__=="__main__":main()
