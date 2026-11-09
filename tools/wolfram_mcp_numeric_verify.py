#!/usr/bin/env python3
"""Fail-closed numeric extraction for one Wolfram Cloud MCP arithmetic check.

Provider data is parsed in memory only. No full answer, numerical provider
output, arbitrary string excerpt or provider payload is saved in receipts.
A numeric result must be the complete scalar or explicitly labelled RESULT.
"""
from __future__ import annotations

from fractions import Fraction
import json
import math
import re

MAX_TEXT_CHARS = 20000
MAX_CONTENT_PARTS = 8
MAX_STRUCTURED_DEPTH = 6
MAX_VALUES = 12
SCALAR = re.compile(r"[+-]?(?:(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?|\d+\s*/\s*\d+)")
LABEL = re.compile(r"^(?:wolfram(?:\|alpha)?\s+)?(?:result|exact\s+result|decimal(?:\s+approximation)?|approximate\s+result|answer)$",re.I)
LATEX_FRAC = re.compile(r"\\(?:dfrac|frac)\s*\{\s*([+-]?\d+)\s*\}\s*\{\s*(\d+)\s*\}")
MARKDOWN_LABEL = re.compile(r"^\s*(?:#{1,5}\s*)?(?:\*\*)?(?:wolfram(?:\|alpha)?\s+)?(result|exact\s+result|decimal(?:\s+approximation)?|approximate\s+result|answer)(?:\*\*)?\s*(?::|=|\u2014)?\s*(.*?)\s*$",re.I)
POD_LABELS = {"result","exact result","decimal approximation","approximate result","answer"}


def _scalar(source: str) -> float:
    s = source.strip().replace("−","-").replace("⁄","/").replace("≈","").strip()
    if s == "¼":
        s = "1/4"
    for opener, closer in ((r"\(",r"\)"),(r"\[",r"\]"),("$$","$$"),("$","$")):
        if s.startswith(opener) and s.endswith(closer):
            s = s[len(opener):-len(closer)].strip()
            break
    if s.startswith(r"\boxed{") and s.endswith("}"):
        s = s[len(r"\boxed{"):-1].strip()
    frac = LATEX_FRAC.fullmatch(s)
    if frac:
        s = frac.group(1) + "/" + frac.group(2)
    if s.startswith("**") and s.endswith("**"):
        s = s[2:-2].strip()
    if not SCALAR.fullmatch(s):
        raise ValueError("NOT_A_COMPLETE_SCALAR")
    try:
        val=float(Fraction(s.replace(" ",""))) if "/" in s else float(s)
    except (ValueError,ZeroDivisionError,OverflowError):
        raise ValueError("INVALID_SCALAR") from None
    if not math.isfinite(val):
        raise ValueError("NONFINITE_SCALAR")
    return val


def _structured_values(obj, depth: int=0) -> list[float]:
    if depth > MAX_STRUCTURED_DEPTH:
        raise ValueError("STRUCTURE_TOO_DEEP")
    values=[]
    if isinstance(obj,list):
        for part in obj[:MAX_VALUES]:
            if isinstance(part,(dict,list)):
                values += _structured_values(part,depth+1)
        return values[:MAX_VALUES]
    if not isinstance(obj,dict):
        return values
    # No arbitrary input, query, notes or metadata keys: only result labels.
    for key in ("result","Result","answer","Answer","exactResult","plaintext"):
        if key not in obj or (key=="plaintext" and
                not LABEL.fullmatch(str(obj.get("title","")))):
            continue
        value=obj[key]
        if isinstance(value,(str,int,float)):
            try:
                values.append(_scalar(str(value)))
            except ValueError:
                if isinstance(value,str):
                    values += _text_values(value)
        elif isinstance(value,(dict,list)):
            values += _structured_values(value,depth+1)
    pods=obj.get("pods")
    if isinstance(pods,list):
        for pod in pods[:MAX_VALUES]:
            if not isinstance(pod,dict) or str(pod.get("title","")).lower() not in POD_LABELS:
                continue
            subs=pod.get("subpods",[])
            if not isinstance(subs,list):
                continue
            for sub in subs[:MAX_VALUES]:
                if isinstance(sub,dict):
                    for key in ("plaintext","text"):
                        v=sub.get(key)
                        if isinstance(v,str):
                            try:
                                values.append(_scalar(v))
                            except ValueError:
                                values += _text_values(v)
    return values[:MAX_VALUES]


def _text_values(text: str) -> list[float]:
    if not isinstance(text,str) or len(text)>MAX_TEXT_CHARS:
        raise ValueError("TEXT_TOO_LARGE_OR_WRONG_TYPE")
    text=text.strip()
    if not text:
        return []
    try:
        return [_scalar(text)]
    except ValueError:
        pass
    if text.startswith("{") or text.startswith("["):
        try:
            obj=json.loads(text)
        except ValueError:
            obj=None
        if isinstance(obj,(dict,list)):
            return _structured_values(obj,0)
    lines=[x.strip() for x in text.splitlines()]
    values=[]
    for i,line in enumerate(lines):
        if line.startswith("|") and line.endswith("|"):
            cells=[x.strip().replace("**","") for x in line.strip("|").split("|")]
            if len(cells)==2 and LABEL.fullmatch(cells[0]):
                try:
                    values.append(_scalar(cells[1]))
                except ValueError:
                    pass
            continue
        m=MARKDOWN_LABEL.fullmatch(line.replace("**",""))
        if not m or not LABEL.fullmatch(m.group(1)):
            continue
        remainder=m.group(2).strip()
        if remainder:
            try:
                values.append(_scalar(remainder))
            except ValueError:
                pass
        else:
            following=[x for x in lines[i+1:i+4] if x]
            if following:
                try:
                    values.append(_scalar(following[0]))
                except ValueError:
                    pass
    return values[:MAX_VALUES]


def verify_numeric_content(content: list[dict], expected: float,
                           structured_content=None) -> tuple[bool,str]:
    """Return only Boolean and fixed status, never raw Wolfram content."""
    if not isinstance(expected,(int,float)) or not math.isfinite(expected):
        raise ValueError("INVALID_LOCAL_REFERENCE")
    if not isinstance(content,list) or not 1<=len(content)<=MAX_CONTENT_PARTS:
        return False,"PROVIDER_PART_COUNT_UNSUPPORTED"
    values=[]
    try:
        for part in content:
            if not isinstance(part,dict):
                return False,"PROVIDER_CONTENT_MALFORMED"
            if part.get("type")=="text":
                values += _text_values(part.get("text",""))
        if structured_content is not None:
            values += _structured_values(structured_content)
    except (ValueError,RecursionError):
        return False,"PROVIDER_FORMAT_OUTSIDE_BOUNDS"
    if not values:
        return False,"PROVIDER_NUMERIC_RESULT_UNAVAILABLE"
    if len(values)>MAX_VALUES:
        return False,"PROVIDER_TOO_MANY_RESULTS"
    if any(abs(x-values[0])>1e-9 for x in values[1:]):
        return False,"PROVIDER_AMBIGUOUS_NUMERIC_RESULTS"
    if abs(values[0]-expected)>1e-9:
        return False,"PROVIDER_MATH_DISAGREEMENT"
    return True,"PROVIDER_MATH_MATCH_CONFIRMED"


def safe_shape_summary(content: list[dict], structured_content=None) -> dict:
    """Coarse flags only, no text, values, provider-provided labels or keys."""
    if not isinstance(content,list):
        return {"classification":"NON_LIST_CONTENT"}
    texts=[part.get("text","") for part in content
           if isinstance(part,dict) and part.get("type")=="text"]
    joined="\n".join(t[:MAX_TEXT_CHARS] for t in texts if isinstance(t,str))
    _,status=verify_numeric_content(content,0,structured_content)
    return {
        "classification":"SCHEMA_FLAGS_ONLY",
        "parts":min(99,len(content)),
        "text_parts":len(texts),
        "has_structured_content":isinstance(structured_content,(dict,list)),
        "contains_json_object_syntax":any(
            isinstance(t,str) and t.strip().startswith("{") for t in texts),
        "contains_result_label":bool(re.search(r"(?:^|[\n|#* ])result\s*[:=|]?",joined,re.I)),
        "contains_markdown_table":bool(re.search(r"^\s*\|.*\|\s*$",joined,re.M)),
        "contains_latex_fraction":r"\frac" in joined or r"\dfrac" in joined,
        "contains_xml_like_syntax":bool(re.search(r"<(?:pod|subpod|plaintext|math)",joined,re.I)),
        "only_image_or_resource_parts":len(texts)==0,
        "numeric_candidate_recognized":status in (
            "PROVIDER_MATH_MATCH_CONFIRMED","PROVIDER_MATH_DISAGREEMENT",
            "PROVIDER_AMBIGUOUS_NUMERIC_RESULTS"),
    }
