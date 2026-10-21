"""
app.schemas.persona
-------------------
Pydantic schema for evidence-grounded synthetic customer personas (Step 9).

Represents diverse customer profiles grounded in observed population statistics,
retrieved evidence, and explicit behavioral hypotheses.

STRICT BOUNDARY:
Persona profiles represent hypothetical customers and their general needs/constraints.
They do NOT contain product interest scores, purchase-intent ratings, product-fit
evaluations, or business success probabilities.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CustomerType(str, Enum):
    CONSUMER = "consumer"
    B2B = "b2b"
    SME = "sme"


class BehavioralHypotheses(BaseModel):
    """
    Hypothesized behavioral inclinations on documented 1–10 integer scales.
    1 = Lowest intensity, 10 = Highest intensity.
    """
    model_config = ConfigDict(extra="forbid")

    price_sensitivity: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        description="1=Price insensitive, 10=Highly price-sensitive / budget-constrained"
    )
    convenience_preference: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        description="1=Tolerates high operational friction, 10=Requires extreme convenience / turn-key"
    )
    brand_trust_importance: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        description="1=Willing to experiment with unknown brands, 10=Demands verified brand credibility"
    )
    risk_tolerance: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        description="1=Extremely risk-averse, 10=Early adopter / high risk tolerance"
    )
    digital_adoption: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        description="1=Prefers offline/manual processes, 10=Digital-first / tech-savvy"
    )


class B2BAttributes(BaseModel):
    """
    Contextual organizational attributes for B2B or SME decision-maker personas.
    """
    model_config = ConfigDict(extra="forbid")

    job_role: Optional[str] = Field(default=None, description="Title or organizational function")
    organization_size: Optional[str] = Field(default=None, description="Headcount or company scale (e.g. 10-50 employees)")
    purchasing_authority: Optional[str] = Field(default=None, description="Authority level (e.g. Sole decision maker, Recommender, Committee)")
    procurement_constraints: List[str] = Field(default_factory=list, description="Budget approval cycles, compliance or vendor limits")


class PersonaProvenance(BaseModel):
    """
    Tracks factual evidence grounding, inferred attributes, and explicit assumptions.
    Maintains a strict distinction between observed statistics and synthetic personas.
    """
    model_config = ConfigDict(extra="forbid")

    supporting_evidence_ids: List[str] = Field(
        default_factory=list,
        description="Identifiers of underlying evidence chunks or records informing this profile"
    )
    observed_market_statistics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Population benchmarks cited (e.g. PLFS district salary averages, Census literacy)"
    )
    inferred_attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Attributes deduced indirectly from evidence"
    )
    explicit_assumptions: List[str] = Field(
        default_factory=list,
        description="Assumptions intentionally generated to complete the fictional persona"
    )
    unknown_or_unavailable_attributes: List[str] = Field(
        default_factory=list,
        description="Demographic or behavioral dimensions with no supporting evidence"
    )
    is_synthetic: bool = Field(
        default=True,
        description="Indicates this persona is a synthetic construct, not an individual real human"
    )
    is_statistically_representative: bool = Field(
        default=False,
        description="Strictly False unless formal sampling weights prove statistical representation"
    )


class Persona(BaseModel):
    """
    Typed, evidence-informed synthetic customer persona.
    """
    model_config = ConfigDict(extra="forbid")

    # 1. Identity & Segment
    persona_id: str = Field(description="Deterministic stable persona identifier")
    name: str = Field(description="Descriptive persona title (e.g. 'Anil Mehta - Small Machine Workshop Owner')")
    customer_type: CustomerType = Field(default=CustomerType.CONSUMER, description="Consumer, B2B, or SME")
    segment: str = Field(description="Specific customer segment target (e.g. 'Automotive Parts Manufacturer')")
    geography: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Geographic scope where persona resides (e.g. {'state': 'Gujarat', 'district': 'Ahmedabad'})"
    )

    # 2. Demographic & Contextual Profile
    age_band: Optional[str] = Field(default=None, description="Plausible age group (e.g. '25-34', '35-49')")
    occupation: Optional[str] = Field(default=None, description="Job title, profession, or employment category")
    education_level: Optional[str] = Field(default=None, description="Educational attainment (e.g. 'Graduate in Commerce', 'Diploma')")
    income_band: Optional[str] = Field(default=None, description="Plausible income range consistent with labour statistics")
    household_context: Optional[str] = Field(default=None, description="Household structure (e.g. 'Nuclear family of 4')")
    household_size: Optional[int] = Field(default=None, ge=1, description="Number of household members")

    # 3. Contextual B2B attributes (when applicable)
    b2b_attributes: Optional[B2BAttributes] = Field(default=None, description="Organizational details if B2B/SME")

    # 4. Behavioral Hypotheses
    behavioral_hypotheses: BehavioralHypotheses = Field(
        default_factory=BehavioralHypotheses,
        description="Psychographic and behavioral tendencies on 1-10 scales"
    )

    # 5. Needs, Pain Points & Constraints
    goals_and_needs: List[str] = Field(default_factory=list, description="Primary motivations and desired outcomes")
    pain_points: List[str] = Field(default_factory=list, description="Current frustrations, bottlenecks, or unaddressed issues")
    purchasing_constraints: List[str] = Field(default_factory=list, description="Barriers to adoption, cashflow limits, switching hurdles")
    usage_context: Optional[str] = Field(default=None, description="Typical environment or circumstance where product category is used")

    # 6. Provenance & Uncertainty
    provenance: PersonaProvenance = Field(
        default_factory=PersonaProvenance,
        description="Audit trail of observed evidence, inferences, and assumptions"
    )

    @model_validator(mode="after")
    def validate_persona_boundaries(self) -> "Persona":
        """
        Verify required identity attributes and strictly enforce Step 9 boundary:
        No evaluation or purchase-intent fields allowed.
        """
        if not self.persona_id or not self.persona_id.strip():
            raise ValueError("persona_id cannot be empty.")
        if not self.name or not self.name.strip():
            raise ValueError("name cannot be empty.")
        if not self.segment or not self.segment.strip():
            raise ValueError("segment cannot be empty.")

        # Ensure synthetic status is acknowledged
        if not self.provenance.is_synthetic:
            raise ValueError("Synthetic persona must have provenance.is_synthetic=True.")

        return self
