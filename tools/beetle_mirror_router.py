#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, pathlib, re
from collections import deque
from typing import Any
from beetle_shard_store import iter_lines

LENSES=("FORWARD","REVERSE","COUNTEREVIDENCE","CONTROL")
MAX_BATCH_BYTES=4_000_000  # Must agree with every Beetle memory receiver.

def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def safe_repo(repo:str)->str: return re.sub(r'[^A-Za-z0-9_.-]+','__',repo)
def load_json(p:pathlib.Path,default):
    if not p.exists(): return default
    return json.loads(p.read_text(encoding='utf-8'))
def atomic(p:pathlib.Path,obj:Any):
    p.parent.mkdir(parents=True,exist_ok=True); tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8'); tmp.replace(p)
def canon(obj): return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def encoded(obj): return (json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode('utf-8')
def queue_batch(directory:pathlib.Path,repo:str,payload:dict[str,Any],created_at:str)->int:
    """Keep every new snapshot addressable until the receiver acknowledges it.

    The queue and immutable batch are committed together on beetle-state.  A
    receiver that wakes hourly can therefore replay all 20-minute snapshots.
    """
    if len(encoded(payload))>MAX_BATCH_BYTES:
        raise ValueError(f'Beetle delivery batch exceeds receiver limit: {repo}')
    path=directory/'delivery.json'; queue=load_json(path,{
      'schema':'janus.beetle.delivery_queue.v1','target_repository':repo,
      'next_sequence':1,'entries':[]})
    if queue.get('schema')!='janus.beetle.delivery_queue.v1' or queue.get('target_repository')!=repo:
        raise ValueError(f'invalid delivery queue for {repo}')
    entries=queue.get('entries')
    if not isinstance(entries,list) or queue.get('next_sequence')!=len(entries)+1:
        raise ValueError(f'broken delivery sequence for {repo}')
    for index,item in enumerate(entries,1):
        if item.get('sequence')!=index: raise ValueError(f'noncontiguous delivery sequence for {repo}')
    bid=payload['batch_id']; batch_path=directory/'batches'/f'{bid}.json'
    if batch_path.exists():
        if load_json(batch_path,None)!=payload:
            raise ValueError(f'immutable batch collision: {repo}/{bid}')
    else:
        atomic(batch_path,payload)
    digest=hashlib.sha256(batch_path.read_bytes()).hexdigest()
    previous=next((e for e in entries if e['batch_id']==bid),None)
    if previous:
        if previous['sha256']!=digest: raise ValueError(f'batch hash drift: {repo}/{bid}')
        return int(previous['sequence'])
    sequence=queue['next_sequence']
    entries.append({'sequence':sequence,'batch_id':bid,'sha256':digest,'created_at':created_at})
    queue['next_sequence']=sequence+1
    atomic(path,queue)
    return sequence

def make_packet(repo:str,items:list[dict[str,Any]],snapshot_cap:int,
                fragment_index:int,fragment_count:int,snapshot_items_total:int)->dict[str,Any]:
    """Commit to *all* routed bytes, including metadata, not only context IDs.

    Previously a fixed set of IDs with an updated summary reused a batch ID
    but had different bytes, permanently colliding with an immutable package.
    """
    body={'schema':'janus.beetle.repo_memory_batch.v1','target_repository':repo,
          'items':items,'selection':'BALANCED_LENS_ROLLING_TOP','snapshot_cap':snapshot_cap,
          'fragment_index':fragment_index,'fragment_count':fragment_count,
          'snapshot_items_total':snapshot_items_total,
          'claim_ceiling':'DISCOVERY_MEMORY_ONLY__TARGET_REPO_MUST_VERIFY_INDEPENDENTLY'}
    bid=hashlib.sha256(canon(body)).hexdigest()[:20]
    return {'batch_id':bid,**body}

def queue_snapshot(directory:pathlib.Path,repo:str,selected:list[dict[str,Any]],
                   snapshot_cap:int,created_at:str,*,max_bytes:int=MAX_BATCH_BYTES)->list[tuple[dict[str,Any],int]]:
    """Preserve an oversize snapshot as several immutable receiver-sized parts.

    All parts are validated before the first queue mutation. The receiver
    replays the parts in order, so no selected context is silently discarded.
    Full raw discovery evidence remains in the sharded Beetle source store.
    """
    if not 1<=max_bytes<=MAX_BATCH_BYTES or not selected:
        raise ValueError('invalid Beetle snapshot size or empty selection')
    fragments:list[list[dict[str,Any]]]=[]
    current:list[dict[str,Any]]=[]
    # Conservative estimate reserves sufficient decimal digits for *any*
    # fragment index/count before publishing the final content-addressed ID.
    upper=len(selected)
    for item in selected:
        trial=current+[item]
        probe=make_packet(repo,trial,snapshot_cap,upper,upper,len(selected))
        if len(encoded(probe))>max_bytes:
            if not current:
                raise ValueError(f'single Beetle discovery exceeds receiver limit: {repo}')
            fragments.append(current)
            current=[item]
            probe=make_packet(repo,current,snapshot_cap,upper,upper,len(selected))
            if len(encoded(probe))>max_bytes:
                raise ValueError(f'single Beetle discovery exceeds receiver limit: {repo}')
        else:
            current=trial
    if current:
        fragments.append(current)
    packets=[make_packet(repo,items,snapshot_cap,index,len(fragments),len(selected))
             for index,items in enumerate(fragments,1)]
    if any(len(encoded(packet))>max_bytes for packet in packets):
        raise ValueError('Beetle fragment planning exceeded receiver cap')
    # No queue change before every fragment passes the size/address checks.
    return [(packet,queue_batch(directory,repo,packet,created_at)) for packet in packets]
def preview_text(value:Any,limit:int)->str:
    return str(value or '')[:limit]
def preview_list(value:Any,limit:int=32)->list[str]:
    return [preview_text(x,100) for x in value[:limit]] if isinstance(value,list) else []
def to_item(c:dict[str,Any],repo:str)->dict[str,Any]:
    # A preview is not the archived raw source. Bound every untrusted text
    # field before it enters a cross-repository Git blob; retain its full
    # source hash for independent lookup against the sharded source archive.
    item={
      'schema':'janus.beetle.repo_memory_item.v2','target_repository':repo,
      'candidate_id':preview_text(c.get('candidate_id'),128),'context_id':preview_text(c.get('context_id'),128),
      'direction_id':preview_text(c.get('direction_id'),256),
      'base_direction_id':preview_text(c.get('base_direction_id',c.get('direction_id')),256),
      'mirror_lens':c.get('mirror_lens','FORWARD'),
      'direction_title':preview_text(c.get('direction_title',c.get('direction_id')),256),
      'source':preview_text(c.get('source'),120),'url':preview_text(c.get('url'),1500),
      'title':preview_text(c.get('title'),300),'summary':preview_text(c.get('summary'),6000),
      'tags':preview_list(c.get('tags',[])),'score':c.get('context_score'),
      'keyword_hits':preview_list(c.get('context_keyword_hits',[])),
      'source_published':preview_text(c.get('published'),80),
      'source_updated':preview_text(c.get('updated'),80),
      'epistemic_status':'DISCOVERY_INBOX__UNVERIFIED__NO_PROOF_AUTHORITY',
      'source_context_sha256':hashlib.sha256(canon(c)).hexdigest(),
      'delivery_preview_only':True,
      'firewall':['ROUTED_NE_VERIFIED','INBOX_NE_EVIDENCE','PRIORITY_NE_TRUTH','MIRROR_LENS_NE_CONFIRMATION','SAME_SOURCE_CONTEXTS_NE_INDEPENDENT_SOURCES']
    }
    item['delivery_preview_truncated']=any([
        len(str(c.get('summary') or ''))>6000, len(str(c.get('title') or ''))>300,
        len(str(c.get('url') or ''))>1500,
        any(isinstance(c.get(k),list) and len(c[k])>32 for k in ('tags','context_keyword_hits')),
    ])
    return item
def compact(items:list[dict[str,Any]],limit:int)->list[dict[str,Any]]:
    # Stable rank: scientific relevance score first, then context id.
    ranked=sorted(items,key=lambda x:(float(x.get('score') or 0),str(x.get('context_id') or '')),reverse=True)
    quota=max(1,limit//len(LENSES)); chosen=[]; ids=set()
    for lens in LENSES:
        lane=[x for x in ranked if x.get('mirror_lens')==lens]
        for x in lane[:quota]:
            cid=x.get('context_id')
            if cid not in ids: chosen.append(x); ids.add(cid)
    for x in ranked:
        if len(chosen)>=limit: break
        cid=x.get('context_id')
        if cid not in ids: chosen.append(x); ids.add(cid)
    return chosen[:limit]
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--state-dir',required=True); ap.add_argument('--effective-config',required=True); ap.add_argument('--max-contexts',type=int,default=1200); ap.add_argument('--max-items-per-repo',type=int,default=48); a=ap.parse_args()
    root=pathlib.Path(a.state_dir); cfg=load_json(pathlib.Path(a.effective_config),{})
    routes={d['id']:d.get('target_repositories',[]) for d in cfg.get('directions',[])}
    seen_path=root/'route_seen.json'; seen=load_json(seen_path,{})
    rows=deque(maxlen=a.max_contexts)
    for line in iter_lines(root,'contexts'):
        if line.strip():
            try: rows.append(json.loads(line))
            except Exception: pass
    eligible:dict[str,list[dict[str,Any]]]={}
    for c in rows:
        did=c.get('direction_id'); cid=c.get('candidate_id'); ctx=c.get('context_id')
        if not did or not cid or not ctx or did not in routes: continue
        for repo in routes[did]: eligible.setdefault(repo,[]).append(to_item(c,repo))
    summary={'schema':'janus.beetle.mirror_router.run.v3','at':now(),'repositories':{},'total_snapshot_items':0,'total_newly_selected_contexts':0,'input':'contexts.parts/','snapshot_cap_per_repo':a.max_items_per_repo}
    for repo,items in sorted(eligible.items()):
        selected=compact(items,a.max_items_per_repo)
        d=root/'mirrors'/safe_repo(repo)
        sent=queue_snapshot(d,repo,selected,a.max_items_per_repo,summary['at'])
        payload,sequence=sent[-1]
        bid=payload['batch_id']
        atomic(d/'latest.json',payload)  # legacy readers see a labelled final fragment
        new_count=0; lens_counts={lens:0 for lens in LENSES}
        for x in selected:
            lens=str(x.get('mirror_lens','FORWARD')); lens_counts[lens]=lens_counts.get(lens,0)+1
            token=f"{x['context_id']}|{repo}"
            if token not in seen:
                new_count+=1; seen[token]={'first_selected_at':summary['at'],'direction_id':x.get('direction_id'),'context_id':x.get('context_id')}
        summary['repositories'][repo]={'batch_id':bid,'delivery_sequence':sequence,
            'batch_ids':[packet['batch_id'] for packet,_ in sent],
            'delivery_sequences':[seq for _,seq in sent],
            'fragment_count':len(sent),'snapshot_items':len(selected),
            'newly_selected_contexts':new_count,'lens_counts':lens_counts,'eligible_contexts':len(items)}
        summary['total_snapshot_items']+=len(selected); summary['total_newly_selected_contexts']+=new_count
    atomic(seen_path,seen); atomic(root/'latest_routing.json',summary); print(json.dumps(summary,ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
