#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, pathlib, re
from typing import Any

def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def safe_repo(repo:str)->str: return re.sub(r'[^A-Za-z0-9_.-]+','__',repo)
def load_json(p:pathlib.Path,default):
    if not p.exists(): return default
    return json.loads(p.read_text(encoding='utf-8'))
def atomic(p:pathlib.Path,obj:Any):
    p.parent.mkdir(parents=True,exist_ok=True); tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8'); tmp.replace(p)
def canon(obj): return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--state-dir',required=True); ap.add_argument('--effective-config',required=True); ap.add_argument('--max-candidates',type=int,default=300); a=ap.parse_args()
    root=pathlib.Path(a.state_dir); cfg=load_json(pathlib.Path(a.effective_config),{})
    routes={d['id']:d.get('target_repositories',[]) for d in cfg.get('directions',[])}
    route_meta={d['id']:{'base_direction_id':d.get('base_direction_id',d['id']),'mirror_lens':d.get('mirror_lens','FORWARD'),'title':d.get('title',d['id'])} for d in cfg.get('directions',[])}
    seen_path=root/'route_seen.json'; seen=load_json(seen_path,{})
    cand_path=root/'candidates.jsonl'; rows=[]
    if cand_path.exists():
        with cand_path.open(encoding='utf-8',errors='replace') as f:
            for line in f:
                if line.strip():
                    try: rows.append(json.loads(line))
                    except Exception: pass
    rows=rows[-a.max_candidates:]
    per_repo={}
    for c in rows:
        did=c.get('direction_id'); cid=c.get('candidate_id')
        if not did or not cid or did not in routes: continue
        for repo in routes[did]:
            token=f'{cid}|{repo}'
            if token in seen: continue
            m=route_meta[did]
            item={
              'schema':'janus.beetle.repo_memory_item.v1','routed_at':now(),'target_repository':repo,
              'candidate_id':cid,'direction_id':did,'base_direction_id':m['base_direction_id'],'mirror_lens':m['mirror_lens'],
              'direction_title':m['title'],'source':c.get('source'),'url':c.get('url'),'title':c.get('title'),
              'summary':c.get('summary'),'tags':c.get('tags',[]),'score':c.get('score'),'keyword_hits':c.get('keyword_hits',[]),
              'source_published':c.get('published'),'source_updated':c.get('updated'),
              'epistemic_status':'DISCOVERY_INBOX__UNVERIFIED__NO_PROOF_AUTHORITY',
              'firewall':['ROUTED_NE_VERIFIED','INBOX_NE_EVIDENCE','PRIORITY_NE_TRUTH','MIRROR_LENS_NE_CONFIRMATION']
            }
            per_repo.setdefault(repo,[]).append(item); seen[token]={'routed_at':item['routed_at'],'direction_id':did}
    summary={'schema':'janus.beetle.mirror_router.run.v1','at':now(),'repositories':{},'total_new_items':0}
    for repo,items in sorted(per_repo.items()):
        payload={'schema':'janus.beetle.repo_memory_batch.v1','created_at':now(),'target_repository':repo,'items':items,
                 'claim_ceiling':'DISCOVERY_MEMORY_ONLY__TARGET_REPO_MUST_VERIFY_INDEPENDENTLY'}
        bid=hashlib.sha256(canon(payload)).hexdigest()[:20]; payload['batch_id']=bid
        d=root/'mirrors'/safe_repo(repo); atomic(d/'batches'/f'{bid}.json',payload); atomic(d/'latest.json',payload)
        summary['repositories'][repo]={'batch_id':bid,'new_items':len(items)}; summary['total_new_items']+=len(items)
    atomic(seen_path,seen); atomic(root/'latest_routing.json',summary); print(json.dumps(summary,ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
