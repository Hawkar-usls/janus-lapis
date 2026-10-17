#!/usr/bin/env python3
"""Inspect unabridged GEO SOFT plus Wu counts header for true experimental units.

A GSM, a filename suffix -1, or six numbered columns is NOT evidence that
each library comes from a unique unpooled mouse. Group tokens alone are not
authority for exact GSM<->bulk-column mapping.
"""
import collections
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request

ROOT=Path(os.environ.get("TOPA_PD1_ROOT","prior/topa_pd1_acquisition"))
OUT=Path(os.environ.get("TOPA_CROSSWALK_OUT","topa_pd1_biological_crosswalk"))
OUT.mkdir(parents=True,exist_ok=True)
WU_URL="https://ftp.ncbi.nlm.nih.gov/geo/series/GSE327nnn/GSE327655/suppl/GSE327655_counts_All_Samples.csv.gz"
WU_SHA256="ebf519149d26a2c77841fd945f5aca8f861ff61f68d38f8c2a896833be70f327"
def sha(p):
 d=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):d.update(b)
 return d.hexdigest()
def soft(path):
 series=collections.defaultdict(list)
 samples={}
 current=None
 with gzip.open(path,"rt",encoding="utf-8",errors="replace") as f:
  for line in f:
   t=line.strip()
   if t.startswith("^SAMPLE = "):
    current=t.split(" = ",1)[1]
    samples[current]=collections.defaultdict(list)
   elif t.startswith("^SERIES = "):
    current=None
   elif current and t.startswith("!Sample_") and " = " in t:
    k,v=t.split(" = ",1);samples[current][k].append(v)
   elif current is None and t.startswith("!Series_") and " = " in t:
    k,v=t.split(" = ",1);series[k].append(v)
 return series,samples
def get(x,k):return x.get(k,[])
def sample_evidence(gsm,meta):
 title="; ".join(get(meta,"!Sample_title"))
 chars=get(meta,"!Sample_characteristics_ch1")
 desc=get(meta,"!Sample_description")
 alltext=" \n".join(v for val in meta.values() for v in val)
 # Matching "replicate 1" or "TAC-1" is not a validated mouse identifier.
 matches=re.findall(r"(?:animal|mouse|specimen|subject)[_ -]?(?:ID|identifier)\s*[:=]\s*([a-zA-Z0-9_.-]+)",alltext,re.I)
 pooling=bool(re.search(r"\bpool(?:ed|ing)?\b|\bcombined\s+(?:hearts|mice|animals|samples)\b",alltext,re.I))
 return {"gsm":gsm,"title":title,
  "source_name":get(meta,"!Sample_source_name_ch1"),
  "characteristics":chars,"description":desc[:12],
  "relation":get(meta,"!Sample_relation"),
  "library_strategy":get(meta,"!Sample_library_strategy"),
  "data_processing":get(meta,"!Sample_data_processing")[:8],
  "raw_animal_ID_tokens":matches,
  "explicit_pooling_mention":pooling,
  "columns_mentioned_in_sample_metadata":sorted(set(re.findall(r"\b(?:TAC|TP)[123]\b",alltext,re.I))),
  "independent_animal_status":"UNKNOWN_UNLESS_UNIQUE_PRIMARY_MOUSE_ID_AND_POOLING_AUDITED"}
def grab_header():
 req=urllib.request.Request(WU_URL,headers={"User-Agent":"JANUS-TOPA-experimental-unit-audit/1.0"})
 p=OUT/"GSE327655_counts_All_Samples.csv.gz"
 with urllib.request.urlopen(req,timeout=50) as f,p.open("wb") as q:
  size=0
  while True:
   b=f.read(1<<19)
   if not b:break
   size+=len(b)
   if size>10*1024*1024:raise ValueError("Bounded Wu counts source cap")
   q.write(b)
 if sha(p)!=WU_SHA256:raise ValueError("Wu counts source hash does not match previous receipt")
 with gzip.open(p,"rt",encoding="utf-8") as f:header=f.readline().strip()
 return {"url":WU_URL,"size_bytes":p.stat().st_size,"sha256":sha(p),"columns":header.split(",")[:30]}
manifest=json.loads((ROOT/"manifest.json").read_text())
report={"schema":"janus.topa.gsm_independent_animal_crosswalk_v1",
        "date_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source":{"Chen_DOI":"10.1038/s41421-026-00924-2","Wu_DOI":"10.1161/CIRCULATIONAHA.125.074024",
                  "Chen_GEO":"GSE293489","Wu_GEO":"GSE327655",
                  "original_GitHub_artifact":12098558095,"manifest":str(ROOT/"manifest.json")},
        "series":{},"sample_catalogs":{},"Wu_bulk_counts_header":None}
for gse in ("GSE293489","GSE327655"):
 p=ROOT/gse/(gse+"_family.soft.gz")
 if not p.exists():raise FileNotFoundError(str(p))
 rec=next((v for v in manifest["files"] if v.get("path","").endswith(str(p)) and v.get("status")=="ACQUIRED"),None)
 if rec is None or sha(p)!=rec.get("sha256"):raise ValueError("Invalid GEO source SHA for "+gse)
 se, sa=soft(p)
 report["series"][gse]={"series_overall_design":se.get("!Series_overall_design",[]),
   "series_summary":se.get("!Series_summary",[])[:5],
   "sample_count":len(sa),"sample_ids":sorted(sa)}
 report["sample_catalogs"][gse]=[sample_evidence(gsm,v) for gsm,v in sorted(sa.items())]
report["Wu_bulk_counts_header"]=grab_header()
# Strict machine check: a unique explicit animal identifier per GSM must be
# present in metadata and absent any pooling before group inference.
status={}
for gse, samples in report["sample_catalogs"].items():
 ids=[x["raw_animal_ID_tokens"] for x in samples]
 unique=all(len(x)==1 for x in ids) and len({x[0] for x in ids})==len(ids)
 unpooled=not any(x["explicit_pooling_mention"] for x in samples)
 status[gse]={"GSM_count":len(samples),"unique_explicit_mouse_IDs_present":unique,
              "pooling_excluded_by_direct_evidence":False, # lack of 'pooled' token is not positive proof
              "animal_level_inference_admitted":False,
              "sample_metadata_contains_pooling_keyword":not unpooled,
              "no_pooling_keyword_does_not_prove_no_pooling":True}
report["experimental_units"]=status
columns=set(report["Wu_bulk_counts_header"]["columns"])
expected={"TAC1","TAC2","TAC3","TP1","TP2","TP3"}
mentions=[(s["gsm"],s["columns_mentioned_in_sample_metadata"]) for s in report["sample_catalogs"]["GSE327655"]]
exact=all(len(y)==1 for x,y in mentions) and set(y[0] for x,y in mentions)==expected
report["Wu_column_map"]={"counts_data_columns":sorted(columns&expected),
 "GEO_titles":{x["gsm"]:x["title"] for x in report["sample_catalogs"]["GSE327655"]},
 "source_metadata_specific_column_tokens":{gsm:val for gsm,val in mentions},
 "explicit_sixway_matching_proven":exact,
 "proposed_from_naming_only":{"TAC1..3":"GSM9662756..GSM9662758 (TAC+anti-IgG)",
                              "TP1..3":"GSM9662759..GSM9662761 (TAC+anti-PD1)"},
 "authority":"EXPLICIT_INDIVIDUAL_COLUMN_NAME_IN_PRIMARY_SAMPLE_METADATA" if exact else "GROUP_LEVEL_PATTERN_ONLY_NOT_AUTHOR_VERIFIED"}
report["gates"]={"GEO_FAMILY_SOFT_BYTES_SHA256":"PASS",
 "WU_COUNTS_SOURCE_SHA256":"PASS","GSM_GROUP_ATTRIBUTES":"PRESENT",
 "WU_BULK_COLUMN_TO_TREATMENT":"NOT_CERTIFIED" if not exact else "GEO_SAMPLE_EXPLICIT_MATCH",
 "WU_INDIVIDUAL_MOUSE_UNITS":"NOT_VERIFIED",
 "CHEN_INDIVIDUAL_MOUSE_UNITS":"NOT_VERIFIED",
 "ANIMAL_LEVEL_CELL_PROPORTION_TESTS":"BLOCKED",
 "SCAR_REVERSAL_EXIT":"NOT_ESTABLISHED"}
(OUT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print("TOPA_BIOLOGICAL_UNIT_SUMMARY_START")
print(json.dumps({"gates":report["gates"],"experimental_units":status,
 "Wu_column_map":report["Wu_column_map"],
 "study_overall_design":{g:v["series_overall_design"] for g,v in report["series"].items()}},ensure_ascii=False))
print("TOPA_BIOLOGICAL_UNIT_SUMMARY_END")
