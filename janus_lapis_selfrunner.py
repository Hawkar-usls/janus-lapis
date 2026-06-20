#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime, UTC
import subprocess, sys, os, shutil, json

HERE = Path(__file__).resolve().parent
WORK = HERE / "_JanusLapis_RUNNER"
RUNS = WORK / "janus_lapis_runs"

def now():
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00","Z")

def main():
    WORK.mkdir(exist_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "LapisModernGPT.py", WORK / "LapisModernGPT.py")

    trials = os.environ.get("JANUS_LAPIS_TRIALS_PER_ARCHETYPE", "3000")
    seed = os.environ.get("JANUS_LAPIS_SEED", "1618")
    top = os.environ.get("JANUS_LAPIS_TOP_PER_ARCHETYPE", "3")
    reps = os.environ.get("JANUS_LAPIS_REPLICATES", "1")
    no_transformer = os.environ.get("JANUS_LAPIS_NO_TRANSFORMER", "0") == "1"

    cmd = [
        sys.executable, str(WORK / "LapisModernGPT.py"),
        "--outdir", str(RUNS),
        "full-run",
        "--trials-per-archetype", trials,
        "--seed", seed,
        "--top-per-archetype", top,
        "--replicates", reps,
    ]
    if no_transformer:
        cmd.append("--no-transformer")

    print(json.dumps({"ts": now(), "event": "janus_lapis_v015_start", "cmd": " ".join(cmd)}, ensure_ascii=False))
    p = subprocess.run(cmd, text=True, capture_output=True)
    (RUNS / "JANUS_LAPIS_console.log").write_text(p.stdout + "\n" + p.stderr, encoding="utf-8")
    print(p.stdout[-9000:])
    if p.returncode != 0:
        print(p.stderr)
        raise SystemExit(p.returncode)

    print("\nDONE.")
    print("Review/send this ZIP:")
    print(RUNS / "SEND_TO_REVIEWERS_JANUS_LAPIS.zip")
    print("\nMain summary:")
    print(RUNS / "janus_lapis_summary.json")

if __name__ == "__main__":
    main()
