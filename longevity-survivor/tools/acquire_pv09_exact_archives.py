#!/usr/bin/env python3
"""Acquire exact page-discovered old P. vanderplanki sequence archives.
Only archived MidgeBase hrefs are used; no inferred filenames are admitted.
"""
from __future__ import annotations
import hashlib,json,os,time,urllib.parse,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

OUT=Path(os.environ.get('JANUS_PV09_EXACT_OUT','pv09_exact_archives')).resolve();OUT.mkdir(parents=True,exist_ok=True)
UA='JANUS-LONGEVITY-SURVIVOR/1.0 exact-Pv09-MidgeBase-acquisition'
ORIGINALS={
 'pv09_genome':'http://bertone.nises-f.affrc.go.jp/files/pv/assembly/PvScaf_v0.9.fasta.zip',
 'pv20121018_nt':'http://bertone.nises-f.affrc.go.jp/files/pv/genemodel/Pv20121018.all.fa.tar.gz',
 'pv20121018_aa':'http://bertone.nises-f.affrc.go.jp/files/pv/genemodel/Pv20121018.all.aa.tar.gz',
}

def sha(b):return hashlib.sha256(b).hexdigest()
def get(u,t=90):
 req=urllib.request.Request(u,headers={'User-Agent':UA,'Accept':'*/*'})
 with urllib.request.urlopen(req,timeout=t) as r:return r.read(),r.geturl(),r.headers.get('Content-Type','')
def kind(b):
 if b[:4]==b'PK\x03\x04':return 'ZIP'
 if b[:2]==b'\x1f\x8b':return 'GZIP'
 if b.lstrip().startswith(b'>'):return 'FASTA'
 if b[:200].lstrip().lower().startswith((b'<!doctype html',b'<html')):return 'HTML'
 return 'OTHER'
def avail(orig,ts='20220405'):
 u='https://archive.org/wayback/available?'+urllib.parse.urlencode({'url':orig,'timestamp':ts})
 for n in range(3):
  try:
   b,f,c=get(u,30);o=json.loads(b);return {'status':'PASS','url':u,'sha256':sha(b),'closest':((o.get('archived_snapshots') or {}).get('closest') or {})}
  except Exception as e:
   err=f'{type(e).__name__}: {e}';time.sleep(2*(n+1))
 return {'status':'FAIL','url':u,'error':err}
def acquire(label,orig):
 av=avail(orig);c=av.get('closest') or {};ts=c.get('timestamp');cu=c.get('url')
 routes=[]
 if cu:
  routes.append(('closest_reported',cu))
  if cu.startswith('http://web.archive.org/'):routes.append(('closest_https','https://web.archive.org/'+cu.split('http://web.archive.org/',1)[1]))
 if ts:
  routes.extend([
   ('standard_https',f'https://web.archive.org/web/{ts}/{orig}'),
   ('identity_https',f'https://web.archive.org/web/{ts}id_/{orig}'),
  ])
 seen=set();attempts=[];accepted=None
 for route,u in routes:
  if u in seen:continue
  seen.add(u)
  for retry in range(2):
   try:
    b,f,ct=get(u,120);k=kind(b);r={'route':route,'retry':retry,'url':u,'status':'PASS','final_url':f,'content_type':ct,'bytes':len(b),'sha256':sha(b),'payload_kind':k,'prefix_hex':b[:16].hex()};attempts.append(r)
    if k in {'ZIP','GZIP','FASTA'}:
     ext='.zip' if k=='ZIP' else '.tar.gz' if k=='GZIP' else '.fasta';p=OUT/(label+ext);p.write_bytes(b);accepted=r|{'saved_as':p.name};break
   except Exception as e:attempts.append({'route':route,'retry':retry,'url':u,'status':'FAIL','error':f'{type(e).__name__}: {e}'})
   if retry==0:time.sleep(3)
  if accepted:break
 return {'label':label,'original_url':orig,'availability':av,'download_attempts':attempts,'retrieved_binary_candidate':accepted,'admission':'RETRIEVED_NOT_YET_CONTENT_VALIDATED' if accepted else 'NOT_RETRIEVED'}
def main():
 results=[]
 with ThreadPoolExecutor(max_workers=3) as ex:
  fs=[ex.submit(acquire,k,v) for k,v in ORIGINALS.items()]
  for f in as_completed(fs):results.append(f.result())
 results.sort(key=lambda x:x['label'])
 s={'artifact_id':'JANUS-PV09-EXACT-MIDGEBASE-ARCHIVE-ACQUISITION-V1_1','source_discovery':{'archived_midgebase_page_timestamp':'20200217020915','rule':'ONLY_EXACT_HREFS_DISCOVERED_ON_ARCHIVED_MIDGEBASE_PAGE_ARE_PROBED'},'results':results,'retrieved_count':sum(bool(x['retrieved_binary_candidate']) for x in results),'old_sequence_admission':'PENDING_CONTENT_VALIDATION','hard_boundaries':['WAYBACK_CAPTURE_NE_AUTOMATIC_BIOLOGICAL_IDENTITY','RETRIEVED_BYTES_MUST_BE_HASHED_AND_CONTENT_VALIDATED','PvScaf_HEADERS_REQUIRED_FOR_GENOME_ADMISSION','PvG_IDENTIFIERS_REQUIRED_FOR_OLD_GENE_MODEL_SEQUENCE_ADMISSION','MISSING_DATA_STAYS_MISSING']}
 (OUT/'exact_archive_acquisition.json').write_text(json.dumps(s,indent=2,ensure_ascii=False)+'\n')
 print('PV09_EXACT_ARCHIVE',json.dumps({'retrieved_count':s['retrieved_count'],'labels':{x['label']:x['admission'] for x in results}},sort_keys=True),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
