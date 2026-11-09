# JANUS Beetle → Wolfram Cloud MCP → Ocean numeric attestation

The official Wolfram Cloud MCP endpoint is `https://agenttools.wolfram.com/mcp`.
The endpoint supports limited, small-scale personal use without an AppID.
It is **not** equivalent to unlimited or bulk access to Wolfram Alpha Results API.

## What changed in JANUS

Earlier, `zeno_n2_analytic` received a live MCP reply, but the response
body was intentionally discarded without a numeric comparison. It remains
a **receipt-only** success and is never retroactively promoted.

A second, separately fixed query ID `zeno_n2_verified_v1` is allowed
**exactly once** by the existing Beetle scheduler. It checks only the
public expression `cos(pi/4)^4` against the independent value `1/4`.
No arbitrary user/model strings are permitted, no auth is sent, no
bulk harvesting takes place. A failure has a seven-day backoff and an
accepted attempt is permanently de-duplicated by its source-bound ID.

The client only marks arithmetic as verified when a clearly labelled
numeric result is parsed and agrees with the independent constant.
Ambiguous, nonnumeric, unknown or conflicting provider outputs cannot
produce a positive verdict.

The SHA-bound attestation is saved to:

`beetle-state:data/beetle-state/wolfram_math/zeno_n2_verified_v1.json`

It contains the fixed public query and our expected number, a Boolean
verification outcome, status, content digest and Beetle receipt digest.
It **does not contain Wolfram's answer text or numeric result**. The
Beetle's existing durable state and ACK/privacy guardrails remain
unchanged.

This verifies elementary arithmetic, **not** a physical signal from the
future, tachyon existence, a measured quantum Zeno effect, or new model
accuracy. Only the already existing JANUS Ocean standard-QM CPU
reference is appropriate for interpreting this result.

## Gates and evidence

PR tests are offline and use fake MCP responses. The real provider
call only happens in the existing limited personal-use direction after
a normal Beetle run selects the direction, with four bounded MCP HTTP
steps and a permanent success deduplication. A separate source-bound
Ocean reader may check the saved attestation through the public
`beetle-state` branch; an absent/unparseable result must remain UNKNOWN.

Tests:

```sh
PYTHONPATH=tools python -m unittest discover -s tests -p 'test_wolfram_numeric_verification.py' -v
```

Provider terms and help:
- https://support.wolfram.com/75237
- https://www.wolfram.com/ai/mcp/cloud/
