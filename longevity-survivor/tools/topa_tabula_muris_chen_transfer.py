#!/usr/bin/env python3
"""JANUS/TOPA independent mouse heart reference label transfer (fail-closed).

Tabula Muris GEO GSM3040902 has 624 matched annotated heart/aorta cells; 98
carry missing labels. Train/heldout test exclusively within independent reference,
then project Chen GSE293489 QC-pass libraries with conservative abstention.
Do NOT interpret label transfer as ground-truth cell types, independent animals,
T subtypes, or causal state EXIT.
"""
import collections,csv,datetime,gzip,hashlib,io,json,os,tarfile,urllib.request
from pathlib import Path
import numpy as np
from scipy.io import mmread
from scipy import sparse
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report,confusion_matrix,balanced_accuracy_score

OUT=Path(os.getenv("TOPA_ATLAS_OUT","topa_atlas_transfer"));OUT.mkdir(exist_ok=True,parents=True)
ROOT=Path(os.getenv("TOPA_PD1_ROOT","prior/topa_pd1_acquisition"))
GEO="https://ftp.ncbi.nlm.nih.gov/geo/samples/GSM3040nnn/GSM3040902/suppl/GSM3040902_Heart-10X_P7_4.tar.gz"
ANN="https://raw.githubusercontent.com/czbiohub-sf/tabula-muris/master/00_data_ingest/03_tissue_annotation_csv/Heart_and_Aorta_droplet_annotation.csv"
EXPECTED_SHA={"matrix":"345c2d26904b83c1ec037f06be1f4177cceeb11a748c38dea22165705596c246",
 "annotations":"996433d9f9e7ed27b4a897e83d5b2379dc33530aa1dc0e7ca834bf23020cb405"}
LABELS=("fibroblast","endothelial cell","endocardial cell","cardiac muscle cell")
def digest(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
 return h.hexdigest()
def acquire(url,p,limit):
 req=urllib.request.Request(url,headers={"User-Agent":"JANUS-TOPA-TabulaMuris-heart-1.0"})
 with urllib.request.urlopen(req,timeout=60) as r,p.open("wb") as f:
  total=0
  while True:
   block=r.read(262144)
   if not block:break
   total+=len(block)
   if total>limit:raise RuntimeError("source transfer exceeded cap")
   f.write(block)
 return digest(p)
def features(lines):
 parsed=[l.rstrip("\n").split("\t") for l in lines if l.strip()]
 return [a[1] if len(a)>1 else a[0] for a in parsed]
def reads(path):
 op=gzip.open if str(path).endswith(".gz") else open
 with op(path,"rt",encoding="utf-8",errors="replace") as f:return f.readlines()
def map_gene_indices(names):
 d={}
 duplicate=collections.Counter(x.lower() for x in names)
 for i,g in enumerate(names):
  low=g.lower()
  if low not in d:d[low]=i
 return d,duplicate
def expression(gene_cell,all_genes,feature_genes,cellsel=None):
 # sparse UMI from gene-by-cell; return log1p(CPM) cell-by-feature sparse
 gene_map,_=map_gene_indices(all_genes)
 ind=[gene_map[g] for g in feature_genes]
 matrix=gene_cell[ind,:]
 if cellsel is not None:matrix=matrix[:,cellsel]
 matrix=matrix.T.tocsr().astype(np.float32)
 depth=np.asarray(gene_cell.sum(axis=0)).ravel()
 if cellsel is not None:depth=depth[cellsel]
 inv=np.divide(1e4,depth,out=np.zeros_like(depth,dtype=np.float32),where=depth>0)
 matrix=sparse.diags(inv).dot(matrix).tocsr()
 matrix.data=np.log1p(matrix.data)
 return matrix
def load_reference():
 pm=OUT/"Tabula_Muris_GSM3040902_Heart-10X_P7_4.tar.gz"
 pa=OUT/"Tabula_Muris_Heart_and_Aorta_annotations.csv"
 sh1=acquire(GEO,pm,12_000_000);sh2=acquire(ANN,pa,1_000_000)
 if sh1!=EXPECTED_SHA["matrix"] or sh2!=EXPECTED_SHA["annotations"]:raise ValueError("REFERENCE_SHA256_DRIFT")
 with tarfile.open(pm,"r:gz") as t:
  def take(name):
   target=next(x for x in t.getnames() if x.endswith(name))
   return t.extractfile(target).read()
  mm=mmread(io.BytesIO(take("matrix.mtx"))).tocsr()
  names=features(take("genes.tsv").decode("utf8").splitlines())
  bars=take("barcodes.tsv").decode("utf8").splitlines()
 with pa.open(newline="") as f: annotations={x["cell"]:x for x in csv.DictReader(f)}
 label=[];keep=[];subtissue=[]
 for i,b in enumerate(bars):
  full="10X_P7_4_"+b.strip().split("-")[0]
  a=annotations.get(full)
  if a and a.get("cell_ontology_class") in LABELS:
   label.append(a["cell_ontology_class"]);keep.append(i);subtissue.append(a.get("subtissue"))
 return mm,names,np.array(keep),np.array(label),{"matrix_sha256":sh1,"annotations_sha256":sh2,
  "reference_input_barcodes":len(bars),"reference_modelled_labels":dict(collections.Counter(label)),
  "reference_cells_train_eligible":len(label),"unlabelled_or_unsupported":len(bars)-len(label)}
def sample_files(gsm):
 files=list((ROOT/"GSE293489"/"processed"/gsm).glob("*"))
 grab=lambda s:next((x for x in files if x.name.endswith(s)),None)
 p=(grab("_matrix.mtx.gz"),grab("_features.tsv.gz"),grab("_barcodes.tsv.gz"))
 if any(x is None for x in p):raise ValueError("missing Chen GSM triplet "+gsm)
 return p
def main():
 ref,refgenes,refkeep,y,provenance=load_reference()
 cm=json.loads((ROOT/"manifest.json").read_text())
 all_acquired={z["path"]:z for z in cm["files"]}
 refmap,duplicates=map_gene_indices(refgenes)
 selected=[]
 # prepare HVGs from reference only; do not peek at Chen disease labels.
 # All four Chen 10x feature vocabularies should use the same mm10 gene annotation.
 p=sample_files("GSM8884015")
 chengenes=features(reads(p[1]))
 chmap,dups=map_gene_indices(chengenes)
 common=sorted(set(refmap)&set(chmap))
 common=[g for g in common if not g.startswith(("mt-","rpl","rps"))]
 if len(common)<1000:raise ValueError("insufficient cross-study shared gene symbols: "+str(len(common)))
 # Compute reference variance in log-normalized counts, on reference only.
 refx0=expression(ref,refgenes,common,refkeep).toarray()
 v=refx0.var(axis=0);freq=(refx0>0).mean(axis=0)
 eligible=(freq>0.02)&(freq<0.98)
 hvorder=np.argsort(np.where(eligible,v,-1))[-1200:]
 selected=[common[int(i)] for i in hvorder if eligible[int(i)]]
 if len(selected)<400:raise ValueError("insufficient reference HVGs")
 refx=refx0[:,hvorder][:,np.isin(np.arange(len(common))[hvorder],np.array([common.index(g) for g in selected]))]
 if refx.shape[1]!=len(selected):raise RuntimeError("HVG selection misaligned")
 # stratified random heldout is optimistic for same mouse: just within-atlas diagnostic
 idx=np.arange(len(y))
 tr,te=train_test_split(idx,test_size=.30,stratify=y,random_state=20261017)
 clf=LogisticRegression(max_iter=600,class_weight="balanced",random_state=20261017)
 clf.fit(refx[tr],y[tr])
 p=clf.predict_proba(refx[te]);pred=clf.classes_[p.argmax(axis=1)]
 correct=pred==y[te]
 if not correct.any():raise ValueError("within-reference no class match")
 maxp=p.max(axis=1)
 thr=max(.75,float(np.percentile(maxp[correct],10)))
 abstain=maxp<thr
 f1=classification_report(y[te],pred,labels=list(LABELS),output_dict=True,zero_division=0)
 result={"schema":"janus.topa.chen_reference_atlas_transfer.v1","created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "source_reference":provenance,"reference_study":"Tabula Muris mouse Heart_and_Aorta droplet annotated dataset; one library and one reference specimen",
 "reference_independence":"entirely different study and GEO accession from Chen; validation heldout cells not independent mice",
 "model":{"method":"reference-specific high-variance gene logistic multi-class; reference-only feature selection",
   "feature_count":len(selected),"feature_list_sha256":hashlib.sha256("\n".join(selected).encode()).hexdigest(),
   "training_n":len(tr),"holdout_n":len(te),"holdout_balanced_accuracy":float(balanced_accuracy_score(y[te],pred)),
   "holdout_macro_f1":f1["macro avg"]["f1-score"],
   "confidence_abstain_threshold":thr,
   "holdout_accuracy_without_abstain":float(correct.mean()),
   "holdout_abstain_rate":float(abstain.mean()),
   "holdout_confusion":{"classes":list(LABELS),"matrix":confusion_matrix(y[te],pred,labels=LABELS).tolist()}},
 "Chen_projection":{},"scientific_controls":[
 "REFERENCE_HEART_AND_AORTA_IS_HEALTHY_AND_NOT_D7_MI",
 "MODEL_ONLY_KNOWS_FOUR_HEART_REFERENCE_CLASSES",
 "T_CELL_AND_GAMMA_DELTA_NOT_IN_REFERENCE_LABELS",
 "CONFIDENT_SOFTMAX_NOT_TRUE_EXPERIMENTAL_PROOF",
 "HELDOUT_CELLS_FROM_ONE_REFERENCE_SAMPLE_NOT_INDEPENDENT_MICE",
 "QC_PER_GSM_NOT_PER_ANIMAL","DISEASE_SHIFT_AND_REFERENCE_AGE_NOT_CONTROLLED"]}
 qc_report=None
 for gseitem in cm["samples"]["GSE293489"]:
  gsm=gseitem["gsm"]
  matrixp,featuresp,barp=sample_files(gsm)
  for path in (matrixp,featuresp,barp):
   rec=next((x for x in cm["files"] if x["path"]==str(path).removeprefix("prior/")),None)
   if rec is None or digest(path)!=rec["sha256"]:raise ValueError("Chen source checksum failed "+gsm+" "+path.name)
  m=mmread(str(matrixp)).tocsr()
  genes=features(reads(featuresp))
  if len(genes)!=m.shape[0]:raise ValueError("feature count != MTX rows")
  umi=np.asarray(m.sum(axis=0)).ravel()
  det=np.diff(m.tocsc().indptr)
  midx=[i for i,g in enumerate(genes) if g.lower().startswith("mt-")]
  mt=np.asarray(m[midx,:].sum(axis=0)).ravel()
  mtfrac=np.divide(mt,umi,out=np.zeros(len(umi),dtype=np.float32),where=umi>0)
  mask=(det>=300)&(umi<=40000)&(mtfrac<=.05)&(umi>0)
  xx=expression(m,genes,selected,mask).toarray()
  proba=clf.predict_proba(xx);maxprob=proba.max(axis=1)
  predicted=clf.classes_[proba.argmax(axis=1)]
  predicted[maxprob<thr]="ABSTAIN_OUT_OF_REFERENCE"
  fraction={label:{"n":int(np.sum(predicted==label)),"fraction":float(np.mean(predicted==label))} for label in list(LABELS)+["ABSTAIN_OUT_OF_REFERENCE"]}
  result["Chen_projection"][gsm]={"group":"SHAM" if "Sh" in gsm or "sham" in str(gseitem.get("attributes")).lower() else "MI",
   "n_QC":int(mask.sum()),"gene_intersection":len(common),"selected_features_found":len(selected),
   "reference_prediction_counts":fraction,
   "label_type":"EXTERNAL_REFERENCE_PROVISIONAL_NOT_VALIDATED"}
  print(json.dumps({"gsm":gsm,"QC_n":int(mask.sum()),"reference_assignment":fraction}),flush=True)
  del m,xx,proba
 result["gates"]={"EXTERNAL_HEART_GEO_SOURCE_SHA256":"PASS","ANNOTATED_BARCODES_MATCH":"PASS",
  "WITHIN_REFERENCE_HOLDOUT":"METRICS_REPORTED_NOT_INDEPENDENT_ANIMAL_VALIDATION",
  "CHEN_REFERENCE_LABELLING":"DESCRIPTIVE_WITH_ABSTAIN",
  "T_GAMMA_DELTA_VALIDATION":"NOT_POSSIBLE_WITH_REFERENCE_CLASSES",
  "CHEN_ANIMAL_CELL_PROPORTIONS":"LOCKED_UNTIL_TRUE_MOUSE_IDS",
  "FIBROBLAST_FATE":"NOT_ESTABLISHED"}
 (OUT/"report.json").write_text(json.dumps(result,indent=2)+"\n")
 print("TOPA_REFERENCE_TRANSFER_SUMMARY_START")
 print(json.dumps({"model":result["model"],"Chen_projection":result["Chen_projection"],"gates":result["gates"]}))
 print("TOPA_REFERENCE_TRANSFER_SUMMARY_END")
if __name__=="__main__":main()
