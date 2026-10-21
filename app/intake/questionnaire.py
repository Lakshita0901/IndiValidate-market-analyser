"""
app.intake.questionnaire
------------------------
Interactive CLI questionnaire to collect FounderContext before the pipeline runs (5 essential questions).

Design principles:
  - 5 essential questions asked in sequence ([1/5] to [5/5]).
  - Required fields (customer_category, problem_description) loop until a non-empty value is entered.
  - Optional fields accept blank input (Enter key) and fall back gracefully to None / defaults.
  - Question 4 captures launch location and known alternatives; both answers are optional if unknown.
  - Question 5 captures proposed pricing and completed validation; distinguishes actual validation results from assumptions.
  - Stored validation_notes are intentionally excluded from synthetic persona generation and evaluation prompts.
  - Returns dict (FounderContext.model_dump()) directly serializable into MarketState["founder_context"].
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.founder_context import (
    FounderContext,
    GeographicScope,
    PricingModel,
    ValidationStage,
)


# ── Menu definitions (kept for helper/utility reference) ───────────────────────

_GEOGRAPHIC_SCOPE_MENU = [
    ("1", "Local city / metro area",        GeographicScope.LOCAL_CITY),
    ("2", "Regional / state-level",         GeographicScope.REGIONAL_STATE),
    ("3", "National (whole country)",       GeographicScope.NATIONAL),
    ("4", "Multi-national",                 GeographicScope.MULTI_NATIONAL),
    ("5", "Not decided yet",                GeographicScope.NOT_DECIDED),
]

_PRICING_MODEL_MENU = [
    ("1", "Free (no charge)",               PricingModel.FREE),
    ("2", "Freemium (basic free, paid tiers)", PricingModel.FREEMIUM),
    ("3", "One-time purchase",              PricingModel.ONE_TIME),
    ("4", "Subscription (recurring)",       PricingModel.SUBSCRIPTION),
    ("5", "Usage-based / pay-per-use",      PricingModel.USAGE_BASED),
    ("6", "Marketplace / commission",       PricingModel.MARKETPLACE),
    ("7", "Not decided yet",                PricingModel.NOT_DECIDED),
]

_VALIDATION_STAGE_MENU = [
    ("1", "Idea only — no conversations yet",       ValidationStage.IDEA_ONLY),
    ("2", "Informal conversations (friends, network)", ValidationStage.INFORMAL_CONVOS),
    ("3", "Formal interviews or surveys",           ValidationStage.INTERVIEWS_SURVEYS),
    ("4", "Prototype or pilot live",                ValidationStage.PROTOTYPE_PILOT),
    ("5", "Already have paying customers",          ValidationStage.PAYING_CUSTOMERS),
]


# ── Prompt helpers ────────────────────────────────────────────────────────────

def _prompt_text(label: str, hint: str = "", required: bool = False) -> str:
    """
    Print a question label and return stripped response.
    Does NOT loop — caller manages retries for required fields.
    """
    suffix = " (required)" if required else " [optional — press Enter to skip]"
    print(f"\n{label}{suffix}")
    if hint:
        print(f"  e.g. {hint}")
    try:
        return input("> ").strip()
    except EOFError:
        return ""


def _prompt_menu(label: str, menu: list, default: object) -> object:
    """Present a numbered menu and return selected enum value or default."""
    print(f"\n{label} [optional — press Enter to skip]")
    for key, desc, _ in menu:
        print(f"  {key}. {desc}")
    try:
        raw = input("> ").strip()
    except EOFError:
        return default
    if not raw:
        return default
    for key, _, value in menu:
        if raw == key:
            return value
    print(f"  \u26a0  Invalid selection '{raw}' — using default.")
    return default


def _prompt_int(label: str) -> Optional[int]:
    """Prompt for an optional non-negative integer."""
    print(f"\n{label} [optional — press Enter to skip]")
    try:
        raw = input("> ").strip()
    except EOFError:
        return None
    if not raw:
        return None
    try:
        value = int(raw)
        if value < 0:
            print("  \u26a0  Value must be 0 or greater — skipping.")
            return None
        return value
    except ValueError:
        print(f"  \u26a0  '{raw}' is not a valid whole number — skipping.")
        return None


# ── Answer Parsers for Compound Questions 4 & 5 ──────────────────────────────

def _parse_launch_and_alternatives(raw: str) -> Tuple[Optional[str], List[str]]:
    """
    Parse Question 4 answer into (launch_geography, known_alternatives).
    Supports formats:
      - 'Ahmedabad; alternatives: public charging, diesel gensets'
      - 'Ahmedabad, Gujarat; public chargers, manual logs'
      - 'Pune'
      - 'alternatives: Excel, WhatsApp'
      - '' (skip)
    """
    if not raw or not raw.strip():
        return None, []

    text = raw.strip()
    # Check for separator like ';' or '|'
    if ";" in text or "|" in text:
        delimiter = ";" if ";" in text else "|"
        parts = [p.strip() for p in text.split(delimiter, 1)]
        geo_part = parts[0]
        alts_part = parts[1] if len(parts) > 1 else ""
    elif "alternatives:" in text.lower() or "competitors:" in text.lower():
        split_match = re.split(r"(?:alternatives|competitors):\s*", text, flags=re.IGNORECASE)
        geo_part = split_match[0].rstrip(",;- ")
        alts_part = split_match[1] if len(split_match) > 1 else ""
    else:
        # Single string provided — check if it's purely alternatives or geography
        if text.lower().startswith("alternatives") or text.lower().startswith("competitors"):
            geo_part = ""
            alts_part = text
        else:
            geo_part = text
            alts_part = ""

    # Clean geography
    launch_geo: Optional[str] = None
    if geo_part:
        # Strip leading phrases like 'launch in', 'geography:'
        clean_geo = re.sub(r"^(?:launch(?:\s+in)?|geography|location):\s*", "", geo_part, flags=re.IGNORECASE).strip()
        if clean_geo.lower() not in ("unknown", "none", "n/a", "not decided", "tbd", "skip"):
            launch_geo = clean_geo

    # Clean alternatives
    alternatives: List[str] = []
    if alts_part:
        clean_alts = re.sub(r"^(?:alternatives|competitors|workarounds):\s*", "", alts_part, flags=re.IGNORECASE).strip()
        if clean_alts.lower() not in ("unknown", "none", "n/a", "not decided", "tbd", "skip"):
            items = [a.strip() for a in clean_alts.split(",") if a.strip()]
            for item in items:
                if item and item.lower() not in ("none", "n/a"):
                    alternatives.append(item)

    return launch_geo, alternatives


def _parse_pricing_and_validation(
    raw: str,
) -> Tuple[PricingModel, Optional[str], Optional[ValidationStage], Optional[str], Optional[int]]:
    """
    Parse Question 5 answer into:
      (pricing_model, expected_price, validation_stage, validation_notes, validation_sample_size)
    Distinguishes actual validation results from assumptions/hypotheses.
    """
    if not raw or not raw.strip():
        return PricingModel.NOT_DECIDED, None, None, None, None

    text = raw.strip()
    if ";" in text or "|" in text:
        delimiter = ";" if ";" in text else "|"
        parts = [p.strip() for p in text.split(delimiter, 1)]
        price_part = parts[0]
        val_part = parts[1] if len(parts) > 1 else ""
    elif "validation:" in text.lower() or "validated:" in text.lower():
        split_match = re.split(r"(?:validation|validated):\s*", text, flags=re.IGNORECASE)
        price_part = split_match[0].rstrip(",;- ")
        val_part = split_match[1] if len(split_match) > 1 else ""
    else:
        # Determine whether single response relates more to price or validation
        has_price_signals = bool(re.search(r"(?:rs\.?|inr|₹|\$|month|subscription|fee|pricing|per\s+)", text, re.I))
        has_val_signals = bool(re.search(r"(?:interview|survey|pilot|spoke|talked|customer|conversation|idea\s+only)", text, re.I))
        if has_price_signals and not has_val_signals:
            price_part = text
            val_part = ""
        elif has_val_signals and not has_price_signals:
            price_part = ""
            val_part = text
        else:
            price_part = text
            val_part = ""

    # Parse pricing
    expected_price: Optional[str] = None
    pricing_model = PricingModel.NOT_DECIDED
    if price_part and price_part.lower() not in ("unknown", "none", "n/a", "not decided", "tbd", "skip"):
        expected_price = price_part
        p_lower = price_part.lower()
        if "subscription" in p_lower or "per month" in p_lower or "/month" in p_lower or "monthly" in p_lower:
            pricing_model = PricingModel.SUBSCRIPTION
        elif "usage" in p_lower or "pay per" in p_lower or "per kwh" in p_lower or "per charge" in p_lower:
            pricing_model = PricingModel.USAGE_BASED
        elif "commission" in p_lower or "marketplace" in p_lower:
            pricing_model = PricingModel.MARKETPLACE
        elif "freemium" in p_lower:
            pricing_model = PricingModel.FREEMIUM
        elif "free" in p_lower:
            pricing_model = PricingModel.FREE
        elif "one-time" in p_lower or "one time" in p_lower:
            pricing_model = PricingModel.ONE_TIME

    # Parse validation & distinguish results from assumptions
    validation_stage: Optional[ValidationStage] = None
    validation_notes: Optional[str] = None
    sample_size: Optional[int] = None

    if val_part and val_part.lower() not in ("unknown", "none", "n/a", "not decided", "tbd", "skip"):
        v_lower = val_part.lower()

        # Extract sample size if stated (e.g. 'spoke with 10 fleet operators', '5 managers')
        num_match = re.search(
            r"\b(\d+)\s*(?:[a-zA-Z-]+\s+)?(?:people|interviews|conversations|customers|operators|users|managers|clients|drivers|cabs|vehicles|fleets)\b",
            v_lower,
        )
        if num_match:
            try:
                sample_size = int(num_match.group(1))
            except ValueError:
                pass

        # Distinguish actual results vs assumptions
        is_assumption = any(w in v_lower for w in [
            "assumption", "hypothetical", "unvalidated", "not yet", "no validation",
            "idea only", "none yet", "just an idea", "haven't started"
        ])

        if is_assumption:
            validation_stage = ValidationStage.IDEA_ONLY
            validation_notes = f"[ASSUMPTION / UNVALIDATED] {val_part}"
        elif "paying" in v_lower or "revenue" in v_lower or "paid customer" in v_lower:
            validation_stage = ValidationStage.PAYING_CUSTOMERS
            validation_notes = f"[VALIDATION COMPLETED] {val_part}"
        elif "pilot" in v_lower or "prototype" in v_lower or "beta" in v_lower:
            validation_stage = ValidationStage.PROTOTYPE_PILOT
            validation_notes = f"[VALIDATION COMPLETED] {val_part}"
        elif "formal" in v_lower or "survey" in v_lower or "interview" in v_lower:
            validation_stage = ValidationStage.INTERVIEWS_SURVEYS
            validation_notes = f"[VALIDATION COMPLETED] {val_part}"
        elif "informal" in v_lower or "spoke with" in v_lower or "conversations" in v_lower or "talked to" in v_lower:
            validation_stage = ValidationStage.INFORMAL_CONVOS
            validation_notes = f"[VALIDATION COMPLETED] {val_part}"
        else:
            validation_notes = val_part

    return pricing_model, expected_price, validation_stage, validation_notes, sample_size


# ── Public 5-Question Intake Function ─────────────────────────────────────────

def run_founder_intake_questionnaire() -> dict:
    """
    Run the streamlined 5-question interactive founder intake questionnaire.

    Prompts:
      1. [1/5] Target customer category (required).
      2. [2/5] Target customer & decision-maker description (optional).
      3. [3/5] Specific problem solved (required).
      4. [4/5] Launch geography & known alternatives (optional).
      5. [5/5] Proposed pricing & completed validation (optional).

    Returns:
        dict — FounderContext.model_dump(), JSON-serializable for MarketState["founder_context"].
    """
    print("\n" + "=" * 62)
    print("  IndiValidate \u2014 Founder Context Intake (5 Questions)")
    print("  Press Enter to skip any optional question.")
    print("=" * 62)
    print(
        "\nYour answers help calibrate synthetic persona generation and research.\n"
        "All founder-reported information represents contextual input\n"
        "and is never counted as external empirical evidence.\n"
    )

    # ── [1/5] Customer category (required) ───────────────────────────────────
    customer_category = ""
    while not customer_category:
        raw = _prompt_text(
            "[1/5] Who is your target customer?",
            hint="commercial EV fleet operators, SME factory owners",
            required=True,
        )
        if raw:
            customer_category = raw
        else:
            print("  \u26a0  This field is required. Please name your target customer.")

    # ── [2/5] Customer description & decision-maker (optional) ───────────────
    raw = _prompt_text(
        "[2/5] Describe your target customer and decision-maker:",
        hint="fleet owners and operations managers running 5-50 vehicles",
    )
    customer_description: Optional[str] = raw or None

    # ── [3/5] Problem description (required) ─────────────────────────────────
    problem_description = ""
    while not problem_description:
        raw = _prompt_text(
            "[3/5] What specific problem are you solving?",
            hint="unpredictable charger downtime and queueing delays for commercial routes",
            required=True,
        )
        if raw:
            problem_description = raw
        else:
            print("  \u26a0  This field is required. Please describe the problem being solved.")

    # ── [4/5] Launch geography & known alternatives (optional) ───────────────
    raw = _prompt_text(
        "[4/5] Where will you launch, and what alternatives do customers use today?",
        hint="Ahmedabad; alternatives: public charging stations, diesel generators, manual logs",
    )
    launch_geography, known_alternatives = _parse_launch_and_alternatives(raw)

    # ── [5/5] Proposed pricing & completed validation (optional) ─────────────
    raw = _prompt_text(
        "[5/5] What is your proposed pricing, and what validation have you already completed?",
        hint="INR 3,000/month per vehicle; spoke with 5 fleet managers (or: idea only / unvalidated)",
    )
    pricing_model, expected_price, validation_stage, validation_notes, validation_sample_size = _parse_pricing_and_validation(raw)

    # ── Assemble Typed FounderContext ─────────────────────────────────────────
    ctx = FounderContext(
        customer_category=customer_category,
        customer_description=customer_description,
        launch_geography=launch_geography,
        geographic_scope=GeographicScope.LOCAL_CITY if launch_geography else GeographicScope.NOT_DECIDED,
        problem_description=problem_description,
        known_alternatives=known_alternatives,
        pricing_model=pricing_model,
        expected_price=expected_price,
        validation_stage=validation_stage,
        validation_notes=validation_notes,
        validation_sample_size=validation_sample_size,
    )

    print("\n" + "=" * 62)
    print("  \u2713 Founder context captured (5/5 questions). Proceeding with analysis.")
    print("=" * 62 + "\n")

    return ctx.model_dump()
