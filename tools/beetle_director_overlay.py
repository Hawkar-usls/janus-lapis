#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, datetime as dt, json, pathlib, re
from typing import Any
import requests


def now_dt(): return dt.datetime.now(dt.timezone.utc)
def now(): return now_dt().isoformat().replace('+00:00','Z')

def load_local(p): return json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
def load_remote(url: str) -> dict[str,Any]:
    try:
        r=requests.get(url,timeout=30,headers={'User-Agent':'JANUS-Beetle-Director-Overlay/1.0'})
        r.raise_for_status(); obj=r.json(); return obj if isinstance(obj,dict) else {}
    except Exception:
        return {}

def atomic(path: pathlib.Path,obj: Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    tmp.replace(path)

def parse_time(s: str|None):
    if not s: return None
    try: return dt.datetime.fromisoformat(s.replace('Z','+00:00'))
    except Exception: return None

def source_with_lens(src: dict[str,Any], terms: list[str], lens: str) -> dict[str,Any]:
    out=copy.deepcopy(src)
    if lens=='FORWARD' or not terms: return out
    kind=out.get('kind'); q=str(out.get('query','')).strip(); t=terms[:4]
    if kind=='arxiv':
        suffix=' OR '.join(f'all:"{x}"' for x in t)
        out['query']=f'({q}) AND ({suffix})' if q else suffix
    elif kind in {'github','zenodo'}:
        out['query']=(q+' '+' '.join(t[:3])).strip()
    return out

def make_lane(direction: dict[str,Any], lens: str, lens_cfg: dict[str,Any], priority: float) -> dict[str,Any]:
    d=copy.deepcopy(direction)
    base=d['id']; terms=[str(x) for x in lens_cfg.get('terms',[])]
    d['id']=f'{base}::{lens}'
    d['base_direction_id']=base
    d['mirror_lens']=lens
    d['title']=f"{d.get('title',base)} [{lens}]"
    d['effective_priority']=round(priority*float(lens_cfg.get('weight',1.0)),4)
    if terms:
        d['keywords']=list(dict.fromkeys(list(d.get('keywords',[]))+terms))
        d['priority_keywords']=list(dict.fromkeys(list(d.get('priority_keywords',[]))+terms[:4]))
    d['sources']=[source_with_lens(s,terms,lens) for s in d.get('sources',[])]
    return d

def adhoc_to_direction(row: dict[str,Any]) -> dict[str,Any]:
    kws=[str(x) for x in row.get('keywords',[]) if str(x).strip()][:12]
    q=' '.join(kws[:5])
    aq=' OR '.join(f'all:"{x}"' for x in kws[:5])
    return {
      'id':row['id'],'title':row.get('title',row['id']),'enabled':True,
      'priority':float(row.get('priority',65)),'min_score':1.0,
      'mirror_lenses':['FORWARD','REVERSE','COUNTEREVIDENCE','CONTROL'],
      'priority_keywords':kws[:4],'keywords':kws,
      'target_repositories':row.get('target_repositories',[]),
      'sources':[{'kind':'arxiv','enabled':True,'query':aq,'max_results':8},{'kind':'zenodo','enabled':True,'query':q,'max_results':8},{'kind':'github','enabled':True,'query':q,'max_results':8}]
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base',required=True); ap.add_argument('--static-url',required=True); ap.add_argument('--live-url',required=True)
    ap.add_argument('--state-dir',required=True); ap.add_argument('--out',required=True)
    a=ap.parse_args()
    base=load_local(a.base); static=load_remote(a.static_url); live=load_remote(a.live_url)
    state_dir=pathlib.Path(a.state_dir); sched_path=state_dir/'scheduler.json'
    sched=json.loads(sched_path.read_text()) if sched_path.exists() else {'lanes':{},'runs':0}
    priorities={d['id']:float(d.get('priority',0)) for d in base.get('directions',[])}
    priorities.update({k:float(v) for k,v in static.get('base_priorities',{}).items() if k in priorities})
    priorities.update({k:float(v) for k,v in live.get('direction_priorities',{}).items() if k in priorities})
    directions=[copy.deepcopy(d) for d in base.get('directions',[]) if d.get('enabled',True)]
    allow=set(static.get('allowed_target_repositories',[]))
    for ad in live.get('ad_hoc_directions',[]) if isinstance(live.get('ad_hoc_directions',[]),list) else []:
        targets=[x for x in ad.get('target_repositories',[]) if x in allow]
        if targets and ad.get('keywords'):
            z=dict(ad); z['target_repositories']=targets; directions.append(adhoc_to_direction(z)); priorities[z['id']]=float(z.get('priority',65))
    max_primary=int(static.get('scheduling',{}).get('max_primary_directions_per_hour',5))
    max_lanes=int(static.get('scheduling',{}).get('max_mirror_lanes_per_hour',8))
    primary=sorted(directions,key=lambda d:(priorities.get(d['id'],float(d.get('priority',0))),d['id']),reverse=True)[:max_primary]
    lens_defs=static.get('mirror_lenses',{}) or {x:{'weight':1.0,'terms':[]} for x in base.get('default_mirror_lenses',[]) }
    candidates=[]; tnow=now_dt()
    for d in primary:
        for lens in d.get('mirror_lenses',base.get('default_mirror_lenses',['FORWARD'])):
            lc=lens_defs.get(lens,{'weight':1.0,'terms':[]}); key=f"{d['id']}::{lens}"
            last=parse_time(sched.get('lanes',{}).get(key,{}).get('last_selected_at'))
            stale_h=(tnow-last).total_seconds()/3600 if last else 999.0
            p=priorities.get(d['id'],float(d.get('priority',0)))*float(lc.get('weight',1.0))
            # priority dominates; staleness prevents starvation without turning low-priority lanes into evidence.
            rank=p+min(20.0,stale_h*float(static.get('scheduling',{}).get('staleness_bonus_per_hour',0.02)))
            candidates.append((rank,stale_h,key,d,lens,lc,p))
    selected=sorted(candidates,key=lambda x:(x[0],x[1],x[2]),reverse=True)[:max_lanes]
    if static.get('scheduling',{}).get('reserve_one_fairness_slot',True) and candidates and selected:
        oldest=max(candidates,key=lambda x:(x[1],x[2]))
        if oldest[2] not in {x[2] for x in selected}:
            selected[-1]=oldest
    lanes=[]
    for _,_,key,d,lens,lc,p in selected:
        lanes.append(make_lane(d,lens,lc,p))
        sched.setdefault('lanes',{}).setdefault(key,{})['last_selected_at']=now()
        sched['lanes'][key]['times_selected']=int(sched['lanes'][key].get('times_selected',0))+1
    sched['runs']=int(sched.get('runs',0))+1; sched['last_run_at']=now(); atomic(sched_path,sched)
    eff=copy.deepcopy(base); eff['version']=str(base.get('version','2.0'))+'-effective'; eff['directions']=lanes
    eff['effective_meta']={
      'generated_at':now(),'static_directives_loaded':bool(static),'live_priorities_loaded':bool(live),
      'live_source_scout_run_id':live.get('source_scout_run_id'),'selected_base_directions':[d['id'] for d in primary],
      'selected_lanes':[d['id'] for d in lanes], 'priority_semantics':'ATTENTION_ONLY_NOT_EVIDENCE'
    }
    atomic(pathlib.Path(a.out),eff); print(json.dumps(eff['effective_meta'],ensure_ascii=False))
    return 0
if __name__=='__main__': raise SystemExit(main())
