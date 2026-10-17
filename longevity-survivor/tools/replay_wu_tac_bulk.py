#!/usr/bin/env python3
"""Wu mouse TAC bulk counts bounded independent numeric replay; no fabricated biological n."""
import datetime,gzip,hashlib,json,os,pathlib,re,urllib.request
import pandas as pd
OUT=pathlib.Path(os.environ.get("TOPA_WU_OUTPUT","topa_wu_bulk_replay"));OUT.mkdir(parents=True,exist_ok=True)
ROOT="https://ftp.ncbi.nlm.nih.gov/geo/series/GSE327nnn/GSE327655/suppl/"
GSM={"GSM9662756":("TAC_ANTI_IGG",1),"GSM9662757":("TAC_ANTI_IGG",2),"GSM9662758":("TAC_ANTI_IGG",3),
     "GSM9662759":("TAC_ANTI_PD1",1),"GSM9662760":("TAC_ANTI_PD1",2),"GSM9662761":("TAC_ANTI_PD1",3)}
MARKERS=("Cxcl9","Cxcl10","Cxcr3","Pdcd1","Gzmb","Prf1","Postn","Col1a1","Acta2","Trdc","Cd8a","Cd3d","Pdgfra")
def acquire(name):
 url=ROOT+name; req=urllib.request.Request(url,headers={"User-Agent":"JANUS-TOPA-WU-public-replay/1.0"})
 p=OUT/name; limit=20*1024*1024
 with urllib.request.urlopen(req,timeout=60) as f,p.open("wb") as q:
  total=0
  while True:
   b=f.read(262144)
   if not b:break
   total+=len(b)
   if total>limit:raise RuntimeError("per-source cap exceeded")
   q.write(b)
 return p,{"url":url,"path":str(p),"size_bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
def canon(s):return re.sub("[^a-z0-9]","",str(s).lower())
def infer_column(c):
 v=canon(c)
 matches=[]
 for gsm,(group,i) in GSM.items():
  if gsm.lower() in str(c).lower():matches.append(gsm);continue
  if "tac" in v and ("igg" in v or "isotype" in v or "pd1" in v or "pdone" in v):
   typ="TAC_ANTI_IGG" if ("igg" in v or "isotype" in v) and not ("pd1" in v or "pdone" in v) else "TAC_ANTI_PD1" if ("pd1" in v or "pdone" in v) and not ("igg" in v or "isotype" in v) else None
   if typ==group and v.endswith(str(i)):matches.append(gsm)
 return matches[0] if len(matches)==1 else None
def inspect(p):
 d=pd.read_csv(p,compression="gzip",low_memory=False)
 names=[str(x) for x in d.columns]
 gene_col="gene_name" if "gene_name" in d.columns else d.columns[0]
 # Exclude numeric annotation fields (gene_start, gene_end, gene_length).
 numeric_cols=[c for c in ("TAC1","TAC2","TAC3","TP1","TP2","TP3") if c in d.columns and pd.to_numeric(d[c],errors="coerce").notna().mean()>0.99]
 # These labels have not yet been linked by the authors to exact GSM IDs.
 mapped={str(c):None for c in numeric_cols}
 rowkey=d[gene_col].astype(str)
 target={z:[] for z in MARKERS}
 for gene in MARKERS:
  idx=rowkey.str.lower().eq(gene.lower())
  if idx.any():
   target[gene]=[int(i) for i in d.index[idx]]
 result={"shape":list(d.shape),"columns":names,"gene_identifier_column":str(gene_col),
   "gene_examples":rowkey.head(8).tolist(),"numeric_columns":list(map(str,numeric_cols)),
   "explicitly_resolved_columns":mapped,"markers_found_row_indices":target,
   "ambiguous_genes":[k for k,v in target.items() if len(v)>1]}
 return d,gene_col,numeric_cols,mapped,result
report={"schema":"janus.topa.wu_tac_bulk_replay.v1","created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
   "source_series":"GSE327655","groups":{"TAC_ANTI_IGG":3,"TAC_ANTI_PD1":3},
   "files":[],"assays":{},"firewalls":["RNA_SEQ_BULK != CELL_TYPE_FRACTION","TAC1_3_VS_TP1_3_SOURCE_COLUMNS != VERIFIED_GSM_OR_TREATMENT_MAPPING","GSM != VERIFIED_INDEPENDENT_MOUSE","NO_PVALUES_UNTIL_BIOLOGICAL_UNIT_CROSSWALK","FPKM != RAW_COUNTS","TRANSCRIPTOMICS != FIBROBLAST_EXIT"]}
for assay,name in (("counts","GSE327655_counts_All_Samples.csv.gz"),("FPKM","GSE327655_FPKM_All_Samples.csv.gz")):
 try:
  p,receipt=acquire(name);report["files"].append(receipt)
  data,gcol,nums,mapped,info=inspect(p)
  info["status"]="INSPECTED"
  if assay=="counts" and set(map(str,nums))=={"TAC1","TAC2","TAC3","TP1","TP2","TP3"}:
   per={}
   for c in nums:
    total=float(pd.to_numeric(data[c],errors="coerce").fillna(0).sum())
    per[str(c)]={"source_column":str(c),"group_label_in_data":"TAC" if str(c).startswith("TAC") else "TP",
       "GSM_crosswalk":"NOT_VERIFIED", "total_library_counts":total, "genes":{}}
    for gene,idxs in info["markers_found_row_indices"].items():
     if len(idxs)==1:
      v=float(pd.to_numeric(data.loc[idxs[0],c],errors="coerce"))
      per[str(c)]["genes"][gene]={"raw_count":v,"cpm":round(v*1e6/total,6) if total else None}
   info["descriptive_per_source_column"]=per
   groups={}
   for gene in MARKERS:
    groupvalues={}
    for grp,heads in (("TAC",("TAC1","TAC2","TAC3")),("TP",("TP1","TP2","TP3"))):
     vals=[per[c]["genes"][gene]["cpm"] for c in heads if gene in per[c]["genes"]]
     groupvalues[grp]=vals
    if len(groupvalues["TAC"])==3 and len(groupvalues["TP"])==3:
     a=sum(groupvalues["TAC"])/3;b=sum(groupvalues["TP"])/3
     groups[gene]={"TAC_CPM":groupvalues["TAC"],"TP_CPM":groupvalues["TP"],
       "TAC_mean_CPM":round(a,6),"TP_mean_CPM":round(b,6),
       "TP_over_TAC_ratio":round(b/a,6) if a else None}
   info["descriptive_group_comparison"]=groups
   info["status"]="COUNTS_CPM_REPLAYED_SOURCE_COLUMN_LABELS_ONLY"
   info["caution"]="TAC1..3 and TP1..3 not yet independently mapped to specific GSMs/anti-IgG vs anti-PD1; no p-values"
  else:info["status"]="BLOCKED_UNRECOGNIZED_SOURCE_COUNT_COLUMNS"
  report["assays"][assay]=info
 except Exception as e:report["assays"][assay]={"status":"ERROR","error":str(e)[:300]}
report["gates"]={"OFFICIAL_SOURCE_ACQUISITION":"PASS" if len(report["files"])==2 else "FAIL",
   "BULK_CPM_REPLAY":report["assays"].get("counts",{}).get("status"),
   "INDEPENDENT_MOUSE_N":"NOT_VERIFIED","INFERENTIAL_PVALUES":"NOT_CALCULATED",
   "CELL_TYPE_PROPORTIONS":"NOT_APPLICABLE_BULK","FIBROBLAST_STRICT_EXIT":"NOT_ESTABLISHED"}
(OUT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
for item in report["files"]:print("SOURCE_RECEIPT",json.dumps(item))
print("TOPA_WU_NUMERIC_SUMMARY_START")
print(json.dumps({"gates":report["gates"],"assays":report["assays"]},indent=2))
print("TOPA_WU_NUMERIC_SUMMARY_END")
if report["gates"]["OFFICIAL_SOURCE_ACQUISITION"]!="PASS":raise SystemExit(2)
