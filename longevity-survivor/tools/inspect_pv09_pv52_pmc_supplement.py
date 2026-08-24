#!/usr/bin/env python3
"""Acquire official PMC supplementary material for the 2022 Pv5.2 paper and
inspect it for an explicit Pv0.9/PvG -> Pv5.2/g.t identifier bridge.

No relation is admitted from proximity, row order, coordinates across assemblies,
or approximate identifier similarity.
"""
from __future__ import annotations
import gzip, hashlib, io, json, os, re, tarfile, urllib.request, urllib.error
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

OUT=Path(os.environ.get('JANUS_PV_SUPP_OUT','pv09_pv52_pmc_supplement')).resolve(); OUT.mkdir(parents=True,exist_ok=True)
PMC='PMC8982440'
OA=f'https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={PMC}'
DIRECT=f'https://pmc.ncbi.nlm.nih.gov/articles/{PMC}/bin/lqac029_supplemental_files.zip'
PVG=re.compile(rb'PvG\d+(?:\.t\d+)?')
GT=re.compile(rb'(?<![A-Za-z0-9])g\d+(?:\.t\d+)?(?![A-Za-z0-9])',re.I)
TERMS=[b'Pv0.9',b'Pv5.2',b'liftover',b'liftOver',b'cross-reference',b'cross reference',b'old gene',b'new gene']

def sha(b): return hashlib.sha256(b).hexdigest()
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'JANUS-LONGEVITY-SURVIVOR/1.0 public-supplement-audit'})
    with urllib.request.urlopen(req,timeout=240) as r: return r.read(),r.geturl(),r.headers.get('Content-Type','')

def scan_bytes(name,b):
    pvs=sorted(set(x.decode('utf-8','replace') for x in PVG.findall(b)))
    gts=sorted(set(x.decode('utf-8','replace') for x in GT.findall(b)))
    hits=[t.decode() for t in TERMS if t.lower() in b.lower()]
    same=[]
    for line in b.splitlines():
        lp=sorted(set(x.decode('utf-8','replace') for x in PVG.findall(line)))
        lg=sorted(set(x.decode('utf-8','replace') for x in GT.findall(line)))
        if lp and lg and len(same)<10000: same.append({'pvg':lp,'gt':lg,'line':line[:3000].decode('utf-8','replace')})
    return {'name':name,'bytes':len(b),'sha256':sha(b),'unique_pvg':len(pvs),'unique_gt':len(gts),'pvg_examples':pvs[:20],'gt_examples':gts[:20],'term_hits':hits,'same_line_pvg_gt':len(same)},same

def recursively_scan(name,b,records,crossrefs,depth=0):
    if depth>4:return
    rec,same=scan_bytes(name,b); records.append(rec)
    for x in same: crossrefs.append({'member':name,**x})
    try:
        if b[:4]==b'PK\x03\x04':
            with zipfile.ZipFile(io.BytesIO(b)) as z:
                for zi in z.infolist():
                    if not zi.is_dir():
                        try: recursively_scan(f'{name}!{zi.filename}',z.read(zi),records,crossrefs,depth+1)
                        except Exception: pass
            return
    except Exception: pass
    if b[:2]==b'\x1f\x8b':
        try: recursively_scan(name+'!gunzip',gzip.decompress(b),records,crossrefs,depth+1)
        except Exception:pass

def inspect_payload(label,source_url,payload,final,ctype):
    records=[];cross=[];members=[]
    meta={'label':label,'source_url':source_url,'final_url':final,'content_type':ctype,'bytes':len(payload),'sha256':sha(payload)}
    if payload[:2]==b'\x1f\x8b':
        try:
            with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as tf:
                for m in tf.getmembers():
                    if not m.isfile():continue
                    f=tf.extractfile(m)
                    if not f:continue
                    b=f.read(); members.append({'name':m.name,'bytes':len(b),'sha256':sha(b)}); recursively_scan(m.name,b,records,cross)
        except tarfile.TarError:
            recursively_scan(label,payload,records,cross)
    else:
        recursively_scan(label,payload,records,cross)
    return meta,members,records,cross

def main():
    oa,_,_=get(OA); (OUT/'oa_response.xml').write_bytes(oa)
    root=ET.fromstring(oa); links=[]
    for e in root.iter():
        href=e.attrib.get('href')
        if href: links.append({'format':e.attrib.get('format'),'href':href})
    (OUT/'oa_links.json').write_text(json.dumps(links,indent=2)+'\n')
    official=[x['href'] for x in links if x.get('format')=='tgz' or str(x.get('href','')).endswith(('.tar.gz','.tgz'))]
    candidates=[]
    candidates.extend(official)                     # exact NCBI-returned href first
    for u in official:
        if u.startswith('ftp://ftp.ncbi.nlm.nih.gov/'):
            candidates.append('https://ftp.ncbi.nlm.nih.gov/'+u.split('ftp.ncbi.nlm.nih.gov/',1)[1])
    candidates.append(DIRECT)                       # official PMC article supplement path fallback
    attempts=[]; chosen=None
    for u in candidates:
        try:
            b,final,ctype=get(u)
            attempts.append({'url':u,'status':'PASS','bytes':len(b),'sha256':sha(b),'final_url':final,'content_type':ctype})
            chosen=(u,b,final,ctype); break
        except Exception as e:
            attempts.append({'url':u,'status':'FAIL','error':f'{type(e).__name__}: {e}'})
    (OUT/'download_attempts.json').write_text(json.dumps(attempts,indent=2)+'\n')
    if not chosen: raise RuntimeError('all official PMC supplement acquisition routes failed')
    u,payload,final,ctype=chosen
    suffix='.tar.gz' if payload[:2]==b'\x1f\x8b' else '.zip'
    (OUT/f'official_supplement_payload{suffix}').write_bytes(payload)
    meta,members,records,cross=inspect_payload('official_supplement',u,payload,final,ctype)
    meta['oa_api']=OA;meta['oa_response_sha256']=sha(oa);meta['download_attempts']=attempts
    (OUT/'package_provenance.json').write_text(json.dumps(meta,indent=2)+'\n')
    (OUT/'package_members.json').write_text(json.dumps(members,indent=2)+'\n')
    (OUT/'scan_records.json').write_text(json.dumps(records,indent=2)+'\n')
    with (OUT/'explicit_same_line_crossrefs.tsv').open('w',encoding='utf-8') as o:
        o.write('member\tpvg\tgt\tline\n')
        for x in cross:o.write(x['member'].replace('\t',' ')+'\t'+','.join(x['pvg'])+'\t'+','.join(x['gt'])+'\t'+x['line'].replace('\t',' ').replace('\n',' ')+'\n')
    relevant=[r for r in records if r['unique_pvg'] or r['unique_gt'] or r['term_hits']]
    summary={'artifact_id':'JANUS-PV09-PV52-PMC-SUPPLEMENT-BRIDGE-AUDIT-V1','pmc':PMC,'package':meta,'member_count':len(members),'scanned_objects':len(records),'relevant_objects':relevant,'explicit_same_line_pvg_gt_records':len(cross),'admission':'DIRECT_PUBLISHED_PVG_TO_GT_BRIDGE_PRESENT_IN_PMC_SUPPLEMENT' if cross else 'DIRECT_PUBLISHED_PVG_TO_GT_BRIDGE_NOT_FOUND_IN_PMC_SUPPLEMENT','hard_boundaries':['SAME_DOCUMENT_NE_IDENTITY','SAME_LINE_ONLY_CANDIDATE_UNLESS_SEMANTICS_EXPLICIT','ROW_ORDER_IS_NOT_IDENTITY','MISSING_DATA_STAYS_MISSING']}
    (OUT/'supplement_bridge_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('PMC_SUPPLEMENT_SUMMARY',json.dumps(summary,sort_keys=True),flush=True)
    return 0
if __name__=='__main__': raise SystemExit(main())
