#!/usr/bin/env python3
"""Auditable immune- and MI-domain reference control (NOT labelled ground truth).
GSE163465 CD45+ Sham and Day 7 post-MI independent from GSE293489.
No cell-type model is validated without an author barcode->label crosswalk.
"""
import collections,datetime,gzip,hashlib,json,os,pathlib,urllib.request
import numpy as np
from scipy.io import mmread

ROOT=pathlib.Path(os.getenv("TOPA_PD1_ROOT","prior/topa_pd1_acquisition"))
OUT=pathlib.Path(os.getenv("TOPA_IMMUNE_OUT","topa_postmi_immune_reference"))
OUT.mkdir(parents=True,exist_ok=True)
SERIES="GSE163465"
SAMPLES={"GSM4985022":"CD45_SHAM","GSM4985024":"CD45_DAY7_MI"}
SOFT="https://ftp.ncbi.nlm.nih.gov/geo/series/GSE163nnn/GSE163465/soft/GSE163465_family.soft.gz"
PANELS={
 "T_CELL_Cd3d_Cd3e":("Cd3d","Cd3e"),
 "T_CELL_Trac_Cd3e":("Trac","Cd3e"),
 "MYELOID_Lyz2_Tyrobp":("Lyz2","Tyrobp"),
 "MACROPHAGE_Csf1r_Adgre1":("Csf1r","Adgre1"),
 "FIBROBLAST_Dcn_Lum":("Dcn","Lum"),
 "ENDOTHELIAL_Pecam1_Cdh5":("Pecam1","Cdh5"),
 "GAMMA_DELTA_Trdc_Trgc1":("Trdc","Trgc1")}
def sha(path):
 h=hashlib.sha256()
 with open(path,"rb") as f:
  for chunk in iter(lambda:f.read(1<<20),b""):h.update(chunk)
 return h.hexdigest()
def acquire(url,path,limit):
 if url.startswith("ftp://ftp.ncbi.nlm.nih.gov/"):
  url="https://ftp.ncbi.nlm.nih.gov/"+url[len("ftp://ftp.ncbi.nlm.nih.gov/"):]
 if not url.startswith("https://ftp.ncbi.nlm.nih.gov/"):
  raise ValueError("untrusted GEO source location "+url)
 req=urllib.request.Request(url,headers={"User-Agent":"JANUS-TOPA-postMI-primary-audit/1.0"})
 count=0
 with urllib.request.urlopen(req,timeout=75) as r,open(path,"wb") as f:
  while True:
   b=r.read(1<<19)
   if not b:break
   count+=len(b)
   if count>limit:raise ValueError("download cap exceeded "+str(path))
   f.write(b)
 return {"url":url,"sha256":sha(path),"size_bytes":count}
def gzlines(path):
 with gzip.open(path,"rt",encoding="utf-8",errors="replace") as f:
  return [x.rstrip("\r\n").split("\t") for x in f if x.strip()]
def geo_metadata(path):
 sample=None
 result={}
 with gzip.open(path,"rt",encoding="utf-8",errors="replace") as f:
  for raw in f:
   line=raw.strip()
   if line.startswith("^SAMPLE = "):
    sample=line.split(" = ",1)[1]
    if sample in SAMPLES:result[sample]={"files":[],"titles":[],"characteristics":[]}
   elif sample in result and line.startswith("!Sample_") and " = " in line:
    key,value=line.split(" = ",1)
    if key=="!Sample_supplementary_file":result[sample]["files"].append(value)
    elif key=="!Sample_title":result[sample]["titles"].append(value)
    elif key=="!Sample_characteristics_ch1":result[sample]["characteristics"].append(value)
 return result
manifest=json.loads((ROOT/"manifest.json").read_text())
verified={x["path"]:x for x in manifest["files"] if x.get("status")=="ACQUIRED"}
report={"schema":"janus.topa.postmi_immune_reference_marker_control.v1",
 "generated_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "primary_sources":{"Chen":"GSE293489","independent_immune_atlas":SERIES},
 "study_independence":"Different GEO series, not evidence of biological replicate independence",
 "reference_selection":"GSM4985022 CD45+ sham; GSM4985024 CD45+ day7 MI",
 "sample_level_geo_url_fallback":"SAMPLE_URL_CONSTRUCTED_IF_FAMILY_SOFT_LACKS_PER_FILE_LINK__VALIDATE_HTTP_BYTES_HASH_AND_SHAPE",
 "source_bytes":{},"reference_metadata":{},"per_gsm":{},
 "method":{"QC":"detected genes >=300, UMI <=40000, mitochondrial <=5%",
  "marker_rule":"Both prespecified gene markers have >=1 UMI, descriptive only",
  "panels":PANELS},
 "gates":{"EXTERNAL_POSTMI_IMMUNE_MATRICES":"PENDING",
          "AUTHOR_BARCODE_TO_CELLTYPE_ANNOTATIONS":"NOT_IDENTIFIED",
          "INDEPENDENT_SUPERVISED_CELL_LABEL_VALIDATION":"BLOCKED",
          "GAMMA_DELTA_T_SUBTYPE_VALIDATION":"NOT_ESTABLISHED",
          "ANIMAL_LEVEL_PROPORTIONS_AND_CI":"LOCKED",
          "PROFIBROTIC_FATE_EXIT":"NOT_ESTABLISHED"},
 "warnings":["CD45_ENRICHED_REFERENCE_NOT_UNBIASED_WHOLE_HEART",
  "MARKER_COPOSITIVITY_IS_NOT_GROUND_TRUTH_OR_PER_ANIMAL_FRACTION",
  "REFERENCE_MI_TIMEPOINT_AND_PREPARATION_DIFFER_FROM_CHEN",
  "NO_PSEUDOREPLICATION_OR_PER_ANIMAL_CI_WITHOUT_MOUSE_CROSSWALK",
  "DO_NOT_CREATE_SUPERVISED_LABELS_FROM_MARKER_PROXY"]}
def marker_report(mtx,features,barcodes,gsm,group):
 names=[x[1] if len(x)>1 else x[0] for x in features]
 if len(names)!=mtx.shape[0] or len(barcodes)!=mtx.shape[1]:
  raise ValueError("10X triplet dimension mismatch "+gsm)
 if len(set(x[0] for x in barcodes))!=len(barcodes):
  raise ValueError("nonunique 10X barcodes "+gsm)
 cols=mtx.tocsc()
 umi=np.asarray(cols.sum(axis=0)).ravel()
 detected=np.diff(cols.indptr)
 mti=[i for i,g in enumerate(names) if g.lower().startswith("mt-")]
 if len(mti)<10:raise ValueError("insufficient MT gene panel "+gsm)
 mt=np.asarray(mtx[mti,:].sum(axis=0)).ravel()
 frac=np.divide(mt,umi,out=np.zeros(len(umi),dtype=np.float32),where=umi>0)
 mask=(detected>=300)&(umi<=40000)&(frac<=.05)&(umi>0)
 indices={}
 for i,g in enumerate(names):
  if g.lower() not in indices:indices[g.lower()]=i
 pos={}
 for pname,(ga,gb) in PANELS.items():
  if ga.lower() not in indices or gb.lower() not in indices:
   pos[pname]=None
   continue
  a=np.asarray(mtx[indices[ga.lower()],:].toarray()).ravel()>0
  b=np.asarray(mtx[indices[gb.lower()],:].toarray()).ravel()>0
  pos[pname]=a&b&mask
 eligible=int(mask.sum())
 summary={}
 for key,v in pos.items():
  summary[key]={"markers":PANELS[key],"source_feature_found":v is not None,
   "qc_positive_n":int(v.sum()) if v is not None else None,
   "qc_positive_fraction_per_library_not_animal":float(v.sum()/eligible) if v is not None and eligible else None}
 return {"gsm":gsm,"group":group,"raw_barcodes":len(barcodes),
         "qc_pass_cells":eligible,"source_feature_count":len(names),
         "marker_evidence":summary,"interpretation":"DESCRIPTIVE_MARKER_CONTROL_NOT_VALIDATED_CELL_LABELS"}
softpath=OUT/"GSE163465_family.soft.gz"
report["source_bytes"]["GSE163465_SOFT"]=acquire(SOFT,softpath,16000000)
md=geo_metadata(softpath)
if set(md)!=set(SAMPLES):raise ValueError("incomplete independent series sample metadata")
report["reference_metadata"]=md
for gsm,group in SAMPLES.items():
 entry=md[gsm]
 urls={}
 for suffix in ("_matrix.mtx.gz","_features.tsv.gz","_barcodes.tsv.gz"):
  matches=[x for x in entry["files"] if x.endswith(suffix)]
  if len(matches)==1:
   urls[suffix]=matches[0]
  elif len(matches)==0:
   # GEO's family SOFT does not always list sample-level processed files.
   # Use the canonical public sample supplementary naming, then validate
   # actual HTTP response, byte limit, dimensions and SHA256 below.
   stage="Sham" if gsm=="GSM4985022" else "Day_7"
   urls[suffix]="https://ftp.ncbi.nlm.nih.gov/geo/samples/GSM4985nnn/"+gsm+"/suppl/"+gsm+"_"+stage+suffix
  else:
   raise ValueError("ambiguous source triplet "+gsm+" "+suffix+" "+str(matches))
 local={}
 for suffix,url in urls.items():
  target=OUT/(gsm+suffix)
  local[suffix]=target
  report["source_bytes"][gsm+suffix]=acquire(url,target,90000000 if "matrix" in suffix else 2000000)
 m=mmread(str(local["_matrix.mtx.gz"])).tocsr()
 feat=gzlines(local["_features.tsv.gz"])
 bar=gzlines(local["_barcodes.tsv.gz"])
 report["per_gsm"][gsm]=marker_report(m,feat,bar,gsm,group)
 print("INDEPENDENT_GSM",json.dumps(report["per_gsm"][gsm]),flush=True)
 del m
for rec in manifest["samples"]["GSE293489"]:
 gsm=rec["gsm"]
 paths={}
 for suffix in ("_matrix.mtx.gz","_features.tsv.gz","_barcodes.tsv.gz"):
  p=next(iter((ROOT/"GSE293489"/"processed"/gsm).glob("*"+suffix)),None)
  if p is None:raise ValueError("missing Chen matrix "+gsm+" "+suffix)
  key=str(p).removeprefix("prior/")
  if key not in verified or sha(p)!=verified[key]["sha256"]:
   raise ValueError("source SHA failure "+gsm+" "+suffix)
  paths[suffix]=p
 m=mmread(str(paths["_matrix.mtx.gz"])).tocsr()
 grp="SHAM" if "sham" in " ".join(rec["attributes"]).lower() else "MI"
 report["per_gsm"][gsm]=marker_report(m,gzlines(paths["_features.tsv.gz"]),
                                    gzlines(paths["_barcodes.tsv.gz"]),gsm,grp)
 print("CHEN_GSM",json.dumps(report["per_gsm"][gsm]),flush=True)
 del m
report["gates"]["EXTERNAL_POSTMI_IMMUNE_MATRICES"]="ACQUIRED_HASHED_DIMENSION_AUDITED"
report["gates"]["INDEPENDENT_IMMUNE_MARKER_CONTROL"]="DESCRIPTIVE_COMPLETE_NOT_LABEL_VALIDATION"
(OUT/"report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
print("IMMUNE_REFERENCE_GATE",json.dumps(report["gates"]))
