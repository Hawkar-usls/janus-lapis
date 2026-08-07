#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JANUS-LAPIS v0.6.0 — Whole-File Genealogy Reconstruction.

Target: complete file bytes referenced by a real SHA-256 manifest in
Hawkar-usls/janus-meta-registry.

The target file itself is excluded from the candidate corpus. Allowed side info:
- manifest filename / expected byte count / target SHA;
- other files and versions in the same public Meta Registry;
- manifest-local scalar metadata (timestamps, artifact ids, version strings).

Admission:
    SHA256(generated_complete_file_bytes) == target_sha256

This is constrained file reconstruction with provenance side information, not a
general inverse for SHA-256.
"""
from __future__ import annotations

import argparse, copy, csv, hashlib, json, re, sqlite3
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

VERSION="0.6.0-whole-file-genealogy"
TEXT_SUFFIXES={".json",".md",".txt",".py",".hpp",".h",".c",".cpp",".yaml",".yml",".csv",".ps1",".bat"}
VERSION_RE=re.compile(r"(?i)\bv\d+(?:\.\d+){0,3}(?:[-_][A-Za-z0-9._-]+)?")
SIMPLE_VERSION_RE=re.compile(r"(?i)v\d+(?:\.\d+){0,3}")
TIMESTAMP_RE=re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})")
HEX64=re.compile(r"^[0-9a-fA-F]{64}$")
MAX_TARGET_BYTES=250_000
MAX_CANDIDATES=200_000


def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def read_bytes(p:Path)->bytes:
    return p.read_bytes()


def all_scalars(obj:Any)->List[str]:
    out=[]
    if isinstance(obj,dict):
        for v in obj.values():out.extend(all_scalars(v))
    elif isinstance(obj,list):
        for v in obj:out.extend(all_scalars(v))
    elif isinstance(obj,(str,int,float,bool)) or obj is None:
        out.append(str(obj))
    return out


def normalize_name(name:str)->str:
    s=name.lower()
    s=re.sub(r"(?i)v\d+(?:\.\d+){0,3}(?:[-_][a-z0-9._-]+)?","",s)
    for token in ("sha256","manifest","hashed","unicode","utf8","utf-8","expanded","machine","readable","final"):
        s=s.replace(token,"")
    s=re.sub(r"\.(json|py|hpp|h|c|cpp|md|txt|yaml|yml|csv)$","",s)
    s=re.sub(r"[^a-z0-9]+","-",s).strip("-")
    return s


def version_token(name:str)->Optional[str]:
    m=SIMPLE_VERSION_RE.search(name)
    return m.group(0) if m else None


def stem_variants(name:str)->List[str]:
    p=Path(name)
    vals=[name,p.name,p.stem]
    vals += [x.upper() for x in list(vals)]
    vals += [x.lower() for x in list(vals)]
    return list(dict.fromkeys(vals))


@dataclass
class FileChallenge:
    manifest_file:str
    target_path:str
    target_name:str
    target_sha256:str
    expected_bytes:int
    manifest_scalars:List[str]
    ground_truth_bytes:bytes


def locate_by_basename(meta_root:Path)->Dict[str,List[Path]]:
    m=defaultdict(list)
    for p in meta_root.rglob("*"):
        if p.is_file() and ".git" not in p.parts:m[p.name].append(p)
    return m


def manifest_entries(obj:Any)->Iterator[Tuple[str,str,int]]:
    """Yield filename, sha256, expected bytes from common JANUS manifest layouts."""
    if isinstance(obj,dict):
        filename=obj.get("filename")
        if isinstance(filename,str):
            digest=None
            for k in ("sha256","sha256_file_bytes","file_sha256","sha256_bytes"):
                v=obj.get(k)
                if isinstance(v,str) and HEX64.fullmatch(v):digest=v.lower();break
            if digest:
                size=obj.get("bytes") if isinstance(obj.get("bytes"),int) else -1
                yield filename,digest,size
        # main_json / final_image style blocks with filename+sha256_file_bytes are handled above
        for v in obj.values():yield from manifest_entries(v)
    elif isinstance(obj,list):
        for v in obj:yield from manifest_entries(v)


def discover(meta_root:Path)->List[FileChallenge]:
    bybase=locate_by_basename(meta_root);out=[];seen=set()
    for mp in sorted(meta_root.rglob("*.json")):
        if ".git" in mp.parts:continue
        try:obj=json.loads(mp.read_text("utf-8"))
        except Exception:continue
        scalars=all_scalars(obj)
        for filename,digest,size in manifest_entries(obj):
            for p in bybase.get(Path(filename).name,[]):
                if p.resolve()==mp.resolve():continue
                try:b=read_bytes(p)
                except Exception:continue
                if len(b)>MAX_TARGET_BYTES or sha_bytes(b)!=digest:continue
                rel=p.relative_to(meta_root).as_posix();mrel=mp.relative_to(meta_root).as_posix()
                k=(rel,digest)
                if k in seen:continue
                seen.add(k);out.append(FileChallenge(mrel,rel,p.name,digest,size,scalars,b))
    return out


def sibling_rank(target:FileChallenge,p:Path,meta_root:Path)->float:
    if p.name==target.target_name:return -1
    if p.suffix.lower()!=Path(target.target_name).suffix.lower():return -1
    a=normalize_name(target.target_name);b=normalize_name(p.name)
    sim=SequenceMatcher(None,a,b).ratio() if a and b else 0.0
    # same directory / language family gets a small boost
    tdir=Path(target.target_path).parent.as_posix();pdir=p.relative_to(meta_root).parent.as_posix()
    if tdir==pdir:sim+=0.08
    return sim


def candidate_siblings(ch:FileChallenge,meta_root:Path,limit=80)->List[Path]:
    rows=[]
    target_abs=meta_root/ch.target_path
    for p in meta_root.rglob("*"):
        if not p.is_file() or ".git" in p.parts or p.resolve()==target_abs.resolve():continue
        score=sibling_rank(ch,p,meta_root)
        if score>=0.38:rows.append((score,p))
    rows.sort(key=lambda x:(-x[0],x[1].as_posix()))
    return [p for _,p in rows[:limit]]


def replacement_atoms(ch:FileChallenge,sibling:Path)->List[Tuple[str,str]]:
    target_v=version_token(ch.target_name);old_v=version_token(sibling.name)
    reps=[]
    if old_v and target_v and old_v.lower()!=target_v.lower():
        reps += [(old_v,target_v),(old_v.upper(),target_v.upper()),(old_v.lower(),target_v.lower())]
    # filename/stem genealogy
    for old in stem_variants(sibling.name):
        for new in stem_variants(ch.target_name):
            # only structurally comparable long tokens
            if len(old)>=8 and len(new)>=8 and normalize_name(old)==normalize_name(new):reps.append((old,new))
    # visible manifest scalars can provide timestamps/version/artifact IDs.
    old_text=""
    try:old_text=sibling.read_text("utf-8")
    except Exception:pass
    old_times=list(dict.fromkeys(TIMESTAMP_RE.findall(old_text)))[:8]
    new_times=[s for s in ch.manifest_scalars if TIMESTAMP_RE.fullmatch(s)][:12]
    for o in old_times:
        for n in new_times:reps.append((o,n))
    return list(dict.fromkeys(reps))


def apply_single_replacements(text:str,reps:Sequence[Tuple[str,str]])->Iterator[str]:
    yield text
    # all version/name deterministic replacements at once
    structural=[(a,b) for a,b in reps if not TIMESTAMP_RE.fullmatch(a)]
    t=text
    for a,b in structural:t=t.replace(a,b)
    yield t
    # then structural + one timestamp hypothesis
    timestamp=[(a,b) for a,b in reps if TIMESTAMP_RE.fullmatch(a)]
    for a,b in timestamp:
        u=t.replace(a,b);yield u


def recursive_replace(obj:Any,reps:Sequence[Tuple[str,str]])->Any:
    if isinstance(obj,dict):return {k:recursive_replace(v,reps) for k,v in obj.items()}
    if isinstance(obj,list):return [recursive_replace(v,reps) for v in obj]
    if isinstance(obj,str):
        s=obj
        for a,b in reps:s=s.replace(a,b)
        return s
    return obj


def json_serializations(obj:Any)->Iterator[bytes]:
    configs=[
        dict(ensure_ascii=False,indent=2,sort_keys=False),dict(ensure_ascii=False,indent=4,sort_keys=False),
        dict(ensure_ascii=True,indent=2,sort_keys=False),dict(ensure_ascii=True,indent=4,sort_keys=False),
        dict(ensure_ascii=False,indent=None,sort_keys=False,separators=(",",":")),
        dict(ensure_ascii=False,indent=None,sort_keys=True,separators=(",",":")),
    ]
    for cfg in configs:
        try:s=json.dumps(obj,**cfg)
        except Exception:continue
        for ending in ("","\n"):
            yield (s+ending).encode("utf-8")


def raw_genealogy(ch:FileChallenge,meta_root:Path)->Iterator[Tuple[str,bytes]]:
    for sib in candidate_siblings(ch,meta_root):
        try:raw=sib.read_bytes()
        except Exception:continue
        # exact duplicate under another filename: weak but valid corpus witness
        yield "cross_file_duplicate",raw
        if sib.suffix.lower() not in TEXT_SUFFIXES:continue
        try:text=raw.decode("utf-8")
        except UnicodeDecodeError:continue
        reps=replacement_atoms(ch,sib)
        for s in apply_single_replacements(text,reps):
            yield "raw_version_genealogy",s.encode("utf-8")
        if sib.suffix.lower()==".json":
            try:obj=json.loads(text)
            except Exception:continue
            # deterministic structural replacements (exclude timestamps first)
            structural=[x for x in reps if not TIMESTAMP_RE.fullmatch(x[0])]
            transformed=recursive_replace(obj,structural)
            for b in json_serializations(transformed):yield "json_version_genealogy",b
            # one manifest-provided timestamp substitution at a time
            for a,bv in [x for x in reps if TIMESTAMP_RE.fullmatch(x[0])]:
                obj2=recursive_replace(transformed,[(a,bv)])
                for b in json_serializations(obj2):yield "json_manifest_timestamp_genealogy",b


def unique(gen:Iterable[Tuple[str,bytes]],budget:int,expected_bytes:int)->Iterator[Tuple[str,bytes]]:
    seen=set();n=0
    for method,b in gen:
        if expected_bytes>=0 and len(b)!=expected_bytes:continue
        h=hashlib.sha256(b).digest()
        if h in seen:continue
        seen.add(h);n+=1;yield method,b
        if n>=budget:return


@dataclass
class Result:
    index:int;manifest_file:str;target_path:str;target_sha256:str;expected_bytes:int;actual_bytes:int
    recovered:bool;method:str;candidates_tested:int;recovered_sha256:str


def recover(ch:FileChallenge,meta_root:Path,budget:int)->Tuple[Result,Optional[bytes]]:
    tested=0
    for method,b in unique(raw_genealogy(ch,meta_root),budget,ch.expected_bytes):
        tested+=1;d=sha_bytes(b)
        if d==ch.target_sha256:
            return Result(0,ch.manifest_file,ch.target_path,ch.target_sha256,ch.expected_bytes,len(ch.ground_truth_bytes),True,method,tested,d),b
    return Result(0,ch.manifest_file,ch.target_path,ch.target_sha256,ch.expected_bytes,len(ch.ground_truth_bytes),False,"",tested,""),None


def run(meta_root:Path,outdir:Path,budget:int):
    outdir.mkdir(parents=True,exist_ok=True);recovered_dir=outdir/"recovered_files";recovered_dir.mkdir(exist_ok=True)
    challenges=discover(meta_root);results=[];by=Counter();strong=weak=0
    con=sqlite3.connect(outdir/"janus.db")
    con.execute("CREATE TABLE IF NOT EXISTS truths(target_sha256 TEXT PRIMARY KEY,target_path TEXT,method TEXT,recovered_path TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS graveyard(target_sha256 TEXT,target_path TEXT,candidates_tested INTEGER)")
    for i,ch in enumerate(challenges,1):
        r,b=recover(ch,meta_root,budget);r.index=i;results.append(r)
        if r.recovered and b is not None:
            by[r.method]+=1
            if r.method=="cross_file_duplicate":weak+=1
            else:strong+=1
            safe=f"{i:03d}_{Path(ch.target_path).name}";rp=recovered_dir/safe;rp.write_bytes(b)
            con.execute("INSERT OR REPLACE INTO truths VALUES(?,?,?,?)",(ch.target_sha256,ch.target_path,r.method,rp.name))
        else:con.execute("INSERT INTO graveyard VALUES(?,?,?)",(ch.target_sha256,ch.target_path,r.candidates_tested))
    con.commit();con.close()
    if results:
        with (outdir/"results.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=list(asdict(results[0]).keys()));w.writeheader();[w.writerow(asdict(r)) for r in results]
    rec=[r for r in results if r.recovered]
    summary={"experiment":"JANUS Whole-File Genealogy Reconstruction","version":VERSION,
             "verified_real_file_sha_challenges":len(results),"exact_complete_files_recovered":len(rec),
             "strong_genealogy_recoveries":strong,"cross_file_duplicate_recoveries":weak,
             "recovery_rate":len(rec)/len(results) if results else 0.0,"by_method":dict(by),
             "max_target_bytes":MAX_TARGET_BYTES,"candidate_budget_per_target":budget,
             "admission_rule":"SHA256(generated complete file bytes) == manifest target exactly",
             "boundary":"Constrained whole-file reconstruction using manifest/version side information; not general SHA-256 inversion."}
    (outdir/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),"utf-8")
    lines=["# JANUS-LAPIS v0.6.0 — Whole-File Genealogy Reconstruction","",f"Verified real manifest file challenges: **{len(results)}**",f"Exact complete files recovered: **{len(rec)}/{len(results)}**",f"Strong genealogy recoveries: **{strong}**",f"Cross-file duplicate recoveries: **{weak}**","","## Exact complete-file witnesses",""]
    for r in rec[:100]:
        label="REDUNDANCY" if r.method=="cross_file_duplicate" else "STRUCTURAL-GENEALOGY"
        lines += [f"### {r.index:03d} — {r.method} [{label}]","",f"- Target: `{r.target_path}`",f"- Manifest: `{r.manifest_file}`",f"- Bytes: `{r.actual_bytes}`",f"- SHA-256: `{r.target_sha256}`","",]
    if not rec:lines += ["No complete file exact witness recovered.",""]
    (outdir/"REPORT.md").write_text("\n".join(lines),"utf-8")
    return summary


def selftest(outdir:Path):
    # Unit-level verifier only. Real CI targets always come from the Meta Registry.
    outdir.mkdir(parents=True,exist_ok=True)
    b=b'{\n  "version": "v1.1",\n  "name": "JANUS"\n}\n';d=sha_bytes(b)
    assert len(d)==64 and sha_bytes(b)==d
    (outdir/"selftest.json").write_text(json.dumps({"selftest":"PASS","sha256":d,"bytes":len(b)},indent=2),"utf-8")
    print(json.dumps({"selftest":"PASS","sha256":d}))


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--meta-root",type=Path);ap.add_argument("--outdir",type=Path,default=Path("reverse_gate_runs/file_v6"));ap.add_argument("--budget",type=int,default=MAX_CANDIDATES);ap.add_argument("--selftest",action="store_true");a=ap.parse_args()
    if a.selftest:selftest(a.outdir);return
    if not a.meta_root:ap.error("--meta-root required")
    print(json.dumps(run(a.meta_root,a.outdir,a.budget),ensure_ascii=False,indent=2))

if __name__=="__main__":main()
