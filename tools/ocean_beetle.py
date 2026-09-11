#!/usr/bin/env python3
"""
LAPIS OCEAN BEETLE v1.0

Chunked/resumable reader for large remote HDF5 / MATLAB v7.3 files.
Designed for UWA Channel Library .mat files without downloading the whole file.

Core loop:
    DISCOVER -> BITE -> DIGEST -> RECEIPT -> CHECKPOINT -> NEXT

Safety:
- Remote HTTP(S) inputs must support HTTP Range requests by default.
- No full-file materialization is performed by this program.
- Checkpoint binds the run to URL + remote fingerprint + dataset + bite size.
- Receipts are append-only JSONL records linked by SHA-256.

Dependencies:
    numpy h5py fsspec requests

Examples:
    python tools/ocean_beetle.py inspect URL
    python tools/ocean_beetle.py uwa-channel URL --bite 64 --include-tracking
    python tools/ocean_beetle.py uwa-noise NOISE_URL --bite 256
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import fsspec
import h5py
import numpy as np
import requests

VERSION = "1.0.1"
DEFAULT_BLOCK_SIZE = 8 * 1024 * 1024
DEFAULT_MAX_CACHE_BLOCKS = 32


def utc_now() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def sha256_obj(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj)).hexdigest()


def is_http(source: str) -> bool:
    return urlparse(source).scheme in {"http", "https"}


def remote_fingerprint(source: str, timeout: int = 30) -> dict[str, Any]:
    if not is_http(source):
        p = Path(source).expanduser().resolve()
        st = p.stat()
        return {
            "kind": "local",
            "path": str(p),
            "size": st.st_size,
            "mtime_ns": st.st_mtime_ns,
        }

    headers: dict[str, str] = {}
    try:
        r = requests.head(source, allow_redirects=True, timeout=timeout)
        if r.ok:
            headers = {k.lower(): v for k, v in r.headers.items()}
            final_url = r.url
        else:
            final_url = source
    except requests.RequestException:
        final_url = source

    size = None
    try:
        size = int(headers.get("content-length", "") or 0) or None
    except ValueError:
        size = None

    return {
        "kind": "http",
        "url": source,
        "final_url": final_url,
        "size": size,
        "etag": headers.get("etag"),
        "last_modified": headers.get("last-modified"),
        "accept_ranges_header": headers.get("accept-ranges"),
    }


def require_range_support(
    source: str, allow_full_download: bool = False, timeout: int = 30
) -> dict[str, Any]:
    fp = remote_fingerprint(source, timeout=timeout)
    if not is_http(source):
        fp["range_probe"] = "LOCAL_NOT_REQUIRED"
        return fp

    try:
        r = requests.get(
            source,
            headers={"Range": "bytes=0-0", "Accept-Encoding": "identity"},
            allow_redirects=True,
            timeout=timeout,
            stream=True,
        )
        status = r.status_code
        content_range = r.headers.get("Content-Range")
        r.close()
    except requests.RequestException as exc:
        if not allow_full_download:
            raise RuntimeError(f"Range probe failed: {exc}") from exc
        fp["range_probe"] = f"FAILED_BUT_ALLOWED:{type(exc).__name__}"
        return fp

    fp["range_probe_status"] = status
    fp["content_range"] = content_range
    if status != 206 and not allow_full_download:
        raise RuntimeError(
            "Remote server did not answer the 1-byte probe with HTTP 206. "
            "Ocean Beetle refuses to risk a whole-file download. "
            "Use --allow-full-download only if you explicitly accept that risk."
        )
    fp["range_probe"] = "PASS_HTTP_206" if status == 206 else "NOT_206_BUT_ALLOWED"
    return fp


@contextmanager
def open_hdf5(
    source: str,
    *,
    block_size: int,
    max_cache_blocks: int,
    allow_full_download: bool,
):
    """Open HDF5 through a seekable HTTP-range-backed file object."""
    fp = require_range_support(source, allow_full_download=allow_full_download)

    if is_http(source):
        of = fsspec.open(
            source,
            mode="rb",
            block_size=block_size,
            cache_type="blockcache",
            cache_options={"maxblocks": max_cache_blocks},
        )
        raw = of.open()
    else:
        raw = open(Path(source).expanduser(), "rb")

    try:
        h5 = h5py.File(raw, "r")
        try:
            yield h5, fp
        finally:
            h5.close()
    finally:
        raw.close()


def scalar(ds: h5py.Dataset) -> float:
    arr = np.asarray(ds[()])
    return float(arr.reshape(-1)[0])


def jsonable_dtype(dtype: np.dtype) -> str:
    if dtype.fields:
        return str(dtype.descr)
    return str(dtype)


def walk_h5_tree(h5: h5py.File) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def visitor(name: str, obj: h5py.Group | h5py.Dataset) -> None:
        if isinstance(obj, h5py.Dataset):
            rows.append(
                {
                    "path": "/" + name,
                    "kind": "dataset",
                    "shape_disk": list(obj.shape),
                    "dtype": jsonable_dtype(obj.dtype),
                    "chunks": list(obj.chunks) if obj.chunks else None,
                    "compression": obj.compression,
                    "nbytes_logical": int(obj.size * obj.dtype.itemsize),
                }
            )
        else:
            rows.append({"path": "/" + name, "kind": "group"})

    h5.visititems(visitor)
    return rows


def shallow_h5_tree(h5: h5py.File) -> list[dict[str, Any]]:
    """
    Cheap root-level discovery. Avoid recursive visititems() on very large
    remote files unless --deep is explicitly requested.
    """
    rows: list[dict[str, Any]] = []
    for name in h5.keys():
        obj = h5[name]
        if isinstance(obj, h5py.Dataset):
            rows.append(
                {
                    "path": "/" + name,
                    "kind": "dataset",
                    "shape_disk": list(obj.shape),
                    "dtype": jsonable_dtype(obj.dtype),
                    "chunks": list(obj.chunks) if obj.chunks else None,
                    "compression": obj.compression,
                    "nbytes_logical": int(obj.size * obj.dtype.itemsize),
                }
            )
        else:
            rows.append({"path": "/" + name, "kind": "group"})
            if name == "params":
                for child_name in obj.keys():
                    child = obj[child_name]
                    if isinstance(child, h5py.Dataset):
                        rows.append(
                            {
                                "path": f"/{name}/{child_name}",
                                "kind": "dataset",
                                "shape_disk": list(child.shape),
                                "dtype": jsonable_dtype(child.dtype),
                                "chunks": list(child.chunks) if child.chunks else None,
                                "compression": child.compression,
                                "nbytes_logical": int(child.size * child.dtype.itemsize),
                            }
                        )
    return rows


def complex_from_dataset_array(a: np.ndarray) -> np.ndarray:
    names = a.dtype.names
    if names and "real" in names and "imag" in names:
        return np.asarray(a["real"], dtype=np.float64) + 1j * np.asarray(
            a["imag"], dtype=np.float64
        )
    if np.iscomplexobj(a):
        return np.asarray(a)
    return np.asarray(a, dtype=np.float64)


def stats_real(a: np.ndarray) -> dict[str, Any]:
    x = np.asarray(a, dtype=np.float64).reshape(-1)
    finite = np.isfinite(x)
    y = x[finite]
    if y.size == 0:
        return {"count": int(x.size), "finite": 0}
    return {
        "count": int(x.size),
        "finite": int(y.size),
        "min": float(np.min(y)),
        "max": float(np.max(y)),
        "mean": float(np.mean(y)),
        "std": float(np.std(y)),
        "rms": float(np.sqrt(np.mean(y * y))),
    }


def stats_complex(z: np.ndarray) -> dict[str, Any]:
    flat = np.asarray(z).reshape(-1)
    finite = np.isfinite(flat.real) & np.isfinite(flat.imag)
    x = flat[finite]
    if x.size == 0:
        return {"count": int(flat.size), "finite": 0}
    mag = np.abs(x)
    return {
        "count": int(flat.size),
        "finite": int(x.size),
        "magnitude_min": float(np.min(mag)),
        "magnitude_max": float(np.max(mag)),
        "magnitude_mean": float(np.mean(mag)),
        "magnitude_rms": float(np.sqrt(np.mean(mag * mag))),
        "energy": float(np.sum(mag * mag)),
    }


def load_checkpoint(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def append_receipt(path: Path, receipt: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(receipt)
    digest = sha256_obj(body)
    row = {"receipt_sha256": digest, **body}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return digest


def fingerprints_compatible(a: dict[str, Any], b: dict[str, Any]) -> bool:
    keys = ("kind", "size", "etag", "last_modified", "path", "mtime_ns")
    for k in keys:
        if a.get(k) is not None and b.get(k) is not None and a.get(k) != b.get(k):
            return False
    return True


@dataclass
class RunPaths:
    root: Path
    checkpoint: Path
    receipts: Path
    chunks: Path


def make_run_paths(out_dir: str, run_id: str) -> RunPaths:
    root = Path(out_dir) / run_id
    return RunPaths(
        root=root,
        checkpoint=root / "checkpoint.json",
        receipts=root / "receipts.jsonl",
        chunks=root / "chunks",
    )


def derive_run_id(source: str, mode: str, dataset: str) -> str:
    token = hashlib.sha256(f"{source}|{mode}|{dataset}".encode()).hexdigest()[:12]
    safe = Path(urlparse(source).path).name or "remote"
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in safe)
    return f"{mode}-{safe}-{token}"


def resume_or_initialize(
    *,
    paths: RunPaths,
    source: str,
    fingerprint: dict[str, Any],
    mode: str,
    dataset: str,
    axis: int,
    bite: int,
    start: int,
    stop: int,
    force_restart: bool,
) -> dict[str, Any]:
    old = load_checkpoint(paths.checkpoint)
    spec = {
        "source": source,
        "fingerprint": fingerprint,
        "mode": mode,
        "dataset": dataset,
        "axis": axis,
        "bite": bite,
        "start": start,
        "stop": stop,
    }

    if old and not force_restart:
        if old.get("source") != source:
            raise RuntimeError("Checkpoint source differs; use --force-restart.")
        if not fingerprints_compatible(old.get("fingerprint", {}), fingerprint):
            raise RuntimeError(
                "Remote/local file fingerprint changed; refusing unsafe resume. "
                "Use a new --run-id or --force-restart after review."
            )
        for key in ("mode", "dataset", "axis", "bite", "start", "stop"):
            if old.get(key) != spec[key]:
                raise RuntimeError(
                    f"Checkpoint {key}={old.get(key)!r} differs from requested "
                    f"{spec[key]!r}; use a new --run-id or --force-restart."
                )
        return old

    if old and force_restart:
        stamp = int(time.time())
        paths.checkpoint.rename(paths.checkpoint.with_name(f"checkpoint.{stamp}.bak.json"))
        if paths.receipts.exists():
            paths.receipts.rename(paths.receipts.with_name(f"receipts.{stamp}.bak.jsonl"))

    state = {
        **spec,
        "tool": "LAPIS_OCEAN_BEETLE",
        "tool_version": VERSION,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "next_index": start,
        "bites_completed": 0,
        "last_receipt_sha256": None,
        "status": "READY",
    }
    atomic_write_json(paths.checkpoint, state)
    return state


def save_npz_chunk(path: Path, **arrays: np.ndarray) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def cmd_inspect(args: argparse.Namespace) -> int:
    with open_hdf5(
        args.source,
        block_size=args.block_size,
        max_cache_blocks=args.max_cache_blocks,
        allow_full_download=args.allow_full_download,
    ) as (h5, fp):
        rows = walk_h5_tree(h5) if args.deep else shallow_h5_tree(h5)
        out: dict[str, Any] = {
            "tool": "LAPIS_OCEAN_BEETLE",
            "version": VERSION,
            "source_fingerprint": fp,
            "objects": rows,
        }
        if "h_hat" in h5 and isinstance(h5["h_hat"], h5py.Dataset):
            ds = h5["h_hat"]
            out["uwa_hint"] = {
                "h_hat_disk_shape": list(ds.shape),
                "h_hat_logical_shape_if_matlab_v73_reversed": list(reversed(ds.shape)),
                "note": "UWA reference reader documents logical [delay,receiver,time] "
                "with reversed on-disk HDF5 shape [time,receiver,delay].",
            }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def uwa_params(h5: h5py.File) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "params" in h5 and isinstance(h5["params"], h5py.Group):
        g = h5["params"]
        for key in ("fs_delay", "fs_time", "fc"):
            if key in g and isinstance(g[key], h5py.Dataset):
                out[key] = scalar(g[key])
    if "version" in h5 and isinstance(h5["version"], h5py.Dataset):
        out["version"] = scalar(h5["version"])
    if "f_resamp" in h5 and isinstance(h5["f_resamp"], h5py.Dataset):
        out["f_resamp"] = scalar(h5["f_resamp"])
    return out


def receiver_energy(z_disk_tml: np.ndarray) -> list[float]:
    if z_disk_tml.ndim != 3:
        return []
    return [
        float(np.sum(np.abs(z_disk_tml[:, m, :]) ** 2))
        for m in range(z_disk_tml.shape[1])
    ]


def peak_delay_per_receiver(z_disk_tml: np.ndarray) -> list[int]:
    if z_disk_tml.ndim != 3:
        return []
    out: list[int] = []
    for m in range(z_disk_tml.shape[1]):
        profile = np.sum(np.abs(z_disk_tml[:, m, :]) ** 2, axis=0)
        out.append(int(np.argmax(profile)))
    return out


def maybe_tracking_bite(
    h5: h5py.File,
    *,
    t0: int,
    t1: int,
    params: dict[str, Any],
) -> dict[str, Any]:
    tracking_name = None
    for candidate in ("phi_hat", "theta_hat"):
        if candidate in h5 and isinstance(h5[candidate], h5py.Dataset):
            tracking_name = candidate
            break
    if tracking_name is None:
        return {"present": False}

    fs_delay = params.get("fs_delay")
    fs_time = params.get("fs_time")
    if not fs_delay or not fs_time:
        return {
            "present": True,
            "dataset": tracking_name,
            "read": False,
            "reason": "missing fs_delay/fs_time",
        }

    ratio = float(fs_delay) / float(fs_time)
    n0 = max(0, int(math.floor(t0 * ratio)))
    n1 = min(h5[tracking_name].shape[0], int(math.ceil(t1 * ratio)))
    a = np.asarray(h5[tracking_name][n0:n1, :])
    return {
        "present": True,
        "dataset": tracking_name,
        "read": True,
        "disk_slice": [n0, n1],
        "shape": list(a.shape),
        "stats": stats_real(a),
        "_array": a,
    }


def cmd_uwa_channel(args: argparse.Namespace) -> int:
    mode = "uwa-channel"
    dataset = "h_hat"
    with open_hdf5(
        args.source,
        block_size=args.block_size,
        max_cache_blocks=args.max_cache_blocks,
        allow_full_download=args.allow_full_download,
    ) as (h5, fp):
        if dataset not in h5 or not isinstance(h5[dataset], h5py.Dataset):
            raise KeyError("Dataset /h_hat not found.")
        ds = h5[dataset]
        if len(ds.shape) != 3:
            raise ValueError(f"Expected 3-D h_hat; got shape {ds.shape}.")

        total_t, total_m, total_l = map(int, ds.shape)
        start = max(0, args.start)
        stop = min(total_t, args.stop if args.stop is not None else total_t)
        if start >= stop:
            raise ValueError(f"Empty requested interval [{start}, {stop}).")

        run_id = args.run_id or derive_run_id(args.source, mode, dataset)
        paths = make_run_paths(args.out_dir, run_id)
        state = resume_or_initialize(
            paths=paths,
            source=args.source,
            fingerprint=fp,
            mode=mode,
            dataset=dataset,
            axis=0,
            bite=args.bite,
            start=start,
            stop=stop,
            force_restart=args.force_restart,
        )
        params = uwa_params(h5)

        print(
            json.dumps(
                {
                    "event": "OPEN",
                    "run_id": run_id,
                    "disk_shape": [total_t, total_m, total_l],
                    "logical_shape": [total_l, total_m, total_t],
                    "params": params,
                    "resume_from": state["next_index"],
                    "stop": stop,
                },
                ensure_ascii=False,
            )
        )

        t0 = int(state["next_index"])
        bites_this_invocation = 0
        while t0 < stop:
            if args.max_bites is not None and bites_this_invocation >= args.max_bites:
                break
            t1 = min(stop, t0 + args.bite)
            raw = np.asarray(ds[t0:t1, :, :])
            z = complex_from_dataset_array(raw)

            receipt: dict[str, Any] = {
                "schema": "lapis.ocean_beetle.bite.v1",
                "timestamp": utc_now(),
                "run_id": run_id,
                "mode": mode,
                "source": args.source,
                "dataset": "/h_hat",
                "disk_slice": {"time": [t0, t1], "receiver": [0, total_m], "delay": [0, total_l]},
                "shape": list(z.shape),
                "digest": stats_complex(z),
                "receiver_energy": receiver_energy(z),
                "peak_delay_index_per_receiver": peak_delay_per_receiver(z),
                "params": params,
                "prev_receipt_sha256": state.get("last_receipt_sha256"),
            }

            tracking = None
            if args.include_tracking:
                tracking = maybe_tracking_bite(h5, t0=t0, t1=t1, params=params)
                tracking_for_receipt = dict(tracking)
                tracking_for_receipt.pop("_array", None)
                receipt["tracking"] = tracking_for_receipt

            if args.save_npz:
                arrays = {"h_hat": z}
                if tracking and tracking.get("read") and "_array" in tracking:
                    arrays[str(tracking["dataset"])] = tracking["_array"]
                npz_path = paths.chunks / f"h_hat_t{t0:09d}_{t1:09d}.npz"
                receipt["saved_npz"] = {
                    "path": str(npz_path),
                    "sha256": save_npz_chunk(npz_path, **arrays),
                }

            digest = append_receipt(paths.receipts, receipt)
            state.update(
                {
                    "next_index": t1,
                    "bites_completed": int(state.get("bites_completed", 0)) + 1,
                    "last_receipt_sha256": digest,
                    "updated_at": utc_now(),
                    "status": "COMPLETE" if t1 >= stop else "IN_PROGRESS",
                }
            )
            atomic_write_json(paths.checkpoint, state)
            print(
                json.dumps(
                    {
                        "event": "BITE",
                        "t0": t0,
                        "t1": t1,
                        "receipt_sha256": digest,
                        "next": state["next_index"],
                        "status": state["status"],
                    }
                )
            )
            t0 = t1
            bites_this_invocation += 1

        if t0 < stop:
            print(
                json.dumps(
                    {
                        "event": "PAUSED",
                        "reason": "max_bites reached",
                        "next": t0,
                        "checkpoint": str(paths.checkpoint),
                    }
                )
            )
        else:
            print(
                json.dumps(
                    {
                        "event": "COMPLETE",
                        "bites": state["bites_completed"],
                        "receipts": str(paths.receipts),
                        "checkpoint": str(paths.checkpoint),
                    }
                )
            )
    return 0


def cmd_uwa_noise(args: argparse.Namespace) -> int:
    mode = "uwa-noise"
    dataset = "beta"
    with open_hdf5(
        args.source,
        block_size=args.block_size,
        max_cache_blocks=args.max_cache_blocks,
        allow_full_download=args.allow_full_download,
    ) as (h5, fp):
        if dataset not in h5 or not isinstance(h5[dataset], h5py.Dataset):
            raise KeyError("Dataset /beta not found.")
        ds = h5[dataset]
        if len(ds.shape) != 3:
            raise ValueError(f"Expected 3-D beta; got shape {ds.shape}.")

        total_k, m1, m2 = map(int, ds.shape)
        start = max(0, args.start)
        stop = min(total_k, args.stop if args.stop is not None else total_k)
        if start >= stop:
            raise ValueError(f"Empty requested interval [{start}, {stop}).")

        run_id = args.run_id or derive_run_id(args.source, mode, dataset)
        paths = make_run_paths(args.out_dir, run_id)
        state = resume_or_initialize(
            paths=paths,
            source=args.source,
            fingerprint=fp,
            mode=mode,
            dataset=dataset,
            axis=0,
            bite=args.bite,
            start=start,
            stop=stop,
            force_restart=args.force_restart,
        )
        noise_meta = {}
        for key in ("alpha", "Fs", "version"):
            if key in h5 and isinstance(h5[key], h5py.Dataset):
                noise_meta[key] = scalar(h5[key])

        k0 = int(state["next_index"])
        bites_this_invocation = 0
        while k0 < stop:
            if args.max_bites is not None and bites_this_invocation >= args.max_bites:
                break
            k1 = min(stop, k0 + args.bite)
            raw = np.asarray(ds[k0:k1, :, :])
            receipt = {
                "schema": "lapis.ocean_beetle.bite.v1",
                "timestamp": utc_now(),
                "run_id": run_id,
                "mode": mode,
                "source": args.source,
                "dataset": "/beta",
                "disk_slice": {"k": [k0, k1], "receiver_1": [0, m1], "receiver_2": [0, m2]},
                "shape": list(raw.shape),
                "digest": stats_real(raw),
                "noise_meta": noise_meta,
                "prev_receipt_sha256": state.get("last_receipt_sha256"),
            }
            if args.save_npz:
                npz_path = paths.chunks / f"beta_k{k0:09d}_{k1:09d}.npz"
                receipt["saved_npz"] = {
                    "path": str(npz_path),
                    "sha256": save_npz_chunk(npz_path, beta=raw),
                }

            digest = append_receipt(paths.receipts, receipt)
            state.update(
                {
                    "next_index": k1,
                    "bites_completed": int(state.get("bites_completed", 0)) + 1,
                    "last_receipt_sha256": digest,
                    "updated_at": utc_now(),
                    "status": "COMPLETE" if k1 >= stop else "IN_PROGRESS",
                }
            )
            atomic_write_json(paths.checkpoint, state)
            print(json.dumps({"event": "BITE", "k0": k0, "k1": k1, "receipt_sha256": digest}))
            k0 = k1
            bites_this_invocation += 1

        print(
            json.dumps(
                {
                    "event": "COMPLETE" if k0 >= stop else "PAUSED",
                    "next": k0,
                    "checkpoint": str(paths.checkpoint),
                    "receipts": str(paths.receipts),
                }
            )
        )
    return 0


def add_common_remote_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("source", help="HTTP(S) URL or local HDF5/MAT v7.3 path")
    p.add_argument(
        "--block-size",
        type=int,
        default=DEFAULT_BLOCK_SIZE,
        help=f"HTTP byte-range cache block size (default {DEFAULT_BLOCK_SIZE})",
    )
    p.add_argument(
        "--max-cache-blocks",
        type=int,
        default=DEFAULT_MAX_CACHE_BLOCKS,
        help="Maximum fsspec cached blocks (default 32)",
    )
    p.add_argument(
        "--allow-full-download",
        action="store_true",
        help="Allow servers without HTTP Range support (DANGEROUS for huge files)",
    )


def add_walk_args(p: argparse.ArgumentParser, default_bite: int) -> None:
    add_common_remote_args(p)
    p.add_argument("--bite", type=int, default=default_bite, help="Rows/time frames per bite")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--stop", type=int, default=None)
    p.add_argument(
        "--max-bites",
        type=int,
        default=None,
        help="Process at most N bites this invocation, then checkpoint and exit",
    )
    p.add_argument("--out-dir", default=".ocean_beetle")
    p.add_argument("--run-id", default=None)
    p.add_argument("--save-npz", action="store_true", help="Persist each selected bite")
    p.add_argument("--force-restart", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ocean_beetle",
        description="Chunked/resumable remote HDF5 reader for JANUS/Lapis ocean research.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = p.add_subparsers(dest="command", required=True)

    inspect_p = sub.add_parser("inspect", help="Read only HDF5 metadata/tree")
    add_common_remote_args(inspect_p)
    inspect_p.add_argument("--deep", action="store_true", help="Recursively walk the full HDF5 object tree")
    inspect_p.set_defaults(func=cmd_inspect)

    ch = sub.add_parser(
        "uwa-channel",
        help="Walk UWA /h_hat in time bites; UWA disk order [time,receiver,delay]",
    )
    add_walk_args(ch, default_bite=64)
    ch.add_argument(
        "--include-tracking",
        action="store_true",
        help="Also bite matching phi_hat/theta_hat interval using fs_delay/fs_time",
    )
    ch.set_defaults(func=cmd_uwa_channel)

    nz = sub.add_parser(
        "uwa-noise",
        help="Walk UWA /beta noise covariance in K-axis bites; disk order [K,M,M]",
    )
    add_walk_args(nz, default_bite=256)
    nz.set_defaults(func=cmd_uwa_noise)

    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "bite", 1) <= 0:
        raise SystemExit("--bite must be > 0")
    if getattr(args, "block_size", 1) <= 0:
        raise SystemExit("--block-size must be > 0")
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print(
            json.dumps(
                {"event": "INTERRUPTED", "note": "Last completed bite is checkpointed."}
            ),
            file=sys.stderr,
        )
        return 130
    except Exception as exc:
        print(
            json.dumps(
                {
                    "event": "ERROR",
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
