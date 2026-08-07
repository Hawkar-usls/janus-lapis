#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""iPhone 13 / a-Shell paired live runner for JANUS-LAPIS NerdMinerV2 gate.

Requires sibling file: nerdminer_v2_janus_bridge.py
Default pool is current Public Pool Solo Stratum V1: public-pool.io:3333.
No private key is used. The BTC address is only the worker/payout identifier.
"""

import argparse
import json
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import nerdminer_v2_janus_bridge as core

DEFAULT_POOL = "public-pool.io"
DEFAULT_PORT = 3333
DEFAULT_WALLET = "1F1Y6CdkApZboDF6g1DYrQ8Dke2E5gWiP1"
DEFAULT_WORKER = "JANUS-IP13"


class Tee:
    def __init__(self, path):
        self.console = sys.__stdout__
        self.file = open(path, "a", encoding="utf-8", buffering=1)
    def write(self, s):
        self.console.write(s)
        self.file.write(s)
        self.console.flush()
        self.file.flush()
    def flush(self):
        self.console.flush()
        self.file.flush()
    def close(self):
        self.file.close()


def emit(event, **fields):
    print(json.dumps({
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }, ensure_ascii=False, separators=(",", ":")), flush=True)


def main():
    p = argparse.ArgumentParser(description="JANUS iPhone13 a-Shell live paired tester")
    p.add_argument("--pool", default=DEFAULT_POOL)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--wallet", default=DEFAULT_WALLET)
    p.add_argument("--worker", default=DEFAULT_WORKER)
    p.add_argument("--password", default="x")
    p.add_argument("--jobs", type=int, default=3)
    p.add_argument("--hashes", type=int, default=50000,
                   help="hashes PER strategy, PER real Stratum job")
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--pause", type=float, default=1.0)
    p.add_argument("--submit", action="store_true")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path.cwd() / f"JANUS_IPHONE13_{stamp}.log"
    tee = Tee(log_path)
    sys.stdout = tee
    sys.stderr = tee

    client = None
    try:
        emit("janus_start", identity="JANUS 113.8", device="iPhone13/a-Shell",
             pool=f"{args.pool}:{args.port}", wallet=args.wallet,
             jobs=args.jobs, hashes_per_strategy_per_job=args.hashes,
             submit_enabled=args.submit, log_file=str(log_path))

        if not core.base58check_valid(args.wallet):
            raise RuntimeError("wallet Base58Check failed")

        st = core.selftest()
        emit("ouroboros_selftest", **st)
        if args.selftest:
            emit("janus_stop", reason="selftest_only")
            return 0

        client = core.StratumClient(
            args.pool, args.port, args.wallet, args.worker, args.password, args.timeout
        )
        try:
            client.connect()
        except Exception as exc:
            emit("socket_or_stratum_failure", exception_type=type(exc).__name__,
                 message=str(exc),
                 hint="Send this log as-is; it distinguishes iOS socket/DNS/TCP/Stratum failures.")
            return 3

        emit("stratum_connected", worker=client.worker_name,
             extranonce1=client.extranonce1,
             extranonce2_size=client.extranonce2_size,
             share_difficulty=client.share_difficulty)

        completed = 0
        ex2_counter = 1
        submitted = set()
        while completed < args.jobs:
            try:
                msg = client.read_message()
            except socket.timeout:
                emit("stratum_timeout", timeout_s=args.timeout)
                continue

            method = msg.get("method")
            if method == "mining.set_difficulty":
                client.share_difficulty = float(msg["params"][0])
                emit("pool_difficulty", difficulty=client.share_difficulty)
                continue
            if method != "mining.notify":
                if msg.get("id") is not None:
                    emit("stratum_response", id=msg.get("id"),
                         result=msg.get("result"), error=msg.get("error"))
                continue

            job = core.StratumJob.from_notify(msg["params"])
            ex2 = core.fixed_extranonce2(client.extranonce2_size)
            if client.extranonce2_size > 0:
                ex2 = (ex2_counter % (1 << (8 * min(client.extranonce2_size, 8)))).to_bytes(
                    client.extranonce2_size if client.extranonce2_size <= 8 else 4, "big"
                ).hex()
            ex2_counter += 1

            prefix = core.nerdminer_header_prefix(job, client.extranonce1, ex2)
            network_target = core.compact_to_target(job.nbits)
            completed += 1
            start_nonce = (core.NERDMINER_START_NONCE + (completed - 1) * args.hashes) & core.MASK32

            emit("job_begin", index=completed, job_id=job.job_id,
                 nbits=job.nbits, ntime=job.ntime, extranonce2=ex2,
                 share_difficulty=client.share_difficulty)

            seq, seq_hits = core.scan(
                prefix, core.sequential_nonces(args.hashes, start_nonce),
                client.share_difficulty, network_target, "nerdminer-sequential"
            )
            emit("scan_complete", strategy=seq.strategy, hashes=seq.hashes,
                 share_hits=seq.share_hits, block_hits=seq.block_hits,
                 best_nonce=f"{seq.best_nonce:08x}", best_hash=seq.best_hash,
                 best_difficulty=seq.best_difficulty, elapsed_s=seq.elapsed_s, khs=seq.khs)

            if args.pause > 0:
                time.sleep(args.pause)

            jan, jan_hits = core.scan(
                prefix, core.janus_nonces(args.hashes, prefix, start_nonce),
                client.share_difficulty, network_target, "janus-permuted"
            )
            emit("scan_complete", strategy=jan.strategy, hashes=jan.hashes,
                 share_hits=jan.share_hits, block_hits=jan.block_hits,
                 best_nonce=f"{jan.best_nonce:08x}", best_hash=jan.best_hash,
                 best_difficulty=jan.best_difficulty, elapsed_s=jan.elapsed_s, khs=jan.khs)

            winner = "tie"
            if seq.best_difficulty > jan.best_difficulty:
                winner = "nerdminer-sequential"
            elif jan.best_difficulty > seq.best_difficulty:
                winner = "janus-permuted"
            emit("paired_result", job_id=job.job_id, pair_winner=winner,
                 sequential_best_difficulty=seq.best_difficulty,
                 janus_best_difficulty=jan.best_difficulty,
                 sequential_share_hits=seq.share_hits,
                 janus_share_hits=jan.share_hits)

            for strategy, hits in (("nerdminer-sequential", seq_hits), ("janus-permuted", jan_hits)):
                for nonce, display_hash in hits:
                    key = (job.job_id, ex2, nonce)
                    if key in submitted:
                        continue
                    submitted.add(key)
                    achieved = core.hash_difficulty(core.dsha(core.header_with_nonce(prefix, nonce)))
                    is_block = core.hash_value(core.dsha(core.header_with_nonce(prefix, nonce))) <= network_target
                    if args.submit:
                        sid = client.submit(job, ex2, nonce)
                        emit("share_submitted", id=sid, strategy=strategy, job_id=job.job_id,
                             nonce=f"{nonce:08x}", hash=display_hash,
                             achieved_difficulty=achieved, block_candidate=is_block,
                             payout_worker=client.worker_name)
                    else:
                        emit("qualifying_share_dry_run", strategy=strategy, job_id=job.job_id,
                             nonce=f"{nonce:08x}", hash=display_hash,
                             achieved_difficulty=achieved, block_candidate=is_block)

            emit("job_end", index=completed)
            if args.pause > 0 and completed < args.jobs:
                time.sleep(args.pause)

        emit("janus_stop", reason="requested_job_count_completed", completed_jobs=completed)
        return 0

    except KeyboardInterrupt:
        emit("janus_stop", reason="keyboard_interrupt")
        return 130
    except Exception as exc:
        emit("fatal_exception", exception_type=type(exc).__name__, message=str(exc))
        return 1
    finally:
        try:
            if client is not None:
                client.close()
        finally:
            sys.stdout = tee.console
            sys.stderr = tee.console
            tee.close()
            print(f"LOG: {log_path}")


if __name__ == "__main__":
    raise SystemExit(main())
