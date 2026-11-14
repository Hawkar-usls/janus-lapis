#!/usr/bin/env python3
"""Independent ESSENCE core-receipt verifier at the Universal Beetle receiver.

This is a source-bound *search steering* filter, never empirical evidence or
permission to mutate model weights, code, service or the Beetle's durable ACK.
"""
from __future__ import annotations
import copy
import hashlib
import json
from typing import Any

ROLES={
    "beetle": ("Hawkar-usls/janus-lapis","main","data/beetle/directions.json"),
    "demi_head": ("Hawkar-usls/Demi_Head","main","research/essence/peer_v13/source_ledger.json"),
    "demiurge": ("Hawkar-usls/Janus-Demiurge","main","rex/candidates/rex_lifecycle_heartbeat_ledger_health/fitness.json"),
    "genesis": ("Hawkar-usls/Janus_Genesis","main","research/essence/module_organogenesis_v13/generation_0002.json"),
    "neural": ("Hawkar-usls/Janus-Demiurge","research/essence-neural-state","research/essence/neural_duration/state.json"),
    "swarm": ("Hawkar-usls/janus-distributed-ai-swarm","main","research/essence/peer_v13/source_ledger.json"),
}
TOPICS={"essence_independent_core_tests","essence_prospective_weight_gain"}

def sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,
         separators=(",",":"),ensure_ascii=False,allow_nan=False
         ).encode("utf-8")).hexdigest()

def _hex(value: Any, length: int) -> bool:
    return isinstance(value,str) and len(value)==length and all(
        c in "0123456789abcdef" for c in value)

def valid_catalog(catalog: Any, live: Any) -> bool:
    if not isinstance(catalog,dict) or not isinstance(live,dict):
        return False
    if (catalog.get("schema")!="janus.essence.beetle_core_bridge/2.9"
        or catalog.get("status")!="CORE_LINKED_SEARCH_STEERING_ONLY"
        or catalog.get("science_claim")!="RESEARCH_STEERING_NOT_INDEPENDENT_EVIDENCE"
        or catalog.get("authority_delta")!=0
        or catalog.get("automatic_production_promotion") is not False
        or catalog.get("producer_can_modify_model_weights") is not False
        or catalog.get("producer_can_write_other_repositories") is not False
        or catalog.get("source_count")!=6
        or not isinstance(catalog.get("sources"),list)
        or len(catalog["sources"])!=6
        or not isinstance(catalog.get("search_questions"),list)
        or len(catalog["search_questions"])!=2
        or not _hex(catalog.get("receipt_sha256"),64)
        or catalog["receipt_sha256"]!=sha({k:v for k,v in catalog.items()
                                          if k!="receipt_sha256"})
        or live.get("essence_core_bridge_ingested") is not True
        or live.get("core_bridge_scientific_authority") is not False
        or live.get("essence_core_bridge_receipt_sha256")!=catalog["receipt_sha256"]):
        return False
    sources={}
    for item in catalog["sources"]:
        if not isinstance(item,dict):
            return False
        role=item.get("role")
        if (role not in ROLES or role in sources
            or (item.get("repository"),item.get("ref"),item.get("path"))!=ROLES[role]
            or not all(_hex(item.get(k),n) for k,n in
                       (("commit_sha",40),("git_blob_sha1",40),("json_sha256",64)))
            or item.get("scientific_evidence") is not False
            or item.get("production_authority") is not False):
            return False
        sources[role]=item
    if set(sources)!=set(ROLES):
        return False
    questions={}
    for item in catalog["search_questions"]:
        if not isinstance(item,dict) or item.get("id") not in TOPICS:
            return False
        if item["id"] in questions:
            return False
        if (not isinstance(item.get("keywords"),list)
            or not isinstance(item.get("target_repositories"),list)
            or not isinstance(item.get("title"),str)
            or not isinstance(item.get("priority"),(int,float))):
            return False
        questions[item["id"]]=item
    if set(questions)!=TOPICS:
        return False
    claims=[x for x in live.get("ad_hoc_directions",[]) if
            isinstance(x,dict) and x.get("source")=="ESSENCE_CORE_BRIDGE"]
    if not claims or len(claims)>2:
        return False
    ids=set()
    for item in claims:
        key=item.get("id")
        if not isinstance(key,str) or not key.startswith("demiurge_"):
            return False
        core_id=key[len("demiurge_"):]
        if core_id not in questions or core_id in ids:
            return False
        ids.add(core_id)
        expected=questions[core_id]
        if any(item.get(k)!=expected.get(k)
               for k in ("title","keywords","priority","target_repositories")):
            return False
    return True

def filter_core_topics(live: Any, catalog: Any) -> tuple[dict,bool]:
    source=copy.deepcopy(live) if isinstance(live,dict) else {}
    rows=source.get("ad_hoc_directions",[])
    if not isinstance(rows,list):
        source["ad_hoc_directions"]=[]
        return source,False
    claims=[x for x in rows if isinstance(x,dict) and
            x.get("source")=="ESSENCE_CORE_BRIDGE"]
    if not claims:
        return source,False
    valid=valid_catalog(catalog,source)
    if not valid:
        source["ad_hoc_directions"]=[x for x in rows if not (
            isinstance(x,dict) and x.get("source")=="ESSENCE_CORE_BRIDGE")]
    return source,valid
