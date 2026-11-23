#!/usr/bin/env python3
"""P0.3 bounded private ACK readiness: report counts, never secret or ACK bytes.

The Actions GITHUB_TOKEN scoped to janus-lapis cannot automatically read the
private SkinGPT inbox. Only a separate contents:read secret can authorize it.
No network requests are made when the secret is absent. Output NEVER contains
the credential, batch IDs, ACK body, timestamps or private SHA values.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path

from beetle_delivery_health import (
    PRIVATE_ACK_REPOSITORY, PRIVATE_ACK_TOKEN_ENV,
    fetch_scoped_private_ack, inspect_queue
)

SCHEMA="janus.beetle.private_ack_readiness.v1"
QUEUE=Path("mirrors/Hawkar-usls__SkinGPT/delivery.json")


def assess(queue, token_present: bool, ack, error=None):
    if not isinstance(queue,dict) or queue.get("target_repository")!=PRIVATE_ACK_REPOSITORY:
        raise ValueError("P03_QUEUE_SCOPE_DENIED")
    entries=queue.get("entries")
    if (queue.get("schema")!="janus.beetle.delivery_queue.v1"
        or type(entries) is not list or len(entries)>1000
        or type(queue.get("next_sequence")) is not int
        or queue["next_sequence"]!=len(entries)+1):
        raise ValueError("P03_QUEUE_STRUCTURE_INVALID")
    for i,x in enumerate(entries,1):
        if (type(x) is not dict or type(x.get("sequence")) is not int
            or x["sequence"]!=i
            or not isinstance(x.get("created_at"),str)
            or not re.fullmatch(r"[0-9a-f]{20}",str(x.get("batch_id","")))
            or not re.fullmatch(r"[0-9a-f]{64}",str(x.get("sha256","")))):
            raise ValueError("P03_QUEUE_SOURCE_ENTRY_INVALID")
    # The original sender validator rejects mismatched identities and SHA.
    if not token_present:
        status="HOLD_READ_CREDENTIAL_NOT_CONFIGURED"
        confirmed=0
        produced=len(queue.get("entries", []))
        pending=produced
    elif ack is None:
        status="HOLD_PRIVATE_ACK_UNAVAILABLE"
        confirmed=0
        produced=len(queue.get("entries", []))
        pending=produced
    else:
        observed=inspect_queue(queue,ack,error,dt.datetime(2026,11,23,tzinfo=dt.timezone.utc),180)
        produced=observed["produced"]
        confirmed=observed["confirmed"]
        pending=observed["pending"]
        status=(
            "INBOX_DURABLE_ACK_MATCHED__NOT_CONSUMED" if observed["status"]=="UP_TO_DATE"
            else "HOLD_PRIVATE_ACK_CONFLICT" if observed["status"]=="ACK_CONFLICT"
            else "HOLD_PRIVATE_ACK_PENDING"
        )
    result={
        "schema":SCHEMA,"status":status,
        "target_repository":PRIVATE_ACK_REPOSITORY,
        "produced":produced,"confirmed":confirmed,"pending":pending,
        "credential_scope":"REQUIRES_SEPARATELY_CONFIGURED_PRIVATE_CONTENTS_READ",
        "token_value_output":False,"private_ack_contents_output":False,
        "receipt_or_model_consumption_attested":False,
        "external_custodian_attested":False,
        "p03_phase_admitted":False,"producer_workflow_dispatched":False,
        "routing_or_queue_modified":False,
    }
    result["result_sha256"]=hashlib.sha256(json.dumps(result,sort_keys=True,
        ensure_ascii=False,separators=(",",":")).encode("utf-8")).hexdigest()
    return result


def check(state_dir:Path, fetcher=fetch_scoped_private_ack):
    path=state_dir/QUEUE
    if path.is_symlink() or not path.is_file() or path.stat().st_size>100_000:
        raise ValueError("P03_QUEUE_MISSING_OR_UNSAFE")
    queue=json.loads(path.read_bytes())
    token=os.environ.get(PRIVATE_ACK_TOKEN_ENV,"")
    ack,error=fetcher(PRIVATE_ACK_REPOSITORY,token) if token else (None,None)
    return assess(queue,bool(token),ack,error)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--state-dir",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    result=check(args.state_dir)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    if args.out.is_file():
        raise ValueError("P03_DIAGNOSTIC_RECEIPT_EXISTS")
    args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"produced":result["produced"],
      "confirmed":result["confirmed"],"pending":result["pending"],
      "result_sha256":result["result_sha256"]},sort_keys=True))


if __name__=="__main__":
    main()
