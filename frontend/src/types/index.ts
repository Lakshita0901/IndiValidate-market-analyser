// TypeScript definitions matching IndiValidate / Market Analyzer Pydantic Schemas

export type PageId = 'overview' | 'new-analysis' | 'progress' | 'personas' | 'market-insights' | 'reports';

export type AnswerBasis = 'retrieved_evidence' | 'mixed' | 'model_knowledge';

export type EvidenceStatus =
  | 'supported'
  | 'contradicted'
  | 'mixed'
  | 'insufficient_evidence'
  | 'not_applicable';

export type GeographicScope =
  | 'local_city'
  | 'regional_state'
  | 'national'
  | 'multi_national'
  | 'not_decided';

export type PricingModel =
  | 'free'
  | 'freemium'
  | 'one_time_purchase'
  | 'subscription'
  | 'usage_based'
  | 'marketplace_commission'
  | 'not_decided';

export type ValidationStage =
  | 'idea_only'
  | 'informal_conversations'
  | 'interviews_or_surveys'
  | 'prototype_or_pilot'
  | 'paying_customers';

export interface FounderContext {
  customer_category: string;
  customer_description?: string | null;
  launch_geography?: string | null;
  geographic_scope?: GeographicScope;
  problem_description: string;
  known_alternatives?: string[];
  pricing_model?: PricingModel;
  expected_price?: string | null;
  validation_stage?: ValidationStage | null;
  validation_notes?: string | null;
  validation_sample_size?: number | null;
}

export interface AnalyzeRequest {
  idea: string;
  founder_context?: FounderContext | null;
  persona_count?: number;
  evaluation_concurrency?: number;
}

export interface HealthResponse {
  status: string;
  service: string;
}

export interface ExecutiveSummary {
  idea_description: string;
  target_customer_segments: string[];
  strongest_promising_signals: string[];
  key_risks_and_barriers: string[];
  critical_unresolved_questions: string[];
  next_validation_priority: string;
}

export interface IdeaAndMarketContext {
  business_idea: string;
  business_category?: string | null;
  target_segments: string[];
  target_geography?: Record<string, unknown> | null;
  intended_use_cases: string[];
  pricing_information: {
    is_specified: boolean;
    supplied_price?: string | null;
    currency?: string | null;
    price_is_conditional: boolean;
    pricing_status: string;
  };
}

export interface PromisingFinding {
  finding_id: string;
  claim_or_hypothesis: string;
  category: string;
  relevant_segments: string[];
  supporting_persona_ids: string[];
  supporting_evidence_ids: string[];
  evidence_sources: string[];
  evidence_validation_status: EvidenceStatus;
  rationale: string;
  caveats_and_assumptions: string[];
  suggested_real_world_validation: string;
}

export interface RiskOrBarrierFinding {
  finding_id: string;
  concern_or_barrier: string;
  barrier_category: string;
  relevant_segments: string[];
  reporting_persona_ids: string[];
  contradicting_or_supporting_evidence_ids: string[];
  evidence_sources: string[];
  evidence_validation_status: EvidenceStatus;
  rationale: string;
  caveats: string[];
  suggested_mitigation_or_test: string;
}

export interface SegmentComparisonItem {
  segment_name: string;
  persona_count: number;
  evaluated_personas_count: number;
  median_scores: {
    interest?: number | null;
    purchase_intent?: number | null;
    perceived_value?: number | null;
    affordability?: number | null;
    adoption_barrier?: number | null;
    [key: string]: number | null | undefined;
  };
  valued_features: string[];
  main_concerns: string[];
  affordability_and_adoption_summary: string;
  relevant_evidence_ids: string[];
  important_evidence_gaps: string[];
  suggested_validation_experiment: string;
}

export interface PrioritizedFeatureHypothesis {
  feature_name: string;
  positive_mentions_count: number;
  negative_mentions_count: number;
  persona_ids: string[];
  segment_distribution: string[];
  evidence_validation_status: EvidenceStatus;
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  priority_tier: string;
  main_uncertainty: string;
  suggested_next_validation_step: string;
}

export interface PricingAndAffordabilityReport {
  supplied_price?: string | null;
  currency?: string | null;
  pricing_status: string;
  price_is_conditional: boolean;
  simulated_affordability_summary: string;
  contextual_earnings_evidence?: {
    location?: string;
    regular_salaried_avg_inr?: number;
    regular_wage_mean?: number;
    [key: string]: unknown;
  } | null;
  unresolved_pricing_questions: string[];
  recommended_wtp_experiment: string;
}

export interface EvidenceTraceabilityItem {
  evidence_id: string;
  source_type: string;
  source_title: string;
  geography?: Record<string, unknown> | null;
  observation_period?: string | null;
  factual_summary: string;
  caveats_and_limitations: string[];
  findings_supported: string[];
  findings_contradicted: string[];
}

export interface DisagreementItem {
  topic: string;
  relevant_segments_or_personas: Record<string, unknown>;
  observed_spread_or_difference: string;
  plausible_explanation: string;
  is_observed_or_hypothesized: string;
  evidence_needed_to_resolve: string;
}

export interface EvidenceCoverageReport {
  total_findings_evaluated: number;
  supported_count: number;
  contradicted_count: number;
  mixed_count: number;
  insufficient_evidence_count: number;
  not_applicable_count: number;
  evidence_coverage_ratio: number;
  coverage_formula_explanation: string;
  sources_represented: string[];
  unsupported_assumptions: string[];
  unresolved_pricing_assumptions: string[];
  important_evidence_gaps: string[];
}

export interface RecommendedExperiment {
  recommendation_id: string;
  question_to_validate: string;
  target_segment: string;
  strategic_rationale: string;
  supporting_finding_ids: string[];
  suggested_experiment_type: string;
  measurement_metric: string;
  decision_rule_hypothesis: string;
  experiment_limitations: string;
}

export interface ResearchQuestionAnswer {
  question: string;
  answer: string;
  basis: AnswerBasis;
  supporting_sources: string[];
  assumptions: string[];
  confidence: string;
  limitations: string[];
  requires_external_validation: boolean;
}

export interface MarketValidationReport {
  report_id: string;
  generated_at: string;
  executive_summary: ExecutiveSummary;
  idea_and_context: IdeaAndMarketContext;
  what_appears_promising: PromisingFinding[];
  what_may_not_work: RiskOrBarrierFinding[];
  segment_comparison: SegmentComparisonItem[];
  feature_prioritization: PrioritizedFeatureHypothesis[];
  pricing_and_affordability: PricingAndAffordabilityReport;
  evidence_traceability: EvidenceTraceabilityItem[];
  disagreement_and_uncertainty: DisagreementItem[];
  evidence_coverage_audit: EvidenceCoverageReport;
  recommended_experiments: RecommendedExperiment[];
  research_questions_analysis?: ResearchQuestionAnswer[];
  diagnostics?: Record<string, unknown>;
}

export interface PersonaProblem {
  problem: string;
  whyItMatters: string;
}

export interface PersonaProfile {
  persona_id: string;
  name: string;
  occupation: string;
  segment: string;
  location?: string;
  avatarSeed?: string;
  avatarVariant?: number;
  genderHint?: 'male' | 'female' | 'neutral';
  customer_description: string;
  situation: string;
  top_problems: PersonaProblem[];
  desired_features: string[];
  main_objection: string;
  proposed_solutions: string[];
  pricing_concerns: string;
  rejection_reasons: string[];
  supporting_evidence: { id: string; source: string; text: string }[];
  validation_questions: string[];
  scores: {
    interest_score: number;
    simulated_purchase_intent: number;
    perceived_value_score: number;
    affordability_score: number;
    adoption_barrier_score: number;
  };
  price_is_conditional?: boolean;
}

export type AnalysisRunStatus = 'completed' | 'completed_with_failures' | 'failed' | 'running';

export interface AnalysisRunRecord {
  id: string;
  idea: string;
  geography?: string | null;
  timestamp: string;
  status: AnalysisRunStatus;
  evidenceCoverageRatio: number;
  supportedFindingsCount: number;
  totalFindingsCount: number;
  report?: MarketValidationReport | null;
}
