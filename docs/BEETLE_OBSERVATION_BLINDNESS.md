# Beetle → Genesis: delivery alarms vs. observation loss

The hourly `.github/workflows/janus-beetle-home-watchdog.yml` has two independent
incident classes. An ACK is a durable discovery inbox receipt, **not** evidence
of runtime execution, scientific proof, or permission to take external action.

| Observer status | Delivery Issue | Observation-loss Issue |
| --- | --- | --- |
| `PASS` / `WARN` | Close an existing confirmed delivery incident | Close observation-loss incident |
| `ALERT` | Open/update the confirmed delivery incident | Close observation-loss incident (telemetry exists) |
| `UNKNOWN`, under threshold | Do not open or close | No public alert yet; record receipt |
| `UNKNOWN`, at least 3 samples and 180 minutes | Do not open or close | Open/reopen a separate issue and assign repository owner |

## Durable evidence

After the observer runs, an `always()` step normalizes missing or invalid output
to an explicit `UNKNOWN` receipt. It uploads an artifact named
`janus-watchdog-<STATUS>-<RUN_ID>` even when the read-only observer fails.

The main-only Issue job reads the history of *that workflow's* completed runs
and status-named artifacts via GitHub REST, then checks consecutive `UNKNOWN`
samples and actual elapsed wall time. Legacy, absent, expired, duplicated, or
mismatched artifacts never count as confirmed `UNKNOWN`. The source run and
observation duration are linked in the separate incident issue. The issue
reuses one identity across recurrences; repeated reports do not write.

Only the main-branch incident job has `issues:write` and `actions:read`.
Untrusted PR runs cannot write public incidents. Machine updates preserve human
notes and leave human-edited assignees alone. Native GitHub/email notifications
depend on the assignee's GitHub notification preferences.

## Independent durable receipt integrity

The read-only watchdog also fetches the latest Genesis Cloud HOME receipt from
the restricted path declared by `STATE.json`. It validates the path's sequence
and run identity, compares the receipt's exact bytes against the SHA-256 stored
in `STATE.json`, and cross-checks checkpoint identity, staged Beetle context,
and the no-execution/no-external-effect guards. A demonstrable hash or receipt
content contradiction is `ALERT` (`GENESIS_HOME_RECEIPT_*`), even when the
checkpoint commit is recent. A GitHub read failure or unavailable receipt is
`UNKNOWN`: it is not proof that the durable checkpoint was damaged.

This is a *remote independent check* of the latest receipt. Genesis's own
cloud-worker-B separately replays and hashes the cursor/context on each run;
neither mechanism grants scientific or runtime authority to discovery packets.

## Checkpoint history and rollback detection

The watchdog fetches the two newest commits *that changed* Genesis Cloud
HOME `STATE.json`. It first binds the latest commit message to the current
run ID/attempt, then reads the preceding state at its immutable commit SHA.
It checks that `sequence` increased **exactly by one**, that the durable
Beetle cursor did not decrease, and that the `(run_id, run_attempt)` identity
was not reused (GitHub reruns with a higher attempt remain valid). Proven
regression, sequence reuse/gap, and cursor rollback become separate `ALERT`
codes. If GitHub returns a mixed branch/history snapshot during a concurrent
checkpoint update, or the predecessor cannot be read, classify as `UNKNOWN`.

This check catches a rollback written as a *new* checkpoint commit. A force
rewrite which entirely removes newer Git commits can erase its own history;
detecting that requires an independent high-water mark outside the mutable
Cloud HOME branch. The external JANUS Silence Witness supplies an independent
*scheduler* check, but is not yet such a permanent state-sequence anchor.

## Important boundary

The observer cannot detect GitHub Actions being completely disabled, an outage
of GitHub's own Issues/Actions APIs, or a checkout failure that prevents even
the `always()` receipt step from running. Those require a *separate external*
heartbeat monitor. An `UNKNOWN` alarm never asserts the delivery SLO failed.

Local regression suite:

```bash
python -m unittest -q tests.test_beetle_observation_blindness \
  tests.test_beetle_watchdog_receipt tests.test_beetle_incident_issues \
  tests.test_beetle_home_watchdog tests.test_beetle_delivery \
  tests.test_beetle_shard_store
```
