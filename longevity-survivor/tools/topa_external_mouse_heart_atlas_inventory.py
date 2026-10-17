#!/usr/bin/env python3
"""TOPA: bounded acquisition of an independent annotated murine heart reference.

Tabula Muris heart droplet GEO GSM3040902 data and original consortium heart
annotations; provenance and barcode crosswalk audited before any label transfer.
Author supplementary is searched only for actual animal/pooling details.
"""
import collections,csv,datetime,gzip,hashlib,io,json,os,re,tarfile,urllib.request,zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

OUT=Path(os.getenv("TOPA_REFERENCE_OUT","topa_pd1_external_reference"));OUT.mkdir(parents=True,exist_ok=True)
REF_GEO="https://ftp.ncbi.nlm.nih.gov/geo/samples/GSM3040nnn/GSM3040902/suppl/GSM3040902_Heart-10X_P7_4.tar.gz"
REF_ANNOT="https://raw.githubusercontent.com/czbiohub-sf/tabula-muris/master/00_data_ingest/03_tissue_annotation_csv/Heart_and_Aorta_droplet_annotation.csv"
CHEN_SUPPL="https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41421-026-00924-2/MediaObjects/41421_2026_924_MOESM1_ESM.docx"
sources={}
def acquire(key,url,maxsize):
 p=OUT/{"GEO_heart_matrix":"GSM3040902_Heart-10X_P7_4.tar.gz",
 "Tabula_Muris_original_heart_annotations":"Heart_and_Aorta_droplet_annotation.csv",
 "Chen_supplementary":"Chen_2026_supplementary.docx"}[key]
 req=urllib.request.Request(url,headers={"User-Agent":"JANUS-TOPA-primary-crossstudy/1.0"})
 with urllib.request.urlopen(req,timeout=45) as r,p.open("wb") as f:
  count=0
  while True:
   b=r.read(262144)
   if not b:break
   count+=len(b)
   if count>maxsize:raise ValueError("bounded acquisition exceeded "+key)
   f.write(b)
 h=hashlib.sha256(p.read_bytes()).hexdigest()
 sources[key]={"url":url,"sha256":h,"bytes":p.stat().st_size,"status":"ACQUIRED"}
 return p
report={"schema":"janus.topa.independent_heart_reference_acquisition.v1",
 "date_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "reference_publication":"Tabula Muris consortium 2018, GEO GSM3040902 mouse Heart 10X",
 "source_references":{"GEO":"GSM3040902","independent_labels":"czbiohub-sf/tabula-muris/Heart_and_Aorta_droplet_annotation.csv"},
 "sources":sources,"reference":{},"chen_supplementary":{},
 "warnings":["HEART_AND_AORTA_LABELS_NOT_HEART_ONLY","REFERENCE_SINGLE_EXPERIMENT_NOT_INDEPENDENT_TISSUE_BIOLOGICAL_REPLICATION",
             "T_CELL_SUBTYPES_NOT_VALIDATED_BY_BROAD_HEART_REFERENCE",
             "MATCHED_BARCODE_PROVENANCE_REQUIRED"]}
r=acquire("GEO_heart_matrix",REF_GEO,15_000_000)
a=acquire("Tabula_Muris_original_heart_annotations",REF_ANNOT,1_000_000)
with tarfile.open(r,"r:gz") as tar:
 items=[{"name":m.name,"bytes":m.size} for m in tar.getmembers() if m.isfile()]
 paths=[m.name for m in tar.getmembers() if m.isfile()]
 bname=next((n for n in paths if n.endswith("barcodes.tsv") or n.endswith("barcodes.tsv.gz")),None)
 mname=next((n for n in paths if n.endswith("matrix.mtx") or n.endswith("matrix.mtx.gz")),None)
 gname=next((n for n in paths if n.endswith("genes.tsv") or n.endswith("features.tsv") or n.endswith("genes.tsv.gz")),None)
 if not all((bname,mname,gname)):raise RuntimeError("Unexpected reference triplet "+str(paths))
 data=tar.extractfile(bname).read()
 if bname.endswith(".gz"):data=gzip.decompress(data)
 barcodes=[x.strip().split("\t")[0] for x in data.decode("utf-8").splitlines() if x.strip()]
report["reference"]["tar_members"]=items
report["reference"]["10X_members"]={"matrix":mname,"features":gname,"barcodes":bname}
with a.open(newline="",encoding="utf-8") as f: rows=list(csv.DictReader(f))
reference_ids=set("10X_P7_4_"+b.split("-")[0] for b in barcodes)
matches=[x for x in rows if x.get("cell") in reference_ids]
lab=collections.Counter(x.get("cell_ontology_class","NA") for x in matches)
report["reference"].update({"reference_barcode_count":len(barcodes),"original_annotation_records":len(rows),
 "exact_cell_id_crosswalk_count":len(matches),"unmatched_reference_barcodes":len(barcodes)-len(matches),
 "matched_label_counts":dict(lab),"verified_specific_ref_cell_id_examples":[x.get("cell") for x in matches[:5]]})
if len(matches)<100:raise RuntimeError("Tabula Muris heart 10x barcode provenance mismatch: "+str(report["reference"]))
try:
 f=acquire("Chen_supplementary",CHEN_SUPPL,35_000_000)
 with zipfile.ZipFile(f) as z:
  xml=z.read("word/document.xml")
 root=ET.fromstring(xml)
 ns={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
 paras=["".join(t.text or "" for t in x.findall(".//w:t",ns)) for x in root.findall(".//w:p",ns)]
 needle=re.compile(r"\b(pool(?:ed|ing)?|single[- ]cell|individual\s+mouse|animal(?:s)?|heart(?:s)?|sham|M7h[12]|Sh[12])\b",re.I)
 excerpts=[x[:700] for x in paras if needle.search(x)]
 report["chen_supplementary"]={"status":"INSPECTED","paragraphs":len(paras),
   "relevant_context_excerpts":excerpts[:60],
   "individual_mouse_identity_mapping":"NOT_ESTABLISHED_UNLESS_EXPLICIT_FIELD"}
except Exception as e:
 report["chen_supplementary"]={"status":"NOT_ACQUIRED_OR_NOT_READABLE","error":str(e)[:230],
   "individual_mouse_identity_mapping":"NOT_ESTABLISHED"}
report["gates"]={"INDEPENDENT_ATLAS_LABEL_AND_RAW_BARCODE_CROSSWALK":"PASS",
 "REFERENCE_HEART_CLASS_TAXONOMY":"PASS_SOURCE_LABELS_ONLY",
 "AUTHOR_MOUSE_POOLING_EVIDENCE":"NOT_VERIFIED",
 "CHEN_CELL_TYPE_EXTERNAL_TRANSFER":"NOT_YET_PERFORMED",
 "DOUBLETS":"NOT_YET_PERFORMED",
 "STRICT_PROFIBROTIC_EXIT":"NOT_ESTABLISHED"}
(OUT/"inventory.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print("TOPA_REFERENCE_INVENTORY_START")
print(json.dumps({"sources":sources,"reference":report["reference"],"chen_supplementary":report["chen_supplementary"],"gates":report["gates"]},ensure_ascii=False))
print("TOPA_REFERENCE_INVENTORY_END")
