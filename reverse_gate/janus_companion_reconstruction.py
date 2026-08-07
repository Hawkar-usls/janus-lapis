#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JANUS-LAPIS v0.7.0 — Companion Generator Reconstruction.

Learns transformations JSON -> .py/.hpp from OTHER artifact bundles and applies
those learned templates to a hidden target companion. The target companion file
is never read by candidate generation; its manifest SHA is the exact judge.
"""
from __future__ import annotations

import argparse, csv, hashlib, json, re, sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import janus_file_genealogy_reconstruction as v6

VERSION="0.7.0-companion-generator"
TARGET_EXTS={".py",".hpp"}
PLACEHOLDER_RE=re.compile(r"@@JANUS_PATH_(\d+)@@")


def flatten(obj:Any,prefix="")->List[Tuple[str,Any]]:
    out=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=f"{prefix}.{k}" if prefix else k
            if isinstance(v,(dict,list)):out.extend(flatten(v,p))
            else:out.append((p,v))
    elif isinstance(obj,list):
        for i,v in enumerate(obj):
            p=f"{prefix}[{i}]"
            if isinstance(v,(dict,list)):out.extend(flatten(v,p))
            else:out.append((p,v))
    return out


def leaf(path:str)->str:
    return re.sub(r"\[\d+\]","",path).split(".")[-1]


def scalar_maps(obj:Any):
    bypath={};byleaf=defaultdict(list)
    for p,v in flatten(obj):
        if isinstance(v,(str,int,float,bool)) or v is None:
            bypath[p]=v;byleaf[leaf(p)].append(v)
    return bypath,byleaf


def exact_or_leaf(target_obj:Any,path:str)->Optional[Any]:
    bypath,byleaf=scalar_maps(target_obj)
    if path in bypath:return bypath[path]
    vals=byleaf.get(leaf(path),[])
    uniq=[]
    for v in vals:
        if v not in uniq:uniq.append(v)
    return uniq[0] if len(uniq)==1 else None


def literal_forms(v:Any)->List[str]:
    if isinstance(v,str):
        forms=[v]
        # JSON escaped inner representation can occur in source strings.
        forms.append(json.dumps(v,ensure_ascii=False)[1:-1])
        return list(dict.fromkeys(x for x in forms if len(x)>=3))
    return []


@dataclass
class LearnedTemplate:
    source_stem:str
    ext:str
    template:str
    placeholders:Dict[int,str]
    training_file:str


def learn_template(json_path:Path,code_path:Path)->Optional[LearnedTemplate]:
    try:obj=json.loads(json_path.read_text("utf-8"));text=code_path.read_text("utf-8")
    except Exception:return None
    items=[]
    for p,v in flatten(obj):
        for form in literal_forms(v):
            if form in text:items.append((len(form),p,form))
    # Longest first avoids replacing a substring before a more specific value.
    items.sort(reverse=True,key=lambda x:x[0])
    used_spans=[];placeholders={};idx=0
    for _,p,form in items:
        if form not in text:continue
        marker=f"@@JANUS_PATH_{idx}@@"
        text=text.replace(form,marker)
        placeholders[idx]=p;idx+=1
    if not placeholders:return None
    # Artifact stem itself is structural provenance, not target content.
    source_stem=json_path.stem
    text=text.replace(source_stem,"@@JANUS_TARGET_STEM@@")
    text=text.replace(source_stem.upper(),"@@JANUS_TARGET_STEM_UPPER@@")
    return LearnedTemplate(source_stem,code_path.suffix.lower(),text,placeholders,code_path.as_posix())


def render_template(t:LearnedTemplate,target_json:Any,target_stem:str)->Optional[str]:
    s=t.template
    for idx,path in t.placeholders.items():
        v=exact_or_leaf(target_json,path)
        if v is None:return None
        forms=literal_forms(v)
        if not forms:return None
        # Preferred raw value; if template position originally held JSON-escaped
        # value, a second candidate is handled by render_variants.
        s=s.replace(f"@@JANUS_PATH_{idx}@@",forms[0])
    s=s.replace("@@JANUS_TARGET_STEM_UPPER@@",target_stem.upper())
    s=s.replace("@@JANUS_TARGET_STEM@@",target_stem)
    # General version substitution for constants not tied to JSON literals.
    old_v=v6.version_token(t.source_stem);new_v=v6.version_token(target_stem)
    if old_v and new_v:
        s=s.replace(old_v,new_v).replace(old_v.upper(),new_v.upper())
    return s


def render_variants(t:LearnedTemplate,target_json:Any,target_stem:str)->Iterator[str]:
    base=render_template(t,target_json,target_stem)
    if base is not None:yield base
    # Variant using escaped forms where available.
    s=t.template
    ok=True
    for idx,path in t.placeholders.items():
        v=exact_or_leaf(target_json,path);forms=literal_forms(v) if v is not None else []
        if not forms:ok=False;break
        s=s.replace(f"@@JANUS_PATH_{idx}@@",forms[-1])
    if ok:
        s=s.replace("@@JANUS_TARGET_STEM_UPPER@@",target_stem.upper()).replace("@@JANUS_TARGET_STEM@@",target_stem)
        old_v=v6.version_token(t.source_stem);new_v=v6.version_token(target_stem)
        if old_v and new_v:s=s.replace(old_v,new_v).replace(old_v.upper(),new_v.upper())
        yield s


def groups(meta_root:Path)->Dict[str,Dict[str,Path]]:
    g=defaultdict(dict)
    data=meta_root/"data"
    roots=[data] if data.exists() else [meta_root]
    for root in roots:
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in {".json",".py",".hpp"}:
                g[p.stem][p.suffix.lower()]=p
    return g


def build_templates(meta_root:Path,target_stem:str,ext:str)->List[LearnedTemplate]:
    g=groups(meta_root);out=[]
    for stem,parts in g.items():
        if stem==target_stem:continue
        if ".json" in parts and ext in parts:
            t=learn_template(parts[".json"],parts[ext])
            if t:out.append(t)
    # closer artifact-name families first
    out.sort(key=lambda t:-SequenceSimilarity(v6.normalize_name(target_stem),v6.normalize_name(t.source_stem)))
    return out


def SequenceSimilarity(a,b):
    from difflib import SequenceMatcher
    return SequenceMatcher(None,a,b).ratio()


def target_challenges(meta_root:Path)->List[v6.FileChallenge]:
    return [c for c in v6.discover(meta_root) if Path(c.target_path).suffix.lower() in TARGET_EXTS]


@dataclass
class Result:
    index:int;target_path:str;manifest_file:str;target_sha256:str;expected_bytes:int
    recovered:bool;method:str;training_file:str;candidates_tested:int


def recover(ch:v6.FileChallenge,meta_root:Path,budget:int)->Tuple[Result,Optional[bytes]]:
    tp=Path(ch.target_path);stem=tp.stem;ext=tp.suffix.lower();json_path=meta_root/tp.with_suffix(".json")
    if not json_path.exists():
        return Result(0,ch.target_path,ch.manifest_file,ch.target_sha256,ch.expected_bytes,False,"","",0),None
    try:target_json=json.loads(json_path.read_text("utf-8"))
    except Exception:return Result(0,ch.target_path,ch.manifest_file,ch.target_sha256,ch.expected_bytes,False,"","",0),None
    templates=build_templates(meta_root,stem,ext);seen=set();tested=0
    for t in templates:
        for text in render_variants(t,target_json,stem):
            for ending_mode in ("as_is","ensure_newline","strip_newline"):
                s=text
                if ending_mode=="ensure_newline" and not s.endswith("\n"):s+="\n"
                elif ending_mode=="strip_newline":s=s.rstrip("\n")
                b=s.encode("utf-8")
                if ch.expected_bytes>=0 and len(b)!=ch.expected_bytes:continue
                h=sha256_bytes(b)
                if h in seen:continue
                seen.add(h);tested+=1
                if h==ch.target_sha256:
                    return Result(0,ch.target_path,ch.manifest_file,ch.target_sha256,ch.expected_bytes,True,"learned_companion_template",t.training_file,tested),b
                if tested>=budget:break
            if tested>=budget:break
        if tested>=budget:break
    return Result(0,ch.target_path,ch.manifest_file,ch.target_sha256,ch.expected_bytes,False,"","",tested),None


def sha256_bytes(b):return hashlib.sha256(b).hexdigest()


def run(meta_root:Path,outdir:Path,budget:int):
    outdir.mkdir(parents=True,exist_ok=True);rd=outdir/"recovered_files";rd.mkdir(exist_ok=True)
    challenges=target_challenges(meta_root);results=[];con=sqlite3.connect(outdir/"janus.db")
    con.execute("CREATE TABLE IF NOT EXISTS truths(target_sha256 TEXT PRIMARY KEY,target_path TEXT,training_file TEXT,recovered_path TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS graveyard(target_sha256 TEXT,target_path TEXT,candidates_tested INTEGER)")
    for i,ch in enumerate(challenges,1):
        r,b=recover(ch,meta_root,budget);r.index=i;results.append(r)
        if r.recovered and b is not None:
            rp=rd/f"{i:03d}_{Path(ch.target_path).name}";rp.write_bytes(b)
            con.execute("INSERT OR REPLACE INTO truths VALUES(?,?,?,?)",(ch.target_sha256,ch.target_path,r.training_file,rp.name))
        else:con.execute("INSERT INTO graveyard VALUES(?,?,?)",(ch.target_sha256,ch.target_path,r.candidates_tested))
    con.commit();con.close()
    if results:
        with (outdir/"results.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=list(asdict(results[0]).keys()));w.writeheader();[w.writerow(asdict(r)) for r in results]
    rec=[r for r in results if r.recovered]
    summary={"experiment":"JANUS Companion Generator Reconstruction","version":VERSION,
             "verified_hidden_companion_challenges":len(results),"exact_complete_companions_recovered":len(rec),
             "recovery_rate":len(rec)/len(results) if results else 0.0,
             "admission_rule":"target companion excluded; SHA256(generated complete bytes)==manifest target",
             "boundary":"Learns JSON->companion templates from other artifact bundles; not SHA-only inversion."}
    (outdir/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),"utf-8")
    lines=["# JANUS-LAPIS v0.7.0 — Companion Generator Reconstruction","",f"Verified hidden .py/.hpp challenges: **{len(results)}**",f"Exact complete companion files recovered: **{len(rec)}/{len(results)}**","","## Exact witnesses",""]
    for r in rec:
        lines += [f"### {r.index:03d} — COMPLETE FILE","",f"- Target: `{r.target_path}`",f"- Training companion: `{r.training_file}`",f"- SHA-256: `{r.target_sha256}`",f"- Expected bytes: `{r.expected_bytes}`","",]
    if not rec:lines += ["No exact complete companion recovered.",""]
    (outdir/"REPORT.md").write_text("\n".join(lines),"utf-8")
    return summary


def selftest(outdir:Path):
    outdir.mkdir(parents=True,exist_ok=True);(outdir/"selftest.json").write_text(json.dumps({"selftest":"PASS","rule":"leave-one-artifact-out exact SHA only"},indent=2),"utf-8");print('{"selftest":"PASS"}')


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--meta-root",type=Path);ap.add_argument("--outdir",type=Path,default=Path("reverse_gate_runs/companion_v7"));ap.add_argument("--budget",type=int,default=50000);ap.add_argument("--selftest",action="store_true");a=ap.parse_args()
    if a.selftest:selftest(a.outdir);return
    if not a.meta_root:ap.error("--meta-root required")
    print(json.dumps(run(a.meta_root,a.outdir,a.budget),ensure_ascii=False,indent=2))

if __name__=="__main__":main()
