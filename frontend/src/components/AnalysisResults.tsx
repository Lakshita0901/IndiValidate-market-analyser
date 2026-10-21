import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  ShieldAlert,
  Users,
  TrendingUp,
  FlaskConical,
  RotateCcw,
  ExternalLink,
  Info,
  XCircle,
  ChevronDown,
  ChevronUp,
  MapPin,
  AlertCircle,
} from 'lucide-react';
import { MarketValidationReport, PageId, PersonaProfile } from '../types';
import { PersonaCard } from './PersonaCard';
import { PersonaDetailModal } from './PersonaDetailModal';
import { extractPersonasFromReport } from '../utils/personaHelper';

interface AnalysisResultsProps {
  report: MarketValidationReport;
  submittedIdea: string;
  submittedGeography: string | null;
  onViewFullReport: (page: PageId) => void;
  onNewAnalysis: () => void;
  onSelectPersona?: (persona: PersonaProfile | null) => void;
}

// Evidence provenance badge — never labels model-generated findings as empirically corroborated
function EvidenceBadge({ status }: { status: string | undefined }) {
  if (status === 'supported') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-bold text-[#3E7B54] bg-[#EDF6F0] border border-[#3E7B54]/20 px-2 py-0.5 rounded-full">
        <CheckCircle2 className="w-2.5 h-2.5" />
        Empirical Evidence
      </span>
    );
  }
  if (status === 'mixed') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-bold text-[#C06E22] bg-[#FAF2EA] border border-[#C06E22]/20 px-2 py-0.5 rounded-full">
        <Info className="w-2.5 h-2.5" />
        Mixed Support
      </span>
    );
  }
  if (status === 'contradicted') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-bold text-[#873F46] bg-[#F4E9E7] border border-[#873F46]/20 px-2 py-0.5 rounded-full">
        <XCircle className="w-2.5 h-2.5" />
        Contradicted
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-bold text-[#78696B] bg-[#F7F4F2] border border-[#E7DAD8] px-2 py-0.5 rounded-full">
      <AlertTriangle className="w-2.5 h-2.5" />
      Model Hypothesis
    </span>
  );
}

export const AnalysisResults: React.FC<AnalysisResultsProps> = ({
  report,
  submittedIdea,
  submittedGeography,
  onViewFullReport,
  onNewAnalysis,
  onSelectPersona: externalOnSelectPersona,
}) => {
  const [selectedPersona, setSelectedPersona] = useState<PersonaProfile | null>(null);
  const [showAllPersonas, setShowAllPersonas] = useState(false);
  const [showAllPromising, setShowAllPromising] = useState(false);
  const [showAllRisks, setShowAllRisks] = useState(false);

  const handleSelectPersona = (p: PersonaProfile | null) => {
    setSelectedPersona(p);
    externalOnSelectPersona?.(p);
  };

  // Derive metrics from actual report fields only — no fabrication
  const personas = extractPersonasFromReport(report);
  const totalPersonas = personas.length;

  const completedEvals = (report.segment_comparison ?? []).reduce(
    (acc, s) => acc + (s.evaluated_personas_count || 0),
    0
  );
  const totalEvalPersonas =
    Number(report.diagnostics?.total_evaluations ?? completedEvals) || completedEvals;

  const segScores = (report.segment_comparison ?? []).map((s) => s.median_scores ?? {});
  const avgInterest =
    segScores.length > 0
      ? segScores.reduce((acc, s) => acc + (s.interest ?? 0), 0) / segScores.length
      : null;
  const avgPurchaseIntent =
    segScores.length > 0
      ? segScores.reduce((acc, s) => acc + (s.purchase_intent ?? 0), 0) / segScores.length
      : null;

  const coverageAudit = report.evidence_coverage_audit;
  const coveragePct = coverageAudit
    ? Math.round((coverageAudit.evidence_coverage_ratio ?? 0) * 100)
    : null;
  const supportedCount = coverageAudit?.supported_count ?? 0;
  const insufficientEvidence = supportedCount === 0;

  const promisingFindings = report.what_appears_promising ?? [];
  const riskFindings = report.what_may_not_work ?? [];
  const experiments = report.recommended_experiments ?? [];

  const displayPersonas = showAllPersonas ? personas : personas.slice(0, 3);
  const displayPromising = showAllPromising ? promisingFindings : promisingFindings.slice(0, 3);
  const displayRisks = showAllRisks ? riskFindings : riskFindings.slice(0, 3);

  return (
    <div className="space-y-6 animate-fadeIn" id="analysis-results-section">
      {/* Section Divider */}
      <div className="flex items-center gap-3 pt-4">
        <div className="flex-1 h-px bg-[#E7DAD8]" />
        <span className="text-xs font-bold text-[#873F46] uppercase tracking-wider px-2">
          Analysis Complete
        </span>
        <div className="flex-1 h-px bg-[#E7DAD8]" />
      </div>

      {/* Report Header Card */}
      <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-5 sm:p-6 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div className="space-y-2 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="inline-flex items-center gap-1.5 text-xs font-bold text-[#3E7B54] bg-[#EDF6F0] border border-[#3E7B54]/20 px-3 py-1 rounded-full">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Analysis Completed
              </span>
              {insufficientEvidence && (
                <span className="inline-flex items-center gap-1.5 text-xs font-bold text-[#C06E22] bg-[#FAF2EA] border border-[#C06E22]/30 px-3 py-1 rounded-full">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Insufficient Empirical Evidence
                </span>
              )}
            </div>
            <p className="text-[10px] font-mono text-[#78696B] break-all">
              Report ID: {report.report_id}
            </p>
            <h2 className="text-base font-bold text-[#302629] leading-snug">
              {submittedIdea}
            </h2>
            {submittedGeography && (
              <p className="text-xs text-[#78696B] flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 shrink-0 text-[#873F46]" />
                {submittedGeography}
              </p>
            )}
          </div>

          <div className="flex flex-col sm:flex-row gap-2 shrink-0">
            <button
              onClick={onNewAnalysis}
              className="px-4 py-2 text-xs font-bold text-[#78696B] hover:text-[#302629] hover:bg-[#F7F4F2] border border-[#E7DAD8] rounded-xl transition-colors flex items-center justify-center gap-1.5"
              id="new-analysis-reset-btn"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              New Analysis
            </button>
            <button
              onClick={() => onViewFullReport('reports')}
              className="px-4 py-2 bg-[#873F46] hover:bg-[#873F46]/90 text-white rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 shadow-xs transition-all"
              id="view-full-report-btn"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              View Full Report
            </button>
          </div>
        </div>
      </div>

      {/* Summary Metrics */}
      <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-5 sm:p-6 shadow-xs space-y-4">
        <h3 className="text-sm font-bold text-[#302629] flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-[#873F46]" />
          Summary Metrics
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <div className="bg-[#F7F4F2] rounded-xl p-3 text-center border border-[#E7DAD8]">
            <span className="text-xl font-bold text-[#873F46] block">{totalPersonas}</span>
            <span className="text-[10px] font-semibold text-[#78696B] block leading-tight mt-0.5">
              Personas Generated
            </span>
          </div>

          <div className="bg-[#F7F4F2] rounded-xl p-3 text-center border border-[#E7DAD8]">
            <span className="text-xl font-bold text-[#873F46] block">
              {totalEvalPersonas > 0 ? totalEvalPersonas : '—'}
            </span>
            <span className="text-[10px] font-semibold text-[#78696B] block leading-tight mt-0.5">
              Evaluations Completed
            </span>
          </div>

          <div className="bg-[#F7F4F2] rounded-xl p-3 text-center border border-[#E7DAD8]">
            <span className="text-xl font-bold text-[#302629] block">
              {avgInterest !== null ? `${avgInterest.toFixed(1)}/10` : '—'}
            </span>
            <span className="text-[10px] font-semibold text-[#78696B] block leading-tight mt-0.5">
              Avg Interest
              <br />
              <span className="text-[9px] font-normal italic">(Synthetic)</span>
            </span>
          </div>

          <div className="bg-[#F7F4F2] rounded-xl p-3 text-center border border-[#E7DAD8]">
            <span className="text-xl font-bold text-[#302629] block">
              {avgPurchaseIntent !== null ? `${avgPurchaseIntent.toFixed(1)}/10` : '—'}
            </span>
            <span className="text-[10px] font-semibold text-[#78696B] block leading-tight mt-0.5">
              Avg Purchase Intent
              <br />
              <span className="text-[9px] font-normal italic">(Synthetic)</span>
            </span>
          </div>

          <div
            className={`rounded-xl p-3 text-center border ${
              insufficientEvidence
                ? 'bg-[#FAF2EA] border-[#C06E22]/30'
                : 'bg-[#F7F4F2] border-[#E7DAD8]'
            }`}
          >
            <span
              className={`text-xl font-bold block ${
                insufficientEvidence ? 'text-[#C06E22]' : 'text-[#3E7B54]'
              }`}
            >
              {coveragePct !== null ? `${coveragePct}%` : '—'}
            </span>
            <span className="text-[10px] font-semibold text-[#78696B] block leading-tight mt-0.5">
              Evidence Coverage
              {insufficientEvidence && (
                <>
                  <br />
                  <span className="text-[#C06E22] font-bold text-[9px]">Low — verify findings</span>
                </>
              )}
            </span>
          </div>
        </div>

        <div className="flex items-start gap-2.5 p-3 bg-[#FAF2EA] border border-[#C06E22]/20 rounded-xl text-xs text-[#78696B]">
          <ShieldAlert className="w-4 h-4 text-[#C06E22] shrink-0 mt-0.5" />
          <span>
            <strong className="text-[#302629]">Simulation Notice:</strong> Interest and purchase
            intent scores are synthetic multi-agent simulation outputs, not real customer surveys.
            Evidence coverage reflects the fraction of findings corroborated by empirical sources
            (Census 2011, PLFS 2025, Reddit, Google Trends).
          </span>
        </div>
      </div>

      {/* Key Insights */}
      {report.executive_summary && (
        <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-5 sm:p-6 shadow-xs space-y-5">
          <h3 className="text-sm font-bold text-[#302629]">Key Insights</h3>

          {/* Promising Hypotheses */}
          {promisingFindings.length > 0 && (
            <div className="space-y-2">
              <span className="text-xs font-bold text-[#3E7B54] flex items-center gap-1.5 uppercase tracking-wider">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Promising Hypotheses ({promisingFindings.length})
              </span>
              <div className="space-y-2">
                {displayPromising.map((f) => (
                  <div
                    key={f.finding_id}
                    className="p-3 bg-[#EDF6F0] border border-[#3E7B54]/20 rounded-xl text-xs space-y-1"
                  >
                    <p className="text-[#302629] font-medium leading-snug">
                      {f.claim_or_hypothesis}
                    </p>
                    <div className="flex flex-wrap items-center gap-2">
                      <EvidenceBadge status={f.evidence_validation_status} />
                      {f.evidence_sources && f.evidence_sources.length > 0 && (
                        <span className="text-[10px] text-[#78696B]">
                          Sources: {f.evidence_sources.slice(0, 2).join(', ')}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              {promisingFindings.length > 3 && (
                <button
                  onClick={() => setShowAllPromising(!showAllPromising)}
                  className="text-xs font-semibold text-[#873F46] hover:underline flex items-center gap-1 mt-1"
                >
                  {showAllPromising ? (
                    <><ChevronUp className="w-3.5 h-3.5" /> Show less</>
                  ) : (
                    <><ChevronDown className="w-3.5 h-3.5" /> Show all {promisingFindings.length}</>
                  )}
                </button>
              )}
            </div>
          )}

          {/* Risks and Barriers */}
          {riskFindings.length > 0 && (
            <div className="space-y-2">
              <span className="text-xs font-bold text-[#873F46] flex items-center gap-1.5 uppercase tracking-wider">
                <AlertTriangle className="w-3.5 h-3.5" />
                Main Risks &amp; Barriers ({riskFindings.length})
              </span>
              <div className="space-y-2">
                {displayRisks.map((f) => (
                  <div
                    key={f.finding_id}
                    className="p-3 bg-[#F4E9E7] border border-[#873F46]/20 rounded-xl text-xs space-y-1"
                  >
                    <p className="text-[#302629] font-medium leading-snug">
                      {f.concern_or_barrier}
                    </p>
                    <div className="flex flex-wrap items-center gap-2">
                      <EvidenceBadge status={f.evidence_validation_status} />
                      {f.rationale && (
                        <span className="text-[10px] text-[#78696B] line-clamp-1">
                          {f.rationale}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              {riskFindings.length > 3 && (
                <button
                  onClick={() => setShowAllRisks(!showAllRisks)}
                  className="text-xs font-semibold text-[#873F46] hover:underline flex items-center gap-1 mt-1"
                >
                  {showAllRisks ? (
                    <><ChevronUp className="w-3.5 h-3.5" /> Show less</>
                  ) : (
                    <><ChevronDown className="w-3.5 h-3.5" /> Show all {riskFindings.length}</>
                  )}
                </button>
              )}
            </div>
          )}

          {/* Recommended Experiments */}
          {experiments.length > 0 && (
            <div className="space-y-2">
              <span className="text-xs font-bold text-[#C06E22] flex items-center gap-1.5 uppercase tracking-wider">
                <FlaskConical className="w-3.5 h-3.5" />
                Next Validation Steps ({experiments.length})
              </span>
              <div className="space-y-2">
                {experiments.slice(0, 3).map((e) => (
                  <div
                    key={e.recommendation_id}
                    className="p-3 bg-[#FAF2EA] border border-[#C06E22]/20 rounded-xl text-xs space-y-1"
                  >
                    <p className="text-[#302629] font-medium leading-snug">
                      {e.question_to_validate}
                    </p>
                    <div className="flex flex-wrap gap-2 text-[10px] text-[#78696B]">
                      {e.suggested_experiment_type && (
                        <span className="bg-[#F7F4F2] border border-[#E7DAD8] px-1.5 py-0.5 rounded-md font-semibold">
                          {e.suggested_experiment_type}
                        </span>
                      )}
                      {e.target_segment && <span>Target: {e.target_segment}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Fallback: no structured findings — show executive summary strings */}
          {promisingFindings.length === 0 && riskFindings.length === 0 && experiments.length === 0 && (
            <div className="space-y-3">
              {(report.executive_summary.strongest_promising_signals ?? []).map((s, i) => (
                <div key={i} className="p-3 bg-[#EDF6F0] border border-[#3E7B54]/20 rounded-xl text-xs text-[#302629]">
                  <span className="font-bold text-[#3E7B54] block mb-0.5">Promising Signal</span>
                  {s}
                </div>
              ))}
              {(report.executive_summary.key_risks_and_barriers ?? []).map((r, i) => (
                <div key={i} className="p-3 bg-[#F4E9E7] border border-[#873F46]/20 rounded-xl text-xs text-[#302629]">
                  <span className="font-bold text-[#873F46] block mb-0.5">Risk / Barrier</span>
                  {r}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Generated Personas */}
      {personas.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-[#302629] flex items-center gap-2">
              <Users className="w-4 h-4 text-[#873F46]" />
              Generated Personas ({personas.length})
            </h3>
            {personas.length > 3 && (
              <button
                onClick={() => setShowAllPersonas(!showAllPersonas)}
                className="text-xs font-semibold text-[#873F46] hover:underline flex items-center gap-1"
              >
                {showAllPersonas ? (
                  <><ChevronUp className="w-3.5 h-3.5" /> Show fewer</>
                ) : (
                  <><ChevronDown className="w-3.5 h-3.5" /> Show all {personas.length}</>
                )}
              </button>
            )}
          </div>

          <div className="flex items-start gap-2.5 p-3 bg-[#FAF2EA] border border-[#C06E22]/20 rounded-xl text-xs text-[#78696B]">
            <ShieldAlert className="w-4 h-4 text-[#C06E22] shrink-0 mt-0.5" />
            <span>
              These are <strong className="text-[#302629]">synthetic hypothesis archetypes</strong>,
              not real customer interviews. Scores represent simulated responses to stress-test the
              proposal — not verified market conversion data.
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {displayPersonas.map((persona) => (
              <PersonaCard
                key={persona.persona_id}
                persona={persona}
                onClick={handleSelectPersona}
              />
            ))}
          </div>
        </div>
      )}

      {/* Evidence Coverage Audit */}
      {coverageAudit && (
        <div
          className={`rounded-2xl p-4 sm:p-5 border shadow-xs text-xs space-y-3 ${
            insufficientEvidence
              ? 'bg-[#FAF2EA] border-[#C06E22]/30'
              : 'bg-[#F7F4F2] border-[#E7DAD8]'
          }`}
        >
          <div className="flex items-center gap-2">
            <AlertCircle
              className={`w-4 h-4 shrink-0 ${
                insufficientEvidence ? 'text-[#C06E22]' : 'text-[#78696B]'
              }`}
            />
            <span
              className={`font-bold text-sm ${
                insufficientEvidence ? 'text-[#C06E22]' : 'text-[#302629]'
              }`}
            >
              {insufficientEvidence
                ? 'Insufficient Empirical Evidence — Treat all findings as unverified hypotheses'
                : 'Evidence Coverage Audit'}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
            {[
              { label: 'Supported', value: coverageAudit.supported_count, color: 'text-[#3E7B54]' },
              { label: 'Mixed', value: coverageAudit.mixed_count, color: 'text-[#C06E22]' },
              { label: 'Contradicted', value: coverageAudit.contradicted_count, color: 'text-[#873F46]' },
              { label: 'No Evidence', value: coverageAudit.insufficient_evidence_count, color: 'text-[#78696B]' },
            ].map((item) => (
              <div key={item.label} className="bg-white/60 rounded-lg p-2 border border-[#E7DAD8]">
                <span className={`text-lg font-bold block ${item.color}`}>{item.value}</span>
                <span className="text-[10px] text-[#78696B]">{item.label}</span>
              </div>
            ))}
          </div>
          {coverageAudit.sources_represented && coverageAudit.sources_represented.length > 0 && (
            <p className="text-[10px] text-[#78696B]">
              Sources: {coverageAudit.sources_represented.join(' · ')}
            </p>
          )}
        </div>
      )}

      {/* Bottom Navigation */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 py-2">
        <button
          onClick={onNewAnalysis}
          className="w-full sm:w-auto px-5 py-2.5 text-xs font-bold text-[#78696B] hover:text-[#302629] hover:bg-[#FFFFFF] border border-[#E7DAD8] rounded-xl transition-colors flex items-center justify-center gap-1.5"
          id="new-analysis-reset-bottom-btn"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          Start New Analysis
        </button>

        <div className="flex gap-2 w-full sm:w-auto">
          <button
            onClick={() => onViewFullReport('personas')}
            className="flex-1 sm:flex-none px-4 py-2.5 text-xs font-bold text-[#873F46] bg-[#F4E9E7] hover:bg-[#F4E9E7]/80 border border-[#B66B70]/20 rounded-xl transition-colors flex items-center justify-center gap-1.5"
            id="view-personas-btn"
          >
            <Users className="w-3.5 h-3.5" />
            All Personas
          </button>
          <button
            onClick={() => onViewFullReport('overview')}
            className="flex-1 sm:flex-none px-4 py-2.5 bg-[#873F46] hover:bg-[#873F46]/90 text-white rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 shadow-xs transition-all"
            id="view-overview-btn"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            Full Report Overview
          </button>
        </div>
      </div>

      {/* Persona Detail Modal */}
      {selectedPersona && (
        <PersonaDetailModal
          persona={selectedPersona}
          onClose={() => handleSelectPersona(null)}
        />
      )}
    </div>
  );
};

export default AnalysisResults;
