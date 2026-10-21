"""
app.llm
-------
Centralized Mistral LLM provider and factory for IndiValidate.
Handles:
  1. Configuration: Reads MISTRAL_API_KEY and MISTRAL_MODEL from environment.
  2. Factory: Instantiates configured ChatMistralAI models with bounded timeouts and retries.
  3. Diagnostic & Error Isolation: Classifies Mistral exceptions (401, 402, 403, 404, 429, timeout)
     without leaking secrets or credentials.
  4. Non-retryable error detection: Prevents infinite loops on quota, authentication, or account credit failures.

Note: Embeddings remain independent (see app.rag.embeddings).
"""

import logging
import os
import re
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

from langchain_mistralai import ChatMistralAI

logger = logging.getLogger(__name__)

DEFAULT_MISTRAL_MODEL = "open-mistral-nemo"


class MistralRateLimitException(Exception):
    """
    Exception raised when a Mistral API rate limit (HTTP 429 / code 1300) is reached.
    Preserves safe diagnostics, retry-after metadata, and partial evaluation artifacts.
    """

    def __init__(
        self,
        message: str = "Mistral API rate limit reached. Check your organization’s API limits and usage, then retry after the indicated wait.",
        retry_after: Optional[float] = None,
        status_code: int = 429,
        error_code: Optional[Any] = 1300,
        partial_evaluations: Optional[Any] = None,
        diagnostics: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after
        self.status_code = status_code
        self.error_code = error_code
        self.partial_evaluations = partial_evaluations or []
        self.diagnostics = diagnostics or {}


def get_mistral_model_name() -> str:
    """Retrieve the configured Mistral model name from environment or fallback to default."""
    try:
        load_dotenv(override=True)
    except Exception:
        pass
    model = os.getenv("MISTRAL_MODEL", DEFAULT_MISTRAL_MODEL)
    clean = model.strip() if model else ""
    return clean or DEFAULT_MISTRAL_MODEL


def get_mistral_api_key() -> Optional[str]:
    """Retrieve the Mistral API key from environment without logging or exposing it."""
    try:
        load_dotenv(override=True)
    except Exception:
        pass
    key = os.getenv("MISTRAL_API_KEY")
    if key and key.strip():
        return key.strip()
    return None


def has_mistral_api_key() -> bool:
    """Return True if MISTRAL_API_KEY is present and non-empty in the environment."""
    return get_mistral_api_key() is not None


def get_llm(
    model: Optional[str] = None,
    temperature: float = 0.0,
    timeout: float = 45.0,
    max_retries: int = 1,
    api_key: Optional[str] = None,
    **kwargs: Any,
) -> ChatMistralAI:
    """
    Factory creating a configured ChatMistralAI client.

    Parameters:
      model: Optional model ID (defaults to MISTRAL_MODEL or 'mistral-small-latest')
      temperature: Sampling temperature (0.0 for deterministic, 0.7 for creative generation)
      timeout: Request timeout in seconds (default 45.0s to prevent hanging requests)
      max_retries: Maximum SDK-level transient retries (default 1)
      api_key: Optional explicit API key override (defaults to MISTRAL_API_KEY env var)
      **kwargs: Additional options forwarded to ChatMistralAI
    """
    resolved_key = (api_key or get_mistral_api_key() or "").strip()
    resolved_model = (model or get_mistral_model_name()).strip()

    init_kwargs: Dict[str, Any] = {
        "model": resolved_model,
        "temperature": temperature,
        "timeout": timeout,
        "max_retries": max_retries,
        **kwargs,
    }
    if resolved_key:
        init_kwargs["mistral_api_key"] = resolved_key

    return ChatMistralAI(**init_kwargs)


def get_gemini_api_key() -> Optional[str]:
    """Retrieve Gemini/Google API key from environment without logging or exposing it."""
    try:
        load_dotenv(override=True)
    except Exception:
        pass
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key and key.strip():
        return key.strip()
    return None


def has_gemini_api_key() -> bool:
    """Return True if GEMINI_API_KEY or GOOGLE_API_KEY is configured."""
    return get_gemini_api_key() is not None


def get_gemini_llm(
    model: Optional[str] = None,
    temperature: float = 0.2,
    timeout: float = 45.0,
    max_retries: int = 1,
    api_key: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """
    Factory creating a configured ChatGoogleGenerativeAI client.

    ARCHITECTURAL CONSTRAINT:
    Used ONLY for generating startup/customer context, pain-point hypotheses,
    assumptions, and persona-generation guidance when empirical research evidence
    is absent or insufficient.
    MUST NEVER be used as a fallback for Mistral persona generation or evaluation.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    resolved_key = (api_key or get_gemini_api_key() or "").strip()
    if not resolved_key:
        raise ValueError("Google API key not found in environment (GEMINI_API_KEY or GOOGLE_API_KEY).")

    resolved_model = (model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")).strip()
    return ChatGoogleGenerativeAI(
        model=resolved_model,
        google_api_key=resolved_key,
        temperature=temperature,
        timeout=timeout,
        max_retries=max_retries,
        **kwargs,
    )


def classify_mistral_error(exc: Exception) -> Dict[str, Any]:
    """
    Inspect an exception raised during LLM interaction and return a structured,
    sanitized diagnostic dictionary without leaking secrets, tokens, or headers.

    Detects Mistral HTTP 429 errors (including error code 1300 / 'Rate limit exceeded')
    and extracts safe retry-after details when available.
    """
    err_str = str(exc)
    err_type = type(exc).__name__

    # Sanitize any potential accidental token or key in error string
    sanitized = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]{8,}", r"\1[REDACTED]", err_str)
    sanitized = re.sub(r"(api[_-]?key['\":\s=]+)[A-Za-z0-9_\-\.]{8,}", r"\1[REDACTED]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"(mistral_api_key['\":\s=]+)[A-Za-z0-9_\-\.]{8,}", r"\1[REDACTED]", sanitized, flags=re.IGNORECASE)

    classification = "unknown_error"
    is_terminal = False
    status_code: Optional[int] = None
    error_code: Optional[Any] = None
    retry_after: Optional[float] = None
    user_message = "An unexpected error occurred during LLM text generation."

    lower_err = err_str.lower()

    # Extract status_code from exception or response attributes if present
    if hasattr(exc, "status_code") and isinstance(exc.status_code, int):
        status_code = exc.status_code
    elif hasattr(exc, "http_status") and isinstance(exc.http_status, int):
        status_code = exc.http_status
    elif hasattr(exc, "response") and hasattr(exc.response, "status_code"):
        try:
            status_code = int(exc.response.status_code)
        except (ValueError, TypeError):
            pass

    # Extract retry-after from response headers or exception attributes if present
    headers: Dict[str, Any] = {}
    if hasattr(exc, "response") and hasattr(exc.response, "headers") and exc.response.headers:
        try:
            headers = dict(exc.response.headers)
        except Exception:
            pass
    elif hasattr(exc, "headers") and exc.headers:
        try:
            headers = dict(exc.headers)
        except Exception:
            pass

    for header_name in ("retry-after", "Retry-After", "retry-after-ms", "Retry-After-Ms"):
        for h_k, h_v in headers.items():
            if h_k.lower() == header_name.lower() and h_v is not None:
                try:
                    val = float(str(h_v).strip())
                    if "ms" in header_name.lower():
                        val = val / 1000.0
                    if val >= 0:
                        retry_after = val
                        break
                except (ValueError, TypeError):
                    pass
        if retry_after is not None:
            break

    # If retry-after not in headers, inspect error string via regex
    if retry_after is None:
        patterns = [
            r"retry[_-]?after[=:\s]+(\d+(?:\.\d+)?)",
            r"try again in\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?",
            r"wait\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?",
            r"resets in\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?",
            r"in\s+(\d+(?:\.\d+)?)\s*seconds",
        ]
        for pat in patterns:
            match = re.search(pat, err_str, flags=re.IGNORECASE)
            if match:
                try:
                    val = float(match.group(1))
                    if 0 < val <= 300:
                        retry_after = val
                        break
                except (ValueError, TypeError):
                    pass

    # Detect error code (e.g. Mistral rate limit code 1300)
    if "1300" in err_str:
        error_code = 1300
    elif hasattr(exc, "code"):
        error_code = getattr(exc, "code")

    # Classification logic
    is_429 = (
        status_code == 429
        or "429" in err_str
        or error_code == 1300
        or "rate limit" in lower_err
        or "rate_limit" in lower_err
        or "ratelimit" in lower_err
        or "too many requests" in lower_err
    )

    if "401" in err_str or status_code == 401 or "unauthorized" in lower_err or "invalid api key" in lower_err:
        classification = "invalid_credentials"
        is_terminal = True
        status_code = 401
        user_message = "Mistral API authentication failed: The provided MISTRAL_API_KEY is invalid or expired."
    elif "402" in err_str or status_code == 402 or "payment" in lower_err or "insufficient" in lower_err or "credit" in lower_err:
        classification = "insufficient_credits"
        is_terminal = True
        status_code = 402
        user_message = "Mistral account has insufficient credits or requires payment activation."
    elif "403" in err_str or status_code == 403 or "forbidden" in lower_err or "permission" in lower_err:
        classification = "forbidden"
        is_terminal = True
        status_code = 403
        user_message = "Mistral API access forbidden: Check account permissions or organization restrictions."
    elif "404" in err_str or status_code == 404 or "model_not_found" in lower_err or "not found" in lower_err:
        classification = "model_not_found"
        is_terminal = True
        status_code = 404
        user_message = f"Configured Mistral model '{get_mistral_model_name()}' was not found. Please verify MISTRAL_MODEL."
    elif is_429:
        classification = "rate_limit"
        is_terminal = False
        status_code = 429
        if error_code is None and "1300" in err_str:
            error_code = 1300
        user_message = (
            "Mistral API rate limit reached. "
            "Check your organization’s API limits and usage, then retry after the indicated wait."
        )
    elif "timeout" in lower_err or "timed out" in lower_err or status_code == 408:
        classification = "timeout"
        is_terminal = False
        user_message = "Mistral API request timed out."
    elif not has_mistral_api_key():
        classification = "missing_api_key"
        is_terminal = True
        user_message = (
            "Mistral API key not found in environment (MISTRAL_API_KEY). "
            "Please configure MISTRAL_API_KEY in your .env file."
        )

    diag: Dict[str, Any] = {
        "error_type": err_type,
        "classification": classification,
        "is_terminal": is_terminal,
        "status_code": status_code,
        "error_code": error_code,
        "retry_after": retry_after,
        "user_message": user_message,
        "raw_message": sanitized[:300],
    }
    return diag


def calculate_backoff(
    attempt: int,
    retry_after: Optional[float] = None,
    base_delay: float = 2.0,
    max_backoff: float = 30.0,
    jitter_range: Tuple[float, float] = (0.5, 1.5),
) -> float:
    """
    Calculate bounded exponential backoff with jitter.
    Respects the server's retry-after value when available, bounded by max_backoff.
    Never retries indefinitely.
    """
    import random

    if retry_after is not None and retry_after > 0:
        # Respect server retry-after, bounded with slight positive jitter
        wait = float(retry_after) + random.uniform(0.1, 0.4)
        return min(max_backoff, max(1.0, wait))

    # Bounded exponential backoff: base_delay * (2 ** (attempt - 1)) + jitter
    exp_delay = base_delay * (2 ** max(0, attempt - 1))
    jitter = random.uniform(jitter_range[0], jitter_range[1])
    return min(max_backoff, exp_delay + jitter)


def is_rate_limit_error(exc: Exception) -> bool:
    """Return True if an exception represents a rate limit / 429 / code 1300 error."""
    return classify_mistral_error(exc)["classification"] == "rate_limit"


def is_terminal_error(exc: Exception) -> bool:
    """Return True if an error is non-transient and should NOT be retried."""
    return classify_mistral_error(exc)["is_terminal"]
