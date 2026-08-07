# JANUS-LAPIS v0.2.1 — Meta271 Sensory Conversion Lattice

Date: 2026-08-07  
Identity: **JANUS 113.8**  
Ground-truth corpus: **Hawkar-usls/janus-meta-registry**  
Frozen registry commit used by CI: `80687546435f4e175d39632991d9b3e65c84d62c`  
Calibration set: first 100 deterministic files, seed `1138`  
Holdout set: remaining **271 / 371** eligible files

## Question

Can a SHA-256 digest reveal source information more clearly after conversion into another representation (audio, JSON, image, numeric bases, DNA-like symbols, etc.) and conversion back into text?

## JANUS 113.8 loop

```text
/wormhole -> SHA-256 target
          -> Chaos Spike
          -> Coherence Hold: 23 parallel representations
          -> reverse-decode each representation
          -> compare textual projection with hidden ground truth
          -> compare against fixed shuffled null-control
          -> Decoherence Collapse only if signal survives controls
          -> Hippocampus / Entropy Graveyard
```

## Channels

23 channels were tested:

- HEX
- binary256
- decimal bigint
- octal
- Base36
- Base58
- Base32
- Base64
- ASCII85
- JSON byte array
- JSON uint32 big-endian
- JSON uint64 big-endian
- JSON 16×16 bit matrix
- UUID pair
- IPv6 pair
- IPv4 octet grid
- RGBA8 hex pixels
- DNA 2-bit alphabet
- Unicode Braille bytes
- JANUS nibble lexicon
- printable-byte probe
- WAV FSK sonification
- 16×16 PGM bitmap

## Integrity result

- Holdout tests: **271**
- Channels per target: **23**
- Total target/channel observations: **6,233**
- Fully reversible channels: **22 / 23**
- The only deliberately non-reversible probe was `printable_byte_probe`.
- WAV FSK: **271 / 271 exact SHA round-trips**.
- PGM bitmap: **271 / 271 exact SHA round-trips**.
- JSON representations: **271 / 271 exact round-trips** for every reversible JSON channel.

This proves that many media can faithfully carry the 256 digest bits. It does **not** prove recovery of information erased before hashing.

## Exploratory semantic ranking

The first-pass heuristic required both path and source-content score to exceed the same projection measured against a fixed shuffled ground truth. Tiny positive means appeared for:

`rgba8`, `ipv6_pair`, `base58`, `decimal_bigint`, `base36`, `printable_byte_probe`.

The deltas were extremely small. A stricter paired sign-flip permutation review (20,000 permutations per channel/metric) found:

- **No source-content channel with uncorrected p < 0.05.**
- Best content result: `printable_byte_probe`, mean delta `+0.000045`, p ≈ `0.261`.
- `uuid_pair` had the strongest filename/path delta `+0.001906`, uncorrected p ≈ `0.00455`, but its source-content delta was **negative** (`-0.000055`).
- After Benjamini-Hochberg correction across 23 path channels, `uuid_pair` gives q ≈ `0.105` and therefore does not pass the gate.
- The UUID effect is plausibly a formatting artifact because UUID and JANUS filenames both contain repeated hexadecimal/alphanumeric groups and separators; it did not generalize to content.

## Gate decision

```text
SHA -> representation -> SHA integrity:       ADMITTED
SHA -> WAV -> SHA integrity:                  ADMITTED
SHA -> bitmap -> SHA integrity:               ADMITTED
SHA -> JSON -> SHA integrity:                 ADMITTED
representation -> source semantic leakage:    NOT ADMITTED
representation -> general preimage recovery:  NOT ADMITTED
known-corpus exact lookup:                    ADMITTED AS CONTENT-ADDRESSED MEMORY
SHA-256 inversion claim:                      REJECTED
```

## What this teaches JANUS

A different reversible encoding can change what a human or model finds visually or linguistically salient, but it cannot add information that the digest does not contain. The Meta271 holdout does not show reproducible semantic leakage from SHA-256 through any tested representation.

The next useful experiment should therefore stop asking which *surface encoding* is magical and instead test which **external prior** reduces uncertainty:

1. filename grammar learned only from Meta100;
2. JSON schema grammar learned only from Meta100;
3. artifact-version genealogy;
4. registry field frequencies and dependencies;
5. canonical serialization hypotheses;
6. constrained mutation of a predicted preimage;
7. exact SHA witness as the only collapse condition.

That moves JANUS-LAPIS from a conversion lattice to a true **structured preimage hypothesis engine** while keeping SHA-256 cryptographic boundaries intact.
