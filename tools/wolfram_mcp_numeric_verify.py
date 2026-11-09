#!/usr/bin/env python3
"""Bounded, fail-closed in-memory numeric checks of Wolfram Cloud MCP replies.

Only provider text explicitly labelled as a Result / Answer / Exact Result /
Decimal Approximation is eligible. This is an arithmetic cross-check of a
predeclared PUBLIC input, never evidence for physical retrocausality.
Provider output is discarded; only pass/fail and its digest may be retained.
"""
from __future__ import annotations

from fractions import Fraction
import math
import re


class NumericHold(ValueError):
    pass


NUMERIC = re.compile(r"^[+-]?(?:(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?|\d+\s*/\s*\d+)$")
LABELLED = re.compile(
    r"^(?:wolfram(?:\|alpha)?\s+)?(?:result|exact\s+result|"
    r"decimal(?:\s+approximation)?|approximate\s+result|answer)"
    r"\s*(?:[:=]|\s{2,})\s*(.+?)\s*$", re.IGNORECASE
)
LABEL_ONLY = re.compile(
    r"^(?:result|exact\s+result|decimal(?:\s+approximation)?|answer)\s*:?\s*$",
    re.IGNORECASE
)
MAX_TEXT_CHARS = 20000
MAX_CONTENT_PARTS = 8


def _scalar(s: str) -> float:
    s = str(s).strip().replace("−", "-").replace("⁄", "/").replace("≈", "")
    if s == "¼":
        s = "1/4"
    s = s.strip()
    if not NUMERIC.fullmatch(s):
        raise NumericHold("NOT_SCALAR")
    try:
        value = float(Fraction(s.replace(" ", ""))) if "/" in s else float(s)
    except (ValueError, ZeroDivisionError, OverflowError):
        raise NumericHold("INVALID_SCALAR") from None
    if not math.isfinite(value):
        raise NumericHold("NONFINITE_SCALAR")
    return value


def _text_candidates(s: str) -> list[float]:
    s = s.strip()
    if len(s) > MAX_TEXT_CHARS:
        raise NumericHold("OVERSIZED_PROVIDER_TEXT")
    if not s:
        return []
    try:
        return [_scalar(s)]
    except NumericHold:
        pass
    out = []
    lines = [line.strip() for line in s.splitlines()]
    for i, line in enumerate(lines):
        label = LABELLED.fullmatch(line)
        if label:
            try:
                out.append(_scalar(label.group(1)))
            except NumericHold:
                continue
        elif LABEL_ONLY.fullmatch(line) and i + 1 < len(lines):
            try:
                out.append(_scalar(lines[i+1]))
            except NumericHold:
                continue
    return out


def verify_numeric_content(content: list[dict], expected: float) -> tuple[bool, str]:
    """Return only (verified, status). No Wolfram body or numeric value escapes."""
    if not isinstance(content, list) or not 1 <= len(content) <= MAX_CONTENT_PARTS:
        return False, "PROVIDER_PART_COUNT_UNSUPPORTED"
    if not isinstance(expected, (int, float)) or not math.isfinite(expected):
        raise NumericHold("INVALID_INDEPENDENT_REFERENCE")
    candidates = []
    for item in content:
        if not isinstance(item, dict):
            return False, "PROVIDER_CONTENT_MALFORMED"
        # Explicitly reject nontext (image/resources are not numeric results).
        if item.get("type") == "text":
            value = item.get("text")
            if not isinstance(value, str):
                return False, "PROVIDER_NONSTRING_TEXT"
            try:
                candidates.extend(_text_candidates(value))
            except NumericHold:
                return False, "PROVIDER_TEXT_OUTSIDE_BOUNDS"
    if not candidates:
        return False, "PROVIDER_NUMERIC_RESULT_UNAVAILABLE"
    # A response mixing several incompatible labelled results is ambiguous,
    # and no one occurrence of the expected scalar should create a PASS.
    if any(abs(value - candidates[0]) > 1e-9 for value in candidates[1:]):
        return False, "PROVIDER_AMBIGUOUS_NUMERIC_RESULTS"
    if abs(candidates[0] - expected) > 1e-9:
        return False, "PROVIDER_MATH_DISAGREEMENT"
    return True, "PROVIDER_MATH_MATCH_CONFIRMED"
