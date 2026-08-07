# JANUS CHRONONAUT SHA PETUSHOK GATE v5

Chronicle anchor: **2026-08-07 07:26 Europe/Zaporozhye**.

## Purpose

Test whether features extracted from reversible internal SHA-256 round dynamics can predict lower final Bitcoin SHA256d values better than matched random controls, without using full Bitcoin-header SHA256d during sealed nonce selection.

## Exact SHA-round time machine

For a known SHA-256 message schedule word `W[t]` and constant `K[t]`, one compression round is algebraically invertible at the internal working-state level. V5 verifies exact forward→inverse round trips for 16 and 64 rounds.

This does **not** invert SHA-256 as a hash and does not recover an unknown preimage.

## Chrononaut feature vector

For every nonce candidate, before final SHA256d, JANUS computes a frozen feature vector derived from forward and target-conditioned reverse reduced-round trajectories:

```text
J_sha
E_meet
Sigma_sha
Phi_sha
W
nu = W mod 2
chi_forward / chi_return
mu
forward/reverse state-density projections
nonce density
```

`J_sha` and `Sigma_sha` are computational trajectory quantities only; they are not physical negative time or a measured spacelike interval.

## Supervised calibration

Calibration order is mandatory:

1. compute pre-SHA feature vector;
2. only then compute the full Bitcoin-header SHA256d label;
3. label = `log2(achieved difficulty)`;
4. choose ridge regularization by deterministic 4-fold cross-validation;
5. fit the final model;
6. serialize and SHA-256 hash the model;
7. freeze the model before holdout.

Calibration data is excluded from inference.

## Sealed holdout

During sealed holdout:

```text
selection_header_sha256d_calls = 0
model_mutation_allowed          = false
SCOBY-memory mutation           = false
```

Two controls are required:

- `RANDOM_EQUAL`: same number K of final SHA256d evaluations as JANUS.
- `RANDOM_WORK`: K plus an optimistic full-nonce equivalent of the reduced-round selector cost.

A practical signal requires JANUS to beat `RANDOM_WORK`, not merely `RANDOM_EQUAL`.

## Blind future-information / bootstrap gate

After JANUS seals the shortlist and logs a preregistered tag, V5 generates a new random `FUTURE_MESSAGE` and computes:

```text
Q_future = SHA256(FUTURE_MESSAGE)
```

The future tag is compared to the precommitted tag. `FUTURE_MESSAGE` is generated only after the precommit event and is not used for nonce selection.

Chance probability is exactly `2^-b` per trial for a `b`-bit tag. Any excess must survive the preregistered binomial null before it can be called an anomaly candidate.

Even a bootstrap anomaly does **not** establish physical retrocausality until ordinary leakage, RNG, logging, timestamp, scheduling, and implementation explanations are excluded and independent replication succeeds.

## Terminal rule

Only the standard Bitcoin verifier can produce:

```text
PETUSHOK_FOUND = TRUE
```

and only when:

```text
SHA256d(exact 80-byte Bitcoin header) <= network_target(nBits)
```

Pool shares, model predictions, exact internal round reversal, timing symmetry, low p-values, or bootstrap-tag matches are not themselves PETUSHOK.

## Null gate

```text
EXACT_SHA_ROUND_REVERSIBILITY
!= SHA256_PREIMAGE_INVERSION

MATHEMATICAL_TIME_SYMMETRY
!= PHYSICAL_RETROCAUSALITY

HASH_INTEGRITY
!= TRUTH_OF_INTERPRETATION
```

## Admission state before live V5 run

```text
SHA_ROUND_TIME_MACHINE_SELFTEST    = PASS
16_ROUND_FORWARD_REVERSE           = EXACT
64_ROUND_FORWARD_REVERSE           = EXACT
SEALED_SELECTOR_SHA256D_LEAKAGE    = 0 in selftest
SUPERVISED_CORRELATOR_MECHANICS    = PASS on synthetic learnable fixture
PER_HASH_ADVANTAGE                 = NOT_ESTABLISHED
HASHRATE_INDEPENDENCE              = NOT_ESTABLISHED
PHYSICAL_TIME_TRAVEL               = NOT_ESTABLISHED
SHA256_PREIMAGE_BREAK              = NOT_ESTABLISHED
PETUSHOK_FOUND                     = FALSE
```
