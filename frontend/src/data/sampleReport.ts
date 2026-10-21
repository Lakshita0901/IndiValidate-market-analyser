import { MarketValidationReport } from '../types';

export const SAMPLE_MARKET_REPORT: MarketValidationReport = {
  report_id: "MVR-5AA04EFD",
  generated_at: "2026-Q1-Pipeline-Evaluation",
  executive_summary: {
    idea_description: "Smart EV fleet charging hub and reservation software in Ahmedabad with peak-shaving power storage",
    target_customer_segments: ["Commercial EV fleet operators", "Last-mile logistics dispatchers"],
    strongest_promising_signals: [
      "[PROMISING-1] Guaranteed charging slot booking reduces driver idle queue downtime by up to 80 minutes daily.",
      "[PROMISING-2] Centralized telemetry and fleet billing streamlines operational accounting across 5-50 vehicles.",
      "[PROMISING-3] Strong interest in dedicated commercial charging depots away from congested retail public stalls."
    ],
    key_risks_and_barriers: [
      "[RISK-1] Switching inertia from existing diesel generator backups and familiar public station credit cards.",
      "[RISK-2] High price sensitivity if charging markups exceed current retail tariffs without proven uptime SLA.",
      "[RISK-3] Hardware vendor lock-in and charger connector standardization risks across mixed fleets."
    ],
    critical_unresolved_questions: [
      "Will fleet managers accept a monthly SaaS seat subscription, or require purely usage-based kWh billing?",
      "Real-world charging queue tolerance thresholds during morning and evening rush hour turnaround windows."
    ],
    next_validation_priority: "Conduct 10 in-depth discovery interviews with commercial fleet dispatchers in Naroda & Changodar (EXP-1) before deploying physical hardware."
  },
  idea_and_context: {
    business_idea: "Smart EV fleet charging hub and reservation software in Ahmedabad with peak-shaving power storage",
    business_category: "Clean Transportation & B2B SaaS",
    target_segments: ["Commercial EV fleet operators", "Last-mile delivery fleets"],
    target_geography: {
      state: "Gujarat",
      district: "Ahmedabad",
      level: "district"
    },
    intended_use_cases: [
      "Arjun (E-commerce delivery van driver): Needs predictable 30-minute midday top-up along Sarkhej-Gandhinagar highway without queuing behind private cars.",
      "Priya (Fleet operations manager, 18 vans): Needs centralized monthly GST invoicing, battery health monitoring, and guaranteed dawn charger readiness.",
      "Rajesh (B2B logistics owner): Conservative on digital tools; demands 99.5% uptime guarantee and emergency diesel backup before signing exclusive charging contract.",
      "Meena (Grocery dark-store logistics director): Requires automated API scheduling between warehouse dispatch ERP and charging bay reservation system."
    ],
    pricing_information: {
      is_specified: true,
      supplied_price: "3,000",
      currency: "INR",
      price_is_conditional: false,
      pricing_status: "Specified in proposal: INR 3,000/month per vehicle (plus grid electricity at cost)"
    }
  },
  what_appears_promising: [
    {
      finding_id: "PROMISING-1",
      claim_or_hypothesis: "Slot reservation directly eliminates 45-90 minutes of daily queuing friction for time-critical commercial fleets.",
      category: "workflow_efficiency",
      relevant_segments: ["Commercial EV fleet operators"],
      supporting_persona_ids: ["persona_1", "persona_2", "persona_4", "persona_5", "persona_7", "persona_9"],
      supporting_evidence_ids: ["CHUNK-REDDIT-EV-102", "CHUNK-TRENDS-EV-04"],
      evidence_sources: ["reddit", "google_trends"],
      evidence_validation_status: "supported",
      rationale: "Community discussions in Reddit EV forums emphasize that public charger unreliability and queues represent the single largest operational obstacle to fleet electrification.",
      caveats_and_assumptions: ["Assumes hub operator can enforce parking bay discipline and penalize overstaying vehicles."],
      suggested_real_world_validation: "Test reservation deposit mechanism with 5 local delivery fleets."
    },
    {
      finding_id: "PROMISING-2",
      claim_or_hypothesis: "Fleet telematics and centralized GST invoicing reduce administrative overhead for multi-vehicle operators.",
      category: "feature",
      relevant_segments: ["Last-mile delivery fleets"],
      supporting_persona_ids: ["persona_2", "persona_3", "persona_6", "persona_8"],
      supporting_evidence_ids: [],
      evidence_sources: [],
      evidence_validation_status: "insufficient_evidence",
      rationale: "Synthesized persona praise indicates high perceived value, though empirical invoice processing metrics have not been externally audited.",
      caveats_and_assumptions: ["Fleet operators must possess digital invoicing workflows to capture this benefit."],
      suggested_real_world_validation: "Present mock invoicing dashboard during founder discovery interviews."
    }
  ],
  what_may_not_work: [
    {
      finding_id: "RISK-1",
      concern_or_barrier: "High upfront onboarding friction and unwillingness to pay fixed SaaS fees prior to verifying charger uptime.",
      barrier_category: "pricing_and_affordability",
      relevant_segments: ["Commercial EV fleet operators"],
      reporting_persona_ids: ["persona_3", "persona_5", "persona_8"],
      contradicting_or_supporting_evidence_ids: ["CHUNK-PLFS-GUJ-2025"],
      evidence_sources: ["plfs_2025"],
      evidence_validation_status: "mixed",
      rationale: "PLFS wage benchmarks reflect tight operating margins for commercial drivers, leaving little room for redundant overhead.",
      caveats: ["Fixed monthly fees may require flexible volume discounts or usage-only introductory waivers."],
      suggested_mitigation_or_test: "Offer zero-fixed-fee pilot for the first 60 days with pay-per-kWh pricing."
    },
    {
      finding_id: "RISK-2",
      concern_or_barrier: "Grid transformer sanction delays and high capital cost of industrial battery peak-shaving units.",
      barrier_category: "operational_constraints",
      relevant_segments: ["Commercial EV fleet operators"],
      reporting_persona_ids: ["persona_7", "persona_10"],
      contradicting_or_supporting_evidence_ids: [],
      evidence_sources: [],
      evidence_validation_status: "insufficient_evidence",
      rationale: "Discom power load approvals in industrial zones typically face multi-month lead times.",
      caveats: ["Depends on municipal DISCOM policies and commercial tariff brackets."],
      suggested_mitigation_or_test: "Site initial hub adjacent to an existing industrial substation with pre-sanctioned 500kVA load."
    }
  ],
  segment_comparison: [
    {
      segment_name: "Urban Delivery Fleets (5-20 Vehicles)",
      persona_count: 5,
      evaluated_personas_count: 5,
      median_scores: {
        interest: 8.5,
        purchase_intent: 7.2,
        perceived_value: 8.0,
        affordability: 6.5,
        adoption_barrier: 4.2
      },
      valued_features: ["Guaranteed slot booking", "Fast 60kW DC charging", "Unified fleet dashboard"],
      main_concerns: ["SaaS monthly overhead", "Location convenience along delivery corridors"],
      affordability_and_adoption_summary: "High operational urgency to replace diesel queues; moderate price sensitivity mitigated by fuel savings.",
      relevant_evidence_ids: ["CHUNK-REDDIT-EV-102"],
      important_evidence_gaps: ["Exact route density data in Ahmedabad East industrial belt."],
      suggested_validation_experiment: "Run a 14-day WhatsApp reservation concierge pilot with 3 Naroda courier services."
    },
    {
      segment_name: "Independent Commercial EV Drivers",
      persona_count: 5,
      evaluated_personas_count: 5,
      median_scores: {
        interest: 6.8,
        purchase_intent: 4.5,
        perceived_value: 6.0,
        affordability: 4.0,
        adoption_barrier: 7.5
      },
      valued_features: ["Transparent per-unit pricing", "Clean driver rest area"],
      main_concerns: ["Upfront subscription costs", "No corporate expense reimbursement"],
      affordability_and_adoption_summary: "High barrier to any fixed fee; strongly prefer ad-hoc pay-as-you-go charging without apps.",
      relevant_evidence_ids: ["CHUNK-PLFS-GUJ-2025"],
      important_evidence_gaps: ["Daily take-home earnings distribution among self-employed EV cab drivers."],
      suggested_validation_experiment: "Conduct Van Westendorp pricing sensitivity questionnaire at high-traffic public fast chargers."
    }
  ],
  feature_prioritization: [
    {
      feature_name: "Guaranteed Bay Reservation System",
      positive_mentions_count: 8,
      negative_mentions_count: 0,
      persona_ids: ["persona_1", "persona_2", "persona_4", "persona_5", "persona_6", "persona_7", "persona_9", "persona_10"],
      segment_distribution: ["Urban Delivery Fleets", "Independent Commercial EV Drivers"],
      evidence_validation_status: "supported",
      supporting_evidence_ids: ["CHUNK-REDDIT-EV-102"],
      contradicting_evidence_ids: [],
      priority_tier: "High Priority Candidate",
      main_uncertainty: "How to handle and penalize late arrivals without frustrating commercial route schedules.",
      suggested_next_validation_step: "Test 15-minute slot grace period rules in prototype user flows."
    },
    {
      feature_name: "Fleet Battery Telematics & State of Health Reports",
      positive_mentions_count: 6,
      negative_mentions_count: 1,
      persona_ids: ["persona_2", "persona_3", "persona_6", "persona_8"],
      segment_distribution: ["Urban Delivery Fleets"],
      evidence_validation_status: "insufficient_evidence",
      supporting_evidence_ids: [],
      contradicting_evidence_ids: [],
      priority_tier: "Controversial / Needs Revision",
      main_uncertainty: "Requires OBD-II hardware dongles or proprietary OEM vehicle API access.",
      suggested_next_validation_step: "Assess if OBD hardware costs exceed customer willingness to pay."
    }
  ],
  pricing_and_affordability: {
    supplied_price: "3,000",
    currency: "INR",
    pricing_status: "Specified in proposal: INR 3,000/month per vehicle",
    price_is_conditional: false,
    simulated_affordability_summary: "Simulated affordability median is 5.5/10 across commercial operators. For fleet owners, INR 3,000/mo is justified if it saves >2 hours of downtime weekly; for individual owner-drivers, it represents a substantial barrier.",
    contextual_earnings_evidence: {
      location: "Urban Gujarat",
      regular_salaried_avg_inr: 24500,
      regular_wage_mean: 24500
    },
    unresolved_pricing_questions: [
      "Will operators accept fixed monthly subscription or demand purely usage-based kWh markups?",
      "Can electricity volume discounts be passed through to anchor fleet accounts?"
    ],
    recommended_wtp_experiment: "Van Westendorp Price Sensitivity Survey with 15 fleet operations managers."
  },
  evidence_traceability: [
    {
      evidence_id: "CHUNK-PLFS-GUJ-2025",
      source_type: "plfs_2025",
      source_title: "PLFS 2025 Urban Regular Salaried Labour Survey",
      geography: { state: "Gujarat", tru: "Urban" },
      observation_period: "2024-2025",
      factual_summary: "Average regular salaried monthly earnings in urban Gujarat benchmarked at Rs. 24,500/month.",
      caveats_and_limitations: ["Macroeconomic labour aggregate; does not isolate EV fleet logistics owners."],
      findings_supported: ["RISK-1"],
      findings_contradicted: []
    },
    {
      evidence_id: "CHUNK-REDDIT-EV-102",
      source_type: "reddit",
      source_title: "Commercial Fleet Fast Charging Discussions",
      observation_period: "2024-2025",
      factual_summary: "Fleet operators highlight frequent 45-120 minute queue delays at public stations as a primary reason for slow EV adoption.",
      caveats_and_limitations: ["Qualitative user posts; geographic coverage varies."],
      findings_supported: ["PROMISING-1"],
      findings_contradicted: []
    }
  ],
  disagreement_and_uncertainty: [
    {
      topic: "Pricing Structure: Fixed SaaS Subscription vs Pay-As-You-Charge",
      relevant_segments_or_personas: {
        "Corporate Fleets": "Favor predictable fixed billing with SLA guarantees",
        "Independent Operators": "Vehemently oppose monthly subscriptions without immediate liquidity"
      },
      observed_spread_or_difference: "Affordability divergence: 6.5/10 vs 4.0/10",
      plausible_explanation: "Disparity in cash-flow predictability and ability to pass administrative costs to clients.",
      is_observed_or_hypothesized: "Observed Empirical Fact",
      evidence_needed_to_resolve: "Structured enterprise contracts review with Tier-2 fleet operators."
    }
  ],
  evidence_coverage_audit: {
    total_findings_evaluated: 6,
    supported_count: 2,
    contradicted_count: 0,
    mixed_count: 2,
    insufficient_evidence_count: 2,
    not_applicable_count: 0,
    evidence_coverage_ratio: 0.67,
    coverage_formula_explanation: "(supported + contradicted + mixed) / max(1, total_findings). Coverage ratio measures empirical data availability, NOT market viability.",
    sources_represented: ["plfs_2025", "reddit", "google_trends"],
    unsupported_assumptions: [
      "Assumption that municipal DISCOM will approve 500kVA commercial connection within 60 days.",
      "Assumption that fleet drivers will respect allocated 30-minute charging time windows."
    ],
    unresolved_pricing_assumptions: [
      "Anchor fleet willingness to prepay 3 months of reservation slots."
    ],
    important_evidence_gaps: [
      "Local power discom substation capacity in Ahmedabad Changodar & Naroda industrial zones.",
      "Commercial tariff rates for high-tension battery swap and fast-charge depots."
    ]
  },
  recommended_experiments: [
    {
      recommendation_id: "EXP-1",
      question_to_validate: "Do commercial EV fleet dispatchers actively seek dedicated reservation hubs or does existing depot charging suffice?",
      target_segment: "Commercial EV fleet operators",
      strategic_rationale: "Validates core problem urgency before investing in commercial property leases.",
      supporting_finding_ids: ["PROMISING-1", "RISK-1"],
      suggested_experiment_type: "Customer Discovery Interviews",
      measurement_metric: "8 of 10 interviewed dispatchers report losing >1 billable trip per day due to charging queues.",
      decision_rule_hypothesis: "If >= 60% report acute route downtime, proceed with site selection pilot.",
      experiment_limitations: "Interviews reveal stated preference, not actual paid contract commitments."
    },
    {
      recommendation_id: "EXP-2",
      question_to_validate: "What is the acceptable price ceiling for reserved 60kW fast charging during peak dispatch hours?",
      target_segment: "Commercial EV fleet operators",
      strategic_rationale: "Determines whether premium slot booking fees cover industrial battery energy storage amortization.",
      supporting_finding_ids: ["RISK-1"],
      suggested_experiment_type: "Van Westendorp Price Sensitivity Survey & Landing Page Smoke Test",
      measurement_metric: "Optimum price point (OPP) for reservation fee per session.",
      decision_rule_hypothesis: "OPP exceeds INR 150/session on top of base electricity cost.",
      experiment_limitations: "Survey responses may reflect tactical bargaining behavior."
    }
  ],
  research_questions_analysis: [
    {
      question: "What is the core customer problem, and what indicates real market demand or urgency?",
      answer: "Commercial delivery fleets operate under tight delivery turnaround deadlines. When drivers queue at public chargers, every minute spent waiting is lost delivery revenue. Empirical community evidence from Reddit confirms recurring 45-120 minute queue delays at public stations, establishing acute operational urgency for reserved charging.",
      basis: "retrieved_evidence",
      supporting_sources: ["reddit", "google_trends"],
      assumptions: [
        "Fleet schedules are tightly bound to e-commerce dispatch windows.",
        "Public charging station density in Ahmedabad remains insufficient for commercial vehicle volume."
      ],
      confidence: "High - Corroborated by authentic community discussions and search trend volume.",
      limitations: ["Reddit discussions represent qualitative operator sentiment rather than a census of all fleet types."],
      requires_external_validation: false
    },
    {
      question: "What existing alternatives, incumbents, or workarounds do customers currently rely on?",
      answer: "Operators currently rely on two primary workarounds: (1) slow overnight AC charging at private leased yards, which limits daytime vehicle range, and (2) ad-hoc reliance on public fast chargers during lulls. In emergencies, some depot managers maintain backup diesel generator sets for slow charging.",
      basis: "mixed",
      supporting_sources: ["reddit"],
      assumptions: [
        "Overnight depot charging cannot accommodate double-shift delivery operations.",
        "Diesel generators are economically unsustainable as primary charging power."
      ],
      confidence: "Moderate - Combines community workaround reports with operational cost models.",
      limitations: ["Prevalence of industrial diesel generator use is estimated from qualitative feedback."],
      requires_external_validation: true
    },
    {
      question: "What are the willingness-to-pay dynamics and realistic pricing considerations for this offering?",
      answer: "PLFS 2025 benchmarks indicate an urban regular salaried wage mean of INR 24,500/month in Gujarat. For commercial fleet operators, a software fee of INR 3,000/month per vehicle represents ~12% of a driver's base labor cost. This is economically viable only if the service demonstrably recaptures >15 hours of idle driver time monthly.",
      basis: "mixed",
      supporting_sources: ["plfs_2025"],
      assumptions: [
        "Fleet managers calculate software ROI in terms of vehicle uptime and driver billable hours.",
        "Individual owner-drivers will reject fixed monthly subscription tiers."
      ],
      confidence: "Moderate - Grounded in official PLFS labour statistics; willingness to pay remains a hypothesis.",
      limitations: ["Macroeconomic labour benchmarks do not measure corporate logistics software willingness to pay."],
      requires_external_validation: true
    },
    {
      question: "What are the most critical customer adoption barriers, switching costs, or operational risks?",
      answer: "The primary barriers are: (1) switching inertia from existing charging supplier contracts, (2) technical trust in the reservation system to guarantee a functioning bay upon arrival, and (3) discom approval delays for industrial high-voltage power connections.",
      basis: "model_knowledge",
      supporting_sources: [],
      assumptions: [
        "B2B logistics operators have established billing arrangements with existing retail charge point operators.",
        "Discom power sanctions in Gujarat industrial corridors require 3-6 months lead time."
      ],
      confidence: "Moderate - Derived from standard logistics infrastructure and B2B utility procurement patterns.",
      limitations: [
        "Live discom transformer lead times could not be verified from public empirical data.",
        "Requires real-world pilot verification with local Gujarat DISCOM."
      ],
      requires_external_validation: true
    },
    {
      question: "What demographic, geographic, or industry trends support or constrain adoption?",
      answer: "Rapid electrification mandates for e-commerce last-mile fleets (e.g. Swiggy, Zomato, Amazon, Flipkart) drive structural demand for commercial EV charging infrastructure in high-density logistics corridors around Ahmedabad. However, unorganized fleet operators with fewer than 5 vehicles face capital constraints.",
      basis: "model_knowledge",
      supporting_sources: [],
      assumptions: [
        "Last-mile commercial electrification targets will continue accelerating in Tier-1 and Tier-2 Indian hubs.",
        "Municipal clean air zones may prioritize commercial EV delivery access."
      ],
      confidence: "Moderate - Based on industry regulatory directions and logistics macro trends.",
      limitations: ["Specific municipal policy rollouts could not be verified in live state records."],
      requires_external_validation: true
    }
  ],
  diagnostics: {
    report_id: "MVR-5AA04EFD",
    has_market_analysis: true,
    total_personas: 10,
    total_evaluations: 10,
    status: "success",
    warnings: [],
    issues: []
  }
};
