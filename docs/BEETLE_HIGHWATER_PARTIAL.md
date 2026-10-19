# Independent Cloud HOME witness and Beetle partial checkpoints

## High-water witness

The Genesis HOME `STATE.json` branch is not its own independent rollback
anchor. JANUS stores the highest observed sequence, exact receipt SHA-256, and
Genesis state-commit SHA in a **separate repository's GitHub Issue**:

https://github.com/Hawkar-usls/janus-lapis/issues/21

Each watchdog run now compares the live HOME state against this witness. It
alerts on sequence regression, same-sequence identity changes, and Git history
which does not descend from the witnessed commit even if an attacker has
artificially increased `sequence`. Issue/network failures yield `UNKNOWN`,
not a claim of proven delivery failure. Only the trusted main watchdog's
Issues-write job can advance the witness after the local cryptographic receipt
and sequential predecessor checks pass.

The witness shares GitHub's availability and administrator permission domain;
it is independent of **Genesis Git history**, not independent of GitHub as a
service. GitHub Issues edits/deletions by privileged administrators remain
possible and cannot be fully prevented by repository workflows.

Bootstrap is checkpoint #101 / receipt SHA-256
`6b6c0f7b89b89943e75c30759b3dfc55f31d4d34ffc000adf0235ad2d79ed91f`.
The witness does not retroactively prove pre-bootstrap history.

## Interrupted Beetle worker

1. The producer records the verified receipt-head and baseline `seen.json` /
   `cursors.json` after shard migration and before worker execution.
2. If the worker exits nonzero, the normal context projector, mirror router,
   and delivery health step are *skipped*.
3. `beetle_partial_checkpoint.py salvage` validates the receipt hash-chain,
   candidate ID↔receipt correspondence, HTTP Range chunk bytes/SHA and
   contiguous cursor offsets, and enforces the 80 MB Git blob ceiling.
4. Only verified candidate and receipt shards, reconstructed `seen`/`cursors`,
   relevant verified chunks and a marked partial receipt are committed to
   `beetle-state`. Sender queues, receiver ACKs, and unverified subprocess
   grazer output are not staged. The GitHub Actions run remains **failed**.

The worker additionally commits verified progress to the remote `beetle-state`
branch **after every completed research direction and every grazer task**, not
just at the end of a run. Each cut validates receipt ancestry, candidate
pairing, bounded shards and grazer byte SHA before pushing. Failure to push
aborts that worker instead of pretending the data was made durable. The next
worker resumes from the latest committed candidate index and byte cursor.

An isolated offline crash canary created a disposable Git remote, published a
partial checkpoint, killed the worker process with SIGKILL, and confirmed the
candidate and commit still existed on the remote; production files and queues
were not touched by this test.

A killed VM can still lose work produced **since the last completed source/task
checkpoint**. Git push availability and remote repository continuity remain
required. This is bounded recovery, not an impossible claim of fully lossless
recovery from a crash in the middle of an uncommitted network request.

Neither mechanism confers research proof, command authority or external
effect permissions.
