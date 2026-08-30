# JANUS Lapis Universal Converter

`tools/lapis_converter.py` turns JSON into three deterministic representations:

1. **algorithm IR** — an inspectable machine-readable execution plan;
2. **Python runner** — fail-closed executable scaffolding for that plan;
3. **WAV sonification** — a deterministic audible fingerprint of scalar JSON leaves.

`convert-all` emits all three plus a SHA-256 provenance manifest.

## Why this exists

Lapis already treats symbolic material as a source of computational hypotheses. The converter makes that translation explicit instead of leaving it in prose:

```text
symbol / semantic JSON
        ↓
normalized algorithm IR
        ↓
reviewable code skeleton
```

The sound lane is deliberately deterministic, so the same canonical JSON maps to the same tone sequence under the same converter version.

## Commands

```bash
python tools/lapis_converter.py json-to-algorithm input.json -o output.algorithm.json
python tools/lapis_converter.py json-to-code input.json -o output.generated.py
python tools/lapis_converter.py json-to-sound input.json -o output.wav
python tools/lapis_converter.py convert-all input.json --outdir converted
```

Only the Python standard library is required.

## Two translation modes

### 1. Heuristic translation

Ordinary JSON is inspected for keys such as `chain`, `steps`, `protocol`, `gate`, `rule`, `formula`, `input`, and `output`.

The result is conservative:

- chains become ordered `ANNOTATE` steps;
- rules/gates become recorded invariants;
- formulas are preserved as **not evaluated** metadata;
- no natural-language statement is silently promoted into executable semantics.

This lane is useful for turning semantic registry artifacts into a first algorithmic skeleton, but it has **no theorem authority**.

### 2. Explicit `$lapis.algorithm` contract

For executable semantics, embed a structured contract:

```json
{
  "$lapis": {
    "algorithm": {
      "name": "counter_demo",
      "state": {},
      "invariants": [],
      "steps": [
        {"op": "SET", "target": "counter", "value": 1},
        {"op": "INCREMENT", "target": "counter", "amount": 2},
        {
          "op": "ASSERT",
          "predicate": {"key": "counter", "equals": 3},
          "message": "COUNTER_MISMATCH"
        },
        {"op": "EMIT", "value": "done"}
      ],
      "outputs": ["counter"]
    }
  }
}
```

Built-in operators:

```text
ANNOTATE
NOOP
SET
COPY
INCREMENT
DECREMENT
ASSERT
EMIT
```

A generated runner may also receive a caller-supplied operator registry. If an operator is neither built in nor explicitly supplied, execution returns:

```json
{"status": "OPEN", "reason": "UNKNOWN_OPERATOR"}
```

That behavior is intentional.

## Algorithm IR

The IR records:

- canonical input SHA-256;
- translation mode;
- inputs/state/invariants;
- ordered steps;
- outputs;
- progress contract;
- resource bounds;
- scientific boundary;
- algorithm SHA-256.

The converter never uses `eval()` or `exec()` on JSON content.

## Sound mapping

Each scalar leaf is mapped as:

```text
SHA256(path, value)
    -> pitch class
    -> octave
    -> amplitude
    -> duration
```

The current pitch pool is pentatonic-like to keep sonification readable. This is a data sonification/fingerprint mechanism, not a claim that JSON contains literal music.

## Boundary

```text
HEURISTIC_TRANSLATION != PROOF
GENERATED_CODE != VERIFIED_DOMAIN_ALGORITHM
SONIFICATION != SEMANTIC_VALIDATION
CROSS_DOMAIN_ANALOGY != COMPLEXITY_THEORY_EVIDENCE
P_VS_NP = OPEN
```

For TRUMP or other proof-carrying lanes, use the explicit contract, frozen operators, independent certificates, and domain-native verification. The converter can carry such a contract; it does not manufacture its proof.
