import React, { useState } from 'react';
import {
  FileText,
  Download,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  Printer,
  Sparkles,
  Layers,
  ShieldCheck,
  Brain,
  AlertTriangle,
  Tag,
  HelpCircle,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Database
} from 'lucide-react';
import { MarketValidationReport } from '../types';
import { downloadFile, generateReportMarkdown } from '../utils/markdownExporter';

interface ReportsPageProps {
  report: MarketValidationReport | null;
  onNavigateToNew: () => void;
  onLoadSample: () => void;
}

export const ReportsPage: React.FC<ReportsPageProps> = ({
  report,
  onNavigateToNew,
  onLoadSample,
}) => {
  const [copied, setCopied] = useState(false);
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    exec: true,
    context: true,
    promising: true,
    risks: true,
    segments: true,
    features: true,
    pricing: true,
    audit: true,
    experiments: true,
    questions: true,
  });

  const toggleSection = (sec: string) => {
    setOpenSections((prev) => ({ ...prev, [sec]: !prev[sec] }));
  };

  const expandAll = () => {
    setOpenSections({
      exec: true,
      context: true,
      promising: true,
      risks: true,
      segments: true,
      features: true,
      pricing: true,
      audit: true,
      experiments: true,
      questions: true,
    });
  };

  const collapseAll = () => {
    setOpenSections({
      exec: false,
      context: false,
      promising: false,
      risks: false,
      segments: false,
      features: false,
      pricing: false,
      audit: false,
      experiments: false,
      questions: false,
    });
  };

  if (!report) {
    return (
      <div className="bg-[#FFFFFF] border border-dashed border-[#E7DAD8] rounded-2xl p-12 text-center max-w-lg mx-auto">
        <FileText className="w-12 h-12 text-[#B66B70] mx-auto mb-3 opacity-60" />
        <h3 className="text-xl font-bold text-[#302629] mb-1">No Report Available</h3>
        <p className="text-sm text-[#78696B] mb-5 leading-relaxed">
          Run an analysis or preview the sample benchmark report to inspect the full audit document.
        </p>
        <div className="flex justify-center gap-3">
          <button
            onClick={onNavigateToNew}
            className="px-5 py-2.5 bg-[#873F46] hover:bg-[#873F46]/90 text-white rounded-xl text-xs font-bold shadow-xs transition-colors"
          >
            Start New Validation
          </button>
          <button
            onClick={onLoadSample}
            className="px-5 py-2.5 bg-[#F4E9E7] hover:bg-[#F4E9E7]/80 text-[#873F46] border border-[#B66B70]/20 rounded-xl text-xs font-bold transition-colors"
          >
            Load Sample Report
          </button>
        </div>
      </div>
    );
  }

  const handleDownloadMarkdown = () => {
    const md = generateReportMarkdown(report);
    downloadFile(md, `${report.report_id}.md`, 'text/markdown');
  };

  const handleDownloadJSON = () => {
    const jsonStr = JSON.stringify(report, null, 2);
    downloadFile(jsonStr, `${report.report_id}.json`, 'application/json');
  };

  const handleCopyMarkdown = () => {
    const md = generateReportMarkdown(report);
    navigator.clipboard.writeText(md).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handlePrint = () => {
    window.print();
  };

  const getFriendlyStatusBadge = (status: string) => {
    switch ((status || '').toLowerCase()) {
      case 'supported':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#EDF6F0] text-[#3E7B54] border border-[#3E7B54]/20 flex items-center gap-1">
            <CheckCircle2 size={12} />
            Corroborated by Evidence
          </span>
        );
      case 'contradicted':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#F4E9E7] text-[#873F46] border border-[#873F46]/30 flex items-center gap-1">
            <XCircle size={12} />
            Contradicted by Evidence
          </span>
        );
      case 'mixed':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#FAF2EA] text-[#C06E22] border border-[#C06E22]/30 flex items-center gap-1">
            <AlertCircle size={12} />
            Mixed Empirical Signals
          </span>
        );
      case 'insufficient_evidence':
      default:
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#F7F4F2] text-[#78696B] border border-[#E7DAD8] flex items-center gap-1">
            <HelpCircle size={12} />
            Needs more evidence
          </span>
        );
    }
  };

  const getBasisBadge = (basis: string) => {
    switch (basis) {
      case 'retrieved_evidence':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#EDF6F0] text-[#3E7B54] border border-[#3E7B54]/20">
            <Database size={12} className="text-[#3E7B54]" />
            <span>Retrieved Evidence</span>
          </span>
        );
      case 'mixed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#FAF2EA] text-[#C06E22] border border-[#C06E22]/30">
            <Layers size={12} className="text-[#C06E22]" />
            <span>Mixed Signals</span>
          </span>
        );
      case 'model_knowledge':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#F4E9E7] text-[#873F46] border border-[#873F46]/20">
            <Brain size={12} className="text-[#873F46]" />
            <span>Market Domain Reasoning</span>
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

    if (rqa.basis === 'retrieved_evidence' && hasValidSources && !rqa.requires_external_validation) {
      return (
        <span className="text-xs font-bold px-2.5 py-0.5 rounded-full border bg-[#EDF6F0] text-[#3E7B54] border-[#3E7B54]/20 flex items-center gap-1">
          <CheckCircle2 size={12} />
          <span>Empirically Supported</span>
        </span>
      );
    }

    if (rqa.basis === 'retrieved_evidence' && rqa.requires_external_validation) {
      return (
        <span className="text-xs font-bold px-2.5 py-0.5 rounded-full border bg-[#FAF2EA] text-[#C06E22] border-[#C06E22]/30 flex items-center gap-1">
          <HelpCircle size={12} />
          <span>Empirical Signal (Needs Field Validation)</span>
        </span>
      );
    }

    if (rqa.basis === 'mixed') {
      return (
        <span className="text-xs font-bold px-2.5 py-0.5 rounded-full border bg-[#FAF2EA] text-[#C06E22] border-[#C06E22]/30 flex items-center gap-1">
          <AlertCircle size={12} />
          <span>Mixed Signals (Data + Model Prior)</span>
        </span>
      );
    }

    return (
      <span className="text-xs font-bold px-2.5 py-0.5 rounded-full border bg-[#F4E9E7] text-[#873F46] border-[#873F46]/30 flex items-center gap-1">
        <Brain size={12} />
        <span>Model Reasoning (Needs Field Validation)</span>
      </span>
    );
  };

  return (
    <div className="report-page-container space-y-8 max-w-5xl mx-auto animate-fadeIn print:space-y-4 print:max-w-none print:w-full print:m-0 print:p-0">
      {/* Report Header Bar */}
      <div className="report-header-card bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 sm:p-7 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-5 print:rounded-lg print:border-slate-700 print:bg-[#171B20] print:shadow-none print:p-5 print:mb-4">
        <div className="flex-1 min-w-0">
          <div className="hidden print:block text-[11px] font-bold uppercase tracking-wider text-[#A0AAB5] print:text-slate-300 mb-1">
            IndiValidate • Market Validation Audit Report
          </div>
          <div className="flex items-center gap-2 mb-2 print:mb-1.5 flex-wrap">
            <span className="font-mono text-xs font-bold bg-[#F4E9E7] text-[#873F46] px-3 py-1 rounded-full border border-[#B66B70]/20 print:bg-red-950/60 print:text-rose-300 print:border-rose-900/40">
              {report.report_id}
            </span>
            <span className="text-xs text-[#78696B] print:text-slate-300">
              Generated: {(() => {
                if (!report.generated_at) return 'Recent Session';
                const d = new Date(report.generated_at);
                return isNaN(d.getTime()) ? report.generated_at : d.toLocaleDateString();
              })()}
            </span>
          </div>
          <h1 className="report-header-title text-[28px] sm:text-[32px] font-extrabold text-[#302629] leading-tight break-words print:text-[22px] print:leading-snug print:text-white">
            {report.idea_and_context?.business_idea}
          </h1>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2 shrink-0 print:hidden">
          <button
            onClick={handleCopyMarkdown}
            className="px-3.5 py-2 border border-[#E7DAD8] hover:bg-[#F7F4F2] text-[#302629] rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors shadow-2xs"
          >
            {copied ? <Check className="w-4 h-4 text-[#3E7B54]" /> : <Copy className="w-4 h-4 text-[#78696B]" />}
            <span>{copied ? 'Copied' : 'Copy Markdown'}</span>
          </button>
          <button
            onClick={handleDownloadMarkdown}
            className="px-3.5 py-2 border border-[#E7DAD8] hover:bg-[#F7F4F2] text-[#302629] rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors shadow-2xs"
          >
            <Download className="w-4 h-4 text-[#78696B]" />
            <span>Export .md</span>
          </button>
          <button
            onClick={handleDownloadJSON}
            className="px-4 py-2 bg-[#873F46] hover:bg-[#873F46]/90 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-xs transition-colors"
          >
            <Download className="w-4 h-4 text-white" />
            <span>Export JSON</span>
          </button>
          <button
            onClick={handlePrint}
            className="p-2 border border-[#E7DAD8] hover:bg-[#F7F4F2] text-[#78696B] hover:text-[#302629] rounded-xl text-xs font-medium flex items-center justify-center transition-colors shadow-2xs"
            title="Print report"
          >
            <Printer className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Expand/Collapse Controls */}
      <div className="flex justify-end gap-2 text-xs font-bold text-[#78696B] print:hidden">
        <button onClick={expandAll} className="hover:text-[#873F46] transition-colors">Expand All</button>
        <span>•</span>
        <button onClick={collapseAll} className="hover:text-[#873F46] transition-colors">Collapse All</button>
      </div>

      {/* Structured Sections */}
      <div className="space-y-5 print:space-y-3.5">
        {/* Section 1: Executive Summary */}
        <div className="report-section-card bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl overflow-hidden shadow-xs print:rounded-lg print:border-[#2B3138] print:bg-[#171B20] print:shadow-none print:mb-4">
          <button
            onClick={() => toggleSection('exec')}
            className="report-section-header w-full px-7 py-5 flex items-center justify-between text-left hover:bg-[#F7F4F2]/50 transition-colors border-b border-[#E7DAD8] print:bg-[#1D2228] print:border-[#2B3138] print:px-5 print:py-3 print:cursor-default"
          >
            <div className="flex items-center gap-3">
              <span className="w-7 h-7 rounded-xl bg-[#F4E9E7] text-[#873F46] text-xs font-bold flex items-center justify-center print:bg-[#873F46]/30 print:text-rose-300">1</span>
              <h2 className="text-[22px] font-bold text-[#302629] print:text-lg print:text-white">Executive Briefing &amp; Next Steps</h2>
            </div>
            <div className="print:hidden">
              {openSections.exec ? <ChevronUp className="w-5 h-5 text-[#78696B]" /> : <ChevronDown className="w-5 h-5 text-[#78696B]" />}
            </div>
          </button>

          {report.executive_summary && (
            <div className={`report-section-content p-7 space-y-6 print:p-5 print:space-y-4 ${openSections.exec ? 'block' : 'hidden print:block'}`}>
              {/* Executive Summary Paragraphs (16-18px body text) */}
              <div className="text-base sm:text-[17px] text-[#302629] leading-relaxed space-y-4 print:text-[14px] print:text-white">
                <p className="print:text-white">{report.executive_summary.idea_description}</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-2 print:gap-3.5">
                {/* Promising signals */}
                <div className="print-avoid-break bg-[#F7F4F2] rounded-xl p-5 border border-[#E7DAD8] print:bg-[#1a1f26] print:border-[#2B3138] print:p-4">
                  <h3 className="text-lg font-bold text-[#3E7B54] mb-3 flex items-center gap-2 print:text-base print:text-emerald-400">
                    <CheckCircle2 size={18} />
                    Promising Signals
                  </h3>
                  <ul className="space-y-2 text-sm sm:text-[15px] text-[#302629] print:text-xs print:text-white">
                    {(report.executive_summary.strongest_promising_signals || []).map((sig, i) => (
                      <li key={i} className="flex items-start gap-2 print:text-white">
                        <span className="text-[#3E7B54] font-bold print:text-emerald-400">•</span>
                        <span className="print:text-white">{sig}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Key Risks */}
                <div className="print-avoid-break bg-[#FAF2EA]/50 rounded-xl p-5 border border-[#C06E22]/30 print:bg-amber-950/20 print:border-amber-900/40 print:p-4">
                  <h3 className="text-lg font-bold text-[#C06E22] mb-3 flex items-center gap-2 print:text-base print:text-amber-400">
                    <AlertTriangle size={18} />
                    Key Risks &amp; Barriers
                  </h3>
                  <ul className="space-y-2 text-sm sm:text-[15px] text-[#302629] print:text-xs print:text-white">
                    {(report.executive_summary.key_risks_and_barriers || []).map((risk, i) => (
                      <li key={i} className="flex items-start gap-2 print:text-white">
                        <span className="text-[#C06E22] font-bold print:text-amber-400">•</span>
                        <span className="print:text-white">{risk}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Next Validation Priority */}
              {report.executive_summary.next_validation_priority && (
                <div className="print-avoid-break p-5 bg-[#F4E9E7]/40 rounded-xl border border-[#B66B70]/20 print:bg-rose-950/20 print:border-rose-900/40 print:p-4">
                  <h3 className="text-lg font-bold text-[#873F46] mb-2 print:text-base print:text-rose-400">
                    Next Validation Priority
                  </h3>
                  <p className="text-sm sm:text-[15px] text-[#302629] leading-relaxed print:text-xs print:text-white">
                    {report.executive_summary.next_validation_priority}
                  </p>
                </div>
              )}

              {/* Critical Unresolved Questions */}
              {report.executive_summary.critical_unresolved_questions && report.executive_summary.critical_unresolved_questions.length > 0 && (
                <div className="print-avoid-break p-5 bg-[#F7F4F2] rounded-xl border border-[#E7DAD8] print:bg-[#1a1f26] print:border-[#2B3138] print:p-4">
                  <h3 className="text-lg font-bold text-[#302629] mb-2.5 print:text-base print:text-white">
                    Critical Unresolved Questions
                  </h3>
                  <div className="space-y-2">
                    {report.executive_summary.critical_unresolved_questions.map((q, idx) => (
                      <div key={idx} className="flex items-start gap-2 text-sm sm:text-[15px] text-[#302629] print:text-xs print:text-white">
                        <span className="font-bold text-[#873F46] print:text-rose-400">{idx + 1}.</span>
                        <span className="print:text-white">{q}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Section 2: Promising Value Hypotheses */}
        <div className="report-section-card bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl overflow-hidden shadow-xs print:rounded-lg print:border-[#2B3138] print:bg-[#171B20] print:shadow-none print:mb-4">
          <button
            onClick={() => toggleSection('promising')}
            className="report-section-header w-full px-7 py-5 flex items-center justify-between text-left hover:bg-[#F7F4F2]/50 transition-colors border-b border-[#E7DAD8] print:bg-[#1D2228] print:border-[#2B3138] print:px-5 print:py-3 print:cursor-default"
          >
            <div className="flex items-center gap-3">
              <span className="w-7 h-7 rounded-xl bg-[#F4E9E7] text-[#873F46] text-xs font-bold flex items-center justify-center print:bg-[#873F46]/30 print:text-rose-300">2</span>
              <h2 className="text-[22px] font-bold text-[#302629] print:text-lg print:text-white">Promising Findings ({report.what_appears_promising?.length || 0})</h2>
            </div>
            <div className="print:hidden">
              {openSections.promising ? <ChevronUp className="w-5 h-5 text-[#78696B]" /> : <ChevronDown className="w-5 h-5 text-[#78696B]" />}
            </div>
          </button>

          <div className={`report-section-content p-7 space-y-4 print:p-5 print:space-y-3 ${openSections.promising ? 'block' : 'hidden print:block'}`}>
            {(report.what_appears_promising || []).map((pf) => (
              <div key={pf.finding_id} className="print-avoid-break p-5 rounded-xl bg-[#F7F4F2] border border-[#E7DAD8] space-y-2.5 print:bg-[#1a1f26] print:border-[#2B3138] print:p-4">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <h3 className="text-lg font-bold text-[#302629] print:text-base print:text-white">{pf.claim_or_hypothesis}</h3>
                  {getFriendlyStatusBadge(pf.evidence_validation_status)}
                </div>
                <p className="text-sm sm:text-[15px] text-[#78696B] leading-relaxed print:text-xs print:text-slate-300">{pf.rationale}</p>
                <div className="text-xs text-[#3E7B54] bg-[#EDF6F0] p-3 rounded-lg border border-[#3E7B54]/20 font-medium print:bg-emerald-950/20 print:border-emerald-800/40 print:text-emerald-300">
                  <strong className="print:text-emerald-400">Validation Experiment:</strong> <span className="print:text-white">{pf.suggested_real_world_validation}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Section 3: Risks & Adoption Barriers */}
        <div className="report-section-card bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl overflow-hidden shadow-xs print:rounded-lg print:border-[#2B3138] print:bg-[#171B20] print:shadow-none print:mb-4">
          <button
            onClick={() => toggleSection('risks')}
            className="report-section-header w-full px-7 py-5 flex items-center justify-between text-left hover:bg-[#F7F4F2]/50 transition-colors border-b border-[#E7DAD8] print:bg-[#1D2228] print:border-[#2B3138] print:px-5 print:py-3 print:cursor-default"
          >
            <div className="flex items-center gap-3">
              <span className="w-7 h-7 rounded-xl bg-[#F4E9E7] text-[#873F46] text-xs font-bold flex items-center justify-center print:bg-[#873F46]/30 print:text-rose-300">3</span>
              <h2 className="text-[22px] font-bold text-[#302629] print:text-lg print:text-white">Identified Risks &amp; Barriers ({report.what_may_not_work?.length || 0})</h2>
            </div>
            <div className="print:hidden">
              {openSections.risks ? <ChevronUp className="w-5 h-5 text-[#78696B]" /> : <ChevronDown className="w-5 h-5 text-[#78696B]" />}
            </div>
          </button>

          <div className={`report-section-content p-7 space-y-4 print:p-5 print:space-y-3 ${openSections.risks ? 'block' : 'hidden print:block'}`}>
            {(report.what_may_not_work || []).map((rf) => (
              <div key={rf.finding_id} className="print-avoid-break p-5 rounded-xl bg-[#F7F4F2] border border-[#E7DAD8] space-y-2.5 print:bg-[#1a1f26] print:border-[#2B3138] print:p-4">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <h3 className="text-lg font-bold text-[#302629] print:text-base print:text-white">{rf.concern_or_barrier}</h3>
                  {getFriendlyStatusBadge(rf.evidence_validation_status)}
                </div>
                <div className="text-xs text-[#78696B] font-semibold print:text-slate-300">
                  Category: <span className="text-[#302629] uppercase print:text-white">{rf.barrier_category.replace(/_/g, ' ')}</span>
                </div>
                <p className="text-sm sm:text-[15px] text-[#78696B] leading-relaxed print:text-xs print:text-slate-300">{rf.rationale}</p>
                <div className="text-xs text-[#C06E22] bg-[#FAF2EA] p-3 rounded-lg border border-[#C06E22]/20 font-medium print:bg-amber-950/20 print:border-amber-800/40 print:text-amber-300">
                  <strong className="print:text-amber-400">Mitigation / Test:</strong> <span className="print:text-white">{rf.suggested_mitigation_or_test}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Section 4: Customer Segments */}
        <div className="report-section-card bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl overflow-hidden shadow-xs print:rounded-lg print:border-[#2B3138] print:bg-[#171B20] print:shadow-none print:mb-4">
          <button
            onClick={() => toggleSection('segments')}
            className="report-section-header w-full px-7 py-5 flex items-center justify-between text-left hover:bg-[#F7F4F2]/50 transition-colors border-b border-[#E7DAD8] print:bg-[#1D2228] print:border-[#2B3138] print:px-5 print:py-3 print:cursor-default"
          >
            <div className="flex items-center gap-3">
              <span className="w-7 h-7 rounded-xl bg-[#F4E9E7] text-[#873F46] text-xs font-bold flex items-center justify-center print:bg-[#873F46]/30 print:text-rose-300">4</span>
              <h2 className="text-[22px] font-bold text-[#302629] print:text-lg print:text-white">Customer Segments Comparison ({report.segment_comparison?.length || 0})</h2>
            </div>
            <div className="print:hidden">
              {openSections.segments ? <ChevronUp className="w-5 h-5 text-[#78696B]" /> : <ChevronDown className="w-5 h-5 text-[#78696B]" />}
            </div>
          </button>

          <div className={`report-section-content report-section-content-grid p-7 grid grid-cols-1 md:grid-cols-2 gap-5 print:p-5 print:gap-3.5 ${openSections.segments ? 'grid' : 'hidden print:grid'}`}>
            {(report.segment_comparison || []).map((seg, i) => (
              <div key={i} className="print-avoid-break p-5 rounded-xl bg-[#F7F4F2] border border-[#E7DAD8] space-y-3 print:bg-[#1a1f26] print:border-[#2B3138] print:p-4">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-lg font-bold text-[#302629] print:text-base print:text-white">{seg.segment_name}</h3>
                  <span className="text-xs font-bold bg-[#F4E9E7] text-[#873F46] px-2.5 py-0.5 rounded-full print:bg-[#873F46]/30 print:text-rose-300">
                    {seg.evaluated_personas_count} personas
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="bg-[#FFFFFF] p-2 rounded-lg border border-[#E7DAD8] print:bg-[#14171d] print:border-[#2B3138]">
                    <span className="text-[#78696B] block print:text-slate-300">Intent</span>
                    <span className="font-bold text-[#873F46] text-sm print:text-rose-400">
                      {seg.median_scores?.purchase_intent !== undefined && seg.median_scores?.purchase_intent !== null
                        ? `${seg.median_scores.purchase_intent}/10`
                        : '-'}
                    </span>
                  </div>
                  <div className="bg-[#FFFFFF] p-2 rounded-lg border border-[#E7DAD8] print:bg-[#14171d] print:border-[#2B3138]">
                    <span className="text-[#78696B] block print:text-slate-300">Afford.</span>
                    <span className="font-bold text-[#3E7B54] text-sm print:text-emerald-400">
                      {seg.median_scores?.affordability !== undefined && seg.median_scores?.affordability !== null
                        ? `${seg.median_scores.affordability}/10`
                        : '-'}
                    </span>
                  </div>
                  <div className="bg-[#FFFFFF] p-2 rounded-lg border border-[#E7DAD8] print:bg-[#14171d] print:border-[#2B3138]">
                    <span className="text-[#78696B] block print:text-slate-300">Interest</span>
                    <span className="font-bold text-[#302629] text-sm print:text-white">
                      {seg.median_scores?.interest !== undefined && seg.median_scores?.interest !== null
                        ? `${seg.median_scores.interest}/10`
                        : '-'}
                    </span>
                  </div>
                </div>
                <p className="text-xs text-[#78696B] leading-relaxed print:text-slate-300">{seg.affordability_and_adoption_summary}</p>
              </div>
            ))}
            <div className="col-span-full pt-2 text-xs text-[#78696B] italic print:text-slate-400">
              *Note: Persona counts and median scores reflect synthetic simulation archetypes on a 1–10 ordinal scale, not actual market share or conversion probabilities.*
            </div>
          </div>
        </div>

        {/* Section 5: Feature Prioritization */}
        <div className="report-section-card bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl overflow-hidden shadow-xs print:rounded-lg print:border-[#2B3138] print:bg-[#171B20] print:shadow-none print:mb-4">
          <button
            onClick={() => toggleSection('features')}
            className="report-section-header w-full px-7 py-5 flex items-center justify-between text-left hover:bg-[#F7F4F2]/50 transition-colors border-b border-[#E7DAD8] print:bg-[#1D2228] print:border-[#2B3138] print:px-5 print:py-3 print:cursor-default"
          >
            <div className="flex items-center gap-3">
              <span className="w-7 h-7 rounded-xl bg-[#F4E9E7] text-[#873F46] text-xs font-bold flex items-center justify-center print:bg-[#873F46]/30 print:text-rose-300">5</span>
              <h2 className="text-[22px] font-bold text-[#302629] print:text-lg print:text-white">Feature Prioritization ({report.feature_prioritization?.length || 0})</h2>
            </div>
            <div className="print:hidden">
              {openSections.features ? <ChevronUp className="w-5 h-5 text-[#78696B]" /> : <ChevronDown className="w-5 h-5 text-[#78696B]" />}
            </div>
          </button>

          <div className={`report-section-content p-7 space-y-3 print:p-5 print:space-y-2.5 ${openSections.features ? 'block' : 'hidden print:block'}`}>
            {(report.feature_prioritization || []).map((feat, i) => (
              <div key={i} className="print-avoid-break p-4 rounded-xl bg-[#F7F4F2] border border-[#E7DAD8] flex flex-col sm:flex-row sm:items-center justify-between gap-3 print:bg-[#1a1f26] print:border-[#2B3138] print:p-3">
                <div>
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-[#EDF6F0] text-[#3E7B54] print:bg-emerald-950/40 print:text-emerald-300">
                      {feat.priority_tier}
                    </span>
                    <h3 className="text-base font-bold text-[#302629] print:text-sm print:text-white">{feat.feature_name}</h3>
                  </div>
                  <p className="text-xs text-[#78696B] print:text-slate-300">Uncertainty: {feat.main_uncertainty}</p>
                </div>
                <div className="shrink-0">{getFriendlyStatusBadge(feat.evidence_validation_status)}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Section 6: Evidence Coverage Audit */}
        <div className="report-section-card bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl overflow-hidden shadow-xs print:rounded-lg print:border-[#2B3138] print:bg-[#171B20] print:shadow-none print:mb-4">
          <button
            onClick={() => toggleSection('audit')}
            className="report-section-header w-full px-7 py-5 flex items-center justify-between text-left hover:bg-[#F7F4F2]/50 transition-colors border-b border-[#E7DAD8] print:bg-[#1D2228] print:border-[#2B3138] print:px-5 print:py-3 print:cursor-default"
          >
            <div className="flex items-center gap-3">
              <span className="w-7 h-7 rounded-xl bg-[#F4E9E7] text-[#873F46] text-xs font-bold flex items-center justify-center print:bg-[#873F46]/30 print:text-rose-300">6</span>
              <h2 className="text-[22px] font-bold text-[#302629] print:text-lg print:text-white">Evidence Coverage Audit</h2>
            </div>
            <div className="print:hidden">
              {openSections.audit ? <ChevronUp className="w-5 h-5 text-[#78696B]" /> : <ChevronDown className="w-5 h-5 text-[#78696B]" />}
            </div>
          </button>

          {report.evidence_coverage_audit && (
            <div className={`report-section-content p-7 space-y-4 print:p-5 print:space-y-3 ${openSections.audit ? 'block' : 'hidden print:block'}`}>
              <div className="text-sm text-[#78696B] print:text-slate-300 print:text-xs">
                Formula: <code className="bg-[#F7F4F2] px-2 py-0.5 rounded border border-[#E7DAD8] text-xs font-mono print:bg-[#1e242c] print:border-[#334155] print:text-white">{report.evidence_coverage_audit.coverage_formula_explanation}</code>
              </div>
              <div className="print-avoid-break grid grid-cols-2 sm:grid-cols-4 gap-4 print:gap-3">
                <div className="p-4 bg-[#F7F4F2] rounded-xl border border-[#E7DAD8] text-center print:bg-[#1a1f26] print:border-[#2B3138] print:p-3">
                  <span className="text-xs text-[#78696B] block print:text-slate-300">Coverage Ratio</span>
                  <span className="text-2xl font-black text-[#873F46] print:text-xl print:text-rose-400">
                    {((report.evidence_coverage_audit.evidence_coverage_ratio || 0) * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="p-4 bg-[#EDF6F0] rounded-xl border border-[#3E7B54]/20 text-center print:bg-emerald-950/20 print:border-emerald-800/40 print:p-3">
                  <span className="text-xs text-[#3E7B54] block print:text-emerald-400">Corroborated</span>
                  <span className="text-2xl font-black text-[#3E7B54] print:text-xl print:text-emerald-400">{report.evidence_coverage_audit.supported_count}</span>
                </div>
                <div className="p-4 bg-[#FAF2EA] rounded-xl border border-[#C06E22]/20 text-center print:bg-amber-950/20 print:border-amber-800/40 print:p-3">
                  <span className="text-xs text-[#C06E22] block print:text-amber-400">Mixed Signals</span>
                  <span className="text-2xl font-black text-[#C06E22] print:text-xl print:text-amber-400">{report.evidence_coverage_audit.mixed_count}</span>
                </div>
                <div className="p-4 bg-[#F7F4F2] rounded-xl border border-[#E7DAD8] text-center print:bg-[#1a1f26] print:border-[#2B3138] print:p-3">
                  <span className="text-xs text-[#78696B] block print:text-slate-300">Needs Evidence</span>
                  <span className="text-2xl font-black text-[#78696B] print:text-xl print:text-slate-200">{report.evidence_coverage_audit.insufficient_evidence_count}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Section 7: Core Research Questions Analysis */}
        {report.research_questions_analysis && report.research_questions_analysis.length > 0 && (
          <div className="report-section-card bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl overflow-hidden shadow-xs print:rounded-lg print:border-[#2B3138] print:bg-[#171B20] print:shadow-none print:mb-4">
            <button
              onClick={() => toggleSection('questions')}
              className="report-section-header w-full px-7 py-5 flex items-center justify-between text-left hover:bg-[#F7F4F2]/50 transition-colors border-b border-[#E7DAD8] print:bg-[#1D2228] print:border-[#2B3138] print:px-5 print:py-3 print:cursor-default"
            >
              <div className="flex items-center gap-3">
                <span className="w-7 h-7 rounded-xl bg-[#F4E9E7] text-[#873F46] text-xs font-bold flex items-center justify-center print:bg-[#873F46]/30 print:text-rose-300">7</span>
                <h2 className="text-[22px] font-bold text-[#302629] print:text-lg print:text-white">
                  Core Research Questions Analysis ({report.research_questions_analysis.length})
                </h2>
              </div>
              <div className="print:hidden">
                {openSections.questions ? <ChevronUp className="w-5 h-5 text-[#78696B]" /> : <ChevronDown className="w-5 h-5 text-[#78696B]" />}
              </div>
            </button>

            <div className={`report-section-content p-7 space-y-5 print:p-5 print:space-y-4 ${openSections.questions ? 'block' : 'hidden print:block'}`}>
              {report.research_questions_analysis.map((rqa, i) => (
                <div key={i} className="print-avoid-break p-5 rounded-xl bg-[#F7F4F2] border border-[#E7DAD8] space-y-3 print:bg-[#1a1f26] print:border-[#2B3138] print:p-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#E7DAD8] pb-3 print:border-[#2B3138]">
                    <div className="flex items-center gap-2.5">
                      <span className="w-6 h-6 rounded-lg bg-[#F4E9E7] text-[#873F46] text-xs font-bold flex items-center justify-center shrink-0 print:bg-[#873F46]/30 print:text-rose-300">
                        Q{i + 1}
                      </span>
                      <h3 className="text-base font-bold text-[#302629] leading-snug print:text-sm print:text-white">{rqa.question}</h3>
                    </div>
                    <div className="flex items-center gap-2 self-start sm:self-auto shrink-0 flex-wrap">
                      {getBasisBadge(rqa.basis)}
                      {getQuestionValidationBadge(rqa)}
                    </div>
                  </div>

                  <div className="text-sm text-[#302629] leading-relaxed bg-[#FFFFFF] p-4 rounded-lg border border-[#E7DAD8] print:bg-[#14171d] print:border-[#2B3138] print:text-xs print:text-white">
                    {rqa.answer}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs pt-1">
                    <div>
                      <span className="font-bold text-[#78696B] uppercase tracking-wider block mb-1 print:text-slate-300">Supporting Sources</span>
                      {rqa.supporting_sources && rqa.supporting_sources.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {rqa.supporting_sources.map((src, idx) => (
                            <span key={idx} className="px-2 py-0.5 rounded bg-[#F4E9E7] text-[#873F46] font-medium border border-[#B66B70]/20 print:bg-red-950/40 print:text-rose-300 print:border-rose-800/30">
                              {src}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-[#78696B] italic print:text-slate-400">None (Model Knowledge Fallback)</span>
                      )}
                    </div>
                    <div>
                      <span className="font-bold text-[#78696B] uppercase tracking-wider block mb-1 print:text-slate-300">Confidence</span>
                      <p className="text-[#302629] print:text-white">{rqa.confidence}</p>
                    </div>
                    <div>
                      <span className="font-bold text-[#78696B] uppercase tracking-wider block mb-1 print:text-slate-300">Key Limitation</span>
                      <p className="text-[#78696B] print:text-slate-300">{rqa.limitations?.[0] || 'Standard domain constraints apply'}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportsPage;
