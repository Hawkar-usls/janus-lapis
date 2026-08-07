#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JANUS-LAPIS v0.5.0 — Distributed Fragment Reassembly.

Tier: SCHEMA_KNOWN.
The target JSON object's key/type/list-length skeleton is considered allowed side
information; ALL target scalar values are hidden. Values may be sourced only from
OTHER Meta Registry files. The target file is excluded from the fragment corpus.

Success remains exact canonical SHA-256 equality. This is not SHA-only inversion.
"""
from __future__ import annotations

import argparse, copy, csv, hashlib, itertools, json, re, sqlite3
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Sequence, Tuple

import janus_object_reconstruction as v4

VERSION="0.5.0-distributed-fragment-reassembly"
MAX_CANDIDATES=120000


def scalar(v): return v is None or isinstance(v,(str,int,float,bool))

def typ(v):
    if v is None:return "null"
    if isinstance(v,bool):return "bool"
    if isinstance(v,int) and not isinstance(v,bool):return "int"
    if isinstance(v,float):return "float"
    if isinstance(v,str):return "str"
    return type(v).__name__


def skeleton(obj:Any)->Any:
    if isinstance(obj,dict): return {k:skeleton(v) for k,v in obj.items()}
    if isinstance(obj,list): return [skeleton(v) for v in obj]
    return {"__TYPE__":typ(obj)}


def flatten_values(obj:Any,prefix="")->List[Tuple[str,Any]]:
    out=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=f"{prefix}.{k}" if prefix else k
            if scalar(v): out.append((p,v))
            else: out.extend(flatten_values(v,p))
    elif isinstance(obj,list):
        for i,v in enumerate(obj):
            p=f"{prefix}[{i}]"
            if scalar(v): out.append((p,v))
            else: out.extend(flatten_values(v,p))
    return out


def suffixes(path:str)->List[str]:
    # Remove list indices and use 1..3 trailing semantic key components.
    clean=re.sub(r"\[\d+\]","",path)
    parts=[p for p in clean.split(".") if p]
    return [".".join(parts[-n:]) for n in range(1,min(3,len(parts))+1)]


def iter_subobjects(obj:Any,path="")->Iterator[Tuple[str,Any]]:
    if isinstance(obj,(dict,list)):
        yield path,obj
        if isinstance(obj,dict):
            for k,v in obj.items():
                if isinstance(v,(dict,list)):
                    yield from iter_subobjects(v,f"{path}.{k}" if path else k)
        else:
            for i,v in enumerate(obj):
                if isinstance(v,(dict,list)):
                    yield from iter_subobjects(v,f"{path}[{i}]")


class Corpus:
    def __init__(self,meta_root:Path):
        self.files:Dict[str,Any]={}
        self.scalar_index=defaultdict(list)   # (suffix,type)->[(file,value)]
        self.object_index=defaultdict(list)   # schema_signature -> [(file,path,obj)]
        self.dict_keyset_index=defaultdict(list)
        for p in sorted(meta_root.rglob("*.json")):
            if ".git" in p.parts: continue
            try: root=json.loads(p.read_text("utf-8"))
            except Exception: continue
            rel=p.relative_to(meta_root).as_posix(); self.files[rel]=root
            for path,val in flatten_values(root):
                for s in suffixes(path):
                    self.scalar_index[(s,typ(val))].append((rel,val))
            for path,obj in iter_subobjects(root):
                if v4.node_count(obj)>v4.MAX_OBJECT_NODES: continue
                sig=v4.schema_signature(obj)
                self.object_index[sig].append((rel,path,copy.deepcopy(obj)))
                if isinstance(obj,dict):
                    self.dict_keyset_index[tuple(sorted(obj.keys()))].append((rel,path,copy.deepcopy(obj)))

    def scalar_candidates(self,target_file:str,path:str,type_name:str,limit:int=24)->List[Any]:
        scored=[]; seen=[]
        sufs=suffixes(path)
        # longest semantic path suffix first
        for rank,s in enumerate(reversed(sufs)):
            for f,v in self.scalar_index.get((s,type_name),[]):
                if f==target_file or v in seen: continue
                seen.append(v); scored.append((rank,v))
                if len(scored)>=limit:return [x[1] for x in sorted(scored,key=lambda x:x[0])]
        return [x[1] for x in sorted(scored,key=lambda x:x[0])]


def same_object_elsewhere(ch:v4.ObjChallenge,corp:Corpus)->Iterator[Any]:
    sig=v4.schema_signature(ch.ground_truth)
    for f,p,obj in corp.object_index.get(sig,[]):
        if f!=ch.file: yield obj


def same_keyset_objects(ch:v4.ObjChallenge,corp:Corpus)->Iterator[Any]:
    if not isinstance(ch.ground_truth,dict): return
    ks=tuple(sorted(ch.ground_truth.keys()))
    for f,p,obj in corp.dict_keyset_index.get(ks,[]):
        if f!=ch.file: yield obj


def flat_schema_fill(ch:v4.ObjChallenge,corp:Corpus,limit:int=50000)->Iterator[Any]:
    if not isinstance(ch.ground_truth,dict):return
    if any(isinstance(v,(dict,list)) for v in ch.ground_truth.values()):return
    slots=[]; keys=[]
    for k,v in ch.ground_truth.items():
        c=corp.scalar_candidates(ch.file,k,typ(v),limit=18)
        if not c:return
        keys.append(k); slots.append(c)
    n=0
    for combo in itertools.product(*slots):
        yield {k:v for k,v in zip(keys,combo)}; n+=1
        if n>=limit:return


def sequence_list_reassembly(ch:v4.ObjChallenge,corp:Corpus,limit:int=90000)->Iterator[Any]:
    """Reassemble lists of homogeneous dict records using sequence/order fields.

    The target scalar values are never queried. We use only the schema skeleton,
    list length and fragments found in OTHER files.
    """
    gt=ch.ground_truth
    if not (isinstance(gt,list) and gt and all(isinstance(x,dict) for x in gt)):return
    sig=v4.schema_signature(gt[0])
    if any(v4.schema_signature(x)!=sig for x in gt):return
    peers=[(f,p,o) for f,p,o in corp.object_index.get(sig,[]) if f!=ch.file and isinstance(o,dict)]
    if not peers:return
    # If schema has sequence/order/index key, group peer records by that field.
    key=None
    for k in ("sequence","order","index","step","id"):
        if k in gt[0] and scalar(gt[0][k]): key=k; break
    if not key:return
    slots=[]
    for i in range(len(gt)):
        expected=i+1 if isinstance(gt[0].get(key),int) else None
        vals=[]
        for f,p,o in peers:
            if expected is not None and o.get(key)!=expected: continue
            marker=v4.canonical_bytes(o,False)
            if not any(v4.canonical_bytes(x,False)==marker for x in vals): vals.append(o)
            if len(vals)>=20: break
        if not vals:return
        slots.append(vals)
    n=0
    for combo in itertools.product(*slots):
        yield [copy.deepcopy(x) for x in combo];n+=1
        if n>=limit:return


def recursive_schema_fill(ch:v4.ObjChallenge,corp:Corpus,limit:int=60000)->Iterator[Any]:
    """Fill a known schema skeleton from cross-file values by semantic path."""
    positions=flatten_values(ch.ground_truth)
    slots=[]; paths=[]
    for p,v in positions:
        c=corp.scalar_candidates(ch.file,p,typ(v),limit=8)
        if not c:return
        paths.append(p);slots.append(c)
    # Avoid hopeless cartesian explosions.
    space=1
    for s in slots:
        space*=len(s)
        if space>limit*50:return
    n=0
    for combo in itertools.product(*slots):
        obj=v4.blank_from_schema(ch.ground_truth)
        for p,v in zip(paths,combo):v4.set_at(obj,p,copy.deepcopy(v))
        yield obj;n+=1
        if n>=limit:return


def unique(gens:Sequence[Tuple[str,Iterable[Any]]],budget:int):
    seen=set();n=0
    for method,gen in gens:
        for obj in gen:
            try:m=v4.canonical_bytes(obj,False)
            except Exception:continue
            if m in seen:continue
            seen.add(m);n+=1;yield method,obj
            if n>=budget:return


@dataclass
class Result:
    index:int;file:str;object_path:str;hash_path:str;target_sha256:str;ensure_ascii:bool
    recovered:bool;method:str;candidates_tested:int;recovered_json:str;ground_truth_json:str
    schema_known:bool;target_file_excluded:bool


def recover(ch:v4.ObjChallenge,corp:Corpus,budget:int)->Result:
    gens=[
        ("cross_file_exact_shape",same_object_elsewhere(ch,corp)),
        ("cross_file_same_keyset",same_keyset_objects(ch,corp)),
        ("sequence_fragment_reassembly",sequence_list_reassembly(ch,corp)),
        ("flat_schema_fragment_fill",flat_schema_fill(ch,corp)),
        ("recursive_schema_fragment_fill",recursive_schema_fill(ch,corp)),
    ]
    tested=0
    for method,obj in unique(gens,budget):
        tested+=1
        try:d=v4.sha(obj,ch.ensure_ascii)
        except Exception:continue
        if d==ch.target_sha256:
            return Result(0,ch.file,ch.object_path,ch.hash_path,ch.target_sha256,ch.ensure_ascii,True,method,tested,
                          v4.canonical_bytes(obj,ch.ensure_ascii).decode("utf-8"),
                          v4.canonical_bytes(ch.ground_truth,ch.ensure_ascii).decode("utf-8"),True,True)
    return Result(0,ch.file,ch.object_path,ch.hash_path,ch.target_sha256,ch.ensure_ascii,False,"",tested,"",
                  v4.canonical_bytes(ch.ground_truth,ch.ensure_ascii).decode("utf-8"),True,True)


def run(meta_root:Path,outdir:Path,budget:int):
    outdir.mkdir(parents=True,exist_ok=True);corp=Corpus(meta_root)
    raw=v4.discover(meta_root);challenges=[];seen=set()
    for ch in sorted(raw,key=lambda c:(v4.node_count(c.ground_truth),c.target_sha256,c.file)):
        k=(ch.target_sha256,v4.canonical_bytes(ch.ground_truth,ch.ensure_ascii),ch.ensure_ascii)
        if k in seen:continue
        seen.add(k);challenges.append(ch)
    results=[];con=sqlite3.connect(outdir/"janus.db")
    con.execute("CREATE TABLE IF NOT EXISTS truths(target_sha256 TEXT PRIMARY KEY,file TEXT,object_path TEXT,method TEXT,canonical_json TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS graveyard(target_sha256 TEXT,file TEXT,object_path TEXT,candidates_tested INTEGER)")
    for i,ch in enumerate(challenges,1):
        r=recover(ch,corp,budget);r.index=i;results.append(r)
        if r.recovered:con.execute("INSERT OR REPLACE INTO truths VALUES(?,?,?,?,?)",(r.target_sha256,r.file,r.object_path,r.method,r.recovered_json))
        else:con.execute("INSERT INTO graveyard VALUES(?,?,?,?)",(r.target_sha256,r.file,r.object_path,r.candidates_tested))
    con.commit();con.close()
    if results:
        with (outdir/"results.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=list(asdict(results[0]).keys()));w.writeheader();[w.writerow(asdict(r)) for r in results]
    rec=[r for r in results if r.recovered];by=Counter(r.method for r in rec)
    summary={"experiment":"JANUS Distributed Fragment Reassembly","version":VERSION,
             "tier":"SCHEMA_KNOWN_TARGET_VALUES_HIDDEN_TARGET_FILE_EXCLUDED",
             "verified_real_object_sha_challenges":len(results),"exact_objects_recovered":len(rec),
             "recovery_rate":len(rec)/len(results) if results else 0.0,"by_method":dict(by),
             "admission_rule":"exact canonical JSON SHA-256 only",
             "boundary":"Uses JSON schema skeleton plus fragments from other registry files; not SHA-only inversion."}
    (outdir/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),"utf-8")
    lines=["# JANUS-LAPIS v0.5.0 — Distributed Fragment Reassembly","",f"Tier: **{summary['tier']}**",f"Verified real object challenges: **{len(results)}**",f"Exact whole objects recovered: **{len(rec)}/{len(results)}**","","## Witnesses",""]
    for r in rec:
        lines += [f"### {r.index:03d} — {r.method}","",f"- File excluded from fragment corpus: `{r.file}`",f"- Object: `{r.object_path}`",f"- SHA: `{r.target_sha256}`","","```json",r.recovered_json,"```",""]
    if not rec:lines += ["No exact object was recoverable from cross-file fragments under this tier.",""]
    (outdir/"REPORT.md").write_text("\n".join(lines),"utf-8")
    return summary


def selftest(outdir:Path):
    # Build two local files conceptually: target values exist only in another-file fragment corpus.
    outdir.mkdir(parents=True,exist_ok=True)
    obj={"event":"A","sequence":1,"summary":"hello"}
    target=[obj]
    ch=v4.ObjChallenge("target.json","h","sha",v4.sha(target,False),"events","events",False,target,{},[])
    class C:
        object_index={v4.schema_signature(obj):[("other.json","events[0]",obj)],v4.schema_signature(target):[]}
        dict_keyset_index={tuple(sorted(obj.keys())):[("other.json","events[0]",obj)]}
        scalar_index=defaultdict(list)
        def scalar_candidates(self,*a,**k):return []
    r=recover(ch,C(),100)
    assert r.recovered and json.loads(r.recovered_json)==target
    (outdir/"selftest.json").write_text(json.dumps(asdict(r),ensure_ascii=False,indent=2),"utf-8")
    print(json.dumps({"selftest":"PASS","method":r.method},ensure_ascii=False))


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--meta-root",type=Path);ap.add_argument("--outdir",type=Path,default=Path("reverse_gate_runs/object_v5"));ap.add_argument("--budget",type=int,default=MAX_CANDIDATES);ap.add_argument("--selftest",action="store_true");a=ap.parse_args()
    if a.selftest:selftest(a.outdir);return
    if not a.meta_root:ap.error("--meta-root required")
    print(json.dumps(run(a.meta_root,a.outdir,a.budget),ensure_ascii=False,indent=2))

if __name__=="__main__":main()
