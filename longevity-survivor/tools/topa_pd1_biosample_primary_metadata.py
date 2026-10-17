#!/usr/bin/env python3
"""Small public-record provenance check: exact GEO field that maps Wu bulk column.

Use GEO and BioSamples metadata only; never treat distinct accessions, titles,
SRA runs, or absence of "pool" as proof of independent biological animals.
"""
import datetime,gzip,hashlib,json,os,re,urllib.request
from pathlib import Path

OUT=Path(os.environ.get("TOPA_RECORDS_OUT","topa_pd1_records"))
OUT.mkdir(parents=True,exist_ok=True)
SERIES=("GSE293489","GSE327655")
def get_bytes(url,limit=2_000_000):
 req=urllib.request.Request(url,headers={"User-Agent":"JANUS-TOPA-bio-units/1.0"})
 with urllib.request.urlopen(req,timeout=18) as r:
  data=r.read(limit+1)
  if len(data)>limit:raise ValueError("Exceeded public metadata cap")
  return data
def parse(soft):
 samples={};series={};cur=None
 for line in gzip.decompress(soft).decode("utf-8","replace").splitlines():
  if line.startswith("^SAMPLE = "):
   cur=line.split(" = ",1)[1];samples[cur]={}
  elif line.startswith("^SERIES = "):cur=None
  elif line.startswith("!Sample_") and " = " in line and cur:
   k,v=line.split(" = ",1);samples[cur].setdefault(k,[]).append(v)
  elif line.startswith("!Series_") and " = " in line and cur is None:
   k,v=line.split(" = ",1);series.setdefault(k,[]).append(v)
 return series,samples
report={"schema":"janus.topa.geo_gsm_biosample_provenance.v1",
 "run_date":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "sources":{},"samples":{},
 "independence_gate":"FAIL_CLOSED_UNLESS_EXPLICIT_PROOF",
 "mapping_grade":"UNASSESSED",
 "notes":["GEO_SRA_BIOSAMPLE_DISTINCTNESS != INDEPENDENT_MOUSE",
          "GSM_SUFFIXES != ANIMAL_IDS","LACK_OF_POOLING_MENTION != NO_POOLING",
          "ONLY_DIRECT_EXACT_COLUMN_IN_GSM_METADATA_AUTHORIZES_WU_BULK_COLUMN_MATCH"]}
for gse in SERIES:
 url="https://ftp.ncbi.nlm.nih.gov/geo/series/"+gse[:-3]+"nnn/"+gse+"/soft/"+gse+"_family.soft.gz"
 raw=get_bytes(url)
 rec={"url":url,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
 report["sources"][gse]=rec
 series,samples=parse(raw)
 report["samples"][gse]=[]
 for gsm,item in sorted(samples.items()):
  matches=[]
  for field,values in item.items():
   for v in values:
    toks=sorted(set(re.findall(r"\b(?:TAC|TP)[123]\b",v,re.I)))
    if toks:matches.append({"field":field,"value":v[:500],"bulk_count_tokens":toks})
  relation=item.get("!Sample_relation",[])
  samn=sorted(set(re.findall(r"\bSAMN\d+\b"," ".join(relation))))
  r={"gsm":gsm,"title":item.get("!Sample_title",[]),"characteristics":item.get("!Sample_characteristics_ch1",[]),
     "description":item.get("!Sample_description",[])[:7],
     "relation":relation,"linked_BioSample":samn,
     "exact_bulk_column_evidence":matches,
     "explicit_mouse_id_in_geo":None,
     "pooling_proven_absent":False}
  for f,vv in item.items():
   if "mouse id" in f.lower() or "animal id" in f.lower():
    r["explicit_mouse_id_in_geo"]={"field":f,"value":vv}
  report["samples"][gse].append(r)
  print(json.dumps({"gsm":gsm,"title":r["title"],"relation":relation,"count_column_evidence":matches,
                    "sample_mouse_id":r["explicit_mouse_id_in_geo"]},ensure_ascii=False),flush=True)
rec=report["samples"]["GSE327655"]
expected={"GSM9662756":"TAC1","GSM9662757":"TAC2","GSM9662758":"TAC3",
          "GSM9662759":"TP1","GSM9662760":"TP2","GSM9662761":"TP3"}
cross={s["gsm"]:set(y for x in s["exact_bulk_column_evidence"] for y in x["bulk_count_tokens"]) for s in rec}
direct=all(cross.get(gsm)=={bulk} for gsm,bulk in expected.items())
report["mapping_grade"]="DIRECT_EXACT_GSM_SOURCE_METADATA" if direct else "INCOMPLETE_NOT_ADMITTED"
report["mapping_evidence_by_GSM"]={gsm:[x for s in rec if s["gsm"]==gsm for x in s["exact_bulk_column_evidence"]] for gsm in expected}
report["GEO_series_design"]={gse:None for gse in SERIES}
# Linked BioSample records are useful provenance but multiple accessions do not
# themselves prove distinct physical animals or lack of pooling.
for gse,rows in report["samples"].items():
 for x in rows:
  x["BioSample_details"]=[]
  for accession in x["linked_BioSample"][:1]:
   url="https://www.ebi.ac.uk/biosamples/samples/"+accession
   try:
    obj=json.loads(get_bytes(url,limit=200000))
    attrs=obj.get("characteristics",{})
    x["BioSample_details"].append({"source":url,"status":"ACCESSIBLE",
      "biosample_accession":obj.get("accession"),"characteristics":attrs,
      "explicit_individual_animal_id":"NOT_ASSESSED_WITHOUT_AUTHOR_CROSSWALK"})
   except Exception as ex:x["BioSample_details"].append({"source":url,"status":"UNAVAILABLE","error":str(ex)[:180]})
report["gates"]={"WU_EXACT_COUNT_COLUMN_TO_GSM":report["mapping_grade"],
 "CHEN_LIBRARY_TO_UNIQUE_ANIMAL":"NOT_PROVEN",
 "WU_LIBRARY_TO_UNIQUE_ANIMAL":"NOT_PROVEN",
 "BIOLOGICAL_GROUP_INFERENCE":"GEO_CONDITIONS_ONLY",
 "PER_ANIMAL_CELL_PROPORTIONS":"BLOCKED_IF_UNIQUE_ANIMAL_ID_UNPROVEN"}
(OUT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print("TOPA_SOURCE_FIELD_AUDIT_START")
print(json.dumps({"gates":report["gates"],"mapping_evidence_by_GSM":report["mapping_evidence_by_GSM"],
  "BioSample_statuses":{g:[{"gsm":x["gsm"],"relation":x["relation"],"BioSample":x["BioSample_details"]} for x in rows] for g,rows in report["samples"].items()}},ensure_ascii=False))
print("TOPA_SOURCE_FIELD_AUDIT_END")
