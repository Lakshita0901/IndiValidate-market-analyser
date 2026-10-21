"""
app.schemas.persona_evaluation
-------------------------------
Pydantic schema for multi-persona evaluation and simulated purchase intent (Step 10).

Represents structured, explainable simulated customer evaluations of a business idea
from the perspective of individual synthetic personas.

STRICT BOUNDARIES:
1. These evaluations represent simulated hypotheses from synthetic personas, NOT actual customer survey results.
2. Simulated purchase intent is an ordinal 1-10 scale under hypothetical conditions, NOT a real-world conversion probability.
3. This module creates individual persona evaluations. Cross-persona aggregation and final market opportunity scoring belong to subsequent steps.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class PersonaEvaluation(BaseModel):
    """
    Structured simulated customer evaluation of a business idea by a specific persona.

    NUMERICAL SCALES (Documented 1–10 integer scales):
    - interest_score:
        1 = Completely uninterested / irrelevant to persona's context.
        10 = Extremely interested / urgent relevance.
    - simulated_purchase_intent:
        1 = Definitely would not purchase or adopt under foreseeable conditions.
        10 = Highly inclined to purchase/adopt if preconditions and budget met.
        (NOTE: This is NOT a real-world conversion probability).
    - perceived_value_score:
        1 = Negligible perceived value relative to existing alternatives.
        10 = Transformative perceived value / massive improvement over status quo.
    - affordability_score:
        1 = Completely unaffordable / severe budget barrier for this persona.
        10 = Easily affordable / trivial expenditure relative to income/budget.
    - adoption_barrier_score:
        1 = Frictionless adoption / zero operational or behavioral switching costs.
        10 = Prohibitive adoption barriers / high inertia / severe disruption.
    """
    model_config = ConfigDict(extra="forbid")

    # 1. Identity Link
    persona_id: str = Field(description="Deterministic reference to the evaluated persona")

    # 2. Numerical Evaluation Metrics (1-10 integer scales)
    interest_score: int = Field(
        ge=1,
        le=10,
        description="Interest scale (1=Completely uninterested, 10=Extremely interested)"
    )
    simulated_purchase_intent: int = Field(
        ge=1,
        le=10,
        description="Simulated adoption inclination (1=Definitely not, 10=Highly inclined). NOT conversion probability."
    )
    perceived_value_score: int = Field(
        ge=1,
        le=10,
        description="Perceived value relative to alternatives (1=Negligible, 10=Transformative)"
    )
    affordability_score: int = Field(
        ge=1,
        le=10,
        description="Budget fit (1=Completely unaffordable, 10=Easily affordable)"
    )
    adoption_barrier_score: int = Field(
        ge=1,
        le=10,
        description="Adoption friction / switching costs (1=Frictionless, 10=Prohibitive barriers)"
    )

    # 3. Qualitative Reactions
    positive_aspects: List[str] = Field(
        default_factory=list,
        description="Elements of the proposed solution the persona finds compelling"
    )
    negative_aspects: List[str] = Field(
        default_factory=list,
        description="Concerns, drawbacks, risks, or objections identified by the persona"
    )
    needs_addressed: List[str] = Field(
        default_factory=list,
        description="Specific persona goals or pain points addressed by the solution"
    )
    needs_unmet: List[str] = Field(
        default_factory=list,
        description="Important persona needs or expectations that remain unaddressed"
    )

    # 4. Pricing & Product Fit
    pricing_considerations: Optional[str] = Field(
        default=None,
        description="Willingness-to-pay assessment or pricing feedback. Conditional if price unspecified."
    )
    price_is_conditional: bool = Field(
        default=False,
        description="True if proposed price was unspecified in idea and thus conditional/untested"
    )
    valued_features: List[str] = Field(
        default_factory=list,
        description="Specific features the persona would prioritize or pay for"
    )
    unnecessary_features: List[str] = Field(
        default_factory=list,
        description="Features considered superfluous, overly complex, or unneeded by the persona"
    )

    # 5. Reasoning & Attribute Grounding
    reasons_for_assessment: str = Field(
        description="Coherent explanation connecting persona context to the evaluation scores"
    )
    supporting_persona_attributes: List[str] = Field(
        default_factory=list,
        description="Persona attributes that drove this reaction (e.g. 'budget constraint', 'low tech comfort')"
    )

    # 6. Evidence Grounding & Uncertainty Tracking
    supporting_evidence_ids: List[str] = Field(
        default_factory=list,
        description="Identifiers of underlying retrieved evidence chunks supporting the evaluation"
    )
    unsupported_assumptions: List[str] = Field(
        default_factory=list,
        description="Hypotheses or assumptions made during simulation without direct factual evidence"
    )
    evidence_gaps: List[str] = Field(
        default_factory=list,
        description="Information missing from available market evidence that leaves assessment uncertain"
    )

    # 7. Simulation Integrity Flags
    is_simulation: bool = Field(
        default=True,
        description="Explicit flag indicating this is a synthetic simulation, not real customer feedback"
    )
    is_conversion_probability: bool = Field(
        default=False,
        description="Explicitly False: purchase intent is an ordinal scale, NOT a real-world conversion rate"
    )

    @model_validator(mode="after")
    def validate_evaluation_integrity(self) -> "PersonaEvaluation":
        if not self.persona_id or not self.persona_id.strip():
            raise ValueError("persona_id cannot be empty.")
        if not self.reasons_for_assessment or not self.reasons_for_assessment.strip():
            raise ValueError("reasons_for_assessment cannot be empty.")
        if not self.is_simulation:
            raise ValueError("is_simulation must be True for simulated persona evaluations.")
        if self.is_conversion_probability:
            raise ValueError(
                "is_conversion_probability must be False. Simulated purchase intent "
                "cannot be claimed as a real-world conversion probability."
            )
        return self
