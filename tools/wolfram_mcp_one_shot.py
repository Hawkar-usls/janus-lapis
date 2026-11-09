#!/usr/bin/env python3
"""One-shot keyless official Wolfram Cloud MCP client for JANUS Universal Beetle.

This is *not* the paid WolframAlpha Results API and does not scrape web pages.
Only an approved predeclared math probe can execute. Free Cloud MCP is for
limited personal use; do not harvest result corpora or run repeated polling.
Only a provenance digest/receipt is kept, never the provider's response body.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urlparse

MCP_ENDPOINT = "https://agenttools.wolfram.com/mcp"
MCP_DOCS = "https://www.wolfram.com/ai/mcp/cloud/"
PROTOCOL = "2025-06-18"
ALLOWED_NEGOTIATED_PROTOCOLS = ("2025-03-26", "2025-06-18")
MCP_CLIENT_REVISION = "negotiated-protocol-v2"
MAX_BODY_BYTES = 200_000
# Explicitly approved queries are intentionally few. Add new research
# question IDs only by code review, not from model output or mutable config.
CASES = {
    "zeno_n2_analytic": {
        "query": "cos(pi/4)^4",
        "public_reference": 0.25,
        "description": "Quantum Zeno: all-zero measurement record N=2, Omega*T=pi",
    },
}


class MCPHold(ValueError):
    pass


def digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def _read_bounded_response(response, *, expected_id, note_request):
    try:
        if response.status_code not in (200, 202):
            raise MCPHold(f"MCP_HTTP_STATUS_{response.status_code}")
        parts, nbytes = [], 0
        for part in response.iter_content(chunk_size=8192):
            nbytes += len(part)
            if nbytes > MAX_BODY_BYTES:
                raise MCPHold("MCP_RESPONSE_TOO_LARGE")
            parts.append(part)
        body = b"".join(parts)
        note_request(nbytes)
        if expected_id is None and response.status_code == 202:
            return None
        content_type = response.headers.get("Content-Type", "").lower()
        if content_type.startswith("application/json"):
            parsed = json.loads(body)
        elif content_type.startswith("text/event-stream"):
            decoded = body.decode("utf-8")
            candidates = []
            for line in decoded.splitlines():
                if line.startswith("data:"):
                    item = json.loads(line[5:].strip())
                    if isinstance(item, dict) and item.get("id") == expected_id:
                        candidates.append(item)
            if not candidates:
                raise MCPHold("MCP_EXPECTED_SSE_RESULT_MISSING")
            parsed = candidates[-1]
        else:
            raise MCPHold("MCP_UNEXPECTED_CONTENT_TYPE")
        if not isinstance(parsed, dict):
            raise MCPHold("MCP_NON_OBJECT_RESPONSE")
        if expected_id is not None and parsed.get("id") != expected_id:
            raise MCPHold("MCP_MESSAGE_ID_MISMATCH")
        if "error" in parsed:
            raise MCPHold("MCP_REMOTE_ERROR")
        return parsed
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, MCPHold):
            raise
        raise MCPHold("MCP_MALFORMED_RESPONSE") from None
    finally:
        response.close()


def send(session, *, method, params=None, request_id=None, session_id=None,
         protocol_version=PROTOCOL, note_request=lambda n: None):
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": protocol_version,
        "User-Agent": "JANUS-Beetle-Research-OneShot/1",
    }
    if session_id:
        if len(session_id) > 512 or any(c in session_id for c in "\r\n"):
            raise MCPHold("MCP_INVALID_SESSION_ID")
        headers["Mcp-Session-Id"] = session_id
    payload = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        payload["id"] = request_id
    if params is not None:
        payload["params"] = params
    try:
        response = session.post(MCP_ENDPOINT, headers=headers, json=payload,
                                stream=True, timeout=(8, 25), allow_redirects=False)
    except Exception:
        note_request(0)
        raise MCPHold("MCP_TRANSPORT_UNAVAILABLE") from None
    if response.url != MCP_ENDPOINT:
        response.close()
        note_request(0)
        raise MCPHold("MCP_REDIRECT_REFUSED")
    sid = response.headers.get("Mcp-Session-Id")
    result = _read_bounded_response(response, expected_id=request_id, note_request=note_request)
    return result, sid


def one_shot(case_id, session, note_request=lambda n: None):
    if case_id not in CASES:
        raise MCPHold("UNAPPROVED_RESEARCH_QUERY")
    case = CASES[case_id]
    init, sid = send(session, method="initialize", request_id=1, params={
        "protocolVersion": PROTOCOL,
        "capabilities": {},
        "clientInfo": {"name": "janus-beetle-scientific-one-shot", "version": "1.0.0"},
    }, note_request=note_request)
    if not isinstance(init.get("result"), dict):
        raise MCPHold("MCP_INITIALIZE_FAILED")
    negotiated = init["result"].get("protocolVersion")
    if negotiated not in ALLOWED_NEGOTIATED_PROTOCOLS:
        raise MCPHold("MCP_PROTOCOL_VERSION_UNSUPPORTED")
    send(session, method="notifications/initialized", session_id=sid,
         protocol_version=negotiated, note_request=note_request)
    listed, _ = send(session, method="tools/list", request_id=2, session_id=sid,
                     protocol_version=negotiated, note_request=note_request)
    tools = listed.get("result", {}).get("tools", [])
    allowed = [x for x in tools if x.get("name") == "WolframAlpha"]
    if len(allowed) != 1:
        raise MCPHold("WOLFRAMALPHA_MCP_TOOL_MISSING")
    schema = allowed[0].get("inputSchema", {})
    props = schema.get("properties", {})
    required = schema.get("required", [])
    # Tool schemas are dynamic; fail closed unless exactly one required string
    # field can carry the already approved query.
    candidates = [k for k in ("input", "query", "question") if props.get(k, {}).get("type") == "string"]
    if len(candidates) != 1 or any(x != candidates[0] for x in required):
        raise MCPHold("WOLFRAMALPHA_TOOL_SCHEMA_NOT_ALLOWED")
    called, _ = send(session, method="tools/call", request_id=3, session_id=sid,
                     protocol_version=negotiated,
                     params={"name": "WolframAlpha",
                             "arguments": {candidates[0]: case["query"]}},
                     note_request=note_request)
    result = called.get("result", {})
    if result.get("isError") is True:
        raise MCPHold("WOLFRAMALPHA_TOOL_RESULT_ERROR")
    content = result.get("content")
    if not isinstance(content, list) or not content:
        raise MCPHold("WOLFRAMALPHA_EMPTY_RESPONSE")
    # Provider text is NEVER serialized, printed or used as training data.
    return {
        "schema": "janus.beetle.wolfram_keyless_mcp_probe.v1",
        "status": "LIVE_MCP_TOOL_RESPONSE_RECEIVED",
        "source": "Wolfram Cloud MCP, official no-auth personal-use endpoint",
        "server_url": MCP_ENDPOINT,
        "documentation": MCP_DOCS,
        "tool": "WolframAlpha",
        "query_id": case_id,
        "public_question": case["query"],
        "independently_derived_math_baseline": case["public_reference"],
        "provider_content_sha256": digest(content),
        "provider_content_part_count": len(content),
        "provider_response_cached": False,
        "provider_math_answer_verified": False,
        "physical_retrocausality_proven": False,
        "underlying_model_modified": False,
        "mcp_protocol_requested": PROTOCOL,
        "mcp_protocol_negotiated": negotiated,
        "api_appid_or_login_used": False,
        "one_shot_no_bulk_collection": True,
    }
