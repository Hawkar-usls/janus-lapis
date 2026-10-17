#!/usr/bin/env python3
"""Fetch public GEO processed files and Zenodo R script, with byte-level receipts.
No SRA/FASTQ, no bulk RAW.tar, no Seurat RDS. Outputs stay in CI artifacts.
"""
import gzip, hashlib, json, os, pathlib, urllib.parse, urllib.request
OUT=pathlib.Path(os.environ.get("TOPA_OUTPUT","topa_pd1_acquisition"))
OUT.mkdir(parents=True,exist_ok=True)
MAX_FILE=220*1024*1024
MAX_TOTAL=760*1024*1024
USED=0
LOG={"schema":"janus.topa.pd1_acquisition.v1","files":[],"samples":{},"errors":[],"full_replay":False}
ZENODO="https://zenodo.org/records/20983659/files/preprocess.R?download=1"
EXPECTED_MD5="c09afc0f77fa13f63329de811f208f59"
def hashfile(p,which):
 h=hashlib.new(which)
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
 return h.hexdigest()
def fetch(url,path,cap=MAX_FILE,expected_md5=None):
 global USED
 item={"url":url,"path":str(path),"status":"FAILED"}
 LOG["files"].append(item)
 tmp=path.with_name(path.name+".partial")
 try:
  host=urllib.parse.urlparse(url).hostname or ""
  if host!="zenodo.org" and not host.endswith(".ncbi.nlm.nih.gov"):raise RuntimeError("untrusted source")
  path.parent.mkdir(parents=True,exist_ok=True)
  req=urllib.request.Request(url,headers={"User-Agent":"JANUS-TOPA-public-receipt/1.0"})
  amount=0
  with urllib.request.urlopen(req,timeout=65) as inp,tmp.open("wb") as out:
   advertised=int(inp.headers.get("Content-Length") or 0)
   if advertised>cap or USED+advertised>MAX_TOTAL:raise RuntimeError("size cap")
   while True:
    b=inp.read(262144)
    if not b:break
    amount+=len(b)
    if amount>cap or USED+amount>MAX_TOTAL:raise RuntimeError("stream cap")
    out.write(b)
  tmp.replace(path)
  item.update({"status":"ACQUIRED","bytes":amount,"sha256":hashfile(path,"sha256")})
  if expected_md5:
   item["md5"]=hashfile(path,"md5")
   if item["md5"]!=expected_md5:
    item["status"]="CHECKSUM_MISMATCH"
    path.unlink()
    raise RuntimeError("MD5 mismatch")
  USED+=amount
  return path
 except Exception as exc:
  tmp.unlink(missing_ok=True)
  LOG["errors"].append({"path":str(path),"error":str(exc)})
  return None
def parse_geo_soft(path):
 samples={}
 current=None
 with gzip.open(path,"rt",errors="replace") as f:
  for line in f:
   line=line.strip()
   if line.startswith("^SAMPLE = "):
    current=line.partition("=")[2].strip()
    samples[current]={"gsm":current,"title":"","attributes":[],"files":[]}
   if current is None:continue
   s=samples[current]
   if line.startswith("!Sample_title = "):s["title"]=line.partition("=")[2].strip()
   elif line.startswith("!Sample_characteristics_ch1 = "):
    s["attributes"].append(line.partition("=")[2].strip())
   elif line.startswith("!Sample_supplementary_file"):
    url=line.partition("=")[2].strip().replace("ftp://","https://")
    if url.startswith("https://ftp.ncbi.nlm.nih.gov/"):s["files"].append(url)
 return list(samples.values())
fetch(ZENODO,OUT/"zenodo"/"preprocess.R",2*1024*1024,EXPECTED_MD5)
for gse in ("GSE293489","GSE327655"):
 root=f"https://ftp.ncbi.nlm.nih.gov/geo/series/{gse[:-3]}nnn/{gse}"
 soft=fetch(root+f"/soft/{gse}_family.soft.gz",OUT/gse/f"{gse}_family.soft.gz",30*1024*1024)
 if soft:
  try:
   items=parse_geo_soft(soft)
   LOG["samples"][gse]=items
   for item in items:
    for url in item["files"]:
     name=urllib.parse.unquote(urllib.parse.urlparse(url).path.rsplit("/",1)[-1])
     low=name.lower()
     if low.endswith((".mtx.gz",".tsv.gz",".csv.gz",".h5",".txt.gz")) and not any(x in low for x in ("fastq","raw.tar",".bam",".sra")):
      fetch(url,OUT/gse/"processed"/item["gsm"]/name)
  except Exception as e:LOG["errors"].append({"dataset":gse,"error":str(e)})
 else:LOG["samples"][gse]=[{"status":"SOFT_NOT_ACQUIRED"}]
(OUT/"manifest.json").write_text(json.dumps(LOG,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"total_bytes":USED,"files_acquired":sum(x["status"]=="ACQUIRED" for x in LOG["files"]),"failed":len(LOG["errors"]),"zenodo_md5_ok":any(x.get("md5")==EXPECTED_MD5 and x["status"]=="ACQUIRED" for x in LOG["files"])},indent=2))
