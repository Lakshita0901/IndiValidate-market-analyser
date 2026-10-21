"""
Live smoke test of persona generation and research question answering
using the active Mistral model (open-mistral-nemo).
"""

import time
from app.llm import get_llm, get_mistral_model_name
from app.nodes.persona_generation import generate_personas
from app.services.fallback_answer import answer_research_questions, AnswerBasis
from app.nodes.market_report import build_market_validation_report

def run_smoke_test():
    print(f"=== LIVE SMOKE TEST WITH MISTRAL MODEL: {get_mistral_model_name()} ===")
    idea = "Smart electric shuttle service connecting metro stations to IT parks in Pune"

    # 1. Persona Generation Smoke Test
    t0 = time.time()
    personas, diag = generate_personas(idea=idea, count=5)
    t_personas = time.time() - t0
    print(f"Step 9 (Personas): Generated {len(personas)} personas in {t_personas:.1f}s (status: {diag.get('status')})")
    assert len(personas) >= 3, f"Expected at least 3 personas, got {len(personas)}"
    for idx, p in enumerate(personas[:3], 1):
        print(f"  {idx}. {p.persona_id}: {p.name} ({p.occupation})")

    # 2. Research Questions Smoke Test
    t0 = time.time()
    answers, rq_diag = answer_research_questions(
        idea=idea,
        questions=[
            "What is the core customer problem, and what indicates real market demand or urgency?",
            "What are the most critical customer adoption barriers, switching costs, or operational risks?",
        ],
    )
    t_rq = time.time() - t0
    print(f"Step 12/Section 9 (Research Questions): Answered {len(answers)} questions in {t_rq:.1f}s")
    assert len(answers) == 2, f"Expected 2 answers, got {len(answers)}"
    for a in answers:
        print(f"  Q: {a.question[:50]}... | Basis: {a.basis.value} | Answer len: {len(a.answer)}")
        assert len(a.answer) > 50, "Answer should be substantive"
        assert not any("invalid control character" in iss.lower() for iss in rq_diag.get("issues", []))

    print("\n>>> LIVE SMOKE TEST PASSED COMPLETELY! <<<")

if __name__ == "__main__":
    run_smoke_test()
