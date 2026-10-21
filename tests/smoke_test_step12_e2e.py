"""
Live end-to-end smoke test verifying Step 12 completes without errors,
especially when evidence coverage has 0 supported findings.
"""

import time
from app.schemas.persona import Persona, CustomerType, BehavioralHypotheses, PersonaProvenance
from app.schemas.persona_evaluation import PersonaEvaluation
from app.nodes.market_analysis import analyze_market
from app.nodes.market_report import build_market_report_node, build_market_validation_report

def run_step12_e2e_smoke_test():
    print("=== RUNNING STEP 12 LIVE END-TO-END VERIFICATION ===")

    personas = [
        Persona(
            persona_id=f"persona_{i}",
            name=f"Commuter {i}",
            customer_type=CustomerType.CONSUMER,
            segment="Tech Commuters",
            age_band="25-34",
            occupation="Engineer",
            behavioral_hypotheses=BehavioralHypotheses(
                price_sensitivity=5,
                convenience_preference=9,
                brand_trust_importance=6,
                risk_tolerance=6,
                digital_adoption=8,
            ),
            goals_and_needs=["Fast commute", "Reliable schedule"],
            pain_points=["Traffic delays", "Unpredictable transit"],
            purchasing_constraints=["Monthly travel allowance"],
            provenance=PersonaProvenance(is_synthetic=True, is_statistically_representative=False),
        )
        for i in range(1, 5)
    ]

    evaluations = [
        PersonaEvaluation(
            persona_id=f"persona_{i}",
            interest_score=8,
            simulated_purchase_intent=7,
            perceived_value_score=8,
            affordability_score=7,
            adoption_barrier_score=3,
            positive_aspects=["Reserved seating", "Live route tracking"],
            negative_aspects=["Fixed stop locations", "Monthly pass price"],
            needs_addressed=["Fast commute"],
            needs_unmet=["Door-to-door transit"],
            pricing_considerations="Reasonable for working professionals",
            price_is_conditional=True,
            supporting_evidence_ids=[],
            evidence_gaps=["Local route feeder data"],
            unsupported_assumptions=["Guaranteed pickup spot"],
            reasons_for_assessment="Strong value for busy professionals.",
        )
        for i in range(1, 5)
    ]

    # Step 11: Market Analysis with 0 supported evidence
    print("\n--- Step 11: Analyzing market (0 supported evidence scenario) ---")
    analysis, diag11 = analyze_market(
        idea="Smart electric shuttle booking app for urban commuters in Ahmedabad",
        personas=personas,
        evaluations=evaluations,
        retrieved_chunks=[],
    )
    print(f"Evidence Coverage: Supported={analysis.evidence_coverage.supported_count}, Insufficient={analysis.evidence_coverage.insufficient_evidence_count}")
    assert analysis.evidence_coverage.supported_count == 0

    # Step 12: LangGraph Node Execution
    print("\n--- Step 12: Executing build_market_report_node ---")
    t0 = time.time()
    state = {
        "idea": "Smart electric shuttle booking app for urban commuters in Ahmedabad",
        "market_analysis": analysis.model_dump(),
        "personas": [p.model_dump() for p in personas],
        "persona_evaluations": [e.model_dump() for e in evaluations],
        "target_segment": "Tech Commuters",
        "location": "Ahmedabad",
        "district": "Ahmedabad",
        "category": "Transit",
        # Pass pre-computed research question answers so smoke test completes briskly
        "research_question_answers": [],
    }

    result = build_market_report_node(state)
    elapsed = time.time() - t0

    assert "market_report" in result, "Result must contain market_report"
    rep = result["market_report"]
    assert rep.get("report_id"), "Report ID must be present"
    es = rep.get("executive_summary", {})
    next_p = es.get("next_validation_priority")
    assert next_p, "next_validation_priority must be present and non-empty"
    print(f"\nStep 12 Completed in {elapsed:.2f}s!")
    print(f"Report ID: {rep['report_id']}")
    print(f"Next Validation Priority: {next_p}")
    print(f"Strongest Promising Signals: {es.get('strongest_promising_signals')}")
    print(f"Key Risks & Barriers: {es.get('key_risks_and_barriers')}")
    print(f"Recommended Experiments Count: {len(rep.get('recommended_experiments', []))}")
    print("\n>>> STEP 12 END-TO-END SMOKE TEST PASSED! <<<")

if __name__ == "__main__":
    run_step12_e2e_smoke_test()
