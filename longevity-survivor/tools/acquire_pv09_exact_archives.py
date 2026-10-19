#!/usr/bin/env python3
"""Acquire exact page-discovered old P. vanderplanki sequence archives.
Only archived MidgeBase hrefs are used; no inferred filenames are admitted.
Independent web archives are queried before a source is declared unavailable.
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
def save_candidate(label,b,rec):
 k=kind(b)
 if k not in {'ZIP','GZIP','FASTA'}:return None
 ext='.zip' if k=='ZIP' else '.tar.gz' if k=='GZIP' else '.fasta';p=OUT/(label+ext);p.write_bytes(b)
 return rec|{'saved_as':p.name}
def arquivo_history(orig):
 u='https://arquivo.pt/textsearch?'+urllib.parse.urlencode({'prettyPrint':'false','versionHistory':orig,'maxItems':50})
 try:
  b,f,c=get(u,45);o=json.loads(b);items=o.get('response_items') or o.get('responseItems') or []
  return {'status':'PASS','url':u,'final_url':f,'content_type':c,'sha256':sha(b),'total_items':o.get('total_items',o.get('estimated_nr_results')),'items':items}
 except Exception as e:return {'status':'FAIL','url':u,'error':f'{type(e).__name__}: {e}','items':[]}
def avail(orig,ts='20220405'):
 u='https://archive.org/wayback/available?'+urllib.parse.urlencode({'url':orig,'timestamp':ts})
 for n in range(2):
  try:
   b,f,c=get(u,30);o=json.loads(b);return {'status':'PASS','url':u,'sha256':sha(b),'closest':((o.get('archived_snapshots') or {}).get('closest') or {})}
  except Exception as e:err=f'{type(e).__name__}: {e}';time.sleep(2)
 return {'status':'FAIL','url':u,'error':err}
def acquire(label,orig):
 attempts=[];accepted=None
 ah=arquivo_history(orig)
 # Arquivo.pt exposes direct preserved-file links in URL-history records when available.
 for item in ah.get('items',[]):
  for field in ('linkToOriginalFile','linkToNoFrame','linkToArchive'):
   u=item.get(field)
   if not u:continue
   try:
    b,f,ct=get(u,120);k=kind(b);r={'archive':'ARQUIVO_PT','field':field,'url':u,'status':'PASS','final_url':f,'content_type':ct,'bytes':len(b),'sha256':sha(b),'payload_kind':k,'prefix_hex':b[:16].hex(),'record_timestamp':item.get('tstamp'),'record_digest':item.get('digest'),'record_content_length':item.get('contentLength')};attempts.append(r)
    accepted=save_candidate(label,b,r)
    if accepted:break
   except Exception as e:attempts.append({'archive':'ARQUIVO_PT','field':field,'url':u,'status':'FAIL','error':f'{type(e).__name__}: {e}'})
  if accepted:break
 av=avail(orig)
 if not accepted:
  c=av.get('closest') or {};ts=c.get('timestamp');cu=c.get('url');routes=[]
  if cu:
   routes.append(('closest_reported',cu))
   if cu.startswith('http://web.archive.org/'):routes.append(('closest_https','https://web.archive.org/'+cu.split('http://web.archive.org/',1)[1]))
  if ts:routes.extend([('standard_https',f'https://web.archive.org/web/{ts}/{orig}'),('identity_https',f'https://web.archive.org/web/{ts}id_/{orig}')])
  seen=set()
  for route,u in routes:
   if u in seen:continue
   seen.add(u)
   try:
    b,f,ct=get(u,90);k=kind(b);r={'archive':'WAYBACK','route':route,'url':u,'status':'PASS','final_url':f,'content_type':ct,'bytes':len(b),'sha256':sha(b),'payload_kind':k,'prefix_hex':b[:16].hex()};attempts.append(r);accepted=save_candidate(label,b,r)
    if accepted:break
   except Exception as e:attempts.append({'archive':'WAYBACK','route':route,'url':u,'status':'FAIL','error':f'{type(e).__name__}: {e}'})
 return {'label':label,'original_url':orig,'arquivo_pt_history':ah,'wayback_availability':av,'download_attempts':attempts,'retrieved_binary_candidate':accepted,'admission':'RETRIEVED_NOT_YET_CONTENT_VALIDATED' if accepted else 'NOT_RETRIEVED'}
def main():
 results=[]
 with ThreadPoolExecutor(max_workers=3) as ex:
  for f in as_completed([ex.submit(acquire,k,v) for k,v in ORIGINALS.items()]):results.append(f.result())
 results.sort(key=lambda x:x['label'])
 s={'artifact_id':'JANUS-PV09-EXACT-MIDGEBASE-ARCHIVE-ACQUISITION-V1_2','source_discovery':{'archived_midgebase_page_timestamp':'20200217020915','rule':'ONLY_EXACT_HREFS_DISCOVERED_ON_ARCHIVED_MIDGEBASE_PAGE_ARE_PROBED'},'independent_archives_queried':['ARQUIVO_PT','INTERNET_ARCHIVE_WAYBACK'],'results':results,'retrieved_count':sum(bool(x['retrieved_binary_candidate']) for x in results),'old_sequence_admission':'PENDING_CONTENT_VALIDATION','hard_boundaries':['ARCHIVE_INDEX_NE_AUTOMATIC_BIOLOGICAL_IDENTITY','RETRIEVED_BYTES_MUST_BE_HASHED_AND_CONTENT_VALIDATED','PvScaf_HEADERS_REQUIRED_FOR_GENOME_ADMISSION','PvG_IDENTIFIERS_REQUIRED_FOR_OLD_GENE_MODEL_SEQUENCE_ADMISSION','MISSING_DATA_STAYS_MISSING']}
 (OUT/'exact_archive_acquisition.json').write_text(json.dumps(s,indent=2,ensure_ascii=False)+'\n')
 print('PV09_EXACT_ARCHIVE',json.dumps({'retrieved_count':s['retrieved_count'],'labels':{x['label']:x['admission'] for x in results},'arquivo_counts':{x['label']:len(x['arquivo_pt_history'].get('items',[])) for x in results}},sort_keys=True),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
