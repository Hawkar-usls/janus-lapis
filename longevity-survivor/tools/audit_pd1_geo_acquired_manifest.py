#!/usr/bin/env python3
"""Audit the *existing* TOPA GitHub Actions source-byte artifact, without refetching GEO.
Scientific firewall: sample label is not the biological replicate; triplet completeness
is not statistical validity; hashes verify bytes, not group attribution.
"""
from __future__ import annotations
import gzip
import hashlib
import json
import os
import pathlib
import re
import sys
from collections import Counter

def sha256_file(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(2*1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def find_bytes(base,logged_path):
    x=pathlib.Path(logged_path)
    parts=x.parts
    for anchor in ("topa_pd1_acquisition","GSE293489","GSE327655","zenodo"):
        if anchor in parts:
            rest=pathlib.Path(*parts[parts.index(anchor):])
            options=[base/rest,base/"topa_pd1_acquisition"/rest,base/x.name]
            for candidate in options:
                if candidate.is_file():return candidate
    options=[base/x,base/x.name]
    for candidate in options:
        if candidate.is_file():return candidate
    return None

def kind_of(name):
    n=name.lower()
    if n.endswith(("_barcodes.tsv.gz","barcodes.tsv.gz")):return "barcodes"
    if n.endswith(("features.tsv.gz","genes.tsv.gz")):return "features"
    if n.endswith((".mtx.gz",".mtx")):return "matrix_market"
    if n.endswith((".h5",".hdf5")):return "hdf5"
    if n.endswith(".csv.gz"):return "csv"
    if n.endswith(".rds"):return "rds"
    return "other"

def verify_magic(p,kind):
    with p.open("rb") as f:head=f.read(8)
    if p.suffix==".gz":
        if head[:2]!=b"\x1f\x8b":return False
        if kind=="matrix_market":
            with gzip.open(p,"rb") as f: return f.readline(120).startswith(b"%%MatrixMarket")
        return True
    if kind=="hdf5":return head==b"\x89HDF\r\n\x1a\n"
    return True

def signals(item):
    title=item.get("title","")
    attrs=item.get("attributes",[])
    t=" | ".join([title]+attrs)
    def check(p):return bool(re.search(p,t,re.IGNORECASE))
    findings={}
    for name,pat in {
        "MI":r"\b(?:MI|myocardial infarct(?:ion)?)\b",
        "SHAM":r"\bsham\b",
        "TAC":r"\b(?:TAC|transverse aortic constriction|pressure overload)\b",
        "PD1":r"\b(?:PD-?1|Pdcd1|anti.PD.1)\b",
        "WILDTYPE":r"\b(?:wild.?type|WT)\b",
        "CONTROL":r"\b(?:control|isotype|IgG)\b",
        "KNOCKOUT":r"\b(?:knock.?out|KO|delet(?:ion|ed))\b",
    }.items():
        if check(pat):findings[name]=True
    return {"evidence_text":t[:1000],"explicit_tokens":sorted(findings),
        "disease_assignment":"CONFLICT" if (findings.get("MI") and findings.get("SHAM")) or (findings.get("TAC") and findings.get("SHAM")) else "UNVERIFIED_WITHOUT_MANUAL_METADATA_CONTEXT",
        "animal_identity":"UNVERIFIED_NOT_A_GROUP_REPLICATE"}

def main():
    base=pathlib.Path(os.environ.get("TOPA_PRIOR_DIR","prior")).resolve()
    reportdir=pathlib.Path(os.environ.get("TOPA_AUDIT_OUT","topa_pd1_manifest_audit"))
    reportdir.mkdir(parents=True,exist_ok=True)
    xs=list(base.rglob("manifest.json"))
    xs=[p for p in xs if p.parent.name=="topa_pd1_acquisition"]
    if len(xs)!=1:raise RuntimeError(f"expected exactly one pre-existing acquisition manifest; found {len(xs)}")
    manifest=xs[0]
    j=json.loads(manifest.read_text(encoding="utf-8"))
    files=[]
    mismatches=[]
    local_by_gsm={}
    for rec in j.get("files",[]):
        p=find_bytes(base,rec["path"])
        isgood=bool(p and p.is_file())
        sha=sha256_file(p) if isgood else None
        byte_count=p.stat().st_size if isgood else None
        hash_ok=isgood and sha==rec.get("sha256")
        byte_ok=isgood and byte_count==rec.get("bytes")
        kind=kind_of(p.name if p else rec["path"])
        magic_ok=verify_magic(p,kind) if isgood else False
        row={"logged_path":rec["path"],"url":rec.get("url"),
             "status":rec.get("status"),"local_exists":isgood,
             "reported_bytes":rec.get("bytes"),"observed_bytes":byte_count,
             "reported_sha256":rec.get("sha256"),"observed_sha256":sha,
             "hash_ok":bool(hash_ok),"size_ok":bool(byte_ok),"format_magic_ok":bool(magic_ok),"kind":kind}
        files.append(row)
        if rec.get("status")=="ACQUIRED" and not (hash_ok and byte_ok and magic_ok):
            mismatches.append({"path":rec["path"],"error":"MISSING_OR_HASH_SIZE_FORMAT_MISMATCH"})
        if isgood:
            x=p.parts
            if "processed" in x and ("GSE293489" in x or "GSE327655" in x):
                idx=x.index("processed")
                if len(x)>idx+1:
                    gsm=x[idx+1]
                    local_by_gsm.setdefault(gsm,[]).append(row)
    samples=[]
    for gse in ("GSE293489","GSE327655"):
        for s in j.get("samples",{}).get(gse,[]):
            if not s.get("gsm"):continue
            gsm=s["gsm"]
            relevant=local_by_gsm.get(gsm,[])
            kinds=Counter(x["kind"] for x in relevant if x["hash_ok"] and x["format_magic_ok"])
            triplet=(kinds["barcodes"]>0 and kinds["features"]>0 and kinds["matrix_market"]>0)
            standalone=(kinds["hdf5"]>0)
            if triplet: coverage="COMPLETE_LOCAL_10X_TRIPLET"
            elif standalone: coverage="LOCAL_H5_REQUIRES_INTERNAL_READ"
            elif len(relevant)>0: coverage="PARTIAL_LOCAL_FILES"
            else: coverage="NO_MATRIX_LOCAL"
            sample={"gse":gse,"gsm":gsm,"title":s.get("title"),
               "attributes":s.get("attributes",[]),"source_file_urls":s.get("files",[]),
               "verified_acquired_files":[{"name":pathlib.Path(r["logged_path"]).name,"bytes":r["observed_bytes"],"kind":r["kind"]} for r in relevant if r["hash_ok"] and r["format_magic_ok"]],
               "triplet_complete":triplet,"hdf5_present":standalone,
               "coverage":coverage,"n_independent_animals":None,
               "group_evidence":signals(s)}
            samples.append(sample)
    zen=[f for f in files if f["logged_path"].endswith("zenodo/preprocess.R")]
    expected_md5="c09afc0f77fa13f63329de811f208f59"
    zenodo_md5=None
    if zen:
        p=find_bytes(base,zen[0]["logged_path"])
        if p:
            h=hashlib.md5()
            with p.open("rb") as f:
                for piece in iter(lambda:f.read(1024*1024),b""):h.update(piece)
            zenodo_md5=h.hexdigest()
    summary={
      "schema_id":"janus.topa.pd1_mi_tac_manifest_reconciliation.v1",
      "parent_github_run":39026401715,
      "parent_artifact_id":12098558095,
      "parent_artifact_name":"topa-pd1-geo-zenodo-verified-public-bytes",
      "parent_manifest_reported_file_count":len(j.get("files",[])),
      "acquired_file_count":sum(x.get("status")=="ACQUIRED" for x in j.get("files",[])),
      "independent_sha256_verified_count":sum(x["hash_ok"] for x in files),
      "file_hash_size_or_magic_failures":mismatches,
      "zenodo_preprocess_R_expected_md5":expected_md5,
      "zenodo_preprocess_R_actual_md5":zenodo_md5,
      "zenodo_preprocess_R_md5_pass":zenodo_md5==expected_md5,
      "sample_counts_by_geo":{g:sum(s["gse"]==g for s in samples) for g in ("GSE293489","GSE327655")},
      "matrix_coverage_counts_by_geo":{g:dict(Counter(s["coverage"] for s in samples if s["gse"]==g)) for g in ("GSE293489","GSE327655")},
      "all_samples":samples,
      "files":files,
      "scientific_gates":{
        "SOURCE_BYTES_HASH_VERIFIED":"PASS" if not mismatches else "FAIL",
        "ALL_GSM_MATRICES_COMPLETE":"NOT_PROVEN_BY_FILE_COUNT",
        "BIOLOGICAL_GROUP_AND_INDEPENDENT_ANIMAL_MAP":"OPEN_UNVERIFIED",
        "RNA_EXPRESSION_REPLAY":"NOT_PERFORMED",
        "STRICT_PROFIBROTIC_CELL_EXIT":"NOT_ESTABLISHED"
      },
      "constraints":["metadata label does not prove animal identity","cell count does not prove independent biological n",
        "archive receipt != scientific replication","no human PBMC vs mouse cardiac pseudo-pooling"]
    }
    out=reportdir/"reconciliation.json"
    out.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    compact={k:v for k,v in summary.items() if k not in ("files","all_samples")}
    compact["samples"]=[{"gse":s["gse"],"gsm":s["gsm"],"title":s["title"],
        "attributes":s["attributes"],"coverage":s["coverage"],
        "verified_files":len(s["verified_acquired_files"]),
        "group_evidence":s["group_evidence"]} for s in samples]
    (reportdir/"summary.json").write_text(json.dumps(compact,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("TOPA_AUDIT_REPORT_START")
    print(json.dumps(compact,ensure_ascii=False))
    print("TOPA_AUDIT_REPORT_END")
    if mismatches or zenodo_md5!=expected_md5:sys.exit(2)

if __name__=="__main__":main()
