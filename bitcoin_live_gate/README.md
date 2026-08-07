# JANUS-LAPIS — NerdMinerV2 Bitcoin Gate

This module connects the JANUS 113.8 research path to the same Stratum-v1 work model used by `BitMaker-hub/NerdMiner_v2`.

## Why NerdMinerV2

NerdMinerV2 is designed for very low-hashrate ESP32 solo mining and explicitly supports low-difficulty pools such as:

- `public-pool.io:21496`
- `pool.nerdminers.org:3333`
- `pool.nerdminer.io:3333`

Its reference code uses `mining.subscribe`, `mining.authorize`, `mining.suggest_difficulty`, `mining.notify`, and `mining.submit`, builds the coinbase + merkle root locally, and hashes an 80-byte Bitcoin header with double SHA-256.

The JANUS bridge mirrors those rules and keeps the pool job unchanged. Only nonce traversal changes.

## Two paired strategies

```text
nerdminer-sequential
    start near 0xDA54E700
    then walk contiguous uint32 nonces

janus-permuted
    derive an odd affine multiplier + offset from the 76-byte header prefix
    visit nonce = a*i + b mod 2^32
```

Because `a` is odd, the JANUS traversal is a permutation of all 2^32 nonce values. It does not skip or repeat nonce values over a complete cycle.

This is deliberately a **search-order experiment**, not a claim that SHA-256 exposes a gradient.

## Payout worker

Default wallet/worker base:

```text
1F1Y6CdkApZboDF6g1DYrQ8Dke2E5gWiP1
```

Live mode authorizes the pool as:

```text
1F1Y6CdkApZboDF6g1DYrQ8Dke2E5gWiP1.JANUS
```

No private key is required or used. The address is only a pool worker/payout identifier.

## Cryptographic compatibility self-test

The bridge contains the canonical Stratum example that solved Bitcoin testnet block:

```text
000000002076870fe65a2b6eeed84fa892c0db924f1482243a6247d931dcab32
```

Using the documented Stratum job, NerdMiner-compatible byte ordering, `extranonce1=08000002`, `extranonce2=00000001`, and `nonce=b2957c02`, the bridge reproduces that exact block hash.

Run:

```bash
python bitcoin_live_gate/nerdminer_v2_janus_bridge.py selftest
```

## Frozen paired benchmark — 2026-08-07

The first controlled NerdMinerV2-style benchmark used 48 independent extranonce2-derived header prefixes. In every pair, sequential and JANUS received the exact same 76-byte header prefix and exactly 250,000 nonce attempts each.

```text
pairs                              48
hashes / pair / strategy           250,000
hashes / strategy                  12,000,000
total SHA256d                      24,000,000
share difficulty                   0.00015

sequential share hits              21
JANUS share hits                   24

sequential best-hash pair wins     25
JANUS best-hash pair wins          23

sequential global best difficulty  0.0007633569
JANUS global best difficulty       0.0033100983
```

The small difference is **not evidence of predictive power**. Conditional on the 45 observed share hits, a 24-vs-21 split is compatible with chance (`two-sided p ≈ 0.766`). The 25-vs-23 paired best-hash split is also compatible with chance (`p ≈ 0.885`).

That negative control is valuable: the bridge is now calibrated so future live-pool results cannot be declared a JANUS advantage merely because one run got lucky.

Full raw result:

```text
bitcoin_live_gate/NERDMINER_V2_PAIRED_48X250K_2026-08-07.json
```

## Local paired benchmark

```bash
python bitcoin_live_gate/nerdminer_v2_janus_bridge.py paired-benchmark \
  --pairs 48 \
  --hashes-per-pair 250000 \
  --difficulty 0.00015
```

## Live pool mode

Dry-run is the default. The program connects, subscribes, authorizes, receives real `mining.notify` jobs, scans the requested nonce budget, and prints qualifying shares without sending them.

```bash
python bitcoin_live_gate/nerdminer_v2_janus_bridge.py live \
  --pool public-pool.io \
  --port 21496 \
  --wallet 1F1Y6CdkApZboDF6g1DYrQ8Dke2E5gWiP1 \
  --worker JANUS \
  --strategy janus \
  --hashes-per-job 250000
```

To allow actual `mining.submit` for qualifying pool shares, add:

```text
--submit
```

Example:

```bash
python bitcoin_live_gate/nerdminer_v2_janus_bridge.py live \
  --pool public-pool.io \
  --port 21496 \
  --wallet 1F1Y6CdkApZboDF6g1DYrQ8Dke2E5gWiP1 \
  --worker JANUS \
  --strategy janus \
  --hashes-per-job 250000 \
  --submit
```

## Important operational boundary

Live Stratum mining is intentionally **not run in GitHub Actions**. CI is for code/tests; pool mining belongs on the owner's PC, NAS, ESP32/NerdMiner, or other explicitly authorized hardware.

The ChatGPT execution container used during development also blocks raw outbound Stratum TCP/DNS, so the live pool socket must be exercised from a normal networked machine. The local cryptographic self-test and 24-million-hash paired benchmark were executed successfully before this module was committed.

## Current gate state

```text
NerdMinerV2 Stratum/header compatibility    ADMITTED
known solved Stratum block reproduction     ADMITTED
low-diff paired nonce benchmark             ADMITTED
JANUS nonce-order advantage                  NOT ADMITTED
live pool submission code                    IMPLEMENTED, DRY-RUN BY DEFAULT
live pool session from this environment      BLOCKED BY NETWORK SANDBOX
```
