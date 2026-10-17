#!/usr/bin/env python3
"""TOPA provisional doublet score audit, per Chen GSE293489 10X GEM library.

Scrublet is sensitive to supplied loading assumptions. Separate samples are
processed independently; never treat a software doublet call as ground truth,
nor remove cells silently. Expected rate 0.06 is an EXPLICIT sensitivity
parameter, not an empirical cell-loading estimate.
"""
import collections,datetime,gzip,hashlib,json,os,pathlib,sys
import numpy as np
from scipy.io import mmread
import scrublet as scr

ROOT=pathlib.Path(os.getenv("TOPA_PD1_ROOT","prior/topa_pd1_acquisition"))
OUT=pathlib.Path(os.getenv("TOPA_DOUBLET_OUT","topa_pd1_doublet"));OUT.mkdir(exist_ok=True,parents=True)
EXPECTED=0.06
geneset={"Cd3d","Cd3e","Dcn","Lum","Lyz2","Tyrobp","Pecam1","Cdh5","Trdc","Trgc1","Trgc2"}
manifest=json.loads((ROOT/"manifest.json").read_text())
verified={x["path"]:x for x in manifest["files"] if x.get("status")=="ACQUIRED"}
def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()
def source(gsm,suffix):
 file=next(iter((ROOT/"GSE293489"/"processed"/gsm).glob("*"+suffix)),None)
 if file is None:raise FileNotFoundError(gsm+" "+suffix)
 k=str(file).removeprefix("prior/")
 rec=verified.get(k)
 if rec is None or sha(file)!=rec["sha256"]:raise ValueError("source checksum mismatch "+str(file))
 return file
def lines(p):
 with gzip.open(p,"rt",errors="replace") as f:return [z.rstrip("\n").split("\t") for z in f]
result={"schema":"janus.topa.chen_doublet_scrublet_provisional.v1",
 "generated_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "source":"Chen GSE293489 four public 10X matrices, acquired by JANUS run 39026401715",
 "algorithm":"Scrublet / Wolock et al., Cell Systems 2019",
 "parameterization":{"expected_doublet_rate_assumed_not_measured":EXPECTED,
  "sim_doublet_ratio":1.5,"n_prin_comps":30,"random_state":20261017,
  "per_library":True,"author_QC":{"min_genes":300,"max_UMIs":40000,"max_mt_fraction":.05}},
 "per_gsm":{},"gates":{},
 "warnings":["SCRUBLET_SCORES_ARE_PROVISIONAL_NOT_EMPIRICAL_TRUTH",
 "THRESHOLD_AUTOMATIC_AND_UNVALIDATED_WITHOUT_EXPERIMENTAL_MULTIPLEX_LABELS",
 "MULTILINEAGE_EXPRESSION_MAY_BE_AMBIENT_OR_VALID_NOT_ONLY_DOUBLETS",
 "BIOLOGICAL_MOUSE_ID_NOT_VERIFIED","NO_PER_MOUSE_STATISTICAL_TESTS"]}
for sample in manifest["samples"]["GSE293489"]:
 gsm=sample["gsm"];info={"gsm":gsm,"group":("SHAM" if "sham" in " ".join(sample["attributes"]).lower() else "MI")}
 try:
  mat=mmread(str(source(gsm,"_matrix.mtx.gz"))).tocsr()
  features=lines(source(gsm,"_features.tsv.gz"))
  source(gsm,"_barcodes.tsv.gz")
  names=[x[1] if len(x)>1 else x[0] for x in features]
  if len(names)!=mat.shape[0]:raise ValueError("genes dimension mismatch")
  mat_csc=mat.tocsc()
  umi=np.asarray(mat_csc.sum(axis=0)).ravel()
  detected=np.diff(mat_csc.indptr)
  mitochondrial=[i for i,g in enumerate(names) if g.startswith("mt-")]
  if len(mitochondrial)<10:raise ValueError("missing mitochondrial genes")
  mt=np.asarray(mat[mitochondrial,:].sum(axis=0)).ravel()
  mtfrac=np.divide(mt,umi,out=np.zeros(len(umi),dtype=np.float32),where=umi>0)
  good=(detected>=300)&(umi<=40000)&(mtfrac<=.05)&(umi>0)
  counts=mat[:,good].T.tocsr()
  if counts.shape[0]<1000:raise ValueError("too few QC cells for robust scrublet run")
  scrub=scr.Scrublet(counts, expected_doublet_rate=EXPECTED,sim_doublet_ratio=1.5,
                     random_state=20261017)
  scores,called=scrub.scrub_doublets(min_counts=2,min_cells=3,
      min_gene_variability_pctl=85,n_prin_comps=30)
  scores=np.asarray(scores,dtype=float)
  if len(scores)!=counts.shape[0] or not np.isfinite(scores).all():raise ValueError("invalid score vector")
  threshold=getattr(scrub,"threshold_",None)
  if threshold is None:
   status="SCORES_ONLY_NO_ADMISSIBLE_AUTOMATIC_THRESHOLD"
   candidates=None
  else:
   status="AUTO_THRESHOLD_SCORES_NOT_PROVEN_DOUBLETS"
   candidates=np.asarray(called,dtype=bool)
  mapping={}
  for i,g in enumerate(names):
   if g in geneset and g not in mapping:mapping[g]=i
  def positive(g):
   idx=mapping.get(g)
   return np.asarray(counts[:,idx].toarray()).ravel()>0 if idx is not None else np.zeros(counts.shape[0],dtype=bool)
  T=positive("Cd3d") & positive("Cd3e")
  fib=positive("Dcn") & positive("Lum")
  myel=positive("Lyz2") & positive("Tyrobp")
  endo=positive("Pecam1") & positive("Cdh5")
  conflict=(T.astype(int)+fib.astype(int)+myel.astype(int)+endo.astype(int))>=2
  info.update({"status":status,"cells_after_original_QC":int(counts.shape[0]),
   "auto_threshold":float(threshold) if threshold is not None else None,
   "scrublet_predicted_doublets_at_assumed_rate":int(candidates.sum()) if candidates is not None else None,
   "scrublet_predicted_fraction":float(candidates.mean()) if candidates is not None else None,
   "score_percentiles":{str(p):float(np.percentile(scores,p)) for p in (0,25,50,75,90,95,99,100)},
   "cross_lineage_positive_markers_n":int(conflict.sum()),
   "cross_lineage_positive_markers_fraction":float(conflict.mean()),
   "doublet_called_and_cross_lineage_positive_n":int(np.sum(candidates&conflict)) if candidates is not None else None,
   "not_a_doublet_truth_label":True})
 except Exception as e:
  info.update({"status":"ERROR","error":type(e).__name__+": "+str(e)[:400]})
 result["per_gsm"][gsm]=info
 print("TOPA_DOUBLET_GSM",json.dumps(info,ensure_ascii=False),flush=True)
result["gates"]={
 "FOUR_GSM_PROVISIONAL_DOUBLETS":"PROVISIONAL_COMPLETED" if all(x["status"].startswith(("AUTO_THRESHOLD","SCORES_ONLY")) for x in result["per_gsm"].values()) else "FAILED_OR_PARTIAL",
 "EXPERIMENTALLY_VALIDATED_DOUBLETS":"NOT_ESTABLISHED",
 "DOUBLETS_REMOVED_IN_CELL_FRACTION":"NO",
 "INDEPENDENT_ANIMAL_IDS":"NOT_VERIFIED",
 "STRICT_PROFIBROTIC_CELL_EXIT":"NOT_ESTABLISHED"}
(OUT/"report.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
print("TOPA_DOUBLET_SUMMARY_START")
print(json.dumps({"gates":result["gates"],"per_gsm":result["per_gsm"]},ensure_ascii=False))
print("TOPA_DOUBLET_SUMMARY_END")
if result["gates"]["FOUR_GSM_PROVISIONAL_DOUBLETS"]!="PROVISIONAL_COMPLETED":sys.exit(2)
