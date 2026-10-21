"""
scripts/smoke_test_mistral.py
-----------------------------
Explicit provider smoke-test script for Mistral AI integration.
Sends one short request to the configured Mistral model to verify active API
access and available account credits without exposing secrets or launching a full analysis.

Usage:
    py scripts/smoke_test_mistral.py
"""

import os
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

# Ensure .env is loaded
load_dotenv(PROJECT_ROOT / ".env")

from app.llm import (
    classify_mistral_error,
    get_llm,
    get_mistral_api_key,
    get_mistral_model_name,
    has_mistral_api_key,
)


def run_smoke_test() -> int:
    print("=" * 60)
    print("  IndiValidate: Mistral LLM Provider Smoke Test")
    print("=" * 60)

    # 1. Credential Check
    if not has_mistral_api_key():
        print("\n[FAIL] MISTRAL_API_KEY is not set in environment or .env file.")
        print("       Please add your key to .env:")
        print("       MISTRAL_API_KEY=your_actual_mistral_api_key")
        print("=" * 60)
        return 1

    key = get_mistral_api_key() or ""
    masked_key = f"...{key[-4:]}" if len(key) >= 4 else "[TOO SHORT]"
    model_name = get_mistral_model_name()

    print(f"\n[INFO] Configuration:")
    print(f"       Model:     {model_name}")
    print(f"       API Key:   Configured (ending in {masked_key}, length: {len(key)})")

    # 2. Instantiate Client
    try:
        llm = get_llm(temperature=0.0, timeout=20.0, max_retries=1)
    except Exception as exc:
        print(f"\n[FAIL] Client initialization failed: {exc}")
        return 1

    # 3. Send Single Short Ping
    prompt = "Ping! Reply with exactly the single word: OK"
    print(f"\n[INFO] Sending smoke-test probe to Mistral API...")
    t0 = time.time()

    try:
        response = llm.invoke(prompt)
        elapsed = time.time() - t0

        content = response.content if hasattr(response, "content") else str(response)
        if isinstance(content, list):
            content = " ".join(item if isinstance(item, str) else str(item) for item in content)

        clean_resp = str(content).strip()
        print(f"[PASS] Response received in {elapsed:.2f}s:")
        print(f"       >> \"{clean_resp}\"")
        print("\n[SUCCESS] Mistral API integration is active, authenticated, and ready!")
        print("=" * 60)
        return 0

    except Exception as exc:
        elapsed = time.time() - t0
        err_info = classify_mistral_error(exc)
        print(f"\n[FAIL] Probe failed after {elapsed:.2f}s:")
        print(f"       Category:     {err_info['classification']}")
        print(f"       Diagnostic:   {err_info['user_message']}")
        print(f"       Raw Error:    {err_info['raw_message']}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(run_smoke_test())
