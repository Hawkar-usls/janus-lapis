"""Retry only a normal fast-forward Beetle state push after transient transport failure."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import time

TRANSIENT = ("internal server error", "http 500", "http 502", "http 503", "http 504",
             "returned error: 500", "returned error: 502", "returned error: 503",
             "returned error: 504", "connection reset by peer", "could not resolve host",
             "failed to connect", "remote end hung up unexpectedly")
CONFLICT = ("non-fast-forward", "fetch first", "protected branch", "permission denied",
            "authentication failed", "repository not found", "permission to ")


def push_state(git_root: Path, *, runner=None, sleeper=None) -> dict:
    runner = runner or subprocess.run
    sleeper = sleeper or time.sleep
    command = ["git", "-C", str(Path(git_root).resolve()), "push", "origin", "HEAD:beetle-state"]
    for attempt in range(1, 4):
        try:
            done = runner(command, text=True, capture_output=True, timeout=90)
            if done.returncode == 0:
                return {"status": "PUSH_CONFIRMED", "attempts": attempt}
            detail = ((done.stderr or "") + "\n" + (done.stdout or "")).lower()
            retry = (not any(word in detail for word in CONFLICT) and
                     any(word in detail for word in TRANSIENT))
        except subprocess.TimeoutExpired:
            # The remote may already have accepted the commit. Repeating this
            # same normal push is idempotent and cannot overwrite another head.
            retry = True
        if not retry or attempt == 3:
            # Transport diagnostics may contain authentication material. Keep
            # credentials and arbitrary remote output out of durable receipts.
            raise RuntimeError("BEETLE_DURABLE_PUSH_NOT_CONFIRMED") from None
        sleeper(2 ** attempt)
    raise AssertionError("unreachable")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--git-root", type=Path, required=True)
    args = parser.parse_args()
    result = push_state(args.git_root)
    print("BEETLE_DURABLE_PUSH=" + result["status"])
    print("BEETLE_DURABLE_PUSH_ATTEMPTS=" + str(result["attempts"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
