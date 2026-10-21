"""
app.nodes.persona_generation
-----------------------------
Evidence-grounded synthetic customer persona generation node (Step 9).

Generates a diverse population of plausible customer personas informed by
structured Census 2011 demographics, PLFS 2025 labour statistics, and retrieved
market evidence.

STRICT BOUNDARY:
Profiles represent customer context, general needs, and purchasing barriers.
They do NOT assign product interest scores, purchase-intent ratings, or product-fit rankings.
"""

import json
import os
import random
import re
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel

from app.llm import classify_mistral_error, get_llm, has_mistral_api_key, is_terminal_error
from app.utils.json_utils import parse_json_robust, capture_failed_response_diagnostics

from app.schemas.persona import (
    B2BAttributes,
    BehavioralHypotheses,
    CustomerType,
    Persona,
    PersonaProvenance,
)
from app.state import MarketState


class PersonaBatch(BaseModel):
    """Schema container for batch structured persona generation."""
    personas: List[Persona]


# ------------------------------------------------------------------
# 1. Diversity Archetype Matrix Generator
# ------------------------------------------------------------------

def _build_archetype_seeds(
    count: int,
    customer_type: CustomerType,
    target_segment: str,
    founder_context: Optional[Dict[str, Any]] = None,
    seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Generate a diverse matrix of archetype seeds across age, income/resources,
    digital adoption, risk tolerance, and occupational roles.
    Ensures the LLM produces a varied distribution rather than repetitive clones.
    """
    rng = random.Random(seed if seed is not None else 42)

    fc_text = ""
    if founder_context:
        fc_text = f"{founder_context.get('customer_category', '')} {founder_context.get('customer_description', '')} {founder_context.get('problem_description', '')}"

    combined_text = f"{target_segment} {fc_text}".lower()
    is_commercial_fleet = any(k in combined_text for k in [
        "fleet", "charging hub", "commercial ev", "logistics", "freight",
        "ride-hailing", "taxi", "delivery", "transport"
    ])

    if is_commercial_fleet or customer_type in (CustomerType.B2B, CustomerType.SME):
        if is_commercial_fleet:
            roles = [
                ("Small Fleet Owner / Operator", "Sole Owner & Purchasing Decision-Maker", "3-15 commercial EV vehicles"),
                ("Taxi or Ride-Hailing Fleet Manager", "Fleet Operations Manager", "20-60 commercial passenger EVs"),
                ("Last-Mile Delivery Fleet Manager", "Hub & Dispatch Operations Lead", "15-40 2W/3W/4W electric delivery vehicles"),
                ("Logistics Fleet Operations Manager", "Regional Logistics & Depot Head", "40-100 commercial cargo/freight vehicles"),
                ("Larger Fleet Purchasing or Operations Decision-Maker", "Procurement Director / VP Logistics", "100+ commercial enterprise vehicles"),
                ("Independent Owner-Driver in Fleet Network", "Owner-Operator Contractor", "1-2 commercial electric cabs attached to aggregator"),
                ("Intercity Commercial Van Fleet Owner", "Managing Partner", "8-25 commercial passenger/cargo vans"),
                ("Cold-Chain EV Logistics Coordinator", "Cold-Chain Operations Manager", "10-30 temperature-controlled electric vehicles"),
                ("Corporate Employee Transit Fleet Manager", "Transport & Administration Lead", "25-50 employee shuttle vans"),
                ("Commercial Fleet Maintenance Supervisor", "Fleet Technical & Uptime Head", "30-75 mixed commercial EVs"),
            ]
            org_types = [
                "E-Commerce & Courier Delivery Logistics Partner",
                "App-Based Urban Taxi Aggregation Fleet",
                "Intra-City Quick-Commerce Logistics Fleet",
                "Third-Party Express Freight & Distribution Hub",
                "Corporate Employee Transport Fleet Provider",
            ]
            tech_levels = [
                "Telematics & Driver App Connected",
                "Basic GPS Trackers & Excel Dispatch Logs",
                "Centralized Fleet Management SaaS",
            ]
            risk_levels = [
                "Extremely Downtime-Averse (Idle Vehicle = Direct Revenue Loss)",
                "Cost-Per-KM & Operational TCO Focused",
                "Pragmatic / Strict Uptime SLA Dependent",
            ]
        else:
            roles = [
                ("Proprietor / Managing Director", "Sole decision maker", "10-25 employees"),
                ("Operations / Factory Manager", "Key operational recommender", "25-100 employees"),
                ("Finance / Procurement Head", "Budget approver / Cost controller", "50-200 employees"),
                ("Technical Lead / Chief Engineer", "Evaluates feasibility & integration", "15-80 employees"),
                ("Small Workshop Owner / Founder", "Hands-on owner-operator", "3-15 employees"),
            ]
            org_types = ["Small Manufacturing Workshop", "Tier-2 Auto Component Supplier", "Industrial Job Shop", "Commercial Fabrication Facility", "Contract Engineering Unit"]
            tech_levels = ["Traditional / Legacy ERP / Spreadsheets", "Partially Digital / Tally + Manual", "Tech-Forward / Cloud Curious"]
            risk_levels = ["Extremely Risk-Averse (Requires Proven ROI)", "Pragmatic / Compliance-Driven", "Progressive / Modernization-Oriented"]

        seeds = []
        for i in range(count):
            role_info = roles[i % len(roles)]
            org = org_types[i % len(org_types)]
            tech = tech_levels[i % len(tech_levels)]
            risk = risk_levels[i % len(risk_levels)]
            seeds.append({
                "index": i + 1,
                "role": role_info[0],
                "authority": role_info[1],
                "organization_size": role_info[2],
                "industry_context": org,
                "tech_maturity": tech,
                "risk_profile": risk,
            })
        return seeds

    else:
        # Consumer Archetypes
        age_bands = ["18-24 (Student / Early Career)", "25-34 (Young Professional)", "35-49 (Mid-Career Family Head)", "50-64 (Mature Professional / Homemaker)", "65+ (Senior Citizen)"]
        occupations = ["Salaried Corporate Employee", "Self-Employed / Trader", "Public Sector / Government Worker", "Freelancer / Creative Professional", "Homemaker / Caregiver", "College / Postgraduate Student"]
        income_brackets = ["Budget-Constrained / Cost-Sensitive", "Median Benchmark Income", "Upper-Middle / Discretionary Spender", "Affluent / Premium-Oriented"]
        digital_comforts = ["Mobile-Only / Basic App User", "Digital Native / Early Adopter", "Traditional / Offline-Preferred", "Pragmatic / Utility-Driven"]

        seeds = []
        for i in range(count):
            seeds.append({
                "index": i + 1,
                "age_band": age_bands[i % len(age_bands)],
                "occupation": occupations[i % len(occupations)],
                "income_bracket": income_brackets[i % len(income_brackets)],
                "digital_comfort": digital_comforts[i % len(digital_comforts)],
            })
        return seeds


# ------------------------------------------------------------------
# 2. Evidence Context Extraction
# ------------------------------------------------------------------

def _extract_evidence_context(
    research_evidence: Optional[Dict[str, Any]] = None,
    retrieved_chunks: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    Extract factual population constraints and benchmarks from research state.
    """
    context: Dict[str, Any] = {
        "demographic_benchmarks": {},
        "labour_benchmarks": {},
        "qualitative_observations": [],
        "evidence_ids": [],
    }

    if not research_evidence and not retrieved_chunks:
        return context

    ev = research_evidence or {}

    # Census 2011 structured evidence
    census_list = ev.get("census_evidence", [])
    if census_list:
        c_record = census_list[0]
        pca = c_record.get("pca", {})
        c08 = c_record.get("education", {})
        c08a = c_record.get("higher_education", {})
        geo = c_record.get("geography", {})

        context["demographic_benchmarks"] = {
            "state": geo.get("state"),
            "district": geo.get("district"),
            "total_population": pca.get("population", {}).get("total"),
            "literacy_rate_percent": pca.get("literacy", {}).get("crude_literacy_rate_percent"),
            "graduates_total": c08.get("summary", {}).get("levels", {}).get("graduate_and_above", {}).get("persons"),
            "engineering_graduates": c08a.get("summary", {}).get("disciplines", {}).get("engineering_and_technology", {}).get("persons"),
        }

    # PLFS 2025 structured evidence
    plfs_list = ev.get("plfs_evidence", [])
    if plfs_list:
        p_record = plfs_list[0]
        labour = p_record.get("labour_indicators", {}).get("usual_status_ps_plus_ss", {})
        earn = p_record.get("earnings", {})
        edu = p_record.get("education", {})

        context["labour_benchmarks"] = {
            "lfpr_percent": labour.get("lfpr_percent"),
            "wpr_percent": labour.get("wpr_percent"),
            "unemployment_rate_percent": labour.get("unemployment_rate_percent"),
            "avg_monthly_salary_regular_salaried_inr": earn.get("regular_salaried", {}).get("avg_monthly_salary_inr"),
            "avg_monthly_earnings_self_employed_inr": earn.get("self_employed", {}).get("avg_monthly_earnings_inr"),
            "graduate_and_above_percent": edu.get("graduate_and_above_percent"),
        }

    # Retrieved or cleaned chunks
    if retrieved_chunks:
        for item in retrieved_chunks[:6]:
            if hasattr(item, "text") and hasattr(item, "chunk_id"):
                context["qualitative_observations"].append(f"[{item.chunk_id}] {item.text[:180]}")
                context["evidence_ids"].append(item.chunk_id)
            elif isinstance(item, dict):
                cid = item.get("chunk_id", "chunk")
                txt = item.get("text", "")
                context["qualitative_observations"].append(f"[{cid}] {txt[:180]}")
                context["evidence_ids"].append(cid)

    return context


# ------------------------------------------------------------------
# 3. LLM Prompt Construction
# ------------------------------------------------------------------

def _build_generation_prompt(
    idea: str,
    target_segment: str,
    location: str,
    district: str,
    count: int,
    archetype_seeds: List[Dict[str, Any]],
    evidence_context: Dict[str, Any],
    customer_type: CustomerType,
    founder_context: Optional[Dict[str, Any]] = None,
    gemini_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Construct a rigorous prompt for structured JSON persona generation."""
    benchmarks_json = json.dumps({
        "census_2011_benchmarks": evidence_context.get("demographic_benchmarks"),
        "plfs_2025_labour_benchmarks": evidence_context.get("labour_benchmarks"),
    }, indent=2)

    qual_snippets = "\n".join(f"- {s}" for s in evidence_context.get("qualitative_observations", [])[:5]) or "None available."

    seeds_json = json.dumps(archetype_seeds, indent=2)

    founder_block = ""
    if founder_context:
        fc_cat = founder_context.get("customer_category") or "Not specified"
        fc_desc = founder_context.get("customer_description") or "Not specified"
        fc_prob = founder_context.get("problem_description") or "Not specified"
        fc_alts = ", ".join(founder_context.get("known_alternatives", [])) or "None identified"
        fc_geo = founder_context.get("launch_geography") or "Not specified"
        founder_block = f"""
FOUNDER CONTEXT (CONTEXTUAL CALIBRATION ONLY — UNVERIFIED FOUNDER CLAIMS):
- Target Customer Category: {fc_cat}
- Target Customer & Decision-Maker Description: {fc_desc}
- Problem Stated: {fc_prob}
- Known Alternatives/Workarounds Today: {fc_alts}
- Target Launch Geography: {fc_geo}
(NOTE: Founder answers are contextual input to steer customer archetypes, NOT external empirical evidence. validation_notes are strictly excluded.)
"""

    gemini_block = ""
    if gemini_context:
        ctx_dict = gemini_context.model_dump() if hasattr(gemini_context, "model_dump") else (gemini_context if isinstance(gemini_context, dict) else {})
        m_over = ctx_dict.get("market_overview") or ""
        p_hyps = "\n".join(f"  * {h}" for h in ctx_dict.get("pain_point_hypotheses", [])) or "  * None formulated."
        b_hyps = "\n".join(f"  * {b}" for b in ctx_dict.get("adoption_barrier_hypotheses", [])) or "  * None formulated."
        assumptions = "\n".join(f"  * {a}" for a in ctx_dict.get("explicit_assumptions", [])) or "  * None specified."
        guidance = "\n".join(f"  * {g}" for g in ctx_dict.get("persona_generation_guidance", [])) or "  * Generate varied archetypes."
        gemini_block = f"""
MODEL-GENERATED STARTUP CONTEXT & HYPOTHESES (GEMINI GUIDANCE — NOT EMPIRICAL EVIDENCE):
(Note: External empirical research was absent or insufficient. The following hypotheses and guidance were generated by Gemini to steer realistic customer persona design. Personas generated must reflect these hypothesized contexts, record assumptions in explicit_assumptions, and must NOT be attributed to verified empirical sources.)
- Market & Ecosystem Overview: {m_over}
- Customer Pain-Point Hypotheses:
{p_hyps}
- Adoption Barrier Hypotheses:
{b_hyps}
- Key Model Assumptions:
{assumptions}
- Persona Generation Directives for Mistral:
{guidance}
"""

    prompt = f"""You are the evidence-informed synthetic customer persona generator for IndiValidate.

BUSINESS CONTEXT:
- Business Idea: {idea}
- Target Segment: {target_segment or 'General prospective customers'}
- Target Location: {location or 'India'} (District: {district or 'State/Metro area'})
- Primary Customer Type: {customer_type.value}
- Personas Requested: {count}
{founder_block}
{gemini_block}
OBSERVED POPULATION STATISTICS & BENCHMARKS:
{benchmarks_json}

QUALITATIVE MARKET SIGNALS (Reddit / Google Trends excerpts):
{qual_snippets}

DIVERSITY ARCHETYPE SEEDS:
{seeds_json}

CRITICAL RULES & BOUNDARIES:
1. Ground demographic and financial attributes in the observed benchmarks where available (e.g. PLFS district salary and Census literacy), but DO NOT treat aggregate averages as identical values for every individual. Vary realistic personal ranges around the benchmark.
2. DO NOT assign purchase-intent scores, product interest ratings, or business recommendations. Personas must only describe customer identity, contextual background, general goals, pain points, and purchasing constraints.
3. Keep persona IDs deterministic (e.g. "persona_1", "persona_2", ... up to "persona_{count}").
4. Behavioral hypotheses MUST use 1-10 integer scales (price_sensitivity, convenience_preference, brand_trust_importance, risk_tolerance, digital_adoption).
5. State explicit assumptions in provenance.explicit_assumptions and list unmeasured dimensions in provenance.unknown_or_unavailable_attributes.
6. Return ONLY a valid JSON array of {count} Persona objects conforming to the schema below. No conversational markdown outside the JSON block.
7. TARGET CUSTOMER RELEVANCE: When founder context or business idea targets commercial fleet operators or commercial businesses, all personas MUST represent relevant commercial decision-makers and operators within that target group (such as small fleet owner/operators, taxi/ride-hailing fleet managers, last-mile delivery fleet managers, logistics operations managers, larger fleet purchasing/operations heads). Under no circumstances generate college students, homemakers, or casual household EV drivers unless the target segment explicitly demands them.
8. GEMINI HYPOTHESIS INTEGRATION: If model-generated startup context and hypotheses from Gemini are provided above, incorporate them into persona pain points, goals, and constraints. When empirical evidence is absent or insufficient, set supporting_evidence_ids to [] (empty) and explicitly list in provenance.explicit_assumptions that customer pain points were informed by Gemini startup hypotheses without empirical verification.

JSON OUTPUT FORMAT:
[
  {{
    "persona_id": "persona_1",
    "name": "Descriptive Name - Role/Context",
    "customer_type": "{customer_type.value}",
    "segment": "{target_segment or 'Target customer'}",
    "geography": {{"state": "{evidence_context.get('demographic_benchmarks', {}).get('state') or 'Gujarat'}", "district": "{district or 'Ahmedabad'}"}},
    "age_band": "35-44",
    "occupation": "Specific Occupation / Title",
    "education_level": "Specific Education",
    "income_band": "Plausible Monthly Income Range",
    "household_context": "Household description",
    "household_size": 4,
    {'"b2b_attributes": {"job_role": "...", "organization_size": "...", "purchasing_authority": "...", "procurement_constraints": ["..."]},' if customer_type != CustomerType.CONSUMER else ""}
    "behavioral_hypotheses": {{
      "price_sensitivity": 7,
      "convenience_preference": 8,
      "brand_trust_importance": 6,
      "risk_tolerance": 4,
      "digital_adoption": 6
    }},
    "goals_and_needs": ["Goal 1", "Goal 2"],
    "pain_points": ["Pain point 1", "Pain point 2"],
    "purchasing_constraints": ["Constraint 1", "Constraint 2"],
    "usage_context": "When and why this category of solution is needed",
    "provenance": {{
      "supporting_evidence_ids": {json.dumps(evidence_context.get('evidence_ids', []))},
      "observed_market_statistics": {json.dumps(evidence_context.get('labour_benchmarks', {}))},
      "inferred_attributes": {{"income_justification": "Aligned with PLFS district salary distributions"}},
      "explicit_assumptions": ["Assumed family size based on regional census average"],
      "unknown_or_unavailable_attributes": ["Specific disposable hobby expenditure"],
      "is_synthetic": true,
      "is_statistically_representative": false
    }}
  }}
]
"""
    return prompt


# ------------------------------------------------------------------
# 4. JSON Cleaning and Response Parsing
# ------------------------------------------------------------------

def _clean_json_response(raw_text: str) -> str:
    """Extract clean JSON string from LLM output, stripping markdown codeblocks and fences."""
    from app.utils.json_utils import extract_json_candidate
    return extract_json_candidate(raw_text)


def _parse_and_validate_personas(
    raw_response: str,
    expected_count: int,
) -> Tuple[List[Persona], List[str]]:
    """
    Parse raw JSON string into a list of validated Persona instances.
    Returns (validated_personas, validation_issues).
    """
    issues: List[str] = []

    try:
        data = parse_json_robust(raw_response)
    except Exception as e:
        return [], [f"JSON parsing error: {e}"]

    if isinstance(data, dict) and "personas" in data:
        items = data["personas"]
    elif isinstance(data, list):
        items = data
    else:
        return [], [f"Expected JSON list of personas, got {type(data)}."]

    validated: List[Persona] = []
    seen_ids = set()

    for idx, item in enumerate(items, 1):
        if not isinstance(item, dict):
            issues.append(f"Item {idx} is not a dictionary.")
            continue

        # Enforce unique persona_id
        pid = item.get("persona_id") or f"persona_{idx}"
        if pid in seen_ids:
            pid = f"{pid}_{idx}"
            item["persona_id"] = pid
        seen_ids.add(pid)

        # Enforce required provenance synthetic flags
        if "provenance" not in item:
            item["provenance"] = {}
        item["provenance"]["is_synthetic"] = True
        item["provenance"]["is_statistically_representative"] = False

        try:
            p_obj = Persona.model_validate(item)
            validated.append(p_obj)
        except Exception as val_err:
            issues.append(f"Validation failure on persona '{pid}': {val_err}")

    return validated, issues


# ------------------------------------------------------------------
# 5. Master Persona Generation Function
# ------------------------------------------------------------------

def generate_personas(
    idea: str,
    target_segment: str = "",
    location: str = "",
    district: str = "",
    count: int = 10,
    customer_type: Optional[Union[CustomerType, str]] = None,
    research_evidence: Optional[Dict[str, Any]] = None,
    retrieved_chunks: Optional[List[Any]] = None,
    llm: Optional[Any] = None,
    seed: Optional[int] = None,
    max_retries: int = 1,
    founder_context: Optional[Dict[str, Any]] = None,
    gemini_context: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Persona], Dict[str, Any]]:
    """
    Master function to generate evidence-grounded synthetic customer personas.

    Parameters:
    - idea: Business idea string.
    - target_segment: Target audience definition.
    - location: Geographic state or city.
    - district: Geographic district.
    - count: Target number of diverse personas to produce (default: 10).
    - customer_type: Optional CustomerType or string ("consumer", "b2b", "sme").
    - research_evidence: Dictionary of raw/cleaned evidence (Census, PLFS, etc.).
    - retrieved_chunks: Optional list of retrieved evidence chunks.
    - llm: Optional injectable LLM model or test generator.
    - seed: Optional random seed for reproducible archetype distributions.
    - max_retries: Retry attempts for malformed LLM outputs.
    - founder_context: Optional founder-reported context for archetype calibration.

    Returns:
    - (personas_list, diagnostics_dict)
    """
    diagnostics: Dict[str, Any] = {
        "requested_count": count,
        "generated_count": 0,
        "validation_failures_count": 0,
        "duplicates_removed_count": 0,
        "customer_type": "consumer",
        "diversity_metrics": {},
        "issues": [],
    }

    if not idea or not idea.strip():
        raise ValueError("Business idea string cannot be empty.")

    if count < 1:
        raise ValueError(f"Persona count must be at least 1, got {count}.")

    # 1. Determine customer type
    if customer_type:
        c_type = CustomerType(str(customer_type).lower())
    else:
        # Heuristic classification from idea, target segment, and founder context
        b2b_keywords = [
            "saas", "b2b", "enterprise", "factory", "manufactur", "procurement",
            "supply chain", "erp", "sme", "smb", "clinic", "hospital", "school",
            "distributor", "fleet", "commercial", "operator", "logistics", "freight", "transport"
        ]
        text_lower = f"{idea} {target_segment}".lower()
        if founder_context:
            text_lower += f" {founder_context.get('customer_category', '')} {founder_context.get('customer_description', '')}"
        if any(kw in text_lower for kw in b2b_keywords):
            c_type = CustomerType.B2B
        else:
            c_type = CustomerType.CONSUMER

    diagnostics["customer_type"] = c_type.value

    # 2. Extract evidence context & archetype seeds
    ev_context = _extract_evidence_context(research_evidence, retrieved_chunks)
    archetype_seeds = _build_archetype_seeds(count, c_type, target_segment, founder_context=founder_context, seed=seed)

    # 3. Resolve LLM provider
    # 3. Resolve LLM provider
    if llm is None:
        if not has_mistral_api_key():
            diagnostics["status"] = "failed"
            diagnostics["issues"].append("Mistral API key not found in environment (MISTRAL_API_KEY).")
            return [], diagnostics

        llm = get_llm(temperature=0.7, timeout=90.0)

    # 4. Batch Archetype Seeds into manageable chunks of <= 5 to avoid LLM timeouts/truncation
    personas: List[Persona] = []
    batch_size = 5
    seed_batches = [
        archetype_seeds[i : i + batch_size]
        for i in range(0, len(archetype_seeds), batch_size)
    ]
    if not seed_batches:
        seed_batches = [archetype_seeds]

    for b_idx, batch_seeds in enumerate(seed_batches):
        batch_count = len(batch_seeds)
        batch_prompt = _build_generation_prompt(
            idea=idea,
            target_segment=target_segment,
            location=location,
            district=district,
            count=batch_count,
            archetype_seeds=batch_seeds,
            evidence_context=ev_context,
            customer_type=c_type,
            founder_context=founder_context,
            gemini_context=gemini_context,
        )

        batch_personas: List[Persona] = []
        attempt = 0

        while attempt <= max_retries and len(batch_personas) < batch_count:
            attempt += 1

            # Strategy 1: Prefer native schema-constrained structured output if supported
            if hasattr(llm, "with_structured_output"):
                try:
                    structured_llm = llm.with_structured_output(PersonaBatch)
                    res = structured_llm.invoke(batch_prompt)
                    if res and getattr(res, "personas", None) and len(res.personas) > 0:
                        batch_personas = res.personas
                        break
                except Exception as struct_err:
                    diagnostics["issues"].append(
                        f"Batch {b_idx + 1} structured output attempt {attempt} failed: {struct_err}"
                    )

            # Strategy 2: Raw prompt invocation with robust JSON extraction and repair
            raw_text = ""
            try:
                if hasattr(llm, "invoke"):
                    res = llm.invoke(batch_prompt)
                    raw_text = res.content if hasattr(res, "content") else str(res)
                elif callable(llm):
                    raw_text = llm(batch_prompt)
                else:
                    raw_text = str(llm)

                parsed, val_issues = _parse_and_validate_personas(raw_text, batch_count)
                diagnostics["issues"].extend(val_issues)

                if parsed:
                    batch_personas.extend(parsed)
                    break
            except Exception as e:
                err_diag = classify_mistral_error(e)
                diag_info = capture_failed_response_diagnostics(
                    provider="mistral",
                    model=getattr(llm, "model", "unknown") if hasattr(llm, "model") else getattr(llm, "model_name", "unknown"),
                    raw_response=raw_text,
                    exc=e,
                )
                diagnostics["issues"].append(
                    f"LLM execution batch {b_idx + 1} attempt {attempt} failed: {diag_info['error']} (preview={diag_info['raw_preview'][:80]})"
                )
                if err_diag["is_terminal"]:
                    break

        personas.extend(batch_personas)

    # 5. Deduplication and Near-Duplicate Resolution
    deduped: List[Persona] = []
    seen_fingerprints = set()

    for p in personas:
        # Near-duplicate fingerprint: name + occupation + age_band
        fp = f"{p.name.strip().lower()}|{p.occupation or ''}|{p.age_band or ''}|{p.segment.strip().lower()}"
        if fp in seen_fingerprints:
            diagnostics["duplicates_removed_count"] += 1
            continue
        seen_fingerprints.add(fp)
        deduped.append(p)

    final_personas = deduped[:count]

    # Re-index unique sequential deterministic IDs (persona_1 to persona_N)
    for idx, p in enumerate(final_personas, 1):
        p.persona_id = f"persona_{idx}"

    # Epistemic boundary: When empirical evidence is absent or insufficient, ensure personas never claim fake evidence
    if gemini_context and not ev_context.get("evidence_ids"):
        for p in final_personas:
            p.provenance.supporting_evidence_ids = []
            assumption_text = "Informed by Gemini model hypotheses (empirical evidence absent)"
            if assumption_text not in p.provenance.explicit_assumptions:
                p.provenance.explicit_assumptions.append(assumption_text)

    diagnostics["generated_count"] = len(final_personas)
    diagnostics["validation_failures_count"] = len(diagnostics["issues"])

    if len(final_personas) == 0:
        diagnostics["status"] = "failed"
        diagnostics["issues"].append("Persona generation failed: zero personas were successfully generated.")
    elif len(final_personas) < count:
        diagnostics["status"] = "partial_success"
    else:
        diagnostics["status"] = "success"

    # 6. Diversity Metric Tracking
    diagnostics["diversity_metrics"] = {
        "unique_occupations": len(set(p.occupation for p in final_personas if p.occupation)),
        "unique_age_bands": len(set(p.age_band for p in final_personas if p.age_band)),
        "unique_income_bands": len(set(p.income_band for p in final_personas if p.income_band)),
        "digital_adoption_spread": [p.behavioral_hypotheses.digital_adoption for p in final_personas if p.behavioral_hypotheses.digital_adoption is not None],
    }

    return final_personas, diagnostics


# ------------------------------------------------------------------
# 6. LangGraph Node Integration
# ------------------------------------------------------------------

def generate_personas_node(state: MarketState) -> Dict[str, Any]:
    """
    LangGraph node executing evidence-grounded synthetic customer persona generation.
    Surfaces stage failures explicitly if zero personas can be generated.
    """
    idea = state.get("idea", "")
    target = state.get("target_segment", "")
    location = state.get("location", "")
    district = state.get("district", "")
    count = state.get("persona_count", 10)
    customer_type = state.get("customer_type")
    seed = state.get("persona_seed")
    llm = state.get("persona_llm") or state.get("llm")
    generate_flag = state.get("generate_personas", True)

    if not generate_flag:
        return {
            "personas": [],
            "persona_generation_diagnostics": {"status": "skipped", "issues": ["generate_personas is False"]},
        }

    # Safe stage reuse check: if personas already generated, reuse them
    existing_personas = state.get("personas")
    if existing_personas and len(existing_personas) >= count:
        print(f"\n>>> SYNTHETIC PERSONA GENERATION (Step 9): Reusing {len(existing_personas)} cached personas from prior execution.")
        diag = state.get("persona_generation_diagnostics") or {
            "requested_count": count,
            "generated_count": len(existing_personas),
            "status": "reused_from_cache",
        }
        return {
            "personas": existing_personas,
            "persona_generation_diagnostics": diag,
        }

    # Aggregate research evidence from state
    research_evidence = {
        "census_evidence": state.get("census_evidence", []),
        "plfs_evidence": state.get("plfs_evidence", []),
        "reddit_evidence": state.get("reddit_evidence", []),
        "trends_evidence": state.get("trends_evidence", []),
    }

    retrieved_chunks = state.get("retrieved_chunks", []) or state.get("document_chunks", [])
    founder_context = state.get("founder_context")

    print("\n>>> SYNTHETIC PERSONA GENERATION (Step 9)")
    try:
        personas, diag = generate_personas(
            idea=idea,
            target_segment=target,
            location=location,
            district=district,
            count=count,
            customer_type=customer_type,
            research_evidence=research_evidence,
            retrieved_chunks=retrieved_chunks,
            llm=llm,
            seed=seed,
            founder_context=founder_context,
            gemini_context=state.get("gemini_context"),
        )

        personas_data = [p.model_dump() for p in personas]
        print(f"    Personas Generated: {len(personas_data)} / {count} requested (Customer type: {diag.get('customer_type')})")

        if not personas_data:
            diag["status"] = "failed"
            return {
                "personas": [],
                "persona_generation_diagnostics": diag,
                "stage_failures": ["persona_generation"],
            }

        return {
            "personas": personas_data,
            "persona_generation_diagnostics": diag,
        }
    except Exception as e:
        print(f"    Persona Generation Error: {e}")
        return {
            "personas": [],
            "persona_generation_diagnostics": {
                "requested_count": count,
                "generated_count": 0,
                "status": "failed",
                "issues": [f"Persona generation exception: {e}"],
            },
            "stage_failures": ["persona_generation"],
        }
