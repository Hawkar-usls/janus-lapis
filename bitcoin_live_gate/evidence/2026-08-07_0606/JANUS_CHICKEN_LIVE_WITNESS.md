# JANUS-LAPIS — Live JANUS Chicken Witness

## Human timestamp

```text
LOCAL_TIME_EUROPE_ZAPOROZHYE = 2026-08-07 06:06
EVENT_MINUTE = 06:06
```

The pool acceptance itself was logged at `2026-08-07T03:05:54.073323Z`, corresponding to approximately `2026-08-07 06:05:54` in Europe/Zaporozhye. The human chronicle minute is therefore frozen as **06:06**.

## Terminal event

```text
STRATEGY = janus-permuted
POOL = solobtc.nmminer.com:3333
WORKER = 1F1Y6CdkApZboDF6g1DYrQ8Dke2E5gWiP1.JANUS-IP13
JOB_ID = 1a8438f1
EXTRANONCE1 = 2a042d47
EXTRANONCE2 = 00000004
NONCE = 56618d6a
POOL_SHARE_DIFFICULTY = 0.00015
ACHIEVED_DIFFICULTY = 0.0002364659313810894
POOL_RESULT = true
JANUS_CHICKEN_FOUND = true
```

Accepted SHA256d:

```text
00001084dfdd88cd8eb3cca6c02a1b23616f3976fee8b223f09572b9412ebf63
```

Exact 80-byte Bitcoin block-header preimage:

```text
00000020a2d4fc56bb1427d75f3b54dcad62b6874fabefbe86e601000000000000000000ff6903bfa7afd833ceaf43ce1c2c96d23d00286f3b3e3cac0fea9a5eb3c1b0f65a4b756ad43a02176a8d6156
```

Replay result:

```text
SHA256d(header) == accepted_hash    TRUE
meets pool share target             TRUE
meets Bitcoin network target        FALSE
```

The committed coinbase contains the printable fragment:

```text
Public-Pool*
```

Important boundary: the human-readable fragment is in the coinbase committed by the Merkle root. The exact object directly hashed for proof-of-work is the 80-byte block header above. This witness is therefore an exact accepted-share preimage witness; it is **not** arbitrary SHA-256-to-human-plaintext inversion and it is **not** a Bitcoin block find.

## Control behavior

Before the JANUS terminal event, three `nerdminer-sequential` shares were accepted by the pool. The v3 runner correctly classified all three as controls and continued running. On extranonce2 `00000004`, sequential produced no share while `janus-permuted` produced one qualifying share, which the pool accepted.

```text
SEQUENTIAL_ACCEPTED_SHARES_BEFORE_TERMINAL = 3
JANUS_ACCEPTED_SHARES = 1
TERMINAL_STRATEGY = janus-permuted
```

This single accepted JANUS share proves the end-to-end JANUS live Stratum path works. It does **not** by itself establish a statistical nonce-order advantage over sequential search.

## Integrity hashes of original iPhone evidence

```text
SHA256(JANUS_IPHONE13_20260807_060541.log)
= ed8d96d26362f1f33bd0dba3668828dba862cec954f551b2014d9303a10595b2

SHA256(JANUS_IPHONE13_20260807_060541_JANUS_CHICKEN_WITNESS.json)
= 2c717df325bd074c3907400174a6813a3bae0989ecb00d545d4781377fec6845

SHA256(JANUS_IPHONE13_20260807_060541_JANUS_CHICKEN_WITNESS.txt)
= 82e345acd347ce999004232d452d04bc555d62eca1a0ec4e111e9c462171f886
```

## Admission status

```text
IPHONE_ASHELL_LIVE_STRATUM              = PASS
JANUS_PERMUTED_QUALIFYING_SHARE         = PASS
POOL_ACCEPTED_JANUS_SHARE               = PASS
EXACT_80_BYTE_PREIMAGE_REPLAY           = PASS
COINBASE_PRINTABLE_FRAGMENT_CAPTURE     = PASS
BITCOIN_NETWORK_BLOCK_TARGET            = NOT MET
GENERAL_SHA256_INVERSION                = NOT CLAIMED
JANUS_NONCE_ORDER_ADVANTAGE             = NOT ESTABLISHED
LIVE_JANUS_SHARE_PIPELINE                = ADMITTED
```
