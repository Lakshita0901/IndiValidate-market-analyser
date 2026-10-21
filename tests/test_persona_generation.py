"""
tests/test_persona_generation.py
--------------------------------
Unit and integration tests for evidence-grounded synthetic persona generation (Step 9).

Verifies:
1. Persona schema validation and constraints.
2. Valid generated persona output.
3. Configurable persona count.
4. Diversity across relevant attributes (age, occupation, income, behavior).
5. Provenance and assumption tracking.
6. Correct handling of missing demographic evidence.
7. No unsupported claim of population representativeness.
8. Duplicate ID and near-duplicate handling.
9. Invalid LLM output and bounded retry behavior.
10. Missing credentials and provider failure handling.
11. Partial generation success and diagnostics.
12. Reproducibility with deterministic sampling seed.
13. Strict boundary: NO purchase-intent or product evaluation scores.
14. LangGraph node integration with MarketState.
"""

import json
import pytest

from app.schemas.persona import (
    B2BAttributes,
    BehavioralHypotheses,
    CustomerType,
    Persona,
    PersonaProvenance,
)
from app.nodes.persona_generation import (
    _build_archetype_seeds,
    _extract_evidence_context,
    generate_personas,
    generate_personas_node,
)


# ------------------------------------------------------------------
# Test Fixtures & Mock Generators
# ------------------------------------------------------------------

def make_mock_persona_dict(idx: int, prefix: str = "Test", c_type: str = "b2b") -> dict:
    """Construct a single valid persona dictionary for test fixtures."""
    return {
        "persona_id": f"persona_{idx}",
        "name": f"{prefix} Persona {idx} - Senior Role",
        "customer_type": c_type,
        "segment": "Automotive Engineering SME",
        "geography": {"state": "Gujarat", "district": "Ahmedabad"},
        "age_band": f"{25 + idx * 5}-{34 + idx * 5}",
        "occupation": f"Occupation {idx}",
        "education_level": "Bachelor of Engineering",
        "income_band": f"INR {25000 + idx * 10000}/month",
        "household_context": "Family of 4",
        "household_size": 4,
        "b2b_attributes": {
            "job_role": "Managing Director",
            "organization_size": "25-50 staff",
            "purchasing_authority": "Sole decision maker",
            "procurement_constraints": ["Capex limit INR 5L"],
        } if c_type == "b2b" else None,
        "behavioral_hypotheses": {
            "price_sensitivity": 5 + (idx % 5),
            "convenience_preference": 6 + (idx % 4),
            "brand_trust_importance": 7,
            "risk_tolerance": 4,
            "digital_adoption": 6 + (idx % 4),
        },
        "goals_and_needs": [f"Streamline workshop efficiency {idx}", "Reduce machine downtime"],
        "pain_points": [f"High spare part procurement delay {idx}", "Manual stock tracking"],
        "purchasing_constraints": ["Requires local Gujarati support", "Tight cashflow cycles"],
        "usage_context": "Daily plant floor operations",
        "provenance": {
            "supporting_evidence_ids": [f"doc_cen_{idx}"],
            "observed_market_statistics": {"plfs_avg_salary": 22638},
            "inferred_attributes": {"salary_basis": "Derived from regional manufacturing sector data"},
            "explicit_assumptions": ["Assumed 15 years operating history"],
            "unknown_or_unavailable_attributes": ["Exact vendor credit rating"],
            "is_synthetic": True,
            "is_statistically_representative": False,
        },
    }


def make_mock_llm_generator(count: int, c_type: str = "b2b", prefix: str = "Mock"):
    """Returns a callable generator function that produces `count` valid personas as JSON string."""
    def _mock_invoke(prompt: str) -> str:
        items = [make_mock_persona_dict(i, prefix=prefix, c_type=c_type) for i in range(1, count + 1)]
        return json.dumps(items)
    return _mock_invoke


# ------------------------------------------------------------------
# 1. Persona Schema Validation
# ------------------------------------------------------------------

def test_persona_schema_validation():
    """Valid Persona passes validation; empty required fields raise ValueError."""
    data = make_mock_persona_dict(1)
    persona = Persona.model_validate(data)

    assert persona.persona_id == "persona_1"
    assert persona.customer_type == CustomerType.B2B
    assert persona.provenance.is_synthetic is True
    assert persona.provenance.is_statistically_representative is False

    # Invalid empty ID
    invalid_data = dict(data)
    invalid_data["persona_id"] = "   "
    with pytest.raises(ValueError, match="persona_id cannot be empty"):
        Persona.model_validate(invalid_data)

    # Invalid behavioral hypothesis range (> 10)
    invalid_bh = dict(data)
    invalid_bh["behavioral_hypotheses"] = {"price_sensitivity": 15}
    with pytest.raises(ValueError):
        Persona.model_validate(invalid_bh)


# ------------------------------------------------------------------
# 2. Valid Generated Persona Output
# ------------------------------------------------------------------

def test_generate_personas_valid_output():
    """generate_personas successfully produces structured Persona models from generator."""
    mock_llm = make_mock_llm_generator(count=5)
    personas, diag = generate_personas(
        idea="Smart ERP for fabrication workshops in Ahmedabad",
        target_segment="SME factory owners",
        location="Ahmedabad",
        district="Ahmedabad",
        count=5,
        llm=mock_llm,
    )

    assert len(personas) == 5
    assert diag["generated_count"] == 5
    assert diag["requested_count"] == 5
    assert diag["validation_failures_count"] == 0
    for p in personas:
        assert isinstance(p, Persona)
        assert p.provenance.is_synthetic is True


# ------------------------------------------------------------------
# 3. Configurable Persona Count
# ------------------------------------------------------------------

def test_configurable_persona_count():
    """Generating 3 and 12 personas respects the requested count."""
    p_3, d_3 = generate_personas(
        idea="Eco-friendly packaging for cloud kitchens",
        count=3,
        llm=make_mock_llm_generator(count=3, c_type="consumer"),
    )
    assert len(p_3) == 3
    assert d_3["requested_count"] == 3

    p_12, d_12 = generate_personas(
        idea="Eco-friendly packaging for cloud kitchens",
        count=12,
        llm=make_mock_llm_generator(count=12, c_type="consumer"),
    )
    assert len(p_12) == 12
    assert d_12["requested_count"] == 12


# ------------------------------------------------------------------
# 4. Diversity Across Relevant Attributes
# ------------------------------------------------------------------

def test_diversity_across_relevant_attributes():
    """Generated population shows variation across occupations, age bands, and digital scores."""
    personas, diag = generate_personas(
        idea="AI billing tool for Kirana stores",
        count=8,
        llm=make_mock_llm_generator(count=8, c_type="sme"),
    )

    occupations = set(p.occupation for p in personas)
    age_bands = set(p.age_band for p in personas)
    digital_scores = [p.behavioral_hypotheses.digital_adoption for p in personas]

    assert len(occupations) > 1
    assert len(age_bands) > 1
    assert len(set(digital_scores)) > 1
    assert diag["diversity_metrics"]["unique_occupations"] > 1


# ------------------------------------------------------------------
# 5. Provenance and Assumption Tracking
# ------------------------------------------------------------------

def test_provenance_and_assumption_tracking():
    """Each persona explicitly records supporting evidence IDs and assumptions."""
    personas, _ = generate_personas(
        idea="Industrial pump monitoring",
        count=2,
        llm=make_mock_llm_generator(count=2),
    )

    for p in personas:
        assert len(p.provenance.supporting_evidence_ids) > 0
        assert len(p.provenance.explicit_assumptions) > 0
        assert isinstance(p.provenance.unknown_or_unavailable_attributes, list)


# ------------------------------------------------------------------
# 6. Correct Handling of Missing Demographic Evidence
# ------------------------------------------------------------------

def test_missing_demographic_evidence_graceful_handling():
    """When research evidence is completely omitted, persona generation proceeds without failure."""
    personas, diag = generate_personas(
        idea="Freelance developer tax planner",
        count=3,
        research_evidence=None,  # No evidence available
        retrieved_chunks=None,
        llm=make_mock_llm_generator(count=3, c_type="consumer"),
    )

    assert len(personas) == 3
    assert diag["generated_count"] == 3
    # Check that fallback context did not crash
    assert diag["validation_failures_count"] == 0


# ------------------------------------------------------------------
# 7. No Unsupported Claim of Population Representativeness
# ------------------------------------------------------------------

def test_no_unsupported_claim_of_population_representativeness():
    """is_statistically_representative must be False on every generated persona."""
    personas, _ = generate_personas(
        idea="Local tutor marketplace",
        count=4,
        llm=make_mock_llm_generator(count=4, c_type="consumer"),
    )

    for p in personas:
        assert p.provenance.is_statistically_representative is False
        assert p.provenance.is_synthetic is True


# ------------------------------------------------------------------
# 8. Duplicate ID and Near-Duplicate Handling
# ------------------------------------------------------------------

def test_duplicate_id_and_near_duplicate_handling():
    """Duplicate persona IDs are disambiguated, and near-identical profiles are removed."""
    def _duplicate_generator(prompt: str) -> str:
        # Create 2 distinct + 2 exact duplicates with shared ID
        p1 = make_mock_persona_dict(1)
        p1["persona_id"] = "shared_id"

        p1_dupe = make_mock_persona_dict(1)  # Exact same fingerprint
        p1_dupe["persona_id"] = "shared_id"

        p2 = make_mock_persona_dict(2)
        p2["persona_id"] = "shared_id"  # Duplicate ID but different content

        return json.dumps([p1, p1_dupe, p2])

    personas, diag = generate_personas(
        idea="CNC machine analytics",
        count=3,
        llm=_duplicate_generator,
    )

    # One duplicate removed
    assert diag["duplicates_removed_count"] == 1
    # Remaining personas must have strictly unique IDs
    ids = [p.persona_id for p in personas]
    assert len(ids) == len(set(ids))


# ------------------------------------------------------------------
# 9. Invalid LLM Output and Bounded Retry Behavior
# ------------------------------------------------------------------

def test_invalid_llm_output_and_bounded_retry():
    """Generator retries on malformed JSON and recovers if subsequent attempt succeeds."""
    attempts = [0]

    def _flaky_generator(prompt: str) -> str:
        attempts[0] += 1
        if attempts[0] == 1:
            return "NOT VALID JSON: Sorry, I am an AI..."
        else:
            return json.dumps([make_mock_persona_dict(1), make_mock_persona_dict(2)])

    personas, diag = generate_personas(
        idea="Dairy supply chain app",
        count=2,
        llm=_flaky_generator,
        max_retries=2,
    )

    assert len(personas) == 2
    assert attempts[0] == 2
    assert any("JSON parsing error" in iss for iss in diag["issues"])


# ------------------------------------------------------------------
# 10. Missing Credentials & Provider Failure Handling
# ------------------------------------------------------------------

def test_missing_credentials_handling(monkeypatch):
    """When no LLM is provided and API keys are missing, generation reports issue without crash."""
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    personas, diag = generate_personas(
        idea="Online pottery workshops",
        count=5,
        llm=None,
    )

    assert len(personas) == 0
    assert diag["generated_count"] == 0
    assert any("Mistral API key not found" in iss for iss in diag["issues"])


# ------------------------------------------------------------------
# 11. Partial Generation Success and Diagnostics
# ------------------------------------------------------------------

def test_partial_generation_success_reporting():
    """When one persona in a batch fails validation, valid personas are preserved."""
    def _partial_generator(prompt: str) -> str:
        valid_p = make_mock_persona_dict(1)
        invalid_p = {
            "persona_id": "bad_p",
            "name": "Invalid persona missing required fields",
            # missing segment, behavioral hypotheses, etc.
        }
        return json.dumps([valid_p, invalid_p])

    personas, diag = generate_personas(
        idea="Textile export compliance",
        count=2,
        llm=_partial_generator,
    )

    assert len(personas) == 1
    assert personas[0].persona_id == "persona_1"
    assert diag["generated_count"] == 1
    assert diag["validation_failures_count"] >= 1


# ------------------------------------------------------------------
# 12. Reproducibility with Deterministic Sampling Seed
# ------------------------------------------------------------------

def test_reproducibility_with_seed():
    """Identical seed produces identical archetype seed distribution."""
    seeds_a = _build_archetype_seeds(count=5, customer_type=CustomerType.B2B, target_segment="SME", seed=42)
    seeds_b = _build_archetype_seeds(count=5, customer_type=CustomerType.B2B, target_segment="SME", seed=42)

    assert seeds_a == seeds_b


# ------------------------------------------------------------------
# 13. Strict Boundary: NO Purchase-Intent or Evaluation Scores
# ------------------------------------------------------------------

def test_strict_boundary_no_evaluation_scores():
    """Persona schema strictly forbids evaluation, purchase-intent, and fit scores."""
    data = make_mock_persona_dict(1)

    # Injecting forbidden fields must be rejected by extra="forbid"
    for forbidden in ["purchase_intent", "interest_score", "product_fit_score", "recommendation"]:
        bad_data = dict(data)
        bad_data[forbidden] = 8.5
        with pytest.raises(ValueError):
            Persona.model_validate(bad_data)


# ------------------------------------------------------------------
# 14. LangGraph Node Integration with MarketState
# ------------------------------------------------------------------

def test_generate_personas_node_integration():
    """generate_personas_node processes state and returns personas and diagnostics."""
    state = {
        "idea": "B2B chemical compliance tool in Gujarat",
        "target_segment": "Chemical plant managers",
        "location": "Gujarat",
        "district": "Vadodara",
        "persona_count": 3,
        "persona_llm": make_mock_llm_generator(count=3, c_type="b2b"),
        "generate_personas": True,
    }

    node_output = generate_personas_node(state)

    assert "personas" in node_output
    assert "persona_generation_diagnostics" in node_output
    assert len(node_output["personas"]) == 3
    assert node_output["persona_generation_diagnostics"]["generated_count"] == 3
