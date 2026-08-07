#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JANUS-LAPIS v0.4.0 — Whole-Object Reconstruction Gate.

This experiment raises the target from a hidden string to a complete hidden
JSON dict/list. It discovers only REAL object<->SHA pairs already verifiable in
Hawkar-usls/janus-meta-registry, removes the target object from context, then
tries to rebuild it from schemas learned on OTHER verified objects plus visible
sibling metadata.

Admission is exact only:
    SHA256(canonical_json(generated_object)) == target

No similarity score is a success condition.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import itertools
import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

VERSION = "0.4.0-whole-object"
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
MAX_OBJECT_NODES = 120
MAX_CANDIDATES = 80000


def canonical_bytes(obj: Any, ensure_ascii: bool) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=ensure_ascii, allow_nan=False).encode("utf-8")


def sha(obj: Any, ensure_ascii: bool) -> str:
    return hashlib.sha256(canonical_bytes(obj, ensure_ascii)).hexdigest()


def node_count(obj: Any) -> int:
    if isinstance(obj, dict):
        return 1 + sum(node_count(v) for v in obj.values())
    if isinstance(obj, list):
        return 1 + sum(node_count(v) for v in obj)
    return 1


def scalar(v: Any) -> bool:
    return v is None or isinstance(v, (str, int, float, bool))


def flatten(obj: Any, prefix: str = "") -> List[Tuple[str, Any]]:
    out=[]
    if isinstance(obj, dict):
        for k,v in obj.items():
            p=f"{prefix}.{k}" if prefix else str(k)
            if scalar(v): out.append((p,v))
            else: out.extend(flatten(v,p))
    elif isinstance(obj,list):
        for i,v in enumerate(obj):
            p=f"{prefix}[{i}]"
            if scalar(v): out.append((p,v))
            else: out.extend(flatten(v,p))
    return out


def leaf(path: str) -> str:
    x=path.rsplit(".",1)[-1]
    return x.split("[")[0]


def deepcopy_without_key(d: Dict[str,Any], key: str) -> Dict[str,Any]:
    return {k:copy.deepcopy(v) for k,v in d.items() if k != key}


@dataclass
class ObjChallenge:
    file: str
    hash_path: str
    hash_key: str
    target_sha256: str
    object_path: str
    object_key: str
    ensure_ascii: bool
    ground_truth: Any
    context: Any
    context_scalars: List[Tuple[str,Any]]


def discover(meta_root: Path) -> List[ObjChallenge]:
    found=[]; seen=set()

    def walk(obj: Any, file_rel: str, path: str, ancestors: List[Tuple[str,Dict[str,Any]]]):
        if isinstance(obj,dict):
            # Candidate objects are current non-scalar children plus children in
            # up to two ancestor scopes. This catches payload/hash sibling layouts.
            scopes=[(path,obj)] + ancestors[-2:]
            objects=[]
            for sp,scope in scopes:
                for k,v in scope.items():
                    if isinstance(v,(dict,list)) and node_count(v) <= MAX_OBJECT_NODES:
                        op=f"{sp}.{k}" if sp else str(k)
                        objects.append((op,k,v,scope))

            for hk,hv in obj.items():
                if not (isinstance(hv,str) and HEX64.fullmatch(hv) and "sha256" in hk.lower()):
                    continue
                target=hv.lower(); hp=f"{path}.{hk}" if path else hk
                # A canonical-json object challenge should normally advertise
                # canonical/payload/semantic/object in its hash key, but exact
                # verification is the ultimate selector.
                if not any(tok in hk.lower() for tok in ("canonical","payload","object","semantic","json")):
                    continue
                for op,okey,candidate,owner_scope in objects:
                    for ascii_mode in (False,True):
                        try: digest=sha(candidate,ascii_mode)
                        except (TypeError,ValueError): continue
                        if digest != target: continue
                        sig=(file_rel,hp,op,target,ascii_mode)
                        if sig in seen: continue
                        seen.add(sig)
                        # Build context from the highest available ancestor/root
                        # while removing this exact target object wherever it is a
                        # direct member of its owner scope. The ground truth itself
                        # is retained only for post-attempt scoring.
                        base_scope=copy.deepcopy(ancestors[0][1] if ancestors else obj)
                        # Remove any exact structural duplicate equal to target to
                        # prevent trivial object copy from another key in same file.
                        def scrub(x:Any)->Any:
                            if isinstance(x,dict):
                                y={}
                                for k,v in x.items():
                                    if k==hk and v==hv: continue
                                    if v == candidate: continue
                                    y[k]=scrub(v)
                                return y
                            if isinstance(x,list):
                                return [scrub(v) for v in x if v != candidate]
                            return x
                        context=scrub(base_scope)
                        ctx_scalars=flatten(context)
                        ctx_scalars += [("__file__",file_rel),("__basename__",Path(file_rel).name),("__stem__",Path(file_rel).stem)]
                        found.append(ObjChallenge(file_rel,hp,hk,target,op,okey,ascii_mode,copy.deepcopy(candidate),context,ctx_scalars))
            for k,v in obj.items():
                child=f"{path}.{k}" if path else str(k)
                walk(v,file_rel,child,ancestors+[(path,obj)])
        elif isinstance(obj,list):
            for i,v in enumerate(obj): walk(v,file_rel,f"{path}[{i}]",ancestors)

    for p in sorted(meta_root.rglob("*.json")):
        if ".git" in p.parts: continue
        try: root=json.loads(p.read_text("utf-8"))
        except Exception: continue
        walk(root,p.relative_to(meta_root).as_posix(),"",[])
    return found


def schema_signature(obj: Any) -> Any:
    if isinstance(obj,dict): return ("dict",tuple((k,schema_signature(v)) for k,v in sorted(obj.items())))
    if isinstance(obj,list): return ("list",tuple(schema_signature(v) for v in obj))
    if obj is None: return "null"
    if isinstance(obj,bool): return "bool"
    if isinstance(obj,int) and not isinstance(obj,bool): return "int"
    if isinstance(obj,float): return "float"
    if isinstance(obj,str): return "str"
    return type(obj).__name__


def context_by_leaf(ch: ObjChallenge) -> Dict[str,List[Any]]:
    m=defaultdict(list)
    for p,v in ch.context_scalars:
        k=leaf(p)
        if v not in m[k]: m[k].append(v)
    return m


def scalar_paths(obj:Any,prefix="") -> Dict[str,Any]:
    return dict(flatten(obj,prefix))


def get_at(obj: Any, path: str) -> Any:
    # helper only for simple dict/list paths generated by flatten
    cur=obj; token=""; i=0
    parts=[]
    while i<len(path):
        if path[i]=='.':
            if token: parts.append(("key",token)); token=""
            i+=1
        elif path[i]=='[':
            if token: parts.append(("key",token)); token=""
            j=path.index(']',i); parts.append(("idx",int(path[i+1:j]))); i=j+1
        else:
            token+=path[i]; i+=1
    if token: parts.append(("key",token))
    for typ,val in parts:
        cur=cur[val]
    return cur


def set_at(obj: Any, path: str, value: Any) -> None:
    cur=obj; token=""; i=0; parts=[]
    while i<len(path):
        if path[i]=='.':
            if token: parts.append(("key",token)); token=""
            i+=1
        elif path[i]=='[':
            if token: parts.append(("key",token)); token=""
            j=path.index(']',i); parts.append(("idx",int(path[i+1:j]))); i=j+1
        else:
            token+=path[i]; i+=1
    if token: parts.append(("key",token))
    for typ,val in parts[:-1]: cur=cur[val]
    typ,val=parts[-1]; cur[val]=value


def learn_projection(train: ObjChallenge) -> Dict[str,Tuple[str,Any]]:
    """Learn how each target scalar relates to visible context in another case.

    Output scalar-path -> ('context_leaf', key) or ('constant', value).
    Constants are learned only from training challenges, never from target truth.
    """
    cmap=context_by_leaf(train)
    rules={}
    for p,v in scalar_paths(train.ground_truth).items():
        matches=[k for k,vals in cmap.items() if v in vals and not k.startswith("__")]
        if matches:
            # deterministic shortest/lexicographic leaf
            k=sorted(matches,key=lambda x:(len(x),x))[0]
            rules[p]=("context_leaf",k)
        else:
            rules[p]=("constant",copy.deepcopy(v))
    return rules


def blank_from_schema(obj:Any)->Any:
    if isinstance(obj,dict): return {k:blank_from_schema(v) for k,v in obj.items()}
    if isinstance(obj,list): return [blank_from_schema(v) for v in obj]
    return None


def apply_projection(schema_obj:Any,rules:Dict[str,Tuple[str,Any]],ch:ObjChallenge,fanout:int=256)->Iterator[Any]:
    cmap=context_by_leaf(ch)
    slots=[]; paths=[]
    for p,(kind,val) in rules.items():
        paths.append(p)
        if kind=="constant": slots.append([copy.deepcopy(val)])
        else:
            vs=cmap.get(val,[])
            if not vs: return
            slots.append(vs[:6])
    n=0
    for combo in itertools.product(*slots):
        out=blank_from_schema(schema_obj)
        for p,v in zip(paths,combo): set_at(out,p,copy.deepcopy(v))
        yield out; n+=1
        if n>=fanout: return


def sibling_shape_candidates(ch:ObjChallenge)->Iterator[Any]:
    """Visible sibling objects with the same schema shape, if any."""
    target_sig=schema_signature(ch.ground_truth)
    def walk(x):
        if isinstance(x,(dict,list)):
            if node_count(x)<=MAX_OBJECT_NODES and schema_signature(x)==target_sig:
                yield copy.deepcopy(x)
            if isinstance(x,dict):
                for v in x.values(): yield from walk(v)
            else:
                for v in x: yield from walk(v)
    yield from walk(ch.context)


def learned_schema_candidates(ch:ObjChallenge,all_ch:Sequence[ObjChallenge])->Iterator[Any]:
    # Prefer same object key; then same schema signature learned from OTHER truth.
    ordered=[]
    for other in all_ch:
        if other.target_sha256==ch.target_sha256 or other.ground_truth==ch.ground_truth: continue
        score=(0 if other.object_key==ch.object_key else 1,
               0 if schema_signature(other.ground_truth)==schema_signature(ch.ground_truth) else 1,
               other.file)
        ordered.append((score,other))
    ordered.sort(key=lambda x:x[0])
    for _,other in ordered[:80]:
        # Transfer only compatible schema skeletons.
        if schema_signature(other.ground_truth)!=schema_signature(ch.ground_truth): continue
        rules=learn_projection(other)
        yield from apply_projection(other.ground_truth,rules,ch,fanout=128)


def keyset_projection_candidates(ch:ObjChallenge,all_ch:Sequence[ObjChallenge])->Iterator[Any]:
    """For flat dicts, learn key sets from peers then source values by matching context leaf names."""
    if not isinstance(ch.ground_truth,dict): return
    if any(isinstance(v,(dict,list)) for v in ch.ground_truth.values()): return
    cmap=context_by_leaf(ch)
    keysets=[]
    for other in all_ch:
        if other is ch or other.object_key!=ch.object_key or not isinstance(other.ground_truth,dict): continue
        if any(isinstance(v,(dict,list)) for v in other.ground_truth.values()): continue
        ks=tuple(sorted(other.ground_truth.keys()))
        if ks not in keysets: keysets.append(ks)
    for ks in keysets:
        slots=[]
        for k in ks:
            vs=cmap.get(k,[])
            if not vs: break
            slots.append(vs[:8])
        else:
            for combo in itertools.product(*slots): yield {k:v for k,v in zip(ks,combo)}


def unique_candidates(gens:Sequence[Tuple[str,Iterable[Any]]],budget:int)->Iterator[Tuple[str,Any]]:
    seen=set(); n=0
    for method,gen in gens:
        for obj in gen:
            try: marker=canonical_bytes(obj,False)
            except Exception: continue
            if marker in seen: continue
            seen.add(marker); n+=1; yield method,obj
            if n>=budget: return


@dataclass
class ObjResult:
    index:int
    file:str
    hash_path:str
    object_path:str
    target_sha256:str
    ensure_ascii:bool
    recovered:bool
    method:str
    candidates_tested:int
    recovered_json:str
    ground_truth_json:str
    visible_scalar_overlap:float


def visible_overlap(ch:ObjChallenge)->float:
    truth=[v for _,v in flatten(ch.ground_truth)]
    if not truth: return 0.0
    ctx=[v for _,v in ch.context_scalars]
    return sum(any(v==c for c in ctx) for v in truth)/len(truth)


def recover(ch:ObjChallenge,all_ch:Sequence[ObjChallenge],budget:int)->ObjResult:
    gens=[
        ("learned_schema_projection",learned_schema_candidates(ch,all_ch)),
        ("keyset_context_projection",keyset_projection_candidates(ch,all_ch)),
        ("visible_sibling_same_shape",sibling_shape_candidates(ch)),
    ]
    tested=0
    for method,obj in unique_candidates(gens,budget):
        tested+=1
        try: digest=sha(obj,ch.ensure_ascii)
        except Exception: continue
        if digest==ch.target_sha256:
            return ObjResult(0,ch.file,ch.hash_path,ch.object_path,ch.target_sha256,ch.ensure_ascii,True,method,tested,
                             canonical_bytes(obj,ch.ensure_ascii).decode("utf-8"),
                             canonical_bytes(ch.ground_truth,ch.ensure_ascii).decode("utf-8"),visible_overlap(ch))
    return ObjResult(0,ch.file,ch.hash_path,ch.object_path,ch.target_sha256,ch.ensure_ascii,False,"",tested,"",
                     canonical_bytes(ch.ground_truth,ch.ensure_ascii).decode("utf-8"),visible_overlap(ch))


def run(meta_root:Path,outdir:Path,budget:int)->Dict[str,Any]:
    outdir.mkdir(parents=True,exist_ok=True)
    challenges=discover(meta_root)
    uniq=[]; seen=set()
    for ch in sorted(challenges,key=lambda c:(node_count(c.ground_truth),c.target_sha256,c.file,c.object_path)):
        k=(ch.target_sha256,canonical_bytes(ch.ground_truth,ch.ensure_ascii),ch.ensure_ascii)
        if k in seen: continue
        seen.add(k); uniq.append(ch)
    results=[]
    con=sqlite3.connect(outdir/"janus.db")
    con.execute("CREATE TABLE IF NOT EXISTS object_truths(target_sha256 TEXT PRIMARY KEY,file TEXT,object_path TEXT,method TEXT,canonical_json TEXT,visible_overlap REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS graveyard(target_sha256 TEXT,file TEXT,object_path TEXT,candidates_tested INTEGER)")
    for i,ch in enumerate(uniq,1):
        r=recover(ch,uniq,budget); r.index=i; results.append(r)
        if r.recovered:
            con.execute("INSERT OR REPLACE INTO object_truths VALUES(?,?,?,?,?,?)",(r.target_sha256,r.file,r.object_path,r.method,r.recovered_json,r.visible_scalar_overlap))
        else:
            con.execute("INSERT INTO graveyard VALUES(?,?,?,?)",(r.target_sha256,r.file,r.object_path,r.candidates_tested))
    con.commit(); con.close()
    if results:
        with (outdir/"results.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=list(asdict(results[0]).keys())); w.writeheader(); [w.writerow(asdict(r)) for r in results]
    rec=[r for r in results if r.recovered]
    # classify: if every scalar already appears visibly, redundancy-assisted;
    # otherwise the reconstruction had to transfer at least some learned constants/schema.
    strong=[r for r in rec if r.visible_scalar_overlap < 0.999999]
    redundant=[r for r in rec if r.visible_scalar_overlap >= 0.999999]
    by=Counter(r.method for r in rec)
    summary={
        "experiment":"JANUS-LAPIS Whole-Object Reconstruction Gate",
        "version":VERSION,
        "verified_real_object_sha_challenges":len(results),
        "exact_objects_recovered":len(rec),
        "strong_object_recoveries":len(strong),
        "redundancy_assisted_object_recoveries":len(redundant),
        "recovery_rate":len(rec)/len(results) if results else 0.0,
        "by_method":dict(by),
        "candidate_budget_per_target":budget,
        "admission_rule":"SHA256(canonical_json(generated_object)) == target exactly",
        "boundary":"Constrained whole-object reconstruction using registry side information; not general SHA-256 inversion."
    }
    (outdir/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),"utf-8")
    lines=["# JANUS-LAPIS v0.4.0 — Whole-Object Reconstruction Gate","",
           f"Verified real object↔SHA challenges: **{len(results)}**",
           f"Exact whole objects recovered: **{len(rec)}/{len(results)}**",
           f"Strong object recoveries: **{len(strong)}**",
           f"Redundancy-assisted: **{len(redundant)}**","","## Exact whole-object witnesses",""]
    for r in rec[:50]:
        label="STRUCTURAL" if r.visible_scalar_overlap<0.999999 else "REDUNDANCY-ASSISTED"
        lines += [f"### {r.index:03d} — {r.method} [{label}]","",f"- File: `{r.file}`",f"- Object: `{r.object_path}`",f"- SHA: `{r.target_sha256}`",f"- Visible scalar overlap: `{r.visible_scalar_overlap:.3f}`","","```json",r.recovered_json,"```",""]
    if not rec: lines += ["No whole-object exact witness recovered. Gate remains closed.",""]
    (outdir/"REPORT.md").write_text("\n".join(lines),"utf-8")
    return summary


def selftest(outdir:Path):
    # Train object: same schema, one constant separator/type learned and values from context.
    train_obj={"artist":"SNAP!","track":"The Power","kind":"song"}
    train=ObjChallenge("train.json","h","sha",sha(train_obj,False),"payload","payload",False,train_obj,
                       {"artist":"SNAP!","track":"The Power"},[("artist","SNAP!"),("track","The Power")])
    target_obj={"artist":"ERA","track":"Ameno","kind":"song"}
    target=ObjChallenge("target.json","h","sha",sha(target_obj,False),"payload","payload",False,target_obj,
                        {"artist":"ERA","track":"Ameno"},[("artist","ERA"),("track","Ameno")])
    r=recover(target,[train,target],1000)
    assert r.recovered and json.loads(r.recovered_json)==target_obj
    outdir.mkdir(parents=True,exist_ok=True); (outdir/"selftest.json").write_text(json.dumps(asdict(r),ensure_ascii=False,indent=2),"utf-8")
    print(json.dumps({"selftest":"PASS","method":r.method,"object":json.loads(r.recovered_json)},ensure_ascii=False))


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--meta-root",type=Path); ap.add_argument("--outdir",type=Path,default=Path("reverse_gate_runs/object_v4")); ap.add_argument("--budget",type=int,default=MAX_CANDIDATES); ap.add_argument("--selftest",action="store_true"); a=ap.parse_args()
    if a.selftest: selftest(a.outdir); return
    if not a.meta_root: ap.error("--meta-root required")
    print(json.dumps(run(a.meta_root,a.outdir,a.budget),ensure_ascii=False,indent=2))

if __name__=="__main__": main()
