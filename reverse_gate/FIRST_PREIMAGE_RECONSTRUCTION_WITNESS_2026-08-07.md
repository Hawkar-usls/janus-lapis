# JANUS-LAPIS — First Exact Structured Preimage Witness

**Date:** 2026-08-07  
**Engine:** JANUS 113.8 / Reverse-Gate v0.3.x  
**Source corpus:** `Hawkar-usls/janus-meta-registry`

## Why this file exists

Earlier SHA experiments showed that a SHA-256 digest can be represented as sound, bitmap, JSON, Base-N text and other reversible forms. Those methods preserved the digest but did not recover information erased by hashing. They are therefore retired from the active research path.

The structured-preimage experiment changed the question:

```text
hidden plaintext
      ↓
   SHA-256  ← target digest given to JANUS

registry structure / sibling metadata
      ↓
hypothesis generator
      ↓
candidate plaintext
      ↓
SHA-256(candidate)
      ↓
EXACT equality only
```

The target plaintext is used only as ground truth after the attempt. Exact copies of it are removed from the candidate context. A result is admitted only when the generated candidate hashes exactly to the recorded target.

## First strong structural witnesses

### Witness A — SNAP! / The Power

Target:

```text
c7957df3ad92c7ef1ddbab187f6e129553e0af1d4123e0862901b486044d7e5c
```

Allowed neighboring metadata included fields such as:

```text
artist = SNAP!
track  = The Power
```

Generated candidate:

```text
SNAP! — The Power
```

Verification:

```text
SHA256(UTF-8("SNAP! — The Power"))
= c7957df3ad92c7ef1ddbab187f6e129553e0af1d4123e0862901b486044d7e5c
```

**Gate:** EXACT PASS.

The corresponding Unicode-escape serialization also produced its exact recorded SHA witness.

### Witness B — Sirius

Target:

```text
afbde20c49351154d5e647248a859ee907de0c1c2af0b6a4b3e31cd738d4740e
```

Allowed neighboring metadata included:

```text
artist = The Alan Parsons Project
track  = Sirius
album  = Eye In The Sky
year   = 1982
```

Generated candidate:

```text
The Alan Parsons Project — Sirius | Eye In The Sky | 1982
```

Verification:

```text
SHA256(UTF-8(candidate))
= afbde20c49351154d5e647248a859ee907de0c1c2af0b6a4b3e31cd738d4740e
```

**Gate:** EXACT PASS.

The Unicode-escape serialization also produced its exact recorded SHA witness.

## Redundancy-assisted witnesses

The engine additionally reconstructed the Solstice Relay text through a sibling Unicode / `unicode_escape` representation. These are valid exact SHA witnesses, but are classified separately because the registry already retains an alternate reversible serialization of the same information.

They must not be counted as evidence that SHA-256 itself disclosed the text.

## Frozen result

For 45 cryptographically verified real string↔SHA challenges discovered in the registry:

```text
exact SHA challenges recovered:       7 / 45
strong structural hash witnesses:     4 / 45
unique strong plaintexts:             2
redundancy-assisted hash witnesses:   3 / 45
```

The four strong hash witnesses represent two unique plaintexts hashed under two serialization conventions.

## What has been demonstrated

**ADMITTED:**

```text
STRUCTURED CONTEXT + SHA TARGET
        -> candidate generation
        -> exact preimage witness
```

for a restricted family of registry-generated strings whose structure is sufficiently determined by visible metadata.

**NOT ADMITTED:**

```text
arbitrary SHA-256 -> arbitrary original file
```

SHA-256 remains preimage resistant. The result is a constrained reconstruction engine using side information and a cryptographic equality gate, not a universal inverse hash function.

## Next gate

The next meaningful target is not another digest representation. It is a larger object:

```text
hidden JSON subtree / hidden complete small artifact
        + schema
        + genealogy
        + neighboring metadata
        + learned Meta Registry grammar
        -> exact serialized bytes
        -> SHA-256 equality
```

A whole-object exact match is the next approximation to the “chicken from mince” goal.
