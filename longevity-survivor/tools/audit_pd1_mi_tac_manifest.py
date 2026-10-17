#!/usr/bin/env python3
"""Fail-closed GEO manifest, GSM, matrix and biological-unit audit for JANUS TOPA.
This program uses only acquired public bytes and never promotes a scientific EXIT gate.
"""
import collections
import datetime
import gzip
import hashlib
import json
import os
import pathlib
import re
import sys

ROOT=pathlib.Path(os.environ.get("TOPA_OUTPUT","topa_pd1_acquisition"))
REPORT_DIR=pathlib.Path(os.environ.get("TOPA_AUDIT_OUTPUT","topa_pd1_audit"))
REPORT_DIR.mkdir(parents=True,exist_ok=True)
MANIFEST=ROOT/"manifest.json"
TARGET=("GSE293489","GSE327655")
GENES=("Cxcl9","Cxcl10","Cxcr3","Cd3d","Cd3e","Trdc","Trgc1","Trgc2","Cd8a","Cd8b1","Gzmb","Prf1","Nkg7","Pdgfra","Col1a1","Col3a1","Postn","Acta2","Pdcd1")
def sha256(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()
def group(gse,s):
    v=" ".join([s.get("title","")]+s.get("attributes",[])).lower()
    # Strict labels: sham/MI and sham/TAC are never inferred from a bare replicate number.
    if gse=="GSE293489":
        sham=bool(re.search(r"\b(sham|control sham)\b",v))
        mi=bool(re.search(r"\b(myocardial infarction|infarcted|post[- ]?mi|mi group|mi[-_ ]?[0-9])\b",v))
        return "SHAM" if sham and not mi else "MI" if mi and not sham else "UNRESOLVED"
    tac=bool(re.search(r"\b(tac|transverse aortic constriction|pressure overload)\b",v))
    igg=bool(re.search(r"anti[- ]?igg|isotype",v))
    pd1=bool(re.search(r"anti[- ]?pd[- ]?1|anti[- ]?pd[- ]?one",v))
    if not tac:return "UNRESOLVED_NOT_TAC"
    return "TAC_ANTI_IGG" if igg and not pd1 else "TAC_ANTI_PD1" if pd1 and not igg else "UNRESOLVED_TAC_CONTRAST"
def animal(s):
    tokens=[s.get("title","")]+s.get("attributes",[])
    for t in tokens:
        m=re.search(r"\b(?:animal[_ -]?id|mouse[_ -]?id|individual[_ -]?animal|biological[_ -]?replicate)\s*[:=]\s*([A-Za-z0-9_.-]+)",t,re.I)
        if m:return m.group(1)
    return None
def sample_assay(files):
    names=[p.name.lower() for p in files]
    mtx=[x for x in names if x.endswith((".mtx",".mtx.gz"))]
    feat=[x for x in names if ("feature" in x or "gene" in x) and x.endswith((".tsv",".tsv.gz"))]
    bar=[x for x in names if "barcode" in x and x.endswith((".tsv",".tsv.gz"))]
    if mtx and feat and bar:return "10X_TRIPLET_CANDIDATE"
    if mtx:return "MTX_WITH_INCOMPLETE_SIDECARS"
    if any(x.endswith((".h5",".h5ad")) for x in names):return "HDF5_NEEDS_SCHEMA_AUDIT"
    if any(x.endswith((".csv.gz",".tsv.gz",".txt.gz")) for x in names):return "TABLE_NEEDS_SCHEMA_AUDIT"
    return "NO_PROCESSED_MATRIX_DEMONSTRATED"
def gene_profile(files):
    # Only exact 10X GSM-local triplets are eligible; this is descriptive RNA signal,
    # never cell-type proof nor independent animal-level inferential statistics.
    import scipy.io, scipy.sparse
    def choose(part,suffix):
        return next((x for x in files if part in x.name.lower() and x.name.lower().endswith(suffix)),None)
    mat=choose("matrix",".mtx.gz") or choose("matrix",".mtx")
    feat=choose("features",".tsv.gz") or choose("genes",".tsv.gz")
    bar=choose("barcodes",".tsv.gz")
    if not all((mat,feat,bar)):return {"status":"NOT_RUN_INCOMPLETE_10X_TRIPLET"}
    def lines(p):
        op=gzip.open if str(p).endswith(".gz") else open
        with op(p,"rt",errors="replace") as f:return [ln.rstrip("\n").split("\t") for ln in f]
    ff=lines(feat); bb=lines(bar)
    names=[x[1] if len(x)>1 else x[0] for x in ff]
    m=scipy.io.mmread(str(mat)).tocsr()
    if m.shape!=(len(ff),len(bb)):
        return {"status":"NOT_RUN_AMBIGUOUS_MATRIX_ORIENTATION","shape":list(m.shape),"genes":len(ff),"barcodes":len(bb)}
    keep=[(g,i) for i,g in enumerate(names) if g.lower() in {k.lower() for k in GENES}]
    sums=dict(); frac=dict()
    for g,i in keep:
        row=m.getrow(i)
        sums[g]=float(row.sum())
        frac[g]=round(float(row.count_nonzero())/len(bb),6) if bb else None
    total=float(m.sum())
    cpm={g:round(1e6*value/total,6) if total>0 else None for g,value in sums.items()}
    return {"status":"DESCRIPTIVE_ONLY_NOT_CELL_TYPE_IDENTIFICATION","cells":len(bb),"features":len(ff),"total_UMI":total,"gene_raw_counts_sum":sums,"pseudobulk_CPM_all_noncardiomyocytes":cpm,"fraction_barcodes_with_nonzero_transcript":frac,"assay_count_denominator":"all barcodes; not a gated T-cell population"}
a=json.loads(MANIFEST.read_text())
entries=[]
files_by_sample=collections.defaultdict(list)
for ent in a.get("files",[]):
    rec={k:ent.get(k) for k in ("path","url","status","bytes","sha256","md5") if k in ent}
    path=pathlib.Path(ent["path"])
    if ent.get("status")=="ACQUIRED":
        rec["present"]=path.is_file()
        if rec["present"]:
            rec["sha256_match"]=sha256(path)==ent.get("sha256")
            rec["bytes_match"]=path.stat().st_size==ent.get("bytes")
        else:rec.update({"sha256_match":False,"bytes_match":False})
        for gse in TARGET:
            mm=re.search(r"/"+gse+r"/processed/(GSM\d+)/",str(path).replace("\\","/"))
            if mm:files_by_sample[(gse,mm.group(1))].append(path)
    entries.append(rec)
samples={}
results={}
for gse in TARGET:
    ss=[]
    for item in a.get("samples",{}).get(gse,[]):
        gsm=item.get("gsm")
        if not gsm:continue
        fs=files_by_sample.get((gse,gsm),[])
        cls=sample_assay(fs)
        rec={"gsm":gsm,"title":item.get("title"),"attributes":item.get("attributes",[]),
             "group_candidate":group(gse,item),"animal_id_explicit":animal(item),
             "geo_supplementary_urls":item.get("files",[]),
             "acquired_processed_paths":[str(p) for p in fs],"matrix_status":cls}
        if cls=="10X_TRIPLET_CANDIDATE":
            try:rec["rna_descriptive"]=gene_profile(fs)
            except Exception as e:rec["rna_descriptive"]={"status":"ERROR","reason":str(e)[:300]}
        ss.append(rec)
    samples[gse]=ss
    count=collections.Counter(x["group_candidate"] for x in ss)
    known=[x for x in ss if x["animal_id_explicit"]]
    candidate=[x for x in ss if x["matrix_status"]!="NO_PROCESSED_MATRIX_DEMONSTRATED"]
    profiles=[x for x in ss if x.get("rna_descriptive",{}).get("status")=="DESCRIPTIVE_ONLY_NOT_CELL_TYPE_IDENTIFICATION"]
    # Even a complete barcode+gene triplet cannot imply a biological mouse.
    results[gse]={"dataset": "CHEN_MOUSE_MI" if gse=="GSE293489" else "WU_MOUSE_TAC",
      "gsm_count":len(ss),"group_candidate_counts":dict(count),
      "explicit_animal_id_count":len(known),"matrix_file_candidate_gsm_count":len(candidate),
      "verified_10x_descriptive_profiles":len(profiles),
      "animal_level_cell_proportion_replay":"NOT_ADMITTED",
      "animal_level_CXCL9_CXCR3_replay":"NOT_ADMITTED",
      "inferential_pvalues":"NOT_CALCULATED",
      "reason":"GSM=sample accession, not evidence of independently indexed animal; complete assay/animal crosswalk and cell identity required"}
checks={"acquired_records":sum(x.get("status")=="ACQUIRED" for x in entries),
        "all_acquired_source_sha256_and_sizes_verified":all(x.get("sha256_match") and x.get("bytes_match") for x in entries if x.get("status")=="ACQUIRED"),
        "acquisition_reported_errors":a.get("errors",[]),
        "preprocess_R_md5_matches":any(x.get("path","").endswith("zenodo/preprocess.R") and x.get("md5")=="c09afc0f77fa13f63329de811f208f59" and x.get("sha256_match") for x in entries)}
report={"schema_id":"janus.topa.pd1_mi_tac_manifest_gsm_audit.v1",
        "generated_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_run_id":39026401715,
        "source_artifact_id":12098558095,
        "source_archive_sha256":"ef67e3209b6acd66a7e8f3f55b156f15df47e4f827fb99e1b5908f2b5cd62172",
        "input_manifest":str(MANIFEST),
        "checks":checks,"file_inventory":entries,"samples":samples,"separate_study_results":results,
        "firewalls":["GSM != INDEPENDENT_MOUSE","RNA_MARKER_POSITIVITY != CELL_IDENTITY",
           "HUMAN_PBMC != MOUSE_HEART","MI != TAC","PUBLIC_SOURCE_ACQUIRED != SCIENTIFIC_REPLICATION",
           "ABSENT_PER_MOUSE_MAPPING => NO_ANIMAL_LEVEL_PVALUES","CELL_PROPORTION_SHIFT != FIBROBLAST_EXIT"],
        "gate_state":{"MANIFEST_AND_FILE_SHA256_AUDIT":"PASS" if checks["all_acquired_source_sha256_and_sizes_verified"] else "FAIL",
           "BIOLOGICAL_REPLICATE_CROSSWALK":"NOT_ADMITTED_UNLESS_EXPLICIT_ANIMAL_IDS_VALIDATED",
           "SC_RNA_CELL_PROPORTION_REPLAY":"NOT_ADMITTED","CXCL9_CXCR3_INFERENTIAL_REPLAY":"NOT_ADMITTED",
           "STRICT_PROFIBROTIC_CELL_EXIT":"NOT_ESTABLISHED","MECHANICAL_EXIT_COUPLING":"NOT_ADMITTED"}}
out=REPORT_DIR/"report.json"
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
summary={"output":str(out),"checks":checks,"separate_study_results":results,
         "sample_examples":{k:v[:6] for k,v in samples.items()},
         "acquired_paths":[x.get("path") for x in entries if x.get("status")=="ACQUIRED"]}
print(json.dumps(summary,ensure_ascii=False,indent=2))
sys.exit(0 if checks["all_acquired_source_sha256_and_sizes_verified"] else 2)
