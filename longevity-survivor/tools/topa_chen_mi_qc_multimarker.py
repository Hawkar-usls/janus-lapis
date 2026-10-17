#!/usr/bin/env python3
"""JANUS TOPA: auditable Chen GSE293489 single-cell QC and conservative marker classification.

This is NOT a full reference-atlas annotation, not a doublet-corrected analysis,
and NOT biological replication unless a trusted specimen->animal crosswalk exists.
Author-published cutoffs are used; marker assignment is explicitly provisional.
"""
import collections
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import numpy as np
from scipy.io import mmread
from scipy import sparse

ROOT=Path(os.environ.get("TOPA_PD1_ROOT","prior/topa_pd1_acquisition"))
OUT=Path(os.environ.get("TOPA_CHEN_QC_OUT","topa_chen_sc_qc"))
OUT.mkdir(parents=True,exist_ok=True)
MFILE=ROOT/"manifest.json"
GSE="GSE293489"
# Frozen a priori QC directly from Chen 2026 scRNA-seq methods.
FILTER={"min_detected_genes_inclusive":300,"max_UMIs_inclusive":40000,"max_mitochondrial_fraction_inclusive":0.05}
BROAD={
 "T_candidate":["Cd3d","Cd3e","Cd247","Trac","Lck"],
 "B_candidate":["Cd79a","Cd79b","Ms4a1","Cd19"],
 "NK_candidate":["Nkg7","Klrd1","Klrk1","Prf1"],
 "myeloid_candidate":["Lyz2","Csf1r","Adgre1","Tyrobp","Itgam"],
 "fibroblast_candidate":["Dcn","Lum","Pdgfra","Col1a1","Col3a1"],
 "endothelial_candidate":["Pecam1","Cdh5","Kdr","Emcn"],
 "lymphatic_candidate":["Prox1","Lyve1","Pdpn"],
 "pericyte_candidate":["Rgs5","Cspg4","Pdgfrb","Notch3"],
 "smooth_muscle_candidate":["Myh11","Tagln","Acta2","Cnn1"],
 "neutrophil_candidate":["S100a8","S100a9","Ly6g","Csf3r"],
 "cardiomyocyte_contaminant":["Tnnt2","Myh6","Myl2","Actc1"]
}
T_SUBTYPE={
 "gamma_delta":["Trdc","Trgc1","Trgc2"],
 "cd8":["Cd8a","Cd8b1"],
 "cytotoxic":["Nkg7","Gzmb","Prf1","Ccl5"],
 "cd4":["Cd4","Il7r","Tcf7","Ltb"],
 "treg":["Foxp3","Il2ra","Ctla4","Ikzf2"],
 "alpha_beta":["Trac","Trbc1","Trbc2"],
 "pd1":["Pdcd1"],
 "cxcr3":["Cxcr3"]
}
AUX=["Cxcl9","Cxcl10","Postn","Pdgfra","Col1a1","Col3a1","Acta2","Mki67"]
ALL_GENES=set(x for arr in list(BROAD.values())+list(T_SUBTYPE.values()) for x in arr)|set(AUX)
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()
def lines(path):
 op=gzip.open if str(path).endswith(".gz") else open
 with op(path,"rt",errors="replace") as f:
  for line in f:yield line.rstrip("\n").split("\t")
def group(item):
 v=" ".join([item.get("title","")]+item.get("attributes",[])).lower()
 if "treatment: sham" in v:return "SHAM"
 if "treatment: myocardial infarction" in v:return "MI"
 return "UNRESOLVED"
def source_files(gsm, files):
 f=[Path(x["path"]) for x in files if x.get("status")=="ACQUIRED" and "/"+gsm+"/" in x.get("path","").replace("\\","/")]
 find=lambda term,ext:next((x for x in f if term in x.name.lower() and x.name.lower().endswith(ext)),None)
 a=(find("_matrix",".mtx.gz"),find("_features",".tsv.gz"),find("_barcodes",".tsv.gz"))
 if any(x is None for x in a):raise ValueError("Incomplete exact-GSM 10x triplet: "+gsm)
 return a
def get_counts(m, symbol_map, gene):
 ix=symbol_map.get(gene.lower(),[])
 if not ix:return np.zeros(m.shape[1],dtype=np.float32)
 z=np.asarray(m[ix,:].sum(axis=0)).ravel()
 return z.astype(np.float32)
def percentiles(x):
 if len(x)==0:return None
 return {str(k):float(np.percentile(x,k)) for k in (0,5,25,50,75,95,99,100)}
def fmt_counts(lbl, lab):
 counts=collections.Counter(lab.tolist())
 return {k:{"n":int(counts.get(k,0)),"fraction":round(counts.get(k,0)/len(lab),6) if len(lab) else None} for k in lbl}
def main():
 m=json.loads(MFILE.read_text())
 rows=m.get("samples",{}).get(GSE,[])
 if len(rows)!=4:raise ValueError("Expected exactly four Chen GSM entries; got "+str(len(rows)))
 acquired={x["path"]:x for x in m["files"] if x.get("status")=="ACQUIRED"}
 results=[]
 for sample in rows:
  gsm=sample["gsm"]
  group_label=group(sample)
  if group_label=="UNRESOLVED":raise ValueError("Unresolved experimental group "+gsm)
  matpath,featpath,barpath=source_files(gsm,m["files"])
  for p in (matpath,featpath,barpath):
   info=acquired.get(str(p))
   if not p.is_file() or not info or p.stat().st_size!=info["bytes"] or sha(p)!=info["sha256"]:
    raise ValueError("GSM matrix provenance failed "+str(p))
  feats=list(lines(featpath)); barcodes=list(lines(barpath))
  ids=[z[0] for z in feats]
  genes=[z[1] if len(z)>1 else z[0] for z in feats]
  duplicates=collections.Counter(x.lower() for x in genes)
  matrix=mmread(str(matpath))
  matrix=matrix.tocsr()
  if matrix.shape!=(len(feats),len(barcodes)):raise ValueError("GSM matrix triplet dimension mismatch "+gsm)
  if matrix.data.min(initial=0)<0 or not np.issubdtype(matrix.dtype,np.integer):raise ValueError("Expected nonnegative integer UMI counts")
  csc=matrix.tocsc()
  total=np.asarray(csc.sum(axis=0)).ravel().astype(np.int64)
  detected=np.diff(csc.indptr).astype(np.int32)
  mitoix=[i for i,g in enumerate(genes) if g.lower().startswith("mt-")]
  if len(mitoix)<10:raise ValueError("Insufficient mt-genes for mouse 10X mito QC")
  mt=np.asarray(matrix[mitoix,:].sum(axis=0)).ravel().astype(np.float64)
  mtfrac=np.divide(mt,total,out=np.zeros_like(mt),where=total>0)
  passq=(detected>=FILTER["min_detected_genes_inclusive"]) & (total<=FILTER["max_UMIs_inclusive"]) & (mtfrac<=FILTER["max_mitochondrial_fraction_inclusive"]) & (total>0)
  n=int(np.sum(passq))
  if n==0:raise ValueError("No cells passing frozen author QC for "+gsm)
  kept=matrix[:,passq].tocsr()
  keptumi=total[passq]
  keptgenes=detected[passq]
  keptmt=mtfrac[passq]
  mapping=collections.defaultdict(list)
  for i,g in enumerate(genes):
   if g in ALL_GENES: mapping[g.lower()].append(i)
  arr={g:get_counts(kept,mapping,g) for g in ALL_GENES}
  binary={g:arr[g]>0 for g in ALL_GENES}
  N=kept.shape[1]
  def hits(keys):return sum((binary[k].astype(np.int8) for k in keys),start=np.zeros(N,dtype=np.int8))
  supported={}
  for label,marks in BROAD.items():
   num_avail=sum(1 for gene in marks if gene.lower() in mapping)
   if num_avail<2:raise ValueError("Panel has fewer than two source features "+label)
   supported[label]=hits(marks)>=2
  supported["T_candidate"] &= (binary["Cd3d"]|binary["Cd3e"])
  supported["B_candidate"] &= (binary["Cd79a"]|binary["Cd79b"]|binary["Ms4a1"])
  supported["NK_candidate"] &= binary["Nkg7"]
  supported["neutrophil_candidate"] &= (binary["Ly6g"]|binary["S100a8"]|binary["S100a9"])
  supported["fibroblast_candidate"] &= (binary["Dcn"]|binary["Lum"]|binary["Pdgfra"])
  supported["myeloid_candidate"] &= (binary["Lyz2"]|binary["Tyrobp"]|binary["Csf1r"])
  # NK and T can express the same cytotoxic markers; require exclusion before NK.
  supported["NK_candidate"] &= ~supported["T_candidate"]
  # Neutrophils are myeloid. Prefer the narrower candidate if supported.
  supported["myeloid_candidate"] &= ~supported["neutrophil_candidate"]
  ordered=list(BROAD)
  vote=np.stack([supported[k] for k in ordered],axis=0)
  ncand=vote.sum(axis=0)
  idx=vote.argmax(axis=0)
  broad=np.where(ncand==0,"UNRESOLVED",np.where(ncand>1,"AMBIGUOUS",np.asarray(ordered)[idx]))
  t=(broad=="T_candidate")
  subtype=np.full(N,"NOT_T_OR_UNRESOLVED",dtype="<U36")
  subtype[t]="T_UNRESOLVED_SUBTYPE"
  gd=binary["Trdc"]&(binary["Trgc1"]|binary["Trgc2"])
  cd8=binary["Cd8a"] & binary["Cd8b1"]
  cyto=hits(T_SUBTYPE["cytotoxic"])>=1
  treg=binary["Foxp3"]&(binary["Il2ra"]|binary["Ctla4"])
  cd4=binary["Cd4"]&(binary["Il7r"]|binary["Tcf7"]|binary["Ltb"])
  # Contradictory subtype hits not silently assigned. They may be doublets.
  psub=np.stack([gd,cd8,treg,cd4],axis=0).sum(axis=0)
  subtype[t & (psub>1)]="T_AMBIGUOUS_SUBTYPE"
  subtype[t & (psub==1)&gd]="T_GAMMA_DELTA_CANDIDATE"
  subtype[t & (psub==1)&cd8&cyto]="T_CD8_CYTOTOXIC_CANDIDATE"
  subtype[t & (psub==1)&cd8&~cyto]="T_CD8_CANDIDATE"
  subtype[t & (psub==1)&treg]="T_TREG_CANDIDATE"
  subtype[t & (psub==1)&cd4]="T_CD4_CANDIDATE"
  p_t=int(t.sum())
  pd1_n=int((t&binary["Pdcd1"]).sum())
  subcounts=collections.Counter(subtype[t].tolist())
  annotate={k:{"n":int(v),"fraction_of_T_candidates":round(v/p_t,6) if p_t else None} for k,v in sorted(subcounts.items())}
  totalcells=len(barcodes)
  report={
   "gsm":gsm,"author_geo_group":group_label,"sample_title":sample.get("title"),
   "specimen_to_animal_crosswalk":"NOT_AVAILABLE_IN_GEO_SOFT__NO_ANIMAL_LEVEL_N",
   "cellranger_features":len(feats),"mitochondrial_features":len(mitoix),
   "feature_duplicate_symbol_count":sum(1 for g,k in duplicates.items() if k>1),
   "source_sha256":{p.name:acquired[str(p)]["sha256"] for p in (matpath,featpath,barpath)},
   "QC":{"cells_before":totalcells,"cells_after":n,"fraction_pass":round(n/totalcells,6),
    "fail_genes_below_300":int((detected<300).sum()),
    "fail_umi_above_40000":int((total>40000).sum()),
    "fail_mito_above_5pct":int((mtfrac>0.05).sum()),
    "overlapping_failures_counted_per_rule":True,
    "n_genes_before":percentiles(detected),"n_UMI_before":percentiles(total),"pct_mito_before":percentiles(mtfrac*100),
    "n_genes_after":percentiles(keptgenes),"n_UMI_after":percentiles(keptumi),"pct_mito_after":percentiles(keptmt*100),
    "doublet_classification":"NOT_PERFORMED_VALIDATED__CONFLICTING_MULTILINEAGE_STATES_RETAINED_AS_AMBIGUOUS",
    "cellranger_empty_droplet_call":"ORIGINAL_GEO_10X_BARCODES_NOT_RECALLED"},
   "classification":{"method":"multi-marker sparse positive-UMI requirement, conservative binary unintegrated panel",
    "threshold":"at least two markers per broad lineage; T requires CD3D/E; ambiguity preserved",
    "panel":BROAD,"t_subtype_panel":T_SUBTYPE,
    "broad":fmt_counts(ordered+["AMBIGUOUS","UNRESOLVED"],broad),
    "T_subtypes":annotate,
    "T_candidate_n":p_t,"T_candidate_fraction_of_all_QC_cells":round(p_t/n,6),
    "Pdcd1_transcript_positive_T_n":pd1_n,
    "Pdcd1_transcript_positive_fraction_of_T_candidates":round(pd1_n/p_t,6) if p_t else None,
    "Cxcr3_transcript_positive_T_n":int((t&binary["Cxcr3"]).sum()),
    "Cxcl9_positive_T_n":int((t&binary["Cxcl9"]).sum()),
    "Cxcl9_positive_fibroblast_n":int(((broad=="fibroblast_candidate")&binary["Cxcl9"]).sum()),
    "NOT_FLOW_PD1_PROTEIN_OR_GAMMA_DELTA_TCR_PROOF":True}
  }
  results.append(report)
  del csc,matrix,kept
  print(json.dumps({"gsm":gsm,"group":group_label,"QC_cells":n,"QC_from":totalcells,"T_candidates":p_t,
   "fraction_T":report["classification"]["T_candidate_fraction_of_all_QC_cells"],"Pdcd1_RNA_T_pct":report["classification"]["Pdcd1_transcript_positive_fraction_of_T_candidates"],
   "subtypes":annotate},ensure_ascii=False),flush=True)
 bygroup={}
 for g in ("SHAM","MI"):
  group_rows=[x for x in results if x["author_geo_group"]==g]
  bygroup[g]={"GSMs":[x["gsm"] for x in group_rows],
   "sum_QC_cells":sum(x["QC"]["cells_after"] for x in group_rows),
   "per_library_T_fraction":[{"gsm":x["gsm"],"fraction":x["classification"]["T_candidate_fraction_of_all_QC_cells"]} for x in group_rows],
   "independent_mouse_n":"UNKNOWN__NOT_2"}
 root={
  "schema":"janus.topa.chen_mi_multimarker_cellqc.v1",
  "generated_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "source":{"GEO":GSE,"original_run_id":39026401715,"artifact_id":12098558095,
   "original_source_commit":"3f50350954e2bc060c33f5e696f79016b8ac6fe2",
   "source_paper_DOI":"10.1038/s41421-026-00924-2","methods_QC_source":"Chen 2026 original scRNA-seq data analysis methods"},
  "filters":FILTER,
  "libraries":results,"group_descriptive":bygroup,
  "gates":{"SOURCE_BYTES_SHA256":"PASS","AUTHORS_FROZEN_SC_QC":"PASS",
   "MULTIMARKER_CANDIDATE_PROPORTIONS":"PASS_DESCRIPTIVE_PER_GSM_ONLY",
   "CELL_TYPES_EXPERIMENTALLY_VALIDATED":"NO",
   "INDEPENDENT_MOUSE_CROSSWALK":"NOT_VERIFIED",
   "PER_INDEPENDENT_MOUSE_STATISTICS":"BLOCKED_NO_ANIMAL_CROSSWALK",
   "DOUBLETS_REMOVED":"NO","STRICT_FIBROBLAST_EXIT":"NOT_ESTABLISHED","MECHANICAL_EXIT_COUPLING":"NOT_ADMITTED"},
  "firewall":["TWO_GSM_PER_ARM != TWO_VERIFIED_INDEPENDENT_MICE",
   "PDCD1_RNA_POSITIVE != PD1_PROTEIN_POSITIVE",
   "GAMMA_DELTA_TRANSCRIPTS != DIRECT_TCR_GAMMA_DELTA_PROTEIN_EVIDENCE",
   "CANDIDATE_CELL_ANNOTATION != REFERENCE_VALIDATED_CELL_TYPE",
   "CONFLICTING_LINEAGE_MARKERS MAY_INDICATE_DOUBLET_OR_AMBIENT_RNA",
   "SINGLE_SNAPSHOT != ACTIVATED_FIBROBLAST_FATE_OR_EXIT",
   "NO_PVALUES_OR_CI_OF_BIOLOGICAL_EFFECTS_UNTIL_ANIMAL_IDS_AUDITED"],
  "next_TOPA":"Validate mouse pool versus mouse ID via primary supplementary or author correspondence; inspect independent reference annotation and doublet predictions before animal-level proportions."
 }
 (OUT/"report.json").write_text(json.dumps(root,indent=2,ensure_ascii=False)+"\n")
 print("TOPA_CHEN_QC_SUMMARY_START")
 print(json.dumps({"gates":root["gates"],"groups":bygroup,
  "libraries":[{"gsm":x["gsm"],"group":x["author_geo_group"],"QC":x["QC"]["cells_after"],
  "T_candidate_n":x["classification"]["T_candidate_n"],
  "T_candidate_fraction":x["classification"]["T_candidate_fraction_of_all_QC_cells"],
  "pd1_RNA_T_fraction":x["classification"]["Pdcd1_transcript_positive_fraction_of_T_candidates"],
  "T_subtypes":x["classification"]["T_subtypes"]} for x in results]},ensure_ascii=False))
 print("TOPA_CHEN_QC_SUMMARY_END")
if __name__=="__main__":main()
