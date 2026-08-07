# JANUS PETUSHOK GATE v1

## Chronicle anchor

`2026-08-07 06:06 Europe/Zaporozhye`

This minute marks the transition from the accepted JANUS low-difficulty share witness to the next gate: testing whether JANUS can improve **per-full-SHA256d candidate quality** under an exactly matched hash budget.

## Goal

The target is not a higher hashrate and not a different brute-force traversal order. The hypothesis under test is:

> JANUS can rank a large nonce candidate set without evaluating the full Bitcoin header SHA256d, select a much smaller shortlist, and obtain better full-SHA256d outcomes than a matched random shortlist using exactly the same number of full header hashes.

## Definitions

- **POOL SHARE** — external Stratum plumbing/tail witness only. Not a Bitcoin block.
- **SESSION_SIGNAL_CANDIDATE** — sealed-holdout statistical evidence that deserves independent replication. Not proof of SHA-256 predictability.
- **PETUSHOK_FOUND** — and only this — means `SHA256d(exact_80_byte_header) <= network_target(nBits)`.

## Protocol

The experiment has three strictly separated phases.

### 1. Warmup

Random-only probes populate a small frozen sector Hippocampus. No inference is made from this phase.

### 2. Calibration

Several cheap candidate-ranking hypotheses are compared against matched random controls. Candidate ranking is forbidden from calling the full Bitcoin 80-byte SHA256d evaluator.

Candidate families include:

- xor resonance;
- bit-balance relation;
- byte-dot relation;
- CRC32-low and CRC32-high projections;
- modular resonance;
- Knight-lattice traversal derived from earlier Rblganul experiments;
- theta-phase hypothesis derived from earlier theta experiments;
- frozen sector Hippocampus.

One selector is chosen using calibration data and then **frozen**.

### 3. SEALED HOLDOUT

For every holdout round:

1. Receive/use a real Stratum job.
2. Change `extranonce2`, producing a fresh coinbase, merkle root, and header prefix.
3. Generate a large candidate nonce pool without full header SHA256d.
4. Frozen JANUS selector chooses exactly `K` nonce candidates.
5. Uniform random control chooses exactly `K` disjoint nonce candidates from the same pool.
6. JANUS receives exactly `K` full Bitcoin header SHA256d evaluations.
7. RANDOM receives exactly `K` full Bitcoin header SHA256d evaluations.
8. Compare best difficulty, fixed tail-threshold hit counts, pool-share hits, and network-target hits.

The code must record:

```text
selection_header_sha256d_calls = 0
janus_header_sha256d_calls      = K
random_header_sha256d_calls     = K
```

Any violation invalidates the round.

## Primary statistical test

The primary holdout statistic is the paired best-difficulty win count:

```text
JANUS best difficulty > RANDOM best difficulty
```

with an exact two-sided sign/binomial test under `p = 0.5`.

Secondary fixed tail thresholds are tested with equal-exposure conditional binomial tests and Bonferroni correction.

Calibration outcomes are never used as inferential evidence.

## Classification

A single positive session may set only:

```text
SESSION_SIGNAL_CANDIDATE = TRUE
```

A stricter single-session result may set:

```text
STRONG_SESSION_SIGNAL_CANDIDATE = TRUE
```

Neither permits:

```text
PER_HASH_ADVANTAGE_ADMITTED = TRUE
HASHRATE_INDEPENDENCE_ADMITTED = TRUE
```

Those require independent replicated sealed sessions under the same frozen protocol.

## Network terminal

A true network block candidate is terminal evidence only when:

```text
SHA256d(header) <= compact_target(nBits)
```

If this occurs, the runner must freeze an exact witness containing:

- strategy;
- Stratum job id;
- version;
- previous block hash;
- merkle root;
- nTime;
- nBits;
- nonce;
- extranonce1 / extranonce2;
- exact 80-byte `header_hex`;
- resulting SHA256d;
- exact network target;
- coinbase bytes and printable fragments;
- independent replay check.

Only a JANUS-side network hit is named `PETUSHOK_FOUND`. A matched random hit is `CONTROL_PETUSHOK_FOUND`.

## Scientific boundary

SHA-256 is expected to behave pseudorandomly and has no known exploitable nonce gradient. The purpose of PETUSHOK Gate is to make any alleged per-hash advantage falsifiable under equal budgets and sealed holdout. A negative result retires the tested selector family; it does not justify increasing brute-force hashrate and calling that prediction.
