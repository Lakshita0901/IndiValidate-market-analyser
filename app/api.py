"""
app.api
-------
Lightweight FastAPI application exposing HTTP endpoints for IndiValidate.
Designed for performance benchmarking (e.g. JMeter) and programmatic consumption.

Endpoints:
  GET  /health       - Lightweight health check (zero external calls, instant 200)
  POST /api/analyze  - Executes the LangGraph market analysis pipeline for an idea
"""

import hashlib
import json
import logging
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# Ensure environment variables (.env) are loaded before any submodules
load_dotenv(override=True)

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.llm import MistralRateLimitException, classify_mistral_error
from app.schemas.founder_context import FounderContext

logger = logging.getLogger(__name__)

app = FastAPI(
    title="IndiValidate Market Analyzer API",
    description="HTTP API for AI-powered multi-persona market validation",
    version="1.0.0",
)

# Enable CORS for local testing, browser clients, and performance testing tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    service: str


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idea: str = Field(
        ...,
        description="The business idea to validate. Must be a non-empty string.",
        examples=["Smart electric shuttle service connecting metro stations to IT parks in Pune"],
    )
    founder_context: Optional[FounderContext] = Field(
        default=None,
        description="Optional founder-reported intake context (customer category, problem, geography, etc.)",
    )
    persona_count: Optional[int] = Field(
        default=None,
        ge=1,
        le=25,
        description="Optional custom number of personas to generate and evaluate (default 10)",
    )
    evaluation_concurrency: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        description="Optional bounded worker concurrency for persona evaluation (default 3)",
    )

    @field_validator("idea")
    @classmethod
    def validate_idea(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("idea must be a non-empty string")
        return v.strip()


# Cached compiled graph instance for reuse across requests
_graph_instance = None

# Intermediate pipeline state cache to safely resume stages after rate-limit or transient failures
_intermediate_state_cache: Dict[str, Dict[str, Any]] = {}


def get_graph():
    """Retrieve or compile the LangGraph analysis graph (lazy import)."""
    global _graph_instance
    if _graph_instance is None:
        from app.graph import build_graph
        _graph_instance = build_graph()
    return _graph_instance


def _compute_cache_key(idea: str, founder_context: Optional[FounderContext], persona_count: Optional[int]) -> str:
    """Generate a deterministic fingerprint for intermediate stage reuse."""
    clean_idea = " ".join(idea.strip().lower().split())
    fc_dict = founder_context.model_dump() if founder_context else {}
    fc_json = json.dumps(fc_dict, sort_keys=True)
    p_count = persona_count or 10
    raw = f"{clean_idea}|{fc_json}|{p_count}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check endpoint for JMeter / load testing",
    tags=["Health"],
)
def health_check() -> HealthResponse:
    """
    Lightweight health check endpoint.
    Guaranteed to execute in <1ms without calling any LLMs, scrapers, or RAG components.
    """
    return HealthResponse(status="ok", service="IndiValidate")


@app.post(
    "/api/analyze",
    summary="Analyze a business idea using the multi-persona market validation pipeline",
    tags=["Analysis"],
)
def analyze_idea_endpoint(request: AnalyzeRequest) -> Dict[str, Any]:
    """
    Execute the market analyzer pipeline for the given business idea.
    Optionally accepts founder-reported context.
    Returns the final structured MarketValidationReport.
    Supports stage reuse across retries after rate-limit events.
    """
    cache_key = _compute_cache_key(request.idea, request.founder_context, request.persona_count)

    initial_state: Dict[str, Any] = {"idea": request.idea}
    if request.founder_context is not None:
        initial_state["founder_context"] = request.founder_context.model_dump()
    if request.persona_count is not None:
        initial_state["persona_count"] = request.persona_count
    if request.evaluation_concurrency is not None:
        initial_state["evaluation_concurrency"] = request.evaluation_concurrency

    # Pre-populate completed stages from intermediate cache if this idea was previously interrupted
    if cache_key in _intermediate_state_cache:
        cached_state = _intermediate_state_cache[cache_key]
        reusable_keys = [
            "category", "location", "geography_diagnostics", "keywords",
            "target_segment", "research_type", "reddit_evidence", "trends_evidence",
            "census_evidence", "plfs_evidence", "normalized_evidence", "cleaned_evidence",
            "cleaning_diagnostics", "retrieval_documents", "document_chunks",
            "chunk_embeddings", "vector_store_diagnostics", "vector_store_count",
            "chroma_collection_name", "chroma_persist_dir", "research_planning_diagnostics",
            "research_complete", "personas", "persona_generation_diagnostics",
            "persona_evaluations", "persona_evaluation_diagnostics",
        ]
        reused_stages = []
        for k in reusable_keys:
            if k in cached_state and cached_state[k] is not None:
                initial_state[k] = cached_state[k]
                reused_stages.append(k)
        if reused_stages:
            logger.info("Reusing cached intermediate pipeline stages for retry: %s", reused_stages)

    current_state = dict(initial_state)

    try:
        graph = get_graph()
        executed_via_stream = False
        if hasattr(graph, "stream"):
            try:
                stream_res = graph.stream(current_state)
                # Check if stream_res yields output dicts
                for output in stream_res:
                    if isinstance(output, dict):
                        executed_via_stream = True
                        for node_name, node_output in output.items():
                            if isinstance(node_output, dict):
                                current_state.update(node_output)
                                _intermediate_state_cache[cache_key] = current_state
            except TypeError:
                pass

        if executed_via_stream:
            result = current_state
        else:
            result = graph.invoke(current_state)
    except MistralRateLimitException as rle:
        # Preserve partial evaluations and diagnostics in the intermediate cache for safe stage reuse
        if rle.partial_evaluations:
            current_state["persona_evaluations"] = rle.partial_evaluations
        if rle.diagnostics:
            current_state["persona_evaluation_diagnostics"] = rle.diagnostics
        _intermediate_state_cache[cache_key] = current_state

        headers = {}
        if rle.retry_after is not None and rle.retry_after > 0:
            headers["Retry-After"] = str(int(rle.retry_after))

        logger.warning("Mistral rate limit hit during pipeline: %s (retry_after=%s)", rle.message, rle.retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Mistral API rate limit reached. Check your organization’s API limits and usage, then retry after the indicated wait.",
            headers=headers,
        )
    except HTTPException:
        raise
    except Exception as exc:
        _intermediate_state_cache[cache_key] = current_state
        diag = classify_mistral_error(exc)
        if diag["classification"] == "rate_limit":
            headers = {}
            if diag.get("retry_after"):
                headers["Retry-After"] = str(int(diag["retry_after"]))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Mistral API rate limit reached. Check your organization’s API limits and usage, then retry after the indicated wait.",
                headers=headers,
            )

        logger.exception("Unexpected error during pipeline execution: %s", exc)
        import re
        clean_msg = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]{8,}", r"\1[REDACTED]", str(exc))
        clean_msg = re.sub(r"(api[_-]?key['\":\s=]+)[A-Za-z0-9_\-\.]{8,}", r"\1[REDACTED]", clean_msg, flags=re.IGNORECASE)
        clean_msg = clean_msg.split("Traceback (most recent call last):")[0].strip()
        user_msg = (
            diag["user_message"]
            if diag.get("is_terminal")
            else f"Pipeline execution failed: {clean_msg}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=user_msg,
        ) from exc

    if not result or not isinstance(result, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Pipeline execution returned an invalid empty state",
        )

    # 1. Explicitly check for critical stage failures (e.g. persona generation failure)
    stage_failures = result.get("stage_failures", [])
    p_diag = result.get("persona_generation_diagnostics", {})
    mr_diag = result.get("market_report_diagnostics", {})

    if "persona_generation" in stage_failures or (isinstance(p_diag, dict) and p_diag.get("status") == "failed") or (
        not result.get("personas") and result.get("generate_personas", True)
    ):
        p_issues = p_diag.get("issues", []) if isinstance(p_diag, dict) else []
        err_msg = (
            f"Pipeline failed at stage 'persona_generation': {'; '.join(p_issues[:3])}"
            if p_issues
            else "Pipeline failed at stage 'persona_generation': zero personas were generated."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=err_msg,
        )

    if isinstance(mr_diag, dict) and mr_diag.get("status") == "failed":
        mr_issues = mr_diag.get("issues", [])
        err_msg = (
            f"Pipeline failed at stage 'market_report': {'; '.join(mr_issues[:3])}"
            if mr_issues
            else "Pipeline failed to produce a substantive market validation report."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=err_msg,
        )

    # 2. Check market_report existence
    market_report = result.get("market_report")
    if not market_report:
        pe_diag = result.get("persona_evaluation_diagnostics", {})
        if pe_diag.get("rate_limit_encountered"):
            headers = {}
            if pe_diag.get("retry_after"):
                headers["Retry-After"] = str(int(pe_diag["retry_after"]))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Mistral API rate limit reached. Check your organization’s API limits and usage, then retry after the indicated wait.",
                headers=headers,
            )

        diag = result.get("market_report_diagnostics", {})
        issues = diag.get("issues", []) if isinstance(diag, dict) else []
        err_msg = (
            f"Pipeline failed to generate market report: {'; '.join(issues)}"
            if issues
            else "Pipeline failed to produce a valid market report"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=err_msg,
        )

    # Clean intermediate cache upon full pipeline completion
    _intermediate_state_cache.pop(cache_key, None)
    return market_report
