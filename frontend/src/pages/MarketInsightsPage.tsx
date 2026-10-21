import React, { useState } from 'react';
import {
  LineChart,
  ShieldCheck,
  AlertTriangle,
  Sparkles,
  HelpCircle,
  Database,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Brain,
  Layers,
  TrendingUp,
  Tag
} from 'lucide-react';
import { MarketValidationReport } from '../types';

interface MarketInsightsPageProps {
  report: MarketValidationReport | null;
  onNavigateToNew: () => void;
}

export const MarketInsightsPage: React.FC<MarketInsightsPageProps> = ({
  report,
  onNavigateToNew,
}) => {
  const [activeTab, setActiveTab] = useState<'questions' | 'coverage' | 'findings' | 'features' | 'pricing'>('questions');

  if (!report) {
    return (
      <div className="bg-[#FFFFFF] border border-dashed border-[#E7DAD8] rounded-2xl p-12 text-center max-w-lg mx-auto">
        <LineChart className="w-12 h-12 text-[#B66B70] mx-auto mb-3 opacity-60" />
        <h3 className="text-xl font-bold text-[#302629] mb-1">No Market Insights Available</h3>
        <p className="text-sm text-[#78696B] mb-5 leading-relaxed">
          Run an analysis or load the sample benchmark to inspect empirical evidence coverage and research question analysis.
        </p>
        <button
          onClick={onNavigateToNew}
          className="px-5 py-2.5 bg-[#873F46] hover:bg-[#873F46]/90 text-[#FFFFFF] rounded-xl text-xs font-bold shadow-xs transition-colors"
        >
          Start New Validation
        </button>
      </div>
    );
  }

  const cov = report.evidence_coverage_audit;
  const rqas = report.research_questions_analysis || [];
  const promising = report.what_appears_promising || [];
  const risks = report.what_may_not_work || [];
  const features = report.feature_prioritization || [];
  const pa = report.pricing_and_affordability;
  const disagreements = report.disagreement_and_uncertainty || [];

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'supported':
        return (
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-[#EDF6F0] text-[#3E7B54] border border-[#3E7B54]/20 flex items-center gap-1">
            <CheckCircle2 size={13} />
            Corroborated by Evidence
          </span>
        );
      case 'contradicted':
        return (
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-[#F4E9E7] text-[#873F46] border border-[#873F46]/30 flex items-center gap-1">
            <XCircle size={13} />
            Contradicted by Evidence
          </span>
        );
      case 'mixed':
        return (
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-[#FAF2EA] text-[#C06E22] border border-[#C06E22]/30 flex items-center gap-1">
            <AlertCircle size={13} />
            Mixed Empirical Signals
          </span>
        );
      case 'insufficient_evidence':
      default:
        return (
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-[#F7F4F2] text-[#78696B] border border-[#E7DAD8] flex items-center gap-1">
            <HelpCircle size={13} />
            Needs more evidence
          </span>
        );
    }
  };

  const getQuestionValidationBadge = (rqa: {
    basis: string;
    supporting_sources?: string[];
    requires_external_validation: boolean;
  }) => {
    const hasValidSources = Boolean(rqa.supporting_sources && rqa.supporting_sources.length > 0);

    // "Empirically Supported" appears ONLY when basis is retrieved_evidence, has verified sources, and requires no external validation
    if (rqa.basis === 'retrieved_evidence' && hasValidSources && !rqa.requires_external_validation) {
      return (
        <span className="text-xs font-bold px-3 py-1 rounded-full border bg-[#EDF6F0] text-[#3E7B54] border-[#3E7B54]/20 flex items-center gap-1">
          <CheckCircle2 size={12} />
          <span>Empirically Supported</span>
        </span>
      );
    }

    if (rqa.basis === 'retrieved_evidence' && rqa.requires_external_validation) {
      return (
        <span className="text-xs font-bold px-3 py-1 rounded-full border bg-[#FAF2EA] text-[#C06E22] border-[#C06E22]/30 flex items-center gap-1">
          <HelpCircle size={12} />
          <span>Empirical Signal (Needs Field Validation)</span>
        </span>
      );
    }

    if (rqa.basis === 'mixed') {
      return (
        <span className="text-xs font-bold px-3 py-1 rounded-full border bg-[#FAF2EA] text-[#C06E22] border-[#C06E22]/30 flex items-center gap-1">
          <AlertCircle size={12} />
          <span>Mixed Signals (Data + Model Prior)</span>
        </span>
      );
    }

    // model_knowledge or missing sources
    return (
      <span className="text-xs font-bold px-3 py-1 rounded-full border bg-[#F4E9E7] text-[#873F46] border-[#873F46]/30 flex items-center gap-1">
        <Brain size={12} />
        <span>Model Reasoning (Needs Field Validation)</span>
      </span>
    );
  };

  const getBasisBadge = (basis: string) => {
    switch (basis) {
      case 'retrieved_evidence':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#EDF6F0] text-[#3E7B54] border border-[#3E7B54]/20">
            <Database size={13} className="text-[#3E7B54]" />
            <span>Retrieved Evidence</span>
          </span>
        );
      case 'mixed':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#FAF2EA] text-[#C06E22] border border-[#C06E22]/30">
            <Layers size={13} className="text-[#C06E22]" />
            <span>Mixed Signals (Data + Model Prior)</span>
          </span>
        );
      case 'model_knowledge':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#F4E9E7] text-[#873F46] border border-[#873F46]/20">
            <Brain size={13} className="text-[#873F46]" />
            <span>Market Domain Reasoning</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Page Title & Context Header (30-32px title) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-[#E7DAD8]">
        <div>
          <h1 className="text-[30px] sm:text-[32px] font-extrabold text-[#302629] tracking-tight leading-tight">
            Market Insights &amp; Evidence Audit
          </h1>
          <p className="text-sm sm:text-[15px] text-[#78696B] mt-1">
            Empirical data coverage, feature prioritization hypotheses, pricing thresholds, and research question grounding.
          </p>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-[#E7DAD8] bg-[#FFFFFF] px-2 rounded-2xl shadow-2xs overflow-x-auto">
        {[
          { id: 'questions', label: `Core Research Questions (${rqas.length})`, icon: <Brain size={16} /> },
          { id: 'coverage', label: 'Evidence Coverage Audit', icon: <ShieldCheck size={16} /> },
          { id: 'findings', label: `Findings & Risks (${promising.length + risks.length})`, icon: <Sparkles size={16} /> },
          { id: 'features', label: `Feature Prioritization (${features.length})`, icon: <TrendingUp size={16} /> },
          { id: 'pricing', label: 'Pricing & Disagreements', icon: <Tag size={16} /> },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`flex items-center gap-2 px-5 py-4 text-xs font-bold whitespace-nowrap border-b-2 transition-all ${
              activeTab === tab.id
                ? 'border-[#873F46] text-[#873F46] bg-[#F4E9E7]/40'
                : 'border-transparent text-[#78696B] hover:text-[#302629] hover:bg-[#F7F4F2]'
            }`}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* TAB 1: Core Research Questions Analysis */}
      {activeTab === 'questions' && (
        <div className="space-y-6">
          <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-5 shadow-xs">
            <div className="flex items-start gap-3 text-sm text-[#78696B]">
              <HelpCircle className="w-5 h-5 text-[#873F46] shrink-0 mt-0.5" />
              <div>
                <span className="font-bold text-[#302629] text-base block mb-0.5">
                  LLM-Native Fallback &amp; Evidence Grounding Engine
                </span>
                <p className="text-sm leading-relaxed text-[#78696B]">
                  When external sources return no data, core validation dimensions are evaluated using transparent market reasoning rather than leaving blind spots. Every finding clearly declares whether it is backed by empirical citations or model reasoning.
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-5">
            {rqas.map((rqa, i) => (
              <div
                key={i}
                className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 sm:p-7 shadow-xs space-y-4 hover:border-[#B66B70]/40 transition-all"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E7DAD8] pb-4">
                  <div className="flex items-center gap-3">
                    <span className="w-7 h-7 rounded-xl bg-[#F4E9E7] text-[#873F46] text-xs font-bold flex items-center justify-center shrink-0">
                      Q{i + 1}
                    </span>
                    <h3 className="text-lg sm:text-[19px] font-bold text-[#302629] leading-snug">
                      {rqa.question}
                    </h3>
                  </div>
                  <div className="flex items-center gap-2 self-start sm:self-auto shrink-0 flex-wrap">
                    {getBasisBadge(rqa.basis)}
                    {getQuestionValidationBadge(rqa)}
                  </div>
                </div>

                {/* Answer Content (16-18px body) */}
                <div className="text-base text-[#302629] leading-relaxed bg-[#F7F4F2] p-5 rounded-xl border border-[#E7DAD8]">
                  {rqa.answer}
                </div>

                {/* Metadata Grid (14-15px supporting text) */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm pt-1">
                  {/* Sources */}
                  <div className="space-y-1.5">
                    <span className="font-bold text-[#78696B] text-xs uppercase tracking-wider block">
                      Supporting Sources
                    </span>
                    {rqa.supporting_sources && rqa.supporting_sources.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {rqa.supporting_sources.map((src, idx) => (
                          <span
                            key={idx}
                            className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-[#F4E9E7] text-[#873F46] border border-[#B66B70]/20"
                          >
                            {src}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-[#78696B] text-sm italic">
                        None (Synthesized Market Knowledge)
                      </span>
                    )}
                  </div>

                  {/* Confidence */}
                  <div className="space-y-1.5">
                    <span className="font-bold text-[#78696B] text-xs uppercase tracking-wider block">
                      Confidence Assessment
                    </span>
                    <p className="text-[#302629] text-sm leading-relaxed">
                      {rqa.confidence}
                    </p>
                  </div>

                  {/* Limitations */}
                  <div className="space-y-1.5">
                    <span className="font-bold text-[#78696B] text-xs uppercase tracking-wider block">
                      Critical Limitations
                    </span>
                    {rqa.limitations && rqa.limitations.length > 0 ? (
                      <ul className="text-sm text-[#78696B] list-disc list-inside space-y-1">
                        {rqa.limitations.slice(0, 2).map((lim, idx) => (
                          <li key={idx} className="truncate">{lim}</li>
                        ))}
                      </ul>
                    ) : (
                      <span className="text-[#78696B] text-sm">Standard domain constraints apply</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 2: Evidence Coverage Audit */}
      {activeTab === 'coverage' && cov && (
        <div className="space-y-6">
          <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 sm:p-8 shadow-xs space-y-6">
            <div>
              <h2 className="text-[22px] sm:text-2xl font-bold text-[#302629] mb-1">
                Empirical Evidence Coverage Audit
              </h2>
              <p className="text-sm text-[#78696B]">
                Formula: <code className="bg-[#F7F4F2] px-2 py-0.5 rounded border border-[#E7DAD8] text-xs font-mono">{cov.coverage_formula_explanation}</code>
              </p>
            </div>

            {/* Coverage Ratio Progress Bar */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between text-sm font-bold">
                <span className="text-[#302629]">Total Empirical Evidence Coverage Ratio</span>
                <span className="text-[#873F46] text-lg font-black">
                  {(cov.evidence_coverage_ratio * 100).toFixed(0)}%
                </span>
              </div>
              <div className="w-full bg-[#F7F4F2] border border-[#E7DAD8] rounded-full h-4 overflow-hidden flex p-0.5">
                <div
                  className="bg-[#3E7B54] h-full rounded-full transition-all duration-500"
                  style={{ width: `${(cov.supported_count / Math.max(1, cov.total_findings_evaluated)) * 100}%` }}
                  title={`Supported: ${cov.supported_count}`}
                />
                <div
                  className="bg-[#C06E22] h-full rounded-full transition-all duration-500"
                  style={{ width: `${(cov.mixed_count / Math.max(1, cov.total_findings_evaluated)) * 100}%` }}
                  title={`Mixed: ${cov.mixed_count}`}
                />
                <div
                  className="bg-[#873F46] h-full rounded-full transition-all duration-500"
                  style={{ width: `${(cov.contradicted_count / Math.max(1, cov.total_findings_evaluated)) * 100}%` }}
                  title={`Contradicted: ${cov.contradicted_count}`}
                />
              </div>
              <p className="text-xs text-[#78696B] italic">
                *Audit measure of empirical data corroboration across findings, NOT a commercial viability rate.
              </p>
            </div>

            {/* Breakdown Counts */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 pt-2">
              <div className="p-4 bg-[#F7F4F2] rounded-xl border border-[#E7DAD8] text-center">
                <span className="text-xs text-[#78696B] font-bold block mb-1">Total Evaluated</span>
                <span className="text-2xl font-black text-[#302629]">{cov.total_findings_evaluated}</span>
              </div>
              <div className="p-4 bg-[#EDF6F0] rounded-xl border border-[#3E7B54]/20 text-center">
                <span className="text-xs text-[#3E7B54] font-bold block mb-1">Corroborated</span>
                <span className="text-2xl font-black text-[#3E7B54]">{cov.supported_count}</span>
              </div>
              <div className="p-4 bg-[#FAF2EA] rounded-xl border border-[#C06E22]/20 text-center">
                <span className="text-xs text-[#C06E22] font-bold block mb-1">Mixed Signals</span>
                <span className="text-2xl font-black text-[#C06E22]">{cov.mixed_count}</span>
              </div>
              <div className="p-4 bg-[#F4E9E7] rounded-xl border border-[#873F46]/20 text-center">
                <span className="text-xs text-[#873F46] font-bold block mb-1">Contradicted</span>
                <span className="text-2xl font-black text-[#873F46]">{cov.contradicted_count}</span>
              </div>
              <div className="p-4 bg-[#F7F4F2] rounded-xl border border-[#E7DAD8] text-center">
                <span className="text-xs text-[#78696B] font-bold block mb-1">Needs Evidence</span>
                <span className="text-2xl font-black text-[#78696B]">{cov.insufficient_evidence_count}</span>
              </div>
            </div>

            {/* Represented Sources */}
            <div className="pt-2">
              <span className="text-sm font-bold text-[#302629] block mb-2.5">
                Active External Evidence Sources
              </span>
              <div className="flex flex-wrap gap-2">
                {cov.sources_represented && cov.sources_represented.length > 0 ? (
                  cov.sources_represented.map((src, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#F7F4F2] border border-[#E7DAD8] rounded-xl text-xs font-semibold text-[#302629]"
                    >
                      <Database size={14} className="text-[#873F46]" />
                      <span>{src.toUpperCase()}</span>
                    </span>
                  ))
                ) : (
                  <span className="text-sm text-[#78696B] italic">No external sources cited</span>
                )}
              </div>
            </div>

            {/* Important Data Gaps */}
            {cov.important_evidence_gaps && cov.important_evidence_gaps.length > 0 && (
              <div className="p-5 bg-[#FAF2EA]/40 rounded-xl border border-[#C06E22]/30 space-y-2">
                <span className="text-xs font-extrabold text-[#C06E22] uppercase tracking-wider block">
                  Identified Empirical Data Gaps
                </span>
                <ul className="list-disc list-inside text-sm text-[#78696B] space-y-1.5">
                  {cov.important_evidence_gaps.map((gap, idx) => (
                    <li key={idx}>{gap}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: Promising Findings & Risks */}
      {activeTab === 'findings' && (
        <div className="space-y-8">
          {/* Promising Findings */}
          <div className="space-y-4">
            <h2 className="text-[22px] font-bold text-[#302629] flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-[#3E7B54]" />
              <span>Promising Value Hypotheses ({promising.length})</span>
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {promising.map((pf) => (
                <div
                  key={pf.finding_id}
                  className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 shadow-xs space-y-3 hover:border-[#3E7B54]/40 transition-all"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-mono text-xs font-bold text-[#873F46] bg-[#F4E9E7] px-2.5 py-1 rounded-md">
                      {pf.finding_id}
                    </span>
                    {getStatusBadge(pf.evidence_validation_status)}
                  </div>
                  <h3 className="text-lg font-bold text-[#302629] leading-snug">
                    {pf.claim_or_hypothesis}
                  </h3>
                  <p className="text-sm sm:text-[15px] text-[#78696B] leading-relaxed">
                    {pf.rationale}
                  </p>
                  <div className="p-3.5 bg-[#EDF6F0]/60 rounded-xl text-xs text-[#3E7B54] border border-[#3E7B54]/20">
                    <span className="font-bold block mb-1">Recommended Field Validation:</span>
                    <span>{pf.suggested_real_world_validation}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Risks and Barriers */}
          <div className="space-y-4 pt-4 border-t border-[#E7DAD8]">
            <h2 className="text-[22px] font-bold text-[#302629] flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-[#C06E22]" />
              <span>Identified Risks &amp; Friction Points ({risks.length})</span>
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {risks.map((rf) => (
                <div
                  key={rf.finding_id}
                  className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 shadow-xs space-y-3 hover:border-[#C06E22]/40 transition-all"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-mono text-xs font-bold text-[#873F46] bg-[#F4E9E7] px-2.5 py-1 rounded-md">
                      {rf.finding_id}
                    </span>
                    {getStatusBadge(rf.evidence_validation_status)}
                  </div>
                  <h3 className="text-lg font-bold text-[#302629] leading-snug">
                    {rf.concern_or_barrier}
                  </h3>
                  <div className="text-xs text-[#78696B] font-semibold">
                    Category: <span className="text-[#302629] uppercase">{rf.barrier_category.replace(/_/g, ' ')}</span>
                  </div>
                  <p className="text-sm sm:text-[15px] text-[#78696B] leading-relaxed">
                    {rf.rationale}
                  </p>
                  <div className="p-3.5 bg-[#FAF2EA] rounded-xl text-xs text-[#C06E22] border border-[#C06E22]/20">
                    <span className="font-bold block mb-1">Mitigation Strategy:</span>
                    <span>{rf.suggested_mitigation_or_test}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: Feature Prioritization */}
      {activeTab === 'features' && (
        <div className="space-y-5">
          <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 shadow-xs">
            <h2 className="text-[22px] font-bold text-[#302629] mb-1">
              Transparent Feature Priority Tiers
            </h2>
            <p className="text-sm text-[#78696B]">
              Classified by distinct persona mentions: High Priority (≥2 positive, 0 negative), Controversial (&gt;0 pos and &gt;0 neg), or Secondary.
            </p>
          </div>

          <div className="space-y-4">
            {features.map((feat, idx) => (
              <div
                key={idx}
                className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-5 hover:border-[#B66B70]/40 transition-all"
              >
                <div className="space-y-2 flex-1">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span
                      className={`text-xs font-bold px-3 py-1 rounded-full border ${
                        feat.priority_tier.includes('High')
                          ? 'bg-[#EDF6F0] text-[#3E7B54] border-[#3E7B54]/20'
                          : feat.priority_tier.includes('Controversial')
                          ? 'bg-[#FAF2EA] text-[#C06E22] border-[#C06E22]/30'
                          : 'bg-[#F7F4F2] text-[#78696B] border-[#E7DAD8]'
                      }`}
                    >
                      {feat.priority_tier}
                    </span>
                    <h3 className="text-lg font-bold text-[#302629]">
                      {feat.feature_name}
                    </h3>
                  </div>
                  <p className="text-sm text-[#78696B] leading-relaxed">
                    <strong className="text-[#302629]">Main Uncertainty:</strong> {feat.main_uncertainty}
                  </p>
                  <p className="text-xs text-[#78696B]">
                    <strong className="text-[#873F46]">Next Step:</strong> {feat.suggested_next_validation_step}
                  </p>
                </div>

                <div className="flex items-center gap-4 shrink-0 self-start sm:self-auto">
                  <div className="text-right">
                    <div className="text-sm font-black text-[#302629]">
                      <span className="text-[#3E7B54]">+{feat.positive_mentions_count}</span>
                      <span className="text-[#78696B] mx-1">/</span>
                      <span className="text-[#873F46]">-{feat.negative_mentions_count}</span>
                    </div>
                    <span className="text-[11px] text-[#78696B] font-medium block">Persona Mentions</span>
                  </div>
                  {getStatusBadge(feat.evidence_validation_status)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 5: Pricing & Disagreements */}
      {activeTab === 'pricing' && (
        <div className="space-y-6">
          {/* Pricing Assessment */}
          {pa && (
            <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 sm:p-8 shadow-xs space-y-5">
              <div className="flex items-center justify-between border-b border-[#E7DAD8] pb-4">
                <h2 className="text-[22px] font-bold text-[#302629]">
                  Pricing &amp; Affordability Assessment
                </h2>
                <span className="text-xs font-bold px-3 py-1 rounded-full bg-[#F4E9E7] text-[#873F46] border border-[#B66B70]/20">
                  {pa.pricing_status}
                </span>
              </div>

              {pa.price_is_conditional && (
                <div className="p-4 bg-[#FAF2EA] text-[#C06E22] text-sm rounded-xl border border-[#C06E22]/30">
                  <strong>Conditional Pricing Notice:</strong> Proposal did not specify a concrete price. Simulated affordability ratings reflect general economic capacity rather than verified price acceptance.
                </div>
              )}

              <p className="text-base text-[#302629] leading-relaxed">
                {pa.simulated_affordability_summary}
              </p>

              {/* PLFS Labour Benchmark */}
              {pa.contextual_earnings_evidence && (
                <div className="p-5 bg-[#F7F4F2] rounded-xl border border-[#E7DAD8] text-sm space-y-2">
                  <span className="font-bold text-[#302629] block">
                    Contextual Labour Benchmark ({pa.contextual_earnings_evidence.location || 'National'}):
                  </span>
                  <p className="text-[#302629]">
                    Official PLFS 2025 Regular Salaried Mean Wage: ~ Rs.{' '}
                    <strong className="text-[#873F46]">
                      {Number(
                        pa.contextual_earnings_evidence.regular_salaried_avg_inr ||
                          pa.contextual_earnings_evidence.regular_wage_mean ||
                          0
                      ).toLocaleString()}
                    </strong>{' '}
                    / month.
                  </p>
                  <p className="text-xs text-[#78696B] italic">
                    *Epistemic Invariant: Macro wage context illustrates consumer ability to pay, but does NOT establish customer willingness to pay (WTP).
                  </p>
                </div>
              )}

              {pa.recommended_wtp_experiment && (
                <div className="p-4 bg-[#F4E9E7]/40 rounded-xl border border-[#B66B70]/20 text-sm text-[#302629]">
                  <strong className="text-[#873F46]">Recommended WTP Experiment:</strong> {pa.recommended_wtp_experiment}
                </div>
              )}
            </div>
          )}

          {/* Disagreements & Divergence */}
          {disagreements.length > 0 && (
            <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 sm:p-8 shadow-xs space-y-5">
              <h2 className="text-[22px] font-bold text-[#302629]">
                Persona Disagreements &amp; Metric Spread
              </h2>
              <div className="space-y-4">
                {disagreements.map((d, i) => (
                  <div key={i} className="p-5 rounded-xl bg-[#F7F4F2] border border-[#E7DAD8] text-sm space-y-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-bold text-[#302629] text-base">{d.topic}</span>
                      <span className="text-xs font-mono bg-[#FFFFFF] px-2.5 py-1 rounded-md border border-[#E7DAD8] text-[#873F46]">
                        {d.is_observed_or_hypothesized}
                      </span>
                    </div>
                    <p className="text-[#78696B] leading-relaxed">{d.plausible_explanation}</p>
                    {d.evidence_needed_to_resolve && (
                      <div className="text-xs text-[#78696B] pt-1">
                        <strong className="text-[#302629]">Evidence Needed to Resolve:</strong> {d.evidence_needed_to_resolve}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default MarketInsightsPage;
