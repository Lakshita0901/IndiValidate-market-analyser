import { MarketValidationReport } from '../types';

/**
 * Generate a clean, human-readable Markdown export of a MarketValidationReport,
 * adhering to the exact contract and formatting of the backend IndiValidate report.
 */
export function generateReportMarkdown(report: MarketValidationReport): string {
  const lines: string[] = [];

  const ideaTitle = report.idea_and_context?.business_idea || 'Market Analysis';
  lines.push(`# MARKET VALIDATION REPORT: ${ideaTitle.slice(0, 60)}...`);
  lines.push(`**Report ID**: \`${report.report_id}\` | **Status**: Verified Synthetic Simulation & Empirical Audit\n`);

  // 1. Executive Summary
  const es = report.executive_summary;
  if (es) {
    lines.push('## 1. Executive Summary');
    lines.push(`- **Evaluated Concept**: ${es.idea_description}`);
    lines.push(`- **Target Segments**: ${es.target_customer_segments?.join(', ') || 'General Target Market'}`);
    lines.push('\n### Strongest Promising Signals');
    for (const s of (es.strongest_promising_signals || []).slice(0, 4)) {
      lines.push(`- ${s}`);
    }
    lines.push('\n### Key Risks & Adoption Barriers');
    for (const r of (es.key_risks_and_barriers || []).slice(0, 4)) {
      lines.push(`- ${r}`);
    }
    lines.push('\n### Immediate Next Validation Priority');
    lines.push(`> ${es.next_validation_priority}\n`);
  }

  // 2. What Appears Promising
  const promising = report.what_appears_promising || [];
  if (promising.length > 0) {
    lines.push('## 2. What Appears Promising');
    for (const pf of promising.slice(0, 5)) {
      lines.push(`### [${pf.finding_id}] ${pf.claim_or_hypothesis}`);
      lines.push(`- **Category**: ${pf.category} | **Evidence Status**: \`${(pf.evidence_validation_status || 'unknown').toUpperCase()}\``);
      lines.push(`- **Relevant Segments**: ${pf.relevant_segments?.join(', ') || 'General'}`);
      lines.push(`- **Rationale**: ${pf.rationale}`);
      lines.push(`- **Next Test**: ${pf.suggested_real_world_validation}\n`);
    }
  }

  // 3. What May Not Work / Key Barriers
  const risks = report.what_may_not_work || [];
  if (risks.length > 0) {
    lines.push('## 3. What May Not Work / Key Barriers');
    for (const rf of risks.slice(0, 5)) {
      lines.push(`### [${rf.finding_id}] ${rf.concern_or_barrier}`);
      lines.push(`- **Category**: ${rf.barrier_category} | **Evidence Status**: \`${(rf.evidence_validation_status || 'unknown').toUpperCase()}\``);
      lines.push(`- **Relevant Segments**: ${rf.relevant_segments?.join(', ') || 'General'}`);
      lines.push(`- **Context**: ${rf.rationale}`);
      lines.push(`- **Mitigation/Test**: ${rf.suggested_mitigation_or_test}\n`);
    }
  }

  // 4. Segment Comparison Table
  const segments = report.segment_comparison || [];
  if (segments.length > 0) {
    lines.push('## 4. Segment Comparison');
    lines.push('| Segment | Personas (Synth) | Med. Interest | Med. Intent | Med. Affordability | Med. Barrier |');
    lines.push('| :--- | :---: | :---: | :---: | :---: | :---: |');
    for (const sc of segments) {
      const ms = sc.median_scores || {};
      const intScore = ms.interest !== undefined && ms.interest !== null ? `${ms.interest}/10` : '-';
      const intentScore = ms.purchase_intent !== undefined && ms.purchase_intent !== null ? `${ms.purchase_intent}/10` : '-';
      const affScore = ms.affordability !== undefined && ms.affordability !== null ? `${ms.affordability}/10` : '-';
      const barScore = ms.adoption_barrier !== undefined && ms.adoption_barrier !== null ? `${ms.adoption_barrier}/10` : '-';
      lines.push(`| ${sc.segment_name} | ${sc.evaluated_personas_count}/${sc.persona_count} | ${intScore} | ${intentScore} | ${affScore} | ${barScore} |`);
    }
    lines.push('\n*Note: Persona counts represent synthetic simulation allocations, NOT market share or conversion rates.*\n');
  }

  // 5. Feature Prioritization
  const features = report.feature_prioritization || [];
  if (features.length > 0) {
    lines.push('## 5. Feature Prioritization Hypotheses');
    for (const fp of features.slice(0, 6)) {
      lines.push(`- **${fp.feature_name}** (\`${fp.priority_tier}\`): +${fp.positive_mentions_count} / -${fp.negative_mentions_count} personas | Status: \`${fp.evidence_validation_status}\``);
      lines.push(`  *Uncertainty*: ${fp.main_uncertainty} (Next step: ${fp.suggested_next_validation_step})`);
    }
    lines.push('');
  }

  // 6. Pricing & Affordability
  const pa = report.pricing_and_affordability;
  if (pa) {
    lines.push('## 6. Pricing & Affordability Assessment');
    lines.push(`- **Pricing Status**: ${pa.pricing_status}`);
    if (pa.supplied_price) {
      lines.push(`- **Supplied Price**: ${pa.supplied_price} (${pa.currency || 'INR'})`);
    }
    lines.push(`- **Summary**: ${pa.simulated_affordability_summary}`);
    const bench = pa.contextual_earnings_evidence;
    if (bench) {
      const wage = bench.regular_salaried_avg_inr || bench.regular_wage_mean;
      lines.push(`- **Labour Benchmark (${bench.location || 'National'})**: Rs. ${wage ? Number(wage).toLocaleString() : 'N/A'}/month (Source: PLFS 2025)`);
      lines.push('  *CAVEAT: Income context does NOT establish willingness to pay.*');
    }
    lines.push(`- **Recommended Test**: ${pa.recommended_wtp_experiment}\n`);
  }

  // 7. Evidence Coverage Audit
  const ec = report.evidence_coverage_audit;
  if (ec) {
    lines.push('## 7. Evidence Coverage & Audit Metrics');
    lines.push(`- **Total Findings Evaluated**: ${ec.total_findings_evaluated}`);
    lines.push(`- **Evidence Coverage Ratio**: \`${(ec.evidence_coverage_ratio * 100).toFixed(0)}%\` (${ec.coverage_formula_explanation})`);
    lines.push(`- **Validation Breakdown**: Supported=${ec.supported_count}, Contradicted=${ec.contradicted_count}, Mixed=${ec.mixed_count}, Insufficient=${ec.insufficient_evidence_count}`);
    if (ec.sources_represented && ec.sources_represented.length > 0) {
      lines.push(`- **Active Evidence Sources**: ${ec.sources_represented.join(', ')}`);
    }
    lines.push('\n*Disclaimer: Coverage ratio is an empirical data audit measure, NOT a probability of startup success.*\n');
  }

  // 8. Recommended Real-World Validation Experiments
  const experiments = report.recommended_experiments || [];
  if (experiments.length > 0) {
    lines.push('## 8. Recommended Real-World Validation Experiments');
    for (const rx of experiments.slice(0, 4)) {
      lines.push(`### [${rx.recommendation_id}] ${rx.question_to_validate}`);
      lines.push(`- **Experiment Type**: ${rx.suggested_experiment_type} (Target: ${rx.target_segment})`);
      lines.push(`- **Strategic Value**: ${rx.strategic_rationale}`);
      lines.push(`- **Metric / Observation**: ${rx.measurement_metric}`);
      lines.push(`- **Decision Rule Hypothesis**: ${rx.decision_rule_hypothesis}\n`);
    }
  }

  // 9. Core Research Questions Analysis
  const rqas = report.research_questions_analysis || [];
  if (rqas.length > 0) {
    lines.push('## 9. Core Research Questions Analysis');
    for (let i = 0; i < rqas.length; i++) {
      const rqa = rqas[i];
      const sourcesStr = rqa.supporting_sources && rqa.supporting_sources.length > 0
        ? rqa.supporting_sources.join(', ')
        : 'None (Model Knowledge Fallback)';
      const hasValidSources = Boolean(rqa.supporting_sources && rqa.supporting_sources.length > 0);
      const validationStatus = (rqa.basis === 'retrieved_evidence' && hasValidSources && !rqa.requires_external_validation)
        ? 'Empirically Supported'
        : (rqa.basis === 'retrieved_evidence' && rqa.requires_external_validation)
        ? 'Empirical Signal (Field Validation Required)'
        : (rqa.basis === 'mixed')
        ? 'Mixed Signals (Data + Model Prior)'
        : 'Model Reasoning (External Validation Required)';

      lines.push(`### Q${i + 1}: ${rqa.question}`);
      lines.push(`- **Basis**: \`${rqa.basis}\` | **External Validation Required**: \`${rqa.requires_external_validation}\``);
      lines.push(`- **Validation Status**: \`${validationStatus}\``);
      lines.push(`- **Answer**: ${rqa.answer}`);
      lines.push(`- **Confidence**: ${rqa.confidence}`);
      lines.push(`- **Supporting Sources**: ${sourcesStr}`);
      if (rqa.assumptions && rqa.assumptions.length > 0) {
        lines.push('- **Assumptions**:');
        for (const a of rqa.assumptions) {
          lines.push(`  - ${a}`);
        }
      }
      if (rqa.limitations && rqa.limitations.length > 0) {
        lines.push('- **Limitations**:');
        for (const l of rqa.limitations) {
          lines.push(`  - ${l}`);
        }
      }
      lines.push('');
    }
  }

  return lines.join('\n');
}

/**
 * Trigger client-side file download of text/JSON data.
 */
export function downloadFile(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
