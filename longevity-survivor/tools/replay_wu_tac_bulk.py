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
 gene_col=d.columns[0]
 numeric_cols=[]
 for c in d.columns[1:]:
  x=pd.to_numeric(d[c],errors="coerce")
  if len(x)>0 and x.notna().mean()>0.99:numeric_cols.append(c)
 mapped={str(c):infer_column(c) for c in numeric_cols}
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
   "files":[],"assays":{},"firewalls":["RNA_SEQ_BULK != CELL_TYPE_FRACTION","TAC_ANTI_IGG_VS_TAC_ANTI_PD1 != TAC_VS_SHAM","GSM != VERIFIED_INDEPENDENT_MOUSE","NO_PVALUES_UNTIL_BIOLOGICAL_UNIT_CROSSWALK","FPKM != RAW_COUNTS","TRANSCRIPTOMICS != FIBROBLAST_EXIT"]}
for assay,name in (("counts","GSE327655_counts_All_Samples.csv.gz"),("FPKM","GSE327655_FPKM_All_Samples.csv.gz")):
 try:
  p,receipt=acquire(name);report["files"].append(receipt)
  data,gcol,nums,mapped,info=inspect(p)
  info["status"]="INSPECTED"
  if assay=="counts" and nums:
   recognized=[(c,g) for c,g in mapped.items() if g]
   all_unique=len(recognized)==6 and len({x[1] for x in recognized})==6
   if all_unique:
    per={}
    for c,g in recognized:
     cn=next(x for x in nums if str(x)==c)
     total=float(pd.to_numeric(data[cn],errors="coerce").fillna(0).sum())
     per[g]={"source_column":c,"experimental_group":GSM[g][0],"library_total":total,"genes":{}}
     for gene,idxs in info["markers_found_row_indices"].items():
      if len(idxs)==1:
       v=float(pd.to_numeric(data.loc[idxs[0],cn],errors="coerce"))
       per[g]["genes"][gene]={"raw_count":v,"cpm":round(v*1e6/total,6) if total else None}
    info["descriptive_per_GSM"]=per
    info["status"]="COUNTS_CPM_REPLAYED_DESCRIPTIVE_ONLY"
   else:info["status"]="BLOCKED_SAMPLE_COLUMN_MAPPING_UNKNOWN"
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
