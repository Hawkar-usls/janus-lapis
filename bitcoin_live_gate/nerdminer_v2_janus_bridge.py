#!/usr/bin/env python3
"""
JANUS-LAPIS / NerdMinerV2 Stratum bridge.

Purpose
-------
Reproduce the NerdMinerV2 Stratum-v1 job/header pipeline and compare two
nonce traversals on the *same* Bitcoin header prefix:

  nerdminer-sequential : contiguous uint32 nonce order
  janus-permuted       : deterministic full-cycle affine permutation

The JANUS permutation does not claim to predict SHA-256. It is a bijective
reordering of the same nonce space, useful for paired experiments.

Live mode is DRY-RUN by default. Add --submit to transmit qualifying shares.
No private key is required; the Bitcoin address is only the pool worker/payout
identifier.

Reference implementation behavior mirrored from BitMaker-hub/NerdMiner_v2:
- mining.subscribe user-agent NerdMinerV2/<version>
- mining.authorize [wallet.worker, password]
- mining.suggest_difficulty
- extranonce2 fixed to ...0001 for sizes 2/4/8
- version byte reversal, prevhash 4-byte word swap, ntime/nbits reversal
- coinbase and merkle double-SHA256
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import struct
import time
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional

MASK32 = 0xFFFFFFFF
DIFF1_TARGET = int("00000000ffff0000000000000000000000000000000000000000000000000000", 16)
NERDMINER_DEFAULT_DIFFICULTY = 0.00015
NERDMINER_START_NONCE = 0xDA54E700
DEFAULT_WALLET = "1F1Y6CdkApZboDF6g1DYrQ8Dke2E5gWiP1"
DEFAULT_POOL = "public-pool.io"
DEFAULT_PORT = 21496


def dsha(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def base58check_valid(address: str) -> bool:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    try:
        for ch in address:
            n = n * 58 + alphabet.index(ch)
    except ValueError:
        return False
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = 0
    for ch in address:
        if ch == "1":
            pad += 1
        else:
            break
    raw = b"\x00" * pad + raw
    if len(raw) < 5:
        return False
    payload, checksum = raw[:-4], raw[-4:]
    return dsha(payload)[:4] == checksum


def difficulty_to_target(difficulty: float) -> int:
    if difficulty <= 0:
        raise ValueError("difficulty must be > 0")
    return min((1 << 256) - 1, int(DIFF1_TARGET / difficulty))


def compact_to_target(nbits_hex: str) -> int:
    compact = int(nbits_hex, 16)
    exponent = compact >> 24
    coefficient = compact & 0x007FFFFF
    if compact & 0x00800000:
        raise ValueError("negative compact targets are invalid")
    if exponent <= 3:
        return coefficient >> (8 * (3 - exponent))
    return coefficient << (8 * (exponent - 3))


def hash_value(raw_digest: bytes) -> int:
    return int.from_bytes(raw_digest, "little")


def hash_difficulty(raw_digest: bytes) -> float:
    v = hash_value(raw_digest)
    if v == 0:
        return float("inf")
    return DIFF1_TARGET / v


def fixed_extranonce2(size: int) -> str:
    if size not in (2, 4, 8):
        size = 4
    return (1).to_bytes(size, "big").hex()


def swap_prevhash_words(prevhash_hex: str) -> bytes:
    b = bytes.fromhex(prevhash_hex)
    if len(b) != 32:
        raise ValueError("prevhash must be 32 bytes")
    return b"".join(b[i:i+4][::-1] for i in range(0, 32, 4))


@dataclass
class StratumJob:
    job_id: str
    prevhash: str
    coinb1: str
    coinb2: str
    merkle_branch: list[str]
    version: str
    nbits: str
    ntime: str
    clean_jobs: bool = True

    @classmethod
    def from_notify(cls, params: list) -> "StratumJob":
        if len(params) < 9:
            raise ValueError("mining.notify requires 9 params")
        return cls(
            job_id=str(params[0]),
            prevhash=str(params[1]),
            coinb1=str(params[2]),
            coinb2=str(params[3]),
            merkle_branch=[str(x) for x in params[4]],
            version=str(params[5]),
            nbits=str(params[6]),
            ntime=str(params[7]),
            clean_jobs=bool(params[8]),
        )


def coinbase_hash(job: StratumJob, extranonce1: str, extranonce2: str) -> bytes:
    coinbase = bytes.fromhex(job.coinb1 + extranonce1 + extranonce2 + job.coinb2)
    return dsha(coinbase)


def merkle_root(job: StratumJob, extranonce1: str, extranonce2: str) -> bytes:
    root = coinbase_hash(job, extranonce1, extranonce2)
    for branch_hex in job.merkle_branch:
        root = dsha(root + bytes.fromhex(branch_hex))
    return root


def nerdminer_header_prefix(job: StratumJob, extranonce1: str, extranonce2: str) -> bytes:
    """Return the first 76 header bytes in NerdMinerV2's byte order."""
    version = bytes.fromhex(job.version)[::-1]
    prevhash = swap_prevhash_words(job.prevhash)
    merkle = merkle_root(job, extranonce1, extranonce2)
    ntime = bytes.fromhex(job.ntime)[::-1]
    nbits = bytes.fromhex(job.nbits)[::-1]
    prefix = version + prevhash + merkle + ntime + nbits
    if len(prefix) != 76:
        raise AssertionError(f"header prefix is {len(prefix)} bytes, expected 76")
    return prefix


def header_with_nonce(prefix76: bytes, nonce: int) -> bytes:
    if len(prefix76) != 76:
        raise ValueError("prefix must be exactly 76 bytes")
    return prefix76 + struct.pack("<I", nonce & MASK32)


def affine_parameters(seed_material: bytes) -> tuple[int, int]:
    h = hashlib.sha256(seed_material).digest()
    a = int.from_bytes(h[:4], "little") | 1
    b = int.from_bytes(h[4:8], "little")
    return a, b


def sequential_nonces(count: int, start: int = NERDMINER_START_NONCE) -> Iterator[int]:
    for i in range(count):
        yield (start + i) & MASK32


def janus_nonces(count: int, prefix76: bytes, start: int = NERDMINER_START_NONCE) -> Iterator[int]:
    a, b = affine_parameters(prefix76 + struct.pack("<I", start & MASK32))
    for i in range(count):
        yield (a * i + b + start) & MASK32


@dataclass
class ScanResult:
    strategy: str
    hashes: int
    share_hits: int
    block_hits: int
    best_nonce: int
    best_hash: str
    best_difficulty: float
    elapsed_s: float

    @property
    def khs(self) -> float:
        return (self.hashes / max(self.elapsed_s, 1e-12)) / 1000.0


def scan(prefix76: bytes, nonces: Iterable[int], share_difficulty: float,
         network_target: int, strategy: str) -> tuple[ScanResult, list[tuple[int, str]]]:
    share_target = difficulty_to_target(share_difficulty)
    best_value = (1 << 256) - 1
    best_nonce = 0
    best_digest = b"\xff" * 32
    share_hits: list[tuple[int, str]] = []
    block_hits = 0
    count = 0
    t0 = time.perf_counter()

    for nonce in nonces:
        digest = dsha(header_with_nonce(prefix76, nonce))
        value = hash_value(digest)
        count += 1
        if value < best_value:
            best_value = value
            best_nonce = nonce
            best_digest = digest
        if value <= share_target:
            share_hits.append((nonce, digest[::-1].hex()))
        if value <= network_target:
            block_hits += 1

    elapsed = time.perf_counter() - t0
    result = ScanResult(strategy, count, len(share_hits), block_hits, best_nonce,
                        best_digest[::-1].hex(), hash_difficulty(best_digest), elapsed)
    return result, share_hits


TESTNET_NOTIFY = [
    "bf",
    "4d16b6f85af6e2198f44ae2a6de67f78487ae5611b77c6c0440b921e00000000",
    "01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff20020862062f503253482f04b8864e5008",
    "072f736c7573682f000000000100f2052a010000001976a914d23fcdf86f7e756a64a7a9688ef9903327048ed988ac00000000",
    [], "00000002", "1c2ac4af", "504e86ed", False,
]
TESTNET_EXTRANONCE1 = "08000002"
TESTNET_EXTRANONCE2 = "00000001"
TESTNET_SOLVED_NONCE = 0xB2957C02
TESTNET_SOLVED_HASH = "000000002076870fe65a2b6eeed84fa892c0db924f1482243a6247d931dcab32"


def selftest() -> dict:
    assert base58check_valid(DEFAULT_WALLET), "configured BTC payout address failed Base58Check"
    job = StratumJob.from_notify(TESTNET_NOTIFY)
    prefix = nerdminer_header_prefix(job, TESTNET_EXTRANONCE1, TESTNET_EXTRANONCE2)
    digest = dsha(header_with_nonce(prefix, TESTNET_SOLVED_NONCE))
    got = digest[::-1].hex()
    assert got == TESTNET_SOLVED_HASH, (got, TESTNET_SOLVED_HASH)
    sample = list(janus_nonces(100_000, prefix))
    assert len(sample) == len(set(sample))
    assert hash_value(digest) <= compact_to_target(job.nbits)
    return {
        "selftest": "PASS",
        "nerdminer_compatible_solved_block": TESTNET_SOLVED_HASH,
        "wallet_base58check": True,
        "janus_nonce_unique_sample": 100_000,
    }


def benchmark(hashes_per_strategy: int, difficulty: float) -> dict:
    job = StratumJob.from_notify(TESTNET_NOTIFY)
    prefix = nerdminer_header_prefix(job, TESTNET_EXTRANONCE1, TESTNET_EXTRANONCE2)
    network_target = compact_to_target(job.nbits)
    seq, _ = scan(prefix, sequential_nonces(hashes_per_strategy), difficulty,
                  network_target, "nerdminer-sequential")
    jan, _ = scan(prefix, janus_nonces(hashes_per_strategy, prefix), difficulty,
                  network_target, "janus-permuted")
    return {
        "mode": "paired_same_header",
        "share_difficulty": difficulty,
        "hashes_per_strategy": hashes_per_strategy,
        "total_hashes": hashes_per_strategy * 2,
        "sequential": seq.__dict__ | {"khs": seq.khs},
        "janus": jan.__dict__ | {"khs": jan.khs},
        "incremental_signal_claimed": False,
        "note": "Both strategies hash the identical header prefix and differ only in nonce order.",
    }


def paired_benchmark(pairs: int, hashes_per_pair: int, difficulty: float) -> dict:
    base_job = StratumJob.from_notify(TESTNET_NOTIFY)
    network_target = compact_to_target(base_job.nbits)
    rows = []
    seq_total_shares = jan_total_shares = 0
    seq_best_global = jan_best_global = 0.0
    seq_wins = jan_wins = ties = 0
    t0 = time.perf_counter()

    for idx in range(pairs):
        ex2 = (idx + 1).to_bytes(4, "big").hex()
        prefix = nerdminer_header_prefix(base_job, TESTNET_EXTRANONCE1, ex2)
        seq, _ = scan(prefix, sequential_nonces(hashes_per_pair), difficulty,
                      network_target, "nerdminer-sequential")
        jan, _ = scan(prefix, janus_nonces(hashes_per_pair, prefix), difficulty,
                      network_target, "janus-permuted")
        seq_total_shares += seq.share_hits
        jan_total_shares += jan.share_hits
        seq_best_global = max(seq_best_global, seq.best_difficulty)
        jan_best_global = max(jan_best_global, jan.best_difficulty)
        if seq.best_difficulty > jan.best_difficulty:
            seq_wins += 1
        elif jan.best_difficulty > seq.best_difficulty:
            jan_wins += 1
        else:
            ties += 1
        rows.append({
            "pair": idx + 1,
            "extranonce2": ex2,
            "sequential_share_hits": seq.share_hits,
            "janus_share_hits": jan.share_hits,
            "sequential_best_difficulty": seq.best_difficulty,
            "janus_best_difficulty": jan.best_difficulty,
        })

    elapsed = time.perf_counter() - t0
    total_hashes = pairs * hashes_per_pair * 2
    expected_shares_each = (pairs * hashes_per_pair) / (difficulty * (2**32))
    return {
        "mode": "nerdminer_v2_paired_extranonce2",
        "pairs": pairs,
        "hashes_per_pair_per_strategy": hashes_per_pair,
        "hashes_per_strategy": pairs * hashes_per_pair,
        "total_hashes": total_hashes,
        "share_difficulty": difficulty,
        "expected_share_hits_per_strategy_approx": expected_shares_each,
        "sequential_share_hits": seq_total_shares,
        "janus_share_hits": jan_total_shares,
        "sequential_pair_best_wins": seq_wins,
        "janus_pair_best_wins": jan_wins,
        "ties": ties,
        "sequential_best_difficulty_global": seq_best_global,
        "janus_best_difficulty_global": jan_best_global,
        "elapsed_s": elapsed,
        "aggregate_khs": total_hashes / max(elapsed, 1e-12) / 1000.0,
        "incremental_signal_claimed": False,
        "interpretation": "Nonce order alone should not change SHA-256 success probability. Any apparent advantage must survive repeated paired tests on identical header prefixes.",
        "rows": rows,
    }


class StratumClient:
    def __init__(self, host: str, port: int, wallet: str, worker: str,
                 password: str, timeout: float = 15.0):
        if not base58check_valid(wallet):
            raise ValueError("invalid Base58Check Bitcoin address")
        self.host = host
        self.port = port
        self.wallet = wallet
        self.worker_name = f"{wallet}.{worker}" if worker else wallet
        self.password = password
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None
        self.reader = None
        self._id = 0
        self.extranonce1 = ""
        self.extranonce2_size = 4
        self.share_difficulty = NERDMINER_DEFAULT_DIFFICULTY

    def next_id(self) -> int:
        self._id += 1
        return self._id

    def send(self, obj: dict) -> None:
        assert self.sock is not None
        self.sock.sendall((json.dumps(obj, separators=(",", ":")) + "\n").encode())

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.reader = self.sock.makefile("r", encoding="utf-8", newline="\n")
        sid = self.next_id()
        self.send({"id": sid, "method": "mining.subscribe",
                   "params": ["NerdMinerV2/JANUS-LAPIS-v0.3.3"]})
        while True:
            msg = self.read_message()
            if msg.get("id") == sid:
                if msg.get("error"):
                    raise RuntimeError(f"subscribe failed: {msg['error']}")
                result = msg.get("result")
                self.extranonce1 = str(result[1])
                self.extranonce2_size = int(result[2])
                break
        aid = self.next_id()
        self.send({"params": [self.worker_name, self.password], "id": aid,
                   "method": "mining.authorize"})
        did = self.next_id()
        self.send({"id": did, "method": "mining.suggest_difficulty",
                   "params": [NERDMINER_DEFAULT_DIFFICULTY]})

    def read_message(self) -> dict:
        if self.reader is None:
            raise RuntimeError("not connected")
        line = self.reader.readline()
        if not line:
            raise EOFError("pool closed connection")
        return json.loads(line)

    def submit(self, job: StratumJob, extranonce2: str, nonce: int) -> int:
        sid = self.next_id()
        self.send({"id": sid, "method": "mining.submit", "params": [
            self.worker_name, job.job_id, extranonce2, job.ntime,
            f"{nonce & MASK32:08x}"]})
        return sid

    def close(self) -> None:
        try:
            if self.reader is not None:
                self.reader.close()
        finally:
            if self.sock is not None:
                self.sock.close()


def live(args: argparse.Namespace) -> None:
    client = StratumClient(args.pool, args.port, args.wallet, args.worker,
                           args.password, args.timeout)
    client.connect()
    print(json.dumps({"event": "connected", "pool": f"{args.pool}:{args.port}",
                      "worker": client.worker_name,
                      "extranonce1": client.extranonce1,
                      "extranonce2_size": client.extranonce2_size,
                      "submit_enabled": args.submit}))
    extranonce2 = fixed_extranonce2(client.extranonce2_size)
    try:
        while True:
            msg = client.read_message()
            method = msg.get("method")
            if method == "mining.set_difficulty":
                client.share_difficulty = float(msg["params"][0])
                print(json.dumps({"event": "difficulty", "value": client.share_difficulty}))
                continue
            if method != "mining.notify":
                continue
            job = StratumJob.from_notify(msg["params"])
            prefix = nerdminer_header_prefix(job, client.extranonce1, extranonce2)
            network_target = compact_to_target(job.nbits)
            nonce_iter = (sequential_nonces(args.hashes_per_job)
                          if args.strategy == "sequential"
                          else janus_nonces(args.hashes_per_job, prefix))
            result, hits = scan(prefix, nonce_iter, client.share_difficulty,
                                network_target, args.strategy)
            print(json.dumps({"event": "job_scan", "job_id": job.job_id,
                              **result.__dict__}))
            for nonce, display_hash in hits:
                if args.submit:
                    submit_id = client.submit(job, extranonce2, nonce)
                    print(json.dumps({"event": "share_submit", "id": submit_id,
                                      "job_id": job.job_id,
                                      "nonce": f"{nonce:08x}", "hash": display_hash,
                                      "payout_worker": client.worker_name}))
                else:
                    print(json.dumps({"event": "qualifying_share_dry_run",
                                      "job_id": job.job_id,
                                      "nonce": f"{nonce:08x}", "hash": display_hash}))
            if args.once:
                break
    finally:
        client.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="JANUS-LAPIS NerdMinerV2 Stratum bridge")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    b = sub.add_parser("benchmark")
    b.add_argument("--hashes", type=int, default=2_000_000)
    b.add_argument("--difficulty", type=float, default=NERDMINER_DEFAULT_DIFFICULTY)
    pb = sub.add_parser("paired-benchmark")
    pb.add_argument("--pairs", type=int, default=48)
    pb.add_argument("--hashes-per-pair", type=int, default=250_000)
    pb.add_argument("--difficulty", type=float, default=NERDMINER_DEFAULT_DIFFICULTY)
    l = sub.add_parser("live")
    l.add_argument("--pool", default=DEFAULT_POOL)
    l.add_argument("--port", type=int, default=DEFAULT_PORT)
    l.add_argument("--wallet", default=DEFAULT_WALLET)
    l.add_argument("--worker", default="JANUS")
    l.add_argument("--password", default="x")
    l.add_argument("--strategy", choices=["sequential", "janus"], default="janus")
    l.add_argument("--hashes-per-job", type=int, default=250_000)
    l.add_argument("--timeout", type=float, default=15.0)
    l.add_argument("--submit", action="store_true",
                   help="actually submit qualifying pool shares; default is dry-run")
    l.add_argument("--once", action="store_true")
    return p


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "selftest":
        print(json.dumps(selftest(), indent=2))
        return 0
    if args.command == "benchmark":
        print(json.dumps(benchmark(args.hashes, args.difficulty), indent=2))
        return 0
    if args.command == "paired-benchmark":
        print(json.dumps(paired_benchmark(args.pairs, args.hashes_per_pair,
                                          args.difficulty), indent=2))
        return 0
    if args.command == "live":
        live(args)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
