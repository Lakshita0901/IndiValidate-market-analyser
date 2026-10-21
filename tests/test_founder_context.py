"""
tests/test_founder_context.py
-----------------------------
Unit tests for the FounderContext schema (Stage A).

Verifies:
  1. Required fields (customer_category, problem_description).
  2. Optional fields default gracefully to None / NOT_DECIDED / [].
  3. validation_stage is optional (Refinement #1).
  4. Non-negative validation_sample_size constraint.
  5. Whitespace stripping and blank-to-None normalization.
  6. Extra fields are strictly forbidden (extra="forbid").
  7. model_dump() round-trip JSON compatibility.
  8. Epistemic isolation: FounderContext does not count as EvidenceRecord.
"""

import pytest
from pydantic import ValidationError

from app.schemas.founder_context import (
    FounderContext,
    GeographicScope,
    PricingModel,
    ValidationStage,
)


def test_schema_minimal_valid():
    """Only required fields provided; optional fields should take safe defaults."""
    ctx = FounderContext(
        customer_category="SME manufacturers",
        problem_description="Inventory tracking is entirely manual in notebooks",
    )

    assert ctx.customer_category == "SME manufacturers"
    assert ctx.problem_description == "Inventory tracking is entirely manual in notebooks"
    assert ctx.customer_description is None
    assert ctx.launch_geography is None
    assert ctx.geographic_scope == GeographicScope.NOT_DECIDED
    assert ctx.known_alternatives == []
    assert ctx.pricing_model == PricingModel.NOT_DECIDED
    assert ctx.expected_price is None
    assert ctx.validation_stage is None
    assert ctx.validation_notes is None
    assert ctx.validation_sample_size is None


def test_schema_missing_required_fields():
    """Omitting customer_category or problem_description must raise ValidationError."""
    with pytest.raises(ValidationError):
        FounderContext(
            problem_description="Only problem given",
        )

    with pytest.raises(ValidationError):
        FounderContext(
            customer_category="Only category given",
        )


def test_schema_blank_required_fields_rejected():
    """Empty or whitespace-only strings for required fields must raise ValidationError."""
    with pytest.raises(ValidationError):
        FounderContext(
            customer_category="   ",
            problem_description="Some problem",
        )

    with pytest.raises(ValidationError):
        FounderContext(
            customer_category="Valid category",
            problem_description="",
        )


def test_validation_stage_optional():
    """validation_stage is optional per Refinement #1."""
    ctx_none = FounderContext(
        customer_category="Urban parents",
        problem_description="Lack of reliable childcare options",
        validation_stage=None,
    )
    assert ctx_none.validation_stage is None

    ctx_stage = FounderContext(
        customer_category="Urban parents",
        problem_description="Lack of reliable childcare options",
        validation_stage=ValidationStage.IDEA_ONLY,
    )
    assert ctx_stage.validation_stage == ValidationStage.IDEA_ONLY


def test_all_fields_populated():
    """All 7 field groups populated correctly."""
    ctx = FounderContext(
        customer_category="B2B chemical plant managers",
        customer_description="EHS leads at mid-sized chemical plants in Dahej/Ankleshwar",
        launch_geography="Gujarat",
        geographic_scope=GeographicScope.REGIONAL_STATE,
        problem_description="Compliance reporting is siloed across paper logs",
        known_alternatives=["Excel sheets", "Custom in-house ERP"],
        pricing_model=PricingModel.SUBSCRIPTION,
        expected_price="INR 15,000/month",
        validation_stage=ValidationStage.INFORMAL_CONVOS,
        validation_notes="Spoke with 3 plant heads; they confirmed paper logs take 10 hrs/week",
        validation_sample_size=3,
    )

    assert ctx.customer_category == "B2B chemical plant managers"
    assert ctx.geographic_scope == GeographicScope.REGIONAL_STATE
    assert len(ctx.known_alternatives) == 2
    assert ctx.pricing_model == PricingModel.SUBSCRIPTION
    assert ctx.expected_price == "INR 15,000/month"
    assert ctx.validation_sample_size == 3


def test_sample_size_validation():
    """validation_sample_size accepts 0 or positive integer; rejects negative numbers."""
    ctx_zero = FounderContext(
        customer_category="Students",
        problem_description="Exam prep scheduling",
        validation_sample_size=0,
    )
    assert ctx_zero.validation_sample_size == 0

    with pytest.raises(ValidationError):
        FounderContext(
            customer_category="Students",
            problem_description="Exam prep scheduling",
            validation_sample_size=-1,
        )


def test_optional_text_whitespace_normalized_to_none():
    """Whitespace-only values in optional fields normalize to None."""
    ctx = FounderContext(
        customer_category="Freelancers",
        problem_description="Invoicing delays",
        customer_description="   ",
        launch_geography="  ",
        expected_price="  ",
        validation_notes="",
    )
    assert ctx.customer_description is None
    assert ctx.launch_geography is None
    assert ctx.expected_price is None
    assert ctx.validation_notes is None


def test_known_alternatives_filtering():
    """Blank strings in known_alternatives are filtered out and items stripped."""
    ctx = FounderContext(
        customer_category="Clinics",
        problem_description="Patient queues",
        known_alternatives=["  Practo ", "", "  ", "Paper register"],
    )
    assert ctx.known_alternatives == ["Practo", "Paper register"]


def test_extra_fields_forbidden():
    """extra='forbid' prevents schema pollution."""
    with pytest.raises(ValidationError):
        FounderContext(
            customer_category="Startups",
            problem_description="Hiring tech talent",
            unauthorized_field="should fail",
        )


def test_model_dump_serializable():
    """model_dump() produces a dict suitable for LangGraph MarketState."""
    ctx = FounderContext(
        customer_category="Farmers",
        problem_description="Crop disease identification",
        geographic_scope=GeographicScope.NATIONAL,
    )
    d = ctx.model_dump()
    assert isinstance(d, dict)
    assert d["customer_category"] == "Farmers"
    assert d["geographic_scope"] == "national"
    assert "problem_description" in d


def test_epistemic_isolation_not_evidence_record():
    """FounderContext cannot be validated as an EvidenceRecord (epistemic barrier)."""
    from app.schemas.evidence import EvidenceRecord

    ctx = FounderContext(
        customer_category="Retailers",
        problem_description="Inventory shrinkage",
    )
    # Attempting to validate FounderContext dict as EvidenceRecord must fail
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate(ctx.model_dump())
