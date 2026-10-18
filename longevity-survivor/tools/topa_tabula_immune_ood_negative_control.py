#!/usr/bin/env python3
"""Independent OOD negative-control of the frozen Tabula Muris 4-class model.

Transfer exactly the existing healthy-heart/aorta classifier onto publicly
available GSE163465 CD45+ Sham and Day7 MI cells. Prespecified immune marker
co-positive cells are negative controls for the model's 4 nonimmune classes.
Not a supervised ground-truth validation of immune or gamma-delta T labels.
"""
import datetime,gzip,hashlib,json,os,pathlib,urllib.request
import numpy as np
from scipy.io import mmread
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from topa_tabula_muris_chen_transfer import (
 load_reference,features,reads,map_gene_indices,expression,sample_files)
OUT=pathlib.Path(os.environ.get("TOPA_IMMUNE_OOD_OUT","topa_immune_ood"))
OUT.mkdir(exist_ok=True,parents=True)
ATLAS={"GSM4985022":"Sham","GSM4985024":"Day_7"}
EXPECTED_FEATURE_SHA="fc45a9ba5607276d5878790fb85059c0595a9447f46f653f9be2a20d4e2983e8"
def sha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for part in iter(lambda:f.read(1<<20),b""):h.update(part)
 return h.hexdigest()
def acquire(url,p,limit=90000000):
 req=urllib.request.Request(url,headers={"User-Agent":"JANUS-TOPA-immune-reference-OOD/1.0"})
 with urllib.request.urlopen(req,timeout=75) as r,open(p,"wb") as f:
  n=0
  while True:
   b=r.read(1<<19)
   if not b:break
   n+=len(b)
   if n>limit:raise ValueError("source cap exceeded")
   f.write(b)
 return {"url":url,"bytes":n,"sha256":sha(p)}
def lines(p):
 with gzip.open(p,"rt",encoding="utf-8") as f:return [l.rstrip("\r\n").split("\t") for l in f if l.strip()]
ref,refgenes,keep,y,refprov=load_reference()
mapp,_=map_gene_indices(refgenes)
chenfp=sample_files("GSM8884015")[1]
chen_genes=features(reads(chenfp))
chenmap,_=map_gene_indices(chen_genes)
common=sorted(set(mapp)&set(chenmap))
common=[g for g in common if not g.startswith(("mt-","rpl","rps"))]
ref0=expression(ref,refgenes,common,keep).toarray()
v=ref0.var(axis=0);freq=(ref0>0).mean(axis=0)
eligible=(freq>.02)&(freq<.98)
order=np.argsort(np.where(eligible,v,-1))[-1200:]
chosen=[int(i) for i in order if eligible[int(i)]]
selected=[common[i] for i in chosen]
digest=hashlib.sha256("\n".join(selected).encode()).hexdigest()
if digest!=EXPECTED_FEATURE_SHA:raise ValueError("frozen reference feature selection drift")
rr=ref0[:,chosen]
tr,te=train_test_split(np.arange(len(y)),test_size=.30,stratify=y,random_state=20261017)
clf=LogisticRegression(max_iter=600,class_weight="balanced",random_state=20261017)
clf.fit(rr[tr],y[tr])
heldp=clf.predict_proba(rr[te])
maxp=heldp.max(axis=1)
hit=(clf.classes_[heldp.argmax(axis=1)]==y[te])
if not hit.any():raise ValueError("heldout classifier has zero correct")
threshold=max(.75,float(np.percentile(maxp[hit],10)))
report={"schema":"janus.topa.tabula_muris_classifier_postmi_cd45_ood_negative_control.v1",
 "recorded_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "reference":refprov,
 "model":{"four_nonimmune_classes":list(clf.classes_),
          "feature_sha256":digest,
          "threshold":threshold,
          "training_reference_cells":len(tr),
          "calibration_heldout_cells_same_reference":len(te)},
 "provenance":{"reference":"GSM3040902 Tabula Muris original author annotations",
    "external_series":"GSE163465 CD45+ sham and day7 MI",
    "external_same_population_as_chen":False,
    "original_transfer_reference":"run 39068393213 / commit 00f335da8c98f94235be3e1ddd8a575931fda941"},
 "per_gsm":{},"files":{},
 "gates":{"MODEL_FEATURE_LIST_REPLAY":"PASS",
          "IMMUNE_DOMAIN_NEGATIVE_CONTROL":"PENDING",
          "INDEPENDENT_SUPERVISED_T_LABEL_VALIDATION":"BLOCKED_NO_BARCODE_AUTHOR_CELL_LABELS",
          "GAMMA_DELTA_T_VALIDATION":"NOT_ESTABLISHED",
          "CHEN_ANIMAL_INDEPENDENCE":"NOT_VERIFIED",
          "ANIMAL_LEVEL_INFERENCE":"LOCKED",
          "STRICT_CAUSAL_EXIT":"NOT_ESTABLISHED"},
 "warnings":["REFERENCE_HOLDOUT_FROM_SAME_ORIGINAL_ATLAS_NOT_INDEPENDENT_ANIMAL_TEST",
  "CD45_ENRICHED_REFERENCE_MAY_HAVE_CONTAMINATING_NONIMMUNE_CELLS",
  "T_OR_MYELOID_MARKER_COPOSITIVITY_NOT_AUTHOR_GROUND_TRUTH",
  "ACCEPTANCE_OF_NONIMMUNE_LABEL_FOR_MARKER_SUPPORTED_CELL_NE_CONFIRMED_MISCLASSIFICATION",
  "HIGH_SOFTMAX_CONFIDENCE_NE_POSTMI_IMMUNE_RELIABILITY"]}
for gsm,stage in ATLAS.items():
 d={}
 for suffix in ("_matrix.mtx.gz","_features.tsv.gz","_barcodes.tsv.gz"):
  url="https://ftp.ncbi.nlm.nih.gov/geo/samples/GSM4985nnn/"+gsm+"/suppl/"+gsm+"_"+stage+suffix
  p=OUT/(gsm+suffix)
  d[suffix]=p
  report["files"][gsm+suffix]=acquire(url,p,90000000 if "matrix" in suffix else 2000000)
 mat=mmread(str(d["_matrix.mtx.gz"])).tocsr()
 genes=features(reads(d["_features.tsv.gz"]))
 bars=lines(d["_barcodes.tsv.gz"])
 if len(genes)!=mat.shape[0] or len(bars)!=mat.shape[1]:raise ValueError("GEO triplet mismatch "+gsm)
 m=mat.tocsc()
 umi=np.asarray(m.sum(axis=0)).ravel()
 detected=np.diff(m.indptr)
 mtidx=[i for i,g in enumerate(genes) if g.lower().startswith("mt-")]
 mt=np.asarray(mat[mtidx,:].sum(axis=0)).ravel()
 mtfrac=np.divide(mt,umi,out=np.zeros(len(umi),dtype=np.float32),where=umi>0)
 good=(detected>=300)&(umi<=40000)&(mtfrac<=.05)&(umi>0)
 gene_map,_=map_gene_indices(genes)
 if not set(selected).issubset(set(gene_map)):raise ValueError("reference feature mismatch "+gsm)
 def marker(a,b):
  if a.lower() not in gene_map or b.lower() not in gene_map:return None
  v1=np.asarray(mat[gene_map[a.lower()],:].toarray()).ravel()>0
  v2=np.asarray(mat[gene_map[b.lower()],:].toarray()).ravel()>0
  return (v1&v2)[good]
 t=marker("Cd3d","Cd3e")
 myel=marker("Lyz2","Tyrobp")
 if t is None or myel is None:raise ValueError("immune marker controls absent")
 x=expression(mat,genes,selected,good).toarray()
 probs=clf.predict_proba(x)
 accepted=(probs.max(axis=1)>=threshold)
 pred=clf.classes_[probs.argmax(axis=1)]
 supported=t|myel
 def stats(sel):
  return {"n":int(sel.sum()),
          "abstained":int((sel&(~accepted)).sum()),
          "accepted_nonimmune_class":int((sel&accepted).sum()),
          "accepted_fraction_conditional_on_marker_support":float((sel&accepted).sum()/sel.sum()) if sel.any() else None,
          "accepted_classes":{key:int((sel&accepted&(pred==key)).sum()) for key in clf.classes_}}
 info={"gsm":gsm,"condition":"CD45_SHAM" if stage=="Sham" else "CD45_MI_DAY7",
       "qc_cells":int(good.sum()),
       "all_cells":{"n":int(good.sum()),"abstained":int((~accepted).sum()),
                    "accepted_nonimmune_model_class":int(accepted.sum())},
       "T_pair_positive":stats(t),
       "myeloid_pair_positive":stats(myel),
       "either_immune_marker_pair_positive":stats(supported),
       "label_validity":"NEGATIVE_CONTROL_NONIMMUNE_MODEL_ONLY__NOT_AUTHOR_CELLTYPE_TRUTH"}
 report["per_gsm"][gsm]=info
 print("IMMUNE_OOD_GSM",json.dumps(info),flush=True)
 del mat,m,x,probs
report["gates"]["IMMUNE_DOMAIN_NEGATIVE_CONTROL"]="QUANTIFIED_NONIMMUNE_MODEL_ACCEPTANCE_WITHOUT_AUTHOR_LABEL_TRUTH"
(OUT/"report.json").write_text(json.dumps(report,indent=2)+"\n")
print("IMMUNE_OOD_GATE",json.dumps(report["gates"]))
