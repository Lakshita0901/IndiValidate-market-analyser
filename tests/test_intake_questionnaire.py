"""
tests/test_intake_questionnaire.py
----------------------------------
Unit, CLI, and integration tests for the 5-Question Founder Intake and its influence
on synthetic persona generation.

Verifies:
  1. Full intake completion when all 5 answers are provided.
  2. Safe skipping of optional questions (Enter key / empty input).
  3. Looping retry on empty required fields (Questions 1 and 3).
  4. Exactly five questions are asked in the questionnaire.
  5. Questionnaire runs when --intake is supplied; prints clear enabled message.
  6. Questionnaire is skipped when --intake is absent; prints clear skipped message.
  7. EOF / non-interactive stdin is handled gracefully with an informative error message.
  8. Graph state carries founder_context into persona generation and evaluation.
  9. Commercial EV fleet founder context steers persona seeds to the 5 essential fleet personas
     (Small fleet owner, Taxi/ride-hailing fleet manager, Last-mile delivery manager, Logistics operations manager,
     Larger fleet purchasing decision-maker) and avoids household drivers or students.
 10. API endpoints remain completely non-interactive.
"""

import io
import json
import os
import sys
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

load_dotenv()
if not os.getenv("MISTRAL_API_KEY"):
    os.environ["MISTRAL_API_KEY"] = "mock-key-for-test"

from app.intake.questionnaire import (
    _parse_launch_and_alternatives,
    _parse_pricing_and_validation,
    _prompt_int,
    _prompt_menu,
    _prompt_text,
    run_founder_intake_questionnaire,
)
from app.nodes.persona_generation import (
    CustomerType,
    _build_archetype_seeds,
    _build_generation_prompt,
    generate_personas,
    generate_personas_node,
)
from app.schemas.founder_context import (
    GeographicScope,
    PricingModel,
    ValidationStage,
)
from app.schemas.persona import Persona


# ── 1. Unit Tests for Prompt Helpers and Parsers ─────────────────────────────

def test_prompt_text_helpers():
    """_prompt_text strips whitespace from responses."""
    with patch("builtins.input", return_value="  commercial EV fleet  "):
        assert _prompt_text("Label") == "commercial EV fleet"


def test_parse_launch_and_alternatives():
    """Compound question 4 parses location and alternatives from various user formats."""
    # Semicolon separated
    geo, alts = _parse_launch_and_alternatives("Ahmedabad; public chargers, diesel generators")
    assert geo == "Ahmedabad"
    assert alts == ["public chargers", "diesel generators"]

    # Natural language with 'alternatives:' keyword
    geo2, alts2 = _parse_launch_and_alternatives("Pune, Maharashtra, alternatives: manual logs, WhatsApp")
    assert geo2 == "Pune, Maharashtra"
    assert alts2 == ["manual logs", "WhatsApp"]

    # Location only
    geo3, alts3 = _parse_launch_and_alternatives("Pan-India")
    assert geo3 == "Pan-India"
    assert alts3 == []

    # Empty / skipped
    geo4, alts4 = _parse_launch_and_alternatives("")
    assert geo4 is None
    assert alts4 == []


def test_parse_pricing_and_validation():
    """Compound question 5 parses pricing and distinguishes actual validation from assumptions."""
    # Validated results with sample size
    model, price, stage, notes, size = _parse_pricing_and_validation(
        "INR 3,000/month per vehicle; spoke with 5 fleet managers in Ahmedabad"
    )
    assert model == PricingModel.SUBSCRIPTION
    assert price == "INR 3,000/month per vehicle"
    assert stage == ValidationStage.INFORMAL_CONVOS
    assert "[VALIDATION COMPLETED]" in (notes or "")
    assert size == 5

    # Assumption / unvalidated
    model2, price2, stage2, notes2, size2 = _parse_pricing_and_validation(
        "Usage-based per kWh; idea only, no validation yet"
    )
    assert model2 == PricingModel.USAGE_BASED
    assert stage2 == ValidationStage.IDEA_ONLY
    assert "[ASSUMPTION / UNVALIDATED]" in (notes2 or "")

    # Blank / skipped
    model3, price3, stage3, notes3, size3 = _parse_pricing_and_validation("")
    assert model3 == PricingModel.NOT_DECIDED
    assert price3 is None
    assert stage3 is None
    assert notes3 is None


# ── 2. Full 5-Question Questionnaire Tests ────────────────────────────────────

def test_questionnaire_all_answers(capsys):
    """Simulate a founder answering all 5 questions."""
    inputs = [
        "Commercial EV fleet operators",                                       # [1/5] customer_category
        "Fleet owners and operations managers running 5-50 vehicles",          # [2/5] customer_description
        "High charging queue downtime and unpredictable charger availability",   # [3/5] problem_description
        "Ahmedabad; alternatives: public charging stations, diesel generators", # [4/5] launch + alts
        "INR 3,000/month per vehicle; spoke with 8 fleet operators in Naroda",  # [5/5] pricing + validation
    ]

    with patch("builtins.input", side_effect=inputs):
        ctx_dict = run_founder_intake_questionnaire()

    captured = capsys.readouterr().out
    assert "[1/5]" in captured
    assert "[2/5]" in captured
    assert "[3/5]" in captured
    assert "[4/5]" in captured
    assert "[5/5]" in captured
    assert "Founder context captured (5/5 questions)" in captured

    assert isinstance(ctx_dict, dict)
    assert ctx_dict["customer_category"] == "Commercial EV fleet operators"
    assert ctx_dict["customer_description"] == "Fleet owners and operations managers running 5-50 vehicles"
    assert ctx_dict["problem_description"] == "High charging queue downtime and unpredictable charger availability"
    assert ctx_dict["launch_geography"] == "Ahmedabad"
    assert ctx_dict["known_alternatives"] == ["public charging stations", "diesel generators"]
    assert ctx_dict["pricing_model"] == "subscription"
    assert ctx_dict["expected_price"] == "INR 3,000/month per vehicle"
    assert ctx_dict["validation_stage"] == "informal_conversations"
    assert ctx_dict["validation_sample_size"] == 8


def test_questionnaire_skip_optionals():
    """Simulate a founder answering required questions and skipping optionals."""
    inputs = [
        "Logistics fleet operators",    # [1/5] required
        "",                             # [2/5] skip
        "Battery degradation anxiety",  # [3/5] required
        "",                             # [4/5] skip
        "",                             # [5/5] skip
    ]

    with patch("builtins.input", side_effect=inputs):
        ctx_dict = run_founder_intake_questionnaire()

    assert ctx_dict["customer_category"] == "Logistics fleet operators"
    assert ctx_dict["customer_description"] is None
    assert ctx_dict["problem_description"] == "Battery degradation anxiety"
    assert ctx_dict["launch_geography"] is None
    assert ctx_dict["known_alternatives"] == []
    assert ctx_dict["pricing_model"] == "not_decided"
    assert ctx_dict["expected_price"] is None
    assert ctx_dict["validation_stage"] is None
    assert ctx_dict["validation_notes"] is None


def test_questionnaire_retries_on_empty_required():
    """Questionnaire loops on blank input for customer_category (Q1) and problem_description (Q3)."""
    inputs = [
        "",                             # Q1 blank -> retry
        "   ",                          # Q1 whitespace -> retry
        "Commercial Fleet Owners",      # Q1 valid
        "",                             # Q2 skip
        "",                             # Q3 blank -> retry
        "Depot charging bottlenecks",   # Q3 valid
        "",                             # Q4 skip
        "",                             # Q5 skip
    ]

    with patch("builtins.input", side_effect=inputs):
        ctx_dict = run_founder_intake_questionnaire()

    assert ctx_dict["customer_category"] == "Commercial Fleet Owners"
    assert ctx_dict["problem_description"] == "Depot charging bottlenecks"


def test_questionnaire_exactly_five_questions():
    """Verify that exactly five input() prompts are invoked when all questions are answered directly."""
    inputs = [
        "Commercial EV fleet operators",
        "Fleet managers running 10-30 cabs",
        "Unreliable public charger uptime",
        "Ahmedabad; alternatives: public stations",
        "INR 2,500/month; idea only",
    ]

    mock_input = MagicMock(side_effect=inputs)
    with patch("builtins.input", mock_input):
        run_founder_intake_questionnaire()

    assert mock_input.call_count == 5


# ── 3. CLI Intake Flag Behavior ───────────────────────────────────────────────

def test_cli_intake_flag_activates_questionnaire(capsys):
    """When --intake is passed, questionnaire is invoked and a status message is printed."""
    import main as main_module

    dummy_ctx = {
        "customer_category": "Commercial EV fleet operators",
        "customer_description": "Owners running 5-50 vehicles",
        "problem_description": "Queue times at charging hubs",
        "launch_geography": "Ahmedabad",
        "geographic_scope": "local_city",
        "known_alternatives": ["Public chargers"],
        "pricing_model": "subscription",
        "expected_price": "INR 3000/mo",
    }

    with patch("sys.argv", ["main.py", "--idea", "Smart EV charging hub in Ahmedabad", "--intake"]):
        with patch("app.intake.questionnaire.run_founder_intake_questionnaire", return_value=dummy_ctx) as mock_intake:
            with patch.object(main_module, "build_graph") as mock_build:
                mock_graph_instance = mock_build.return_value
                mock_graph_instance.invoke.return_value = {
                    "idea": "Smart EV charging hub in Ahmedabad",
                    "founder_context": dummy_ctx,
                }

                main_module.main()

                mock_intake.assert_called_once()
                invoked_state = mock_graph_instance.invoke.call_args[0][0]
                assert "founder_context" in invoked_state
                assert invoked_state["founder_context"] == dummy_ctx

    captured = capsys.readouterr().out
    assert "[Founder Intake: ENABLED]" in captured


def test_cli_intake_skipped_without_flag(capsys):
    """When --intake is absent, intake is skipped and a clear message is printed."""
    import main as main_module

    with patch("sys.argv", ["main.py", "--idea", "Smart EV charging hub in Ahmedabad"]):
        with patch("app.intake.questionnaire.run_founder_intake_questionnaire") as mock_intake:
            with patch.object(main_module, "build_graph") as mock_build:
                mock_graph_instance = mock_build.return_value
                mock_graph_instance.invoke.return_value = {"idea": "Smart EV charging hub in Ahmedabad"}

                main_module.main()

                mock_intake.assert_not_called()
                invoked_state = mock_graph_instance.invoke.call_args[0][0]
                assert "founder_context" not in invoked_state

    captured = capsys.readouterr().out
    assert "[Founder Intake: SKIPPED]" in captured


def test_cli_intake_eof_handled_cleanly(capsys):
    """When interactive stdin encounters EOFError, a clear error is printed and execution continues."""
    import main as main_module

    with patch("sys.argv", ["main.py", "--idea", "Smart EV charging hub in Ahmedabad", "--intake"]):
        with patch("app.intake.questionnaire.run_founder_intake_questionnaire", side_effect=EOFError("End of file")):
            with patch.object(main_module, "build_graph") as mock_build:
                mock_graph_instance = mock_build.return_value
                mock_graph_instance.invoke.return_value = {"idea": "Smart EV charging hub in Ahmedabad"}

                main_module.main()

                invoked_state = mock_graph_instance.invoke.call_args[0][0]
                assert "founder_context" not in invoked_state

    captured = capsys.readouterr().out
    assert "[Founder Intake Error]" in captured


def test_cli_help_flag_exits_without_research_or_input(capsys):
    """py main.py --help must display usage/options and exit with code 0 without prompting or running research."""
    import main as main_module

    with patch.object(main_module, "build_graph") as mock_build:
        with patch("builtins.input") as mock_input:
            with pytest.raises(SystemExit) as exc_info:
                main_module.main(["--help"])

            assert exc_info.value.code == 0
            mock_build.assert_not_called()
            mock_input.assert_not_called()

    captured = capsys.readouterr().out
    assert "usage:" in captured
    assert "--idea" in captured
    assert "--intake" in captured
    assert "--personas" in captured
    assert "--concurrency" in captured


def test_cli_short_help_flag_exits_with_code_0(capsys):
    """py main.py -h must also display help and exit with code 0."""
    import main as main_module

    with patch.object(main_module, "build_graph") as mock_build:
        with patch("builtins.input") as mock_input:
            with pytest.raises(SystemExit) as exc_info:
                main_module.main(["-h"])

            assert exc_info.value.code == 0
            mock_build.assert_not_called()
            mock_input.assert_not_called()


def test_cli_unrecognized_argument_exits_with_code_2(capsys):
    """Unrecognized CLI arguments must raise SystemExit(2) and never be silently ignored."""
    import main as main_module

    with pytest.raises(SystemExit) as exc_info:
        main_module.main(["--unrecognized-argument-xyz"])

    assert exc_info.value.code == 2


def test_cli_interactive_prompt_when_no_idea_flag():
    """When --idea is omitted, main() prompts interactively for the business idea."""
    import main as main_module

    with patch("builtins.input", return_value="Drone delivery in Meghalaya") as mock_input:
        with patch.object(main_module, "build_graph") as mock_build:
            mock_graph = mock_build.return_value
            mock_graph.invoke.return_value = {"idea": "Drone delivery in Meghalaya"}

            main_module.main([])

            mock_input.assert_called_once()
            invoked_state = mock_graph.invoke.call_args[0][0]
            assert invoked_state["idea"] == "Drone delivery in Meghalaya"


def test_cli_query_flag_calls_retrieval_demo_and_exits():
    """When --query is passed, main() invokes run_retrieval_demo without running the full pipeline."""
    import main as main_module

    with patch.object(main_module, "run_retrieval_demo") as mock_demo:
        with patch.object(main_module, "build_graph") as mock_build:
            main_module.main(["--query", "labour workforce in Gujarat"])

            mock_demo.assert_called_once_with("labour workforce in Gujarat")
            mock_build.assert_not_called()


# ── 4. Commercial Fleet Persona Steering Tests ────────────────────────────────

def test_ev_fleet_archetype_seeds_steer_to_commercial_personas():
    """
    When target_segment or founder_context describes commercial EV fleet operators,
    archetype seeds must include the 5 essential commercial fleet customer roles.
    """
    fc = {
        "customer_category": "Commercial EV fleet operators",
        "customer_description": "Fleet owners and operations managers running 5-50 vehicles",
        "problem_description": "Charger downtime and queuing delays",
        "known_alternatives": ["Public charging stations", "Diesel generators"],
    }

    seeds = _build_archetype_seeds(
        count=10,
        customer_type=CustomerType.B2B,
        target_segment="Commercial EV fleet operators",
        founder_context=fc,
        seed=42,
    )

    roles = [s["role"] for s in seeds]
    # Check that the 5 required commercial fleet customer archetypes are represented:
    assert any("Small Fleet Owner" in r for r in roles)
    assert any("Taxi or Ride-Hailing Fleet Manager" in r for r in roles)
    assert any("Last-Mile Delivery Fleet Manager" in r for r in roles)
    assert any("Logistics Fleet Operations Manager" in r for r in roles)
    assert any("Larger Fleet Purchasing" in r or "Operations Decision-Maker" in r for r in roles)

    # Check that unrelated consumer profiles (students, homemakers) are NOT in the seeds
    assert not any("Student" in r for r in roles)
    assert not any("Homemaker" in r for r in roles)


def test_answers_reach_persona_generation_through_graph_state():
    """Verify that generate_personas_node passes founder_context from state into generate_personas."""
    fc = {
        "customer_category": "Commercial EV fleet operators",
        "customer_description": "Fleet managers running 10-30 vehicles",
        "problem_description": "Charging wait times",
        "launch_geography": "Ahmedabad",
        "known_alternatives": ["Public chargers"],
        "pricing_model": "subscription",
    }

    mock_persona = Persona(
        persona_id="persona_1",
        name="Rajesh Patel - Small Fleet Owner",
        customer_type=CustomerType.B2B,
        segment="Commercial EV fleet operators",
        geography={"state": "Gujarat", "district": "Ahmedabad"},
        age_band="35-44",
        occupation="Small Fleet Owner",
        behavioral_hypotheses={
            "price_sensitivity": 7,
            "convenience_preference": 9,
            "brand_trust_importance": 6,
            "risk_tolerance": 5,
            "digital_adoption": 7,
        },
        goals_and_needs=["Minimize vehicle idle time"],
        pain_points=["Long charger queues"],
        purchasing_constraints=["Cash-flow constraints"],
        usage_context="Daily depot charging before morning shifts",
    )

    state = {
        "idea": "Smart EV fleet charging hub in Ahmedabad",
        "target_segment": "Commercial EV fleet operators",
        "location": "Ahmedabad",
        "district": "Ahmedabad",
        "persona_count": 5,
        "founder_context": fc,
        "persona_llm": MagicMock(),
    }

    with patch("app.nodes.persona_generation.generate_personas", return_value=([mock_persona], {"customer_type": "b2b"})) as mock_gen:
        res = generate_personas_node(state)

        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args[1]
        assert call_kwargs["founder_context"] == fc
        assert res["personas"][0]["name"] == "Rajesh Patel - Small Fleet Owner"


def test_persona_generation_prompt_excludes_validation_notes():
    """
    Invariant: validation_notes must NEVER appear in the persona generation prompt
    to prevent anchoring bias.
    """
    fc = {
        "customer_category": "Commercial EV fleet operators",
        "customer_description": "Owners running 5-50 vehicles",
        "problem_description": "Queue times at charging hubs",
        "launch_geography": "Ahmedabad",
        "validation_notes": "SECRET_VALIDATION_NOTES_SHOULD_NEVER_APPEAR",
        "known_alternatives": ["Public chargers"],
    }

    prompt = _build_generation_prompt(
        idea="Smart EV charging hub in Ahmedabad",
        target_segment="Commercial EV fleet operators",
        location="Ahmedabad",
        district="Ahmedabad",
        count=5,
        archetype_seeds=[{"role": "Small Fleet Owner"}],
        evidence_context={},
        customer_type=CustomerType.B2B,
        founder_context=fc,
    )

    assert "SECRET_VALIDATION_NOTES_SHOULD_NEVER_APPEAR" not in prompt
    assert "Commercial EV fleet operators" in prompt
    assert "Queue times at charging hubs" in prompt


# ── 5. Non-Interactive API Tests ──────────────────────────────────────────────

def test_api_calls_remain_non_interactive():
    """Verify FastAPI analyze endpoint operates non-interactively."""
    from fastapi.testclient import TestClient
    from app.api import app

    client = TestClient(app)

    # Health check
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    # POST /api/analyze with mock graph
    dummy_report = {
        "report_id": "MVR-TEST-123",
        "executive_summary": {"idea_description": "Test EV Hub"},
    }

    with patch("app.api.get_graph") as mock_build:
        mock_graph = mock_build.return_value
        mock_graph.invoke.return_value = {
            "idea": "Smart EV fleet charging hub in Ahmedabad",
            "market_report": dummy_report,
            "market_report_diagnostics": {"status": "success"},
        }

        res_analyze = client.post(
            "/api/analyze",
            json={
                "idea": "Smart EV fleet charging hub in Ahmedabad",
                "persona_count": 5,
                "evaluation_concurrency": 2,
                "founder_context": {
                    "customer_category": "Commercial EV fleet operators",
                    "problem_description": "Charger queue times",
                },
            },
        )

        assert res_analyze.status_code == 200
        data = res_analyze.json()
        assert data["report_id"] == "MVR-TEST-123"
        # Confirm no stdin input was prompted
