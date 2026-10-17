#!/usr/bin/env python3
"""Bounded public GEO Wu TAC processed-count discovery; no SRA/raw read download."""
import datetime,json,os,pathlib,re,urllib.request,urllib.parse,html.parser
OUT=pathlib.Path(os.environ.get("WU_PROBE_OUT","topa_wu_processed_probe"))
OUT.mkdir(exist_ok=True,parents=True)
BASE="https://ftp.ncbi.nlm.nih.gov/geo/series/GSE327nnn/GSE327655/"
class HrefParser(html.parser.HTMLParser):
 def __init__(self):super().__init__();self.hrefs=[]
 def handle_starttag(self,t,a):
  if t=="a":
   v=dict(a).get("href")
   if v:self.hrefs.append(v)
def probe(url,read=False):
 r={"url":url,"status":"UNKNOWN"}
 try:
  req=urllib.request.Request(url,headers={"User-Agent":"JANUS-TOPA-public-metadata/1.0"},method="GET" if read else "HEAD")
  with urllib.request.urlopen(req,timeout=25) as f:
   r.update({"status":f.status,"final_url":f.geturl(),"content_type":f.headers.get("Content-Type"),"content_length":f.headers.get("Content-Length"),"content_disposition":f.headers.get("Content-Disposition")})
   if read:
    data=f.read(512000)
    p=HrefParser()
    p.feed(data.decode("utf-8","replace"))
    r["links"]=sorted({urllib.parse.urljoin(url,x) for x in p.hrefs if x and not x.startswith("?")})[:150]
    r["page_excerpt"]=re.sub("<[^>]+>"," ",data.decode("utf-8","replace"))[:900]
 except Exception as e:r.update({"status":"ERROR","error":str(e)[:200]})
 return r
results={"schema":"janus.topa.wu_tac_processed_counts_locator.v1","time_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"geo":"GSE327655","sources":{},"controls":["directory_listing_not_file_download","html_or_series_matrix_metadata_not_raw_counts","SRA_not_downloaded","only_author_or_GEO_official_sources"]}
for sub in ("suppl/","matrix/"):
 results["sources"][sub]=probe(BASE+sub,read=True)
results["sources"]["geo_ncbi_counts"]=probe("https://www.ncbi.nlm.nih.gov/geo/download/?acc=GSE327655&format=file&type=rnaseq_counts")
results["sources"]["soft"]=probe(BASE+"soft/GSE327655_family.soft.gz")
results["processed_counts_confirmed"]=False
results["decision"]="CANDIDATE_PATHS_ONLY__DOWNLOAD_AND_VALIDATE_IF_COUNT_TABLE_IDENTIFIED"
(OUT/"probe.json").write_text(json.dumps(results,indent=2)+"\n")
print(json.dumps(results,indent=2))
