#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, pathlib
from typing import Any

def canon(obj: Any)->bytes: return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def hid(*parts: str)->str: return hashlib.sha256('\n'.join(parts).encode()).hexdigest()[:24]
def load(p:pathlib.Path, default): return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
def atomic(p:pathlib.Path,obj:Any):
    p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix(p.suffix+'.tmp'); t.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8'); t.replace(p)
def append(p:pathlib.Path,obj:Any):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a',encoding='utf-8') as f: f.write(json.dumps(obj,ensure_ascii=False,sort_keys=True)+'\n')
def score(d:dict[str,Any], c:dict[str,Any]):
    hay=' '.join([str(c.get('title','')),str(c.get('summary','')),' '.join(c.get('tags',[]) or [])]).lower()
    hits=[]; s=0.0
    for kw in d.get('keywords',[]):
        k=str(kw).strip().lower()
        if k and k in hay: hits.append(k); s+=1.0+min(2.0,len(k)/24.0)
    for kw in d.get('priority_keywords',[]):
        k=str(kw).strip().lower()
        if k and k in hay: hits.append(k); s+=3.0
    return s,sorted(set(hits))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--state-dir',required=True); ap.add_argument('--effective-config',required=True); ap.add_argument('--max-source-candidates',type=int,default=500); a=ap.parse_args()
    root=pathlib.Path(a.state_dir); cfg=load(pathlib.Path(a.effective_config),{}); src=root/'candidates.jsonl'; seen_path=root/'context_seen.json'; seen=load(seen_path,{})
    rows=[]
    if src.exists():
        with src.open(encoding='utf-8',errors='replace') as f:
            for line in f:
                if line.strip():
                    try: rows.append(json.loads(line))
                    except Exception: pass
    rows=rows[-a.max_source_candidates:]; added=0
    for c in rows:
        cid=str(c.get('candidate_id',''))
        if not cid: continue
        for d in cfg.get('directions',[]):
            if not d.get('enabled',True): continue
            s,hits=score(d,c); threshold=float(d.get('min_score',1.0))
            if s<threshold: continue
            ctx=hid(cid,str(d['id']));
            if ctx in seen: continue
            row={
              'schema':'janus.universal_beetle.discovery_context.v1','context_id':ctx,'candidate_id':cid,
              'direction_id':d['id'],'base_direction_id':d.get('base_direction_id',d['id']),'mirror_lens':d.get('mirror_lens','FORWARD'),
              'direction_title':d.get('title',d['id']),'context_score':round(s,4),'context_keyword_hits':hits,
              'target_repositories':d.get('target_repositories',[]),
              'source':c.get('source'),'url':c.get('url'),'title':c.get('title'),'summary':c.get('summary'),'tags':c.get('tags',[]),
              'published':c.get('published'),'updated':c.get('updated'),
              'epistemic_status':'DISCOVERY_CONTEXT__NOT_VERIFIED__NO_PROOF_AUTHORITY',
              'firewall':['SAME_SOURCE_MAY_HAVE_MULTIPLE_DISCOVERY_CONTEXTS','CONTEXT_MATCH_NE_INDEPENDENT_EVIDENCE','MIRROR_LENS_NE_CONFIRMATION']
            }
            append(root/'contexts.jsonl',row); seen[ctx]={'candidate_id':cid,'direction_id':d['id']}; added+=1
    atomic(seen_path,seen); out={'schema':'janus.universal_beetle.context_projection_run.v1','new_contexts':added,'source_candidates_scanned':len(rows),'active_lanes':len(cfg.get('directions',[])),'context_ledger':'contexts.jsonl'}; atomic(root/'latest_context_projection.json',out); print(json.dumps(out,ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
