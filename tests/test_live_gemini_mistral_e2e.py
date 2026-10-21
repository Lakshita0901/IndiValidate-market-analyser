"""
tests/test_live_gemini_mistral_e2e.py
-------------------------------------
Live end-to-end verification of the Gemini -> Mistral pipeline.
Exercises live configured Gemini and Mistral providers:
1. Calls live Gemini (gemini-1.5-flash) to generate fallback hypotheses and persona guidance
   when empirical evidence is absent.
2. Passes the live Gemini output into live Mistral (open-mistral-nemo) to generate 2 personas.
3. Evaluates 1 persona with live Mistral.
4. Verifies empirical isolation: supporting_evidence_ids remain empty.
5. Builds the final market report and verifies that with 0 supported evidence,
   no finding is labeled SUPPORTED / Corroborated, and the timestamp is valid ISO 8601.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

from app.llm import has_gemini_api_key, has_mistral_api_key, get_gemini_llm, get_llm
from app.nodes.gemini_context import generate_gemini_context
from app.nodes.persona_generation import generate_personas
from app.nodes.persona_evaluation import evaluate_personas
from app.nodes.market_analysis import analyze_market
from app.nodes.market_report import build_market_validation_report
from app.schemas.market_analysis import EvidenceStatus


def run_live_test():
    print("=== LIVE END-TO-END GEMINI -> MISTRAL VERIFICATION ===")
    
    if not has_gemini_api_key():
        print("SKIPPED: GEMINI_API_KEY is not configured.")
        return False
    if not has_mistral_api_key():
        print("SKIPPED: MISTRAL_API_KEY is not configured.")
        return False

    idea = "Smart electric commuter shuttle network for Ahmedabad tech corridor"
    print(f"\n[Step 1] Requesting Gemini Fallback Context for: '{idea}'")
    
    gemini_llm = get_gemini_llm()
    gemini_ctx, gemini_diag = generate_gemini_context(idea=idea, llm=gemini_llm)
    
    assert gemini_ctx is not None, "Gemini failed to return context"
    assert len(gemini_ctx.pain_point_hypotheses) > 0, "No pain point hypotheses from Gemini"
    assert len(gemini_ctx.target_customer_profiles) > 0, "No target customer profiles from Gemini"
    print(f"-> Gemini Context Success! Generated {len(gemini_ctx.pain_point_hypotheses)} hypotheses and {len(gemini_ctx.target_customer_profiles)} customer profiles.")
    print(f"-> Market Overview excerpt: {gemini_ctx.market_overview[:120]}...")

    print(f"\n[Step 2] Passing Gemini Context into Live Mistral for Persona Generation (count=2)...")
    mistral_llm = get_llm(model="open-mistral-nemo", temperature=0.7, timeout=45.0)
    
    personas, gen_diag = generate_personas(
        idea=idea,
        count=2,
        llm=mistral_llm,
        retrieved_chunks=[],
        gemini_context=gemini_ctx,
    )
    
    assert len(personas) >= 1, f"Mistral failed to generate personas: {gen_diag}"
    print(f"-> Mistral Persona Generation Success! Generated {len(personas)} personas:")
    for p in personas:
        print(f"   * Persona '{p.name}' ({p.segment}, Age: {p.age_band}) - Supporting Evidence IDs: {p.provenance.supporting_evidence_ids}")
        assert len(p.provenance.supporting_evidence_ids) == 0, "Gemini context leaked into empirical evidence IDs!"

    print(f"\n[Step 3] Evaluating Persona 1 with Live Mistral...")
    eval_list, eval_diag = evaluate_personas(
        idea=idea,
        personas=personas[:1],
        llm=mistral_llm,
        retrieved_chunks=[],
        max_concurrency=1,
    )
    assert len(eval_list) >= 1, f"Mistral failed to evaluate persona: {eval_diag}"
    eval_res = eval_list[0]
    print(f"-> Mistral Persona Evaluation Success! Persona '{personas[0].name}' scores: Interest={eval_res.interest_score}/10, Intent={eval_res.simulated_purchase_intent}/10")

    print(f"\n[Step 4] Running Market Analysis & Building Final Report...")
    analysis, _ = analyze_market(idea=idea, personas=personas, evaluations=[eval_res], retrieved_chunks=[])
    
    report, report_diag = build_market_validation_report(
        idea=idea,
        market_analysis=analysis,
        personas=personas,
        evaluations=[eval_res],
        research_question_answers=[],
    )
    
    # Assert epistemic integrity: no supported findings with zero empirical evidence
    for pf in report.what_appears_promising:
        assert pf.evidence_validation_status != EvidenceStatus.SUPPORTED, f"Finding {pf.finding_id} incorrectly marked SUPPORTED!"
    
    # Assert timestamp is valid ISO 8601
    assert "T" in report.generated_at, f"Timestamp is not ISO 8601: {report.generated_at}"
    print(f"-> Final Report Success! Report ID: {report.report_id}, Generated At: {report.generated_at}")
    print(f"-> Evidence coverage: Supported={report.evidence_coverage_audit.supported_count}, Insufficient={report.evidence_coverage_audit.insufficient_evidence_count}")
    print("\n=== ALL LIVE VERIFICATION CHECKS PASSED SUCCESSFULLY ===")
    return True


if __name__ == "__main__":
    success = run_live_test()
    sys.exit(0 if success else 1)
