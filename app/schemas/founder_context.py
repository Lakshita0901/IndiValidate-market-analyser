"""
app.schemas.founder_context
----------------------------
Typed Pydantic schema for founder-reported intake context.

EPISTEMIC STATUS — design invariants enforced by tests:
  - All fields represent FOUNDER CLAIMS: unverified, self-reported information.
  - This schema MUST NEVER be added to normalized_evidence, cleaned_evidence,
    or any list that feeds the external evidence coverage ratio calculation.
  - validation_notes MUST NOT be passed to generate_personas or
    evaluate_personas prompts (anchoring bias risk).
  - launch_geography takes precedence over LLM-inferred location when both are
    present; any conflict is recorded in diagnostics, not silently overwritten.
  - expected_price is for affordability hypothesis framing only and must be
    labelled [FOUNDER-REPORTED, UNVERIFIED] in all report output.
  - The external evidence coverage ratio formula is unchanged by this schema.

Allowed uses of FounderContext:
  - Keyword generation prompts (labelled as founder-reported hints)
  - Geographic scope hints for source selection (as precedence input)
  - Archetype calibration hints for synthetic persona generation
  - Framing context in the final report (with explicit attribution)
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GeographicScope(str, Enum):
    """Intended breadth of geographic reach."""

    LOCAL_CITY = "local_city"
    REGIONAL_STATE = "regional_state"
    NATIONAL = "national"
    MULTI_NATIONAL = "multi_national"
    NOT_DECIDED = "not_decided"


class PricingModel(str, Enum):
    """Intended monetisation model."""

    FREE = "free"
    FREEMIUM = "freemium"
    ONE_TIME = "one_time_purchase"
    SUBSCRIPTION = "subscription"
    USAGE_BASED = "usage_based"
    MARKETPLACE = "marketplace_commission"
    NOT_DECIDED = "not_decided"


class ValidationStage(str, Enum):
    """How far the founder has progressed in real-world validation."""

    IDEA_ONLY = "idea_only"
    INFORMAL_CONVOS = "informal_conversations"
    INTERVIEWS_SURVEYS = "interviews_or_surveys"
    PROTOTYPE_PILOT = "prototype_or_pilot"
    PAYING_CUSTOMERS = "paying_customers"


class FounderContext(BaseModel):
    """
    Founder-reported market context captured before the pipeline runs.

    All seven field groups below are founder claims, not external evidence.
    See module docstring for full epistemic boundary rules.
    """

    model_config = ConfigDict(extra="forbid")

    # ── 1. Customer ──────────────────────────────────────────────────────────
    customer_category: str = Field(
        description=(
            "Broad category of target customer "
            "(e.g. 'urban working professionals', 'SME factory owners')."
        )
    )
    customer_description: Optional[str] = Field(
        default=None,
        description=(
            "More specific description of the target customer "
            "(e.g. 'mid-career salaried employees aged 28-45 in Tier-1 cities'). "
            "None if the founder has not yet narrowed this down."
        ),
    )

    # ── 2. Geography ─────────────────────────────────────────────────────────
    launch_geography: Optional[str] = Field(
        default=None,
        description=(
            "Where the founder intends to launch first "
            "(e.g. 'Pune', 'Maharashtra', 'Pan-India'). "
            "None if not yet decided. "
            "When supplied, takes precedence over LLM-inferred location; "
            "any conflict is recorded in diagnostics rather than silently resolved."
        ),
    )
    geographic_scope: GeographicScope = Field(
        default=GeographicScope.NOT_DECIDED,
        description="Intended breadth of geographic reach.",
    )

    # ── 3. Problem ───────────────────────────────────────────────────────────
    problem_description: str = Field(
        description=(
            "The customer problem the founder is solving, in their own words. "
            "Used as a keyword hint — labelled as founder-reported in prompts."
        )
    )

    # ── 4. Existing Alternatives ─────────────────────────────────────────────
    known_alternatives: List[str] = Field(
        default_factory=list,
        description=(
            "Existing solutions, competitors, or workarounds the founder is aware of. "
            "Empty list means the founder has not identified any yet."
        ),
    )

    # ── 5. Pricing ───────────────────────────────────────────────────────────
    pricing_model: PricingModel = Field(
        default=PricingModel.NOT_DECIDED,
        description="The intended pricing / monetisation model.",
    )
    expected_price: Optional[str] = Field(
        default=None,
        description=(
            "Optional rough price point in mind (e.g. 'INR 299/month', '5% commission'). "
            "Used only for affordability hypothesis framing — "
            "NOT a verified price point. Must be labelled [FOUNDER-REPORTED, UNVERIFIED] "
            "in all report output."
        ),
    )

    # ── 6. Validation Stage (Optional — Refinement #1) ───────────────────────
    validation_stage: Optional[ValidationStage] = Field(
        default=None,
        description=(
            "How far the founder has progressed in validating this idea. "
            "None if the founder is unsure or has not yet conducted any validation."
        ),
    )

    # ── 7. Validation Evidence ───────────────────────────────────────────────
    validation_notes: Optional[str] = Field(
        default=None,
        description=(
            "What the founder has learned so far from conversations, interviews, or pilots. "
            "Stored as raw founder text. "
            "MUST NOT be passed to generate_personas or evaluate_personas prompts. "
            "Included in the final report only with explicit founder-reported attribution."
        ),
    )
    validation_sample_size: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "How many people the founder has spoken with or surveyed, if known. "
            "None means unknown. 0 means no conversations have been conducted yet."
        ),
    )

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("customer_category", "problem_description", mode="before")
    @classmethod
    def required_text_not_blank(cls, v: object) -> str:
        """Required text fields must be non-empty, non-whitespace strings."""
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Field cannot be blank or whitespace-only.")
        return v.strip()

    @field_validator(
        "customer_description",
        "launch_geography",
        "validation_notes",
        "expected_price",
        mode="before",
    )
    @classmethod
    def optional_text_empty_to_none(cls, v: object) -> Optional[str]:
        """Normalize empty strings to None for optional text fields."""
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            return stripped if stripped else None
        return v  # type: ignore[return-value]

    @field_validator("known_alternatives", mode="before")
    @classmethod
    def filter_blank_alternatives(cls, v: object) -> List[str]:
        """Strip whitespace and remove blank entries from the alternatives list."""
        if v is None:
            return []
        if isinstance(v, list):
            return [item.strip() for item in v if isinstance(item, str) and item.strip()]
        return []
