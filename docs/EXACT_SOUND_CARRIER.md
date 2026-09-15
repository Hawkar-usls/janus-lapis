# JANUS Lapis — Exact Sound Carrier

This lane implements a reversible carrier pipeline:

```text
canonical JSON
  -> exact PCM16 WAV carrier
  -> exact canonical JSON recovery
  -> Lapis algorithm IR
  -> fail-closed generated Python
```

It is intentionally separate from the existing musical sonification lane.

## Two sound modes

### Musical sonification

`tools/lapis_converter.py json-to-sound`

Maps JSON leaves to deterministic tones for human inspection. It is lossy and is not decodable back into the source JSON. It has no theorem authority.

### Exact carrier WAV

`tools/lapis_sound_roundtrip.py json-to-exact-sound`

Canonical JSON bytes are framed with:

- magic `JLW1`;
- uint64 payload length;
- SHA-256 of the canonical payload;
- canonical UTF-8 JSON payload.

Each framed byte is represented by an exact PCM16 symbol and repeated a fixed number of samples. Decode is fail-closed. The lane accepts a WAV only if framing, repeated symbols, payload length, SHA-256, UTF-8 JSON parsing and canonical JSON byte equality all pass.

The sound therefore acts only as a carrier. It does not discover semantics and it is not an oracle.

## Commands

```bash
python tools/lapis_sound_roundtrip.py json-to-exact-sound input.json -o carrier.wav
python tools/lapis_sound_roundtrip.py exact-sound-to-json carrier.wav -o recovered.json
python tools/lapis_sound_roundtrip.py exact-sound-to-algorithm carrier.wav -o algorithm.json
python tools/lapis_sound_roundtrip.py exact-sound-to-code carrier.wav -o generated.py
python tools/lapis_sound_roundtrip.py exact-roundtrip input.json --outdir out
```

## SHA-256 PCNER positive control

The repository contains a fixture derived from the TRUMP SHA-256 JSON positive-control machine:

`examples/sha256_json_reference_machine.v1.json`

The CI route checks:

```text
SHA-256 JSON -> exact sound -> recovered JSON -> algorithm IR -> Python code
```

and requires the source and recovered canonical JSON bytes to be identical.

This establishes representation-preserving transport only. It does **not** establish a transfer from SHA-256 to SAT, universal GPEI for CNF, or P=NP.

```text
SOUND_IS_CARRIER_NOT_ORACLE
SHA256_POLY_ROUTE != SAT_POLY_ROUTE
P_VS_NP = OPEN
```
