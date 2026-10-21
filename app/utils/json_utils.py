"""
app.utils.json_utils
--------------------
Robust JSON parsing, repair, and sanitized diagnostic utilities for LLM outputs.
Handles unescaped control characters, raw newlines within strings, markdown fences,
trailing commas, and captures sanitized diagnostics without leaking credentials.
"""

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def sanitize_sensitive_text(text: str) -> str:
    """Redact API keys, authorization headers, and bearer tokens from text/messages."""
    if not text:
        return ""
    clean = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]{8,}", r"\1[REDACTED]", text)
    clean = re.sub(
        r"(api[_-]?key['\":\s=]+)[A-Za-z0-9_\-\.]{8,}",
        r"\1[REDACTED]",
        clean,
        flags=re.IGNORECASE,
    )
    clean = re.sub(r"(https?://api\.mistral\.ai[^\s\"']*)", "[MISTRAL_API_ENDPOINT]", clean)
    return clean


def extract_json_candidate(raw_text: str) -> str:
    """
    Extract the most likely JSON payload from raw LLM output.
    Supports markdown code fences, embedded JSON objects/arrays, and removes surrounding text.
    """
    if not raw_text:
        return ""
    text = raw_text.strip()

    # 1. Check for markdown code fences anywhere in the response
    fence_pattern = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
    fences = fence_pattern.findall(text)
    if fences:
        # Choose the longest fenced block as the candidate
        candidate = max(fences, key=len).strip()
        if candidate.startswith(("{", "[")):
            return candidate

    # 2. Search for outermost JSON object or array bounds
    first_brace = text.find("{")
    first_bracket = text.find("[")

    start_idx = -1
    end_idx = -1

    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        start_idx = first_brace
        end_idx = text.rfind("}")
    elif first_bracket != -1:
        start_idx = first_bracket
        end_idx = text.rfind("]")

    if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
        return text[start_idx : end_idx + 1].strip()

    # Fallback to stripped text
    return text


def repair_json_string(json_str: str) -> str:
    """
    Repair common LLM JSON syntax issues:
    - Unescaped newlines/carriage returns/tabs inside double-quoted string literals.
    - Trailing commas before closing brackets or braces.
    - Single quotes used as key/string delimiters.
    """
    if not json_str:
        return ""

    # Phase 1: Escape raw newlines, carriage returns, and tabs inside double-quoted strings
    chars = []
    in_string = False
    escaped = False

    for ch in json_str:
        if escaped:
            chars.append(ch)
            escaped = False
            continue

        if ch == "\\":
            chars.append(ch)
            escaped = True
            continue

        if ch == '"':
            in_string = not in_string
            chars.append(ch)
            continue

        if in_string:
            if ch == "\n":
                chars.append("\\n")
            elif ch == "\r":
                chars.append("\\r")
            elif ch == "\t":
                chars.append("\\t")
            elif ord(ch) < 32:
                # Other control characters
                chars.append(f"\\u{ord(ch):04x}")
            else:
                chars.append(ch)
        else:
            chars.append(ch)

    repaired = "".join(chars)

    # Phase 2: Remove trailing commas before } or ]
    repaired = re.sub(r",\s*([\]\}])", r"\1", repaired)

    return repaired


def parse_json_robust(raw_text: str) -> Any:
    """
    Parse a JSON string from LLM output with multi-stage recovery:
    1. Direct json.loads with strict=False.
    2. Candidate boundary extraction (removing markdown fences / chit-chat).
    3. Structural repair for unescaped control chars and trailing commas.
    4. Single-to-double quote repair if needed.
    """
    if not raw_text or not raw_text.strip():
        raise json.JSONDecodeError("Empty or blank text provided for JSON parsing", "", 0)

    # Stage 1: Try direct loads with strict=False
    try:
        return json.loads(raw_text.strip(), strict=False)
    except Exception:
        pass

    # Stage 2: Extract candidate from code fences or bracket bounds
    candidate = extract_json_candidate(raw_text)
    try:
        return json.loads(candidate, strict=False)
    except Exception:
        pass

    # Stage 3: Repair control characters, raw newlines in strings, trailing commas
    repaired = repair_json_string(candidate)
    try:
        return json.loads(repaired, strict=False)
    except Exception:
        pass

    # Stage 4: If single quotes were used for JSON keys/strings
    if "'" in repaired and '"' not in repaired:
        single_quote_fixed = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", r'"\1"', repaired)
        try:
            return json.loads(single_quote_fixed, strict=False)
        except Exception:
            pass

    # Final attempt on candidate directly to raise a clean, informative error
    return json.loads(candidate, strict=False)


def capture_failed_response_diagnostics(
    provider: str,
    model: str,
    raw_response: Any,
    exc: Optional[Exception] = None,
) -> Dict[str, Any]:
    """
    Capture structured, sanitized diagnostic information about an LLM failure.
    Ensures zero secret leakage.
    """
    raw_str = ""
    finish_reason = "unknown"

    if hasattr(raw_response, "content"):
        raw_str = str(raw_response.content)
        # Check response metadata
        resp_meta = getattr(raw_response, "response_metadata", {}) or {}
        finish_reason = resp_meta.get("finish_reason") or resp_meta.get("finishReason") or "unknown"
    elif isinstance(raw_response, str):
        raw_str = raw_response
    else:
        raw_str = str(raw_response) if raw_response is not None else ""

    clean_preview = sanitize_sensitive_text(raw_str.strip())[:250]
    error_msg = sanitize_sensitive_text(str(exc)) if exc else None

    return {
        "provider": provider,
        "model": model,
        "finish_reason": finish_reason,
        "response_type": type(raw_response).__name__,
        "raw_response_length": len(raw_str),
        "raw_preview": clean_preview,
        "error": error_msg,
    }
