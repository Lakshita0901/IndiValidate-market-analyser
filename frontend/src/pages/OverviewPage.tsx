import React, { useState } from 'react';
import {
  Compass,
  ArrowRight,
  Activity,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  Users,
  Database,
  MapPin,
  TrendingUp,
  RotateCcw,
  PlusCircle,
  FileText,
  Layers,
  Sparkles,
  Download,
  ShieldCheck,
  ShieldAlert,
  Info,
  Clock,
  ExternalLink,
} from 'lucide-react';
import {
  AnalysisRunRecord,
  AnalysisRunStatus,
  MarketValidationReport,
  PageId,
} from '../types';
import { downloadFile, generateReportMarkdown } from '../utils/markdownExporter';

interface OverviewPageProps {
  report: MarketValidationReport | null;
  onNavigate: (page: PageId) => void;
  onQuickStart: (idea: string) => void;
  onLoadSample: () => void;
  isAnalysisRunning?: boolean;
  activeIdeaText?: string;
  errorMessage?: string | null;
  history?: AnalysisRunRecord[];
  onSelectReport?: (selectedReport: MarketValidationReport) => void;
}

interface SourceVerification {
  key: string;
  title: string;
  category: string;
  datasetName: string;
  status: 'supported' | 'usable_records' | 'no_relevant_records' | 'unavailable';
  statusLabel: string;
  recordsCount: number;
  findingIds: string[];
  sampleRecord?: string;
  limitationNote: string;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  report,
  onNavigate,
  onQuickStart,
  onLoadSample,
  isAnalysisRunning = false,
  activeIdeaText = '',
  errorMessage = null,
  history = [],
  onSelectReport,
}) => {
  const [quickIdea, setQuickIdea] = useState('');

  const handleStart = (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickIdea.trim()) return;
    onQuickStart(quickIdea.trim());
  };

  const sampleIdeas = [
    'Smart EV fleet charging hub and reservation software in Ahmedabad with peak-shaving power storage',
    'B2B cold-chain temperature telemetry sensors for dairy cooperatives in Anand',
    'On-demand solar-powered micro-irrigation pump sharing platform for smallholders in Maharashtra',
  ];

  // 1. Current / Latest Analysis State
  const latestIdea = isAnalysisRunning
    ? activeIdeaText
    : (report?.idea_and_context?.business_idea || history[0]?.idea || 'No active analysis');

  const targetLocation =
    typeof report?.idea_and_context?.target_geography?.location === 'string'
      ? report.idea_and_context.target_geography.location
      : typeof report?.idea_and_context?.target_geography?.city === 'string'
      ? report.idea_and_context.target_geography.city
      : (history[0]?.geography || null);

  const reportId = report?.report_id || history[0]?.id || (isAnalysisRunning ? 'Pending Analysis' : 'Unavailable');
  const timestamp = report?.generated_at || history[0]?.timestamp || (isAnalysisRunning ? 'Live Stream' : 'Unavailable');

  // Compute status of the latest run
  const issues = (report?.diagnostics?.issues as unknown[]) || [];
  const latestStatus: AnalysisRunStatus = isAnalysisRunning
    ? 'running'
    : errorMessage
    ? 'failed'
    : !report
    ? 'failed'
    : issues.length > 0
    ? 'completed_with_failures'
    : 'completed';

  // 2. Compute 4 Application-Level Stat Cards
  // Stat 1: Total analyses run in this session/store
  const totalAnalysesCount = history.length || (report ? 1 : 0);

  // Stat 2: Evaluated personas / attempted personas
  const totalPersonasAttempted = report
    ? Number(report.diagnostics?.total_personas ?? 10)
    : null;
  const successfullyEvaluatedPersonas = report
    ? Number(
        report.diagnostics?.total_evaluations ??
          (report.segment_comparison
            ? report.segment_comparison.reduce((acc, s) => acc + (s.evaluated_personas_count || 0), 0)
            : 10)
      )
    : null;

  // Stat 4: Failed stages vs persona evaluation failures
  const failedStagesCount = errorMessage
    ? 1
    : ((report?.diagnostics?.failed_stages as unknown[])?.length || (latestStatus === 'failed' ? 1 : 0));
  const failedEvaluationsCount =
    totalPersonasAttempted !== null && successfullyEvaluatedPersonas !== null
      ? Math.max(0, totalPersonasAttempted - successfullyEvaluatedPersonas)
      : 0;

  // 3. Evidence Traceability & Source-Level Status Evaluation
  const traceability = report?.evidence_traceability || [];
  const representedSources = (report?.evidence_coverage_audit?.sources_represented || []).map((s) => s.toLowerCase());

  const evaluateSourceStatus = (
    key: string,
    title: string,
    category: string,
    datasetName: string,
    patterns: string[],
    defaultLimitation: string
  ): SourceVerification => {
    if (!report) {
      return {
        key,
        title,
        category,
        datasetName,
        status: 'unavailable',
        statusLabel: 'Unavailable (No Active Report)',
        recordsCount: 0,
        findingIds: [],
        limitationNote: 'Run an analysis to inspect empirical source retrieval.',
      };
    }

    // Match records in evidence traceability
    const matchingRecords = traceability.filter((t) =>
      patterns.some((p) => (t.source_type || '').toLowerCase().includes(p))
    );

    const isRepresented = patterns.some((p) =>
      representedSources.some((src) => src.includes(p))
    );

    // Collect findings supported
    const allSupportedFindings = Array.from(
      new Set(matchingRecords.flatMap((r) => r.findings_supported || []))
    );

    if (matchingRecords.length > 0 && allSupportedFindings.length > 0) {
      return {
        key,
        title,
        category,
        datasetName,
        status: 'supported',
        statusLabel: 'Findings Supported by Evidence',
        recordsCount: matchingRecords.length,
        findingIds: allSupportedFindings,
        sampleRecord: matchingRecords[0].factual_summary,
        limitationNote: matchingRecords[0].caveats_and_limitations?.[0] || defaultLimitation,
      };
    }

    if (matchingRecords.length > 0 || isRepresented) {
      return {
        key,
        title,
        category,
        datasetName,
        status: 'usable_records',
        statusLabel: 'Usable Empirical Records',
        recordsCount: Math.max(1, matchingRecords.length),
        findingIds: [],
        sampleRecord: matchingRecords[0]?.factual_summary || 'Empirical benchmark extracted and vectorized in Chroma store.',
        limitationNote: matchingRecords[0]?.caveats_and_limitations?.[0] || defaultLimitation,
      };
    }

    return {
      key,
      title,
      category,
      datasetName,
      status: 'no_relevant_records',
      statusLabel: 'No Relevant Records Found for Geography',
      recordsCount: 0,
      findingIds: [],
      limitationNote: `No matched observations in ${datasetName} for target location. Domain prior reasoning utilized as fallback.`,
    };
  };

  const sourcesStatusList: SourceVerification[] = [
    evaluateSourceStatus(
      'census',
      'Census 2011 Data',
      'Demographic & Urban Benchmarks',
      'Primary Census Abstract (PCA & C-08)',
      ['census'],
      'Historical 2011 census demographics establish urban baseline density.'
    ),
    evaluateSourceStatus(
      'plfs',
      'Labour & Wage Data (PLFS 2025)',
      'Income & Purchasing Power Benchmarks',
      'Periodic Labour Force Survey 2024-2025',
      ['plfs', 'labour'],
      'State-level wage percentiles benchmark customer pricing affordability.'
    ),
    evaluateSourceStatus(
      'reddit',
      'Reddit Community Discussions',
      'Unprompted Operator & Consumer Discussions',
      'Kaggle Authenticated Indian Subreddit Dataset',
      ['reddit'],
      'Qualitative sentiment from fleet operators and EV drivers detailing queue delays.'
    ),
    evaluateSourceStatus(
      'trends',
      'Google Trends',
      'Search Interest & Keyword Momentum',
      'Relative Search Index (pytrends)',
      ['trend'],
      'Relative search volume trajectories indicate consumer discovery momentum.'
    ),
  ];

  // Stat 3: Number of configured research sources that returned usable empirical evidence
  const usableSourcesCount = sourcesStatusList.filter(
    (s) => s.status === 'supported' || s.status === 'usable_records'
  ).length;

  // 4. Headline Signals (1-line previews with clear provenance labels)
  const topOpportunity = report?.what_appears_promising?.[0];
  const topRisk = report?.what_may_not_work?.[0];
  const topExperiment = report?.recommended_experiments?.[0];

  const getStatusProvenanceBadge = (status?: string) => {
    switch ((status || '').toLowerCase()) {
      case 'supported':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#EDF6F0] text-[#3E7B54] border border-[#3E7B54]/20 flex items-center gap-1 shrink-0">
            <CheckCircle2 size={12} />
            <span>Corroborated by Evidence</span>
          </span>
        );
      case 'contradicted':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#F4E9E7] text-[#873F46] border border-[#873F46]/30 flex items-center gap-1 shrink-0">
            <XCircle size={12} />
            <span>Contradicted by Evidence</span>
          </span>
        );
      case 'mixed':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#FAF2EA] text-[#C06E22] border border-[#C06E22]/30 flex items-center gap-1 shrink-0">
            <AlertTriangle size={12} />
            <span>Mixed Signals</span>
          </span>
        );
      case 'insufficient_evidence':
      default:
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#F7F4F2] text-[#78696B] border border-[#E7DAD8] flex items-center gap-1 shrink-0">
            <HelpCircle size={12} />
            <span>Model Domain Reasoning (Unverified)</span>
          </span>
        );
    }
  };

  const handleExportMarkdown = () => {
    if (!report) return;
    const md = generateReportMarkdown(report);
    downloadFile(md, `${report.report_id || 'validation_report'}.md`, 'text/markdown');
  };

  return (
    <div className="space-y-7 animate-fadeIn">
      {/* ─────────────────────────────────────────────────────────────
          1. Control Center Header Bar & Quick Actions
      ───────────────────────────────────────────────────────────── */}
      <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 sm:p-7 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-5">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full bg-[#F4E9E7] text-[#873F46] text-xs font-bold border border-[#B66B70]/20">
              <Compass size={13} />
              Application Control Center
            </span>
            <span className="text-xs text-[#78696B] flex items-center gap-1">
              <Clock size={12} />
              System Telemetry &amp; Run Governance
            </span>
          </div>
          <h1 className="text-2xl sm:text-[28px] font-extrabold text-[#302629] leading-tight tracking-tight">
            Validation Operations &amp; Evidence Monitor
          </h1>
          <p className="text-xs sm:text-sm text-[#78696B] mt-1 max-w-2xl leading-relaxed">
            Monitor pipeline execution health, cross-run empirical grounding, source retrieval verification, and operational governance across validation analyses.
          </p>
        </div>

        {/* Quick Actions */}
        <div className="flex flex-wrap items-center gap-2.5 shrink-0">
          <button
            onClick={() => onNavigate('new-analysis')}
            className="px-4 py-2.5 bg-[#873F46] hover:bg-[#873F46]/90 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-xs transition-colors"
          >
            <PlusCircle size={15} />
            <span>Start New Analysis</span>
          </button>

          {isAnalysisRunning && (
            <button
              onClick={() => onNavigate('progress')}
              className="px-3.5 py-2.5 bg-[#FAF2EA] hover:bg-[#FAF2EA]/80 text-[#C06E22] border border-[#C06E22]/30 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors animate-pulse"
            >
              <Activity size={15} />
              <span>Open Live Progress</span>
            </button>
          )}

          {report && (
            <>
              <button
                onClick={() => onNavigate('reports')}
                className="px-3.5 py-2.5 border border-[#E7DAD8] hover:bg-[#F7F4F2] text-[#302629] rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors shadow-2xs"
                title="View full audit report"
              >
                <FileText size={15} className="text-[#78696B]" />
                <span>Full Report</span>
              </button>
              <button
                onClick={handleExportMarkdown}
                className="p-2.5 border border-[#E7DAD8] hover:bg-[#F7F4F2] text-[#78696B] hover:text-[#302629] rounded-xl text-xs font-medium flex items-center justify-center transition-colors shadow-2xs"
                title="Export Markdown Report"
              >
                <Download size={15} />
              </button>
            </>
          )}

          <button
            onClick={onLoadSample}
            className="px-3 py-2.5 bg-[#F7F4F2] hover:bg-[#F4E9E7] text-[#78696B] hover:text-[#873F46] rounded-xl text-xs font-medium border border-[#E7DAD8] transition-colors"
            title="Load reference benchmark analysis"
          >
            <RotateCcw size={14} />
          </button>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          2. Latest Analysis Hero
      ───────────────────────────────────────────────────────────── */}
      <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 sm:p-7 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E7DAD8] pb-4 mb-4">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-bold uppercase tracking-wider text-[#78696B]">
              Latest Analysis Execution
            </span>
            <span className="font-mono text-xs font-bold bg-[#F4E9E7] text-[#873F46] px-2.5 py-0.5 rounded-full border border-[#B66B70]/20">
              {reportId}
            </span>
            {targetLocation && (
              <span className="text-xs text-[#78696B] flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-[#F7F4F2] border border-[#E7DAD8]">
                <MapPin size={11} className="text-[#873F46]" />
                {targetLocation}
              </span>
            )}
            <span className="text-xs text-[#78696B]">
              Generated: {timestamp}
            </span>
          </div>

          {/* Status Badge */}
          <div>
            {latestStatus === 'running' && (
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-[#FAF2EA] text-[#C06E22] border border-[#C06E22]/30 flex items-center gap-1.5 animate-pulse">
                <Activity size={13} />
                <span>Running Pipeline Execution</span>
              </span>
            )}
            {latestStatus === 'completed' && (
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-[#EDF6F0] text-[#3E7B54] border border-[#3E7B54]/20 flex items-center gap-1.5">
                <CheckCircle2 size={13} />
                <span>Completed (All Required Stages)</span>
              </span>
            )}
            {latestStatus === 'completed_with_failures' && (
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-[#FAF2EA] text-[#C06E22] border border-[#C06E22]/30 flex items-center gap-1.5">
                <AlertTriangle size={13} />
                <span>Completed with Failures / Warnings</span>
              </span>
            )}
            {latestStatus === 'failed' && (
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-[#F4E9E7] text-[#873F46] border border-[#873F46]/30 flex items-center gap-1.5">
                <XCircle size={13} />
                <span>Pipeline Execution Failed</span>
              </span>
            )}
          </div>
        </div>

        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
          <div className="space-y-2 max-w-3xl">
            <h2 className="text-xl sm:text-2xl font-bold text-[#302629] leading-snug">
              {latestIdea}
            </h2>
            {errorMessage ? (
              <div className="p-3 bg-[#F4E9E7] border border-[#873F46]/30 rounded-xl text-xs text-[#873F46] font-medium flex items-start gap-2">
                <AlertTriangle size={14} className="shrink-0 mt-0.5" />
                <span>{errorMessage}</span>
              </div>
            ) : (
              <p className="text-xs sm:text-sm text-[#78696B] leading-relaxed">
                {report?.executive_summary?.idea_description ||
                  'No executive summary description available. Initiate an analysis to generate calibrated persona evaluations and empirical evidence grounding.'}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            {report && (
              <button
                onClick={() => onNavigate('reports')}
                className="px-4 py-2.5 bg-[#873F46] hover:bg-[#873F46]/90 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-xs transition-colors"
              >
                <span>Open Full Report</span>
                <ArrowRight size={14} />
              </button>
            )}
            {isAnalysisRunning && (
              <button
                onClick={() => onNavigate('progress')}
                className="px-4 py-2.5 bg-[#1D2228] hover:bg-[#2B3138] text-white rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors border border-[#2B3138]"
              >
                <span>View Telemetry Stream</span>
                <ArrowRight size={14} />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          3. Four Application-Level Stat Cards
      ───────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Stat 1: Total analyses run */}
        <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-5 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-[#78696B] uppercase tracking-wider">
              Total Analyses Run
            </span>
            <div className="w-8 h-8 rounded-xl bg-[#F4E9E7] text-[#873F46] flex items-center justify-center">
              <Compass size={16} />
            </div>
          </div>
          <div className="text-2xl font-black text-[#302629] mb-1">
            {totalAnalysesCount}
            <span className="text-xs font-medium text-[#78696B] ml-1.5">
              pipeline runs
            </span>
          </div>
          <div className="text-xs text-[#78696B] leading-tight">
            Historical and active runs logged in current environment
          </div>
        </div>

        {/* Stat 2: Successfully evaluated personas / attempted */}
        <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-5 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-[#78696B] uppercase tracking-wider">
              Evaluated Personas
            </span>
            <div className="w-8 h-8 rounded-xl bg-[#EDF6F0] text-[#3E7B54] flex items-center justify-center">
              <Users size={16} />
            </div>
          </div>
          <div className="text-2xl font-black text-[#302629] mb-1">
            {successfullyEvaluatedPersonas !== null
              ? `${successfullyEvaluatedPersonas} / ${totalPersonasAttempted ?? 10}`
              : 'Unavailable'}
          </div>
          <div className="text-xs text-[#78696B] leading-tight">
            Synthetic archetypes evaluated without rate-limit aborts
          </div>
        </div>

        {/* Stat 3: Number of configured research sources with usable empirical evidence */}
        <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-5 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-[#78696B] uppercase tracking-wider">
              Usable Empirical Sources
            </span>
            <div className="w-8 h-8 rounded-xl bg-[#FAF2EA] text-[#C06E22] flex items-center justify-center">
              <Database size={16} />
            </div>
          </div>
          <div className="text-2xl font-black text-[#873F46] mb-1">
            {usableSourcesCount} / 4
            <span className="text-xs font-medium text-[#78696B] ml-1.5">
              sources
            </span>
          </div>
          <div className="text-xs text-[#78696B] leading-tight">
            Census, PLFS, Reddit, &amp; Trends returning usable records
          </div>
        </div>

        {/* Stat 4: Failed stages/evaluations */}
        <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-5 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-[#78696B] uppercase tracking-wider">
              Failed Stages / Evals
            </span>
            <div className="w-8 h-8 rounded-xl bg-[#F4E9E7] text-[#873F46] flex items-center justify-center">
              <ShieldAlert size={16} />
            </div>
          </div>
          <div className="text-xl font-black text-[#302629] mb-1">
            {failedStagesCount} Stages · {failedEvaluationsCount} Personas
          </div>
          <div className="text-xs text-[#78696B] leading-tight">
            Distinguishing graph faults from persona simulation failures
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          4. Evidence Coverage & Source-Level Status Panel
      ───────────────────────────────────────────────────────────── */}
      <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 sm:p-7 shadow-xs space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-[#302629]">
                Empirical Evidence &amp; Source Verification Panel
              </h2>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#873F46]/10 text-[#873F46]">
                Data Integrity Audit
              </span>
            </div>
            <p className="text-xs text-[#78696B] mt-0.5">
              Rigorous source-level status distinguishing sources that returned usable empirical evidence from unretrieved, failed, or model domain fallbacks.
            </p>
          </div>
          <button
            onClick={() => onNavigate('market-insights')}
            className="text-xs font-bold text-[#873F46] hover:underline flex items-center gap-1 self-start sm:self-auto shrink-0"
          >
            <span>Inspect Full Evidence Audit</span>
            <ArrowRight size={13} />
          </button>
        </div>

        {/* Coverage summary metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          <div className="p-4 bg-[#F7F4F2] rounded-xl border border-[#E7DAD8] text-center">
            <span className="text-xs text-[#78696B] block">Evidence Coverage</span>
            <span className="text-2xl font-black text-[#873F46]">
              {report?.evidence_coverage_audit?.evidence_coverage_ratio !== undefined
                ? `${((report.evidence_coverage_audit.evidence_coverage_ratio || 0) * 100).toFixed(0)}%`
                : 'Unavailable'}
            </span>
            <span className="text-[10px] text-[#78696B] block mt-0.5">
              (supported + mixed) / total
            </span>
          </div>
          <div className="p-4 bg-[#EDF6F0] rounded-xl border border-[#3E7B54]/20 text-center">
            <span className="text-xs text-[#3E7B54] block">Corroborated</span>
            <span className="text-2xl font-black text-[#3E7B54]">
              {report?.evidence_coverage_audit?.supported_count ?? 0}
            </span>
            <span className="text-[10px] text-[#3E7B54] block mt-0.5">
              Backed directly by data
            </span>
          </div>
          <div className="p-4 bg-[#FAF2EA] rounded-xl border border-[#C06E22]/20 text-center">
            <span className="text-xs text-[#C06E22] block">Mixed Signals</span>
            <span className="text-2xl font-black text-[#C06E22]">
              {report?.evidence_coverage_audit?.mixed_count ?? 0}
            </span>
            <span className="text-[10px] text-[#C06E22] block mt-0.5">
              Partial empirical match
            </span>
          </div>
          <div className="p-4 bg-[#F7F4F2] rounded-xl border border-[#E7DAD8] text-center">
            <span className="text-xs text-[#78696B] block">Model Prior Fallbacks</span>
            <span className="text-2xl font-black text-[#78696B]">
              {report?.evidence_coverage_audit?.insufficient_evidence_count ?? 0}
            </span>
            <span className="text-[10px] text-[#78696B] block mt-0.5">
              Needs field validation
            </span>
          </div>
        </div>

        {/* 4 Configured Source Verification Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
          {sourcesStatusList.map((src) => (
            <div
              key={src.key}
              className="p-4 rounded-xl bg-[#F7F4F2] border border-[#E7DAD8] space-y-2.5"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="text-sm font-bold text-[#302629] leading-snug">{src.title}</h3>
                  <span className="text-[11px] text-[#78696B] block">{src.datasetName}</span>
                </div>
                {/* Status Pill */}
                {src.status === 'supported' && (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#EDF6F0] text-[#3E7B54] border border-[#3E7B54]/20 flex items-center gap-1 shrink-0">
                    <CheckCircle2 size={12} />
                    <span>Findings Supported</span>
                  </span>
                )}
                {src.status === 'usable_records' && (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#FAF2EA] text-[#C06E22] border border-[#C06E22]/30 flex items-center gap-1 shrink-0">
                    <Database size={12} />
                    <span>Usable Records</span>
                  </span>
                )}
                {src.status === 'no_relevant_records' && (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#F4E9E7] text-[#873F46] border border-[#873F46]/20 flex items-center gap-1 shrink-0">
                    <AlertTriangle size={12} />
                    <span>No Relevant Records</span>
                  </span>
                )}
                {src.status === 'unavailable' && (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#F7F4F2] text-[#78696B] border border-[#E7DAD8] flex items-center gap-1 shrink-0">
                    <HelpCircle size={12} />
                    <span>Unavailable</span>
                  </span>
                )}
              </div>

              {src.sampleRecord && (
                <div className="text-xs text-[#302629] bg-[#FFFFFF] p-2.5 rounded-lg border border-[#E7DAD8] leading-relaxed line-clamp-2">
                  <span className="font-semibold text-[#78696B] mr-1">Extracted Signal:</span>
                  {src.sampleRecord}
                </div>
              )}

              <div className="text-[11px] text-[#78696B] leading-tight">
                <span className="font-semibold text-[#302629]">Boundary / Limitation:</span>{' '}
                {src.limitationNote}
              </div>
            </div>
          ))}
        </div>

        {/* Epistemic disclaimer */}
        <div className="p-3 bg-[#FAF2EA]/50 rounded-xl border border-[#C06E22]/20 text-xs text-[#302629] flex items-start gap-2">
          <Info size={14} className="text-[#C06E22] shrink-0 mt-0.5" />
          <span>
            <strong>Epistemic Verification Rule:</strong> A successful HTTP request or data fetch does not constitute empirical market evidence. Usable evidence requires verified records that directly ground or constrain customer hypotheses. Zero empirical evidence reflects insufficient validation.
          </span>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          5. Headline Signals (One-line Previews with Provenance)
      ───────────────────────────────────────────────────────────── */}
      <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 sm:p-7 shadow-xs space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-[#302629]">Headline Signals</h2>
            <p className="text-xs text-[#78696B]">
              Concise previews of core findings with explicit evidence provenance. Detailed analysis available in linked report sections.
            </p>
          </div>
        </div>

        <div className="space-y-3 pt-1">
          {/* Signal 1: Top Opportunity */}
          <div className="p-4 rounded-xl bg-[#F7F4F2] border border-[#E7DAD8] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-1 max-w-2xl">
              <span className="text-[11px] font-bold text-[#3E7B54] uppercase tracking-wider block">
                Top Opportunity Hypothesis
              </span>
              <p className="text-sm font-bold text-[#302629] leading-snug">
                {topOpportunity?.claim_or_hypothesis ||
                  report?.executive_summary?.strongest_promising_signals?.[0] ||
                  'No opportunity hypothesis recorded'}
              </p>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              {getStatusProvenanceBadge(topOpportunity?.evidence_validation_status)}
              <button
                onClick={() => onNavigate('market-insights')}
                className="text-xs font-bold text-[#873F46] hover:underline flex items-center gap-1"
              >
                <span>Inspect in Market Insights</span>
                <ArrowRight size={12} />
              </button>
            </div>
          </div>

          {/* Signal 2: Top Risk */}
          <div className="p-4 rounded-xl bg-[#F7F4F2] border border-[#E7DAD8] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-1 max-w-2xl">
              <span className="text-[11px] font-bold text-[#C06E22] uppercase tracking-wider block">
                Top Risk &amp; Adoption Hurdle
              </span>
              <p className="text-sm font-bold text-[#302629] leading-snug">
                {topRisk?.concern_or_barrier ||
                  report?.executive_summary?.key_risks_and_barriers?.[0] ||
                  'No critical risk recorded'}
              </p>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              {getStatusProvenanceBadge(topRisk?.evidence_validation_status)}
              <button
                onClick={() => onNavigate('market-insights')}
                className="text-xs font-bold text-[#873F46] hover:underline flex items-center gap-1"
              >
                <span>Inspect in Market Insights</span>
                <ArrowRight size={12} />
              </button>
            </div>
          </div>

          {/* Signal 3: Next Recommended Experiment */}
          <div className="p-4 rounded-xl bg-[#F7F4F2] border border-[#E7DAD8] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-1 max-w-2xl">
              <span className="text-[11px] font-bold text-[#873F46] uppercase tracking-wider block">
                Next Recommended Experiment
              </span>
              <p className="text-sm font-bold text-[#302629] leading-snug">
                {topExperiment?.question_to_validate ||
                  report?.executive_summary?.next_validation_priority ||
                  'No experiment protocol recorded'}
              </p>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#F4E9E7] text-[#873F46] border border-[#B66B70]/20 flex items-center gap-1 shrink-0">
                <Compass size={12} />
                <span>Empirical Protocol</span>
              </span>
              <button
                onClick={() => onNavigate('reports')}
                className="text-xs font-bold text-[#873F46] hover:underline flex items-center gap-1"
              >
                <span>View Protocol in Full Report</span>
                <ArrowRight size={12} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          6. Recent Analyses Table
      ───────────────────────────────────────────────────────────── */}
      <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 sm:p-7 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-xl font-bold text-[#302629]">Recent Analyses &amp; Run History</h2>
            <p className="text-xs text-[#78696B]">
              Historical runs logged in this environment. Select a run to inspect its full report or export data.
            </p>
          </div>
          <span className="text-xs font-medium text-[#78696B] self-start sm:self-auto">
            {history.length} {history.length === 1 ? 'record' : 'records'} logged
          </span>
        </div>

        {history.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[#E7DAD8] text-[#78696B] font-bold uppercase tracking-wider">
                  <th className="py-3 px-3">Idea Concept</th>
                  <th className="py-3 px-3">Date / Time</th>
                  <th className="py-3 px-3">Run Status</th>
                  <th className="py-3 px-3">Evidence Coverage</th>
                  <th className="py-3 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E7DAD8]">
                {history.map((run) => (
                  <tr key={run.id} className="hover:bg-[#F7F4F2]/50 transition-colors">
                    <td className="py-3 px-3 font-semibold text-[#302629] max-w-xs truncate" title={run.idea}>
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-[10px] text-[#78696B] bg-[#F7F4F2] px-1.5 py-0.5 rounded border border-[#E7DAD8]">
                          {run.id.slice(0, 10)}
                        </span>
                        <span className="truncate">{run.idea}</span>
                      </div>
                    </td>
                    <td className="py-3 px-3 text-[#78696B] whitespace-nowrap">
                      {run.timestamp}
                    </td>
                    <td className="py-3 px-3 whitespace-nowrap">
                      {run.status === 'completed' && (
                        <span className="px-2 py-0.5 rounded-full font-bold bg-[#EDF6F0] text-[#3E7B54] text-[11px]">
                          Completed
                        </span>
                      )}
                      {run.status === 'completed_with_failures' && (
                        <span className="px-2 py-0.5 rounded-full font-bold bg-[#FAF2EA] text-[#C06E22] text-[11px]">
                          Completed with Warnings
                        </span>
                      )}
                      {run.status === 'failed' && (
                        <span className="px-2 py-0.5 rounded-full font-bold bg-[#F4E9E7] text-[#873F46] text-[11px]">
                          Failed
                        </span>
                      )}
                      {run.status === 'running' && (
                        <span className="px-2 py-0.5 rounded-full font-bold bg-[#FAF2EA] text-[#C06E22] text-[11px] animate-pulse">
                          Running
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-3 whitespace-nowrap">
                      {run.evidenceCoverageRatio >= 0 ? (
                        <span className="font-semibold text-[#302629]">
                          {(run.evidenceCoverageRatio * 100).toFixed(0)}% Coverage ({run.supportedFindingsCount} supported)
                        </span>
                      ) : (
                        <span className="text-[#78696B] italic">Unavailable</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-right whitespace-nowrap">
                      {run.report ? (
                        <button
                          onClick={() => {
                            if (onSelectReport) {
                              onSelectReport(run.report!);
                            } else {
                              onNavigate('reports');
                            }
                          }}
                          className="px-2.5 py-1 bg-[#873F46] hover:bg-[#873F46]/90 text-white rounded-lg text-xs font-bold transition-colors shadow-2xs"
                        >
                          Open Report
                        </button>
                      ) : (
                        <span className="text-[#78696B] italic">Report Unavailable</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-6 text-center text-[#78696B] bg-[#F7F4F2] rounded-xl border border-[#E7DAD8]">
            <p className="text-xs">No historical analysis runs logged. Run an analysis or load the benchmark report.</p>
          </div>
        )}

        {/* Persistence Audit Notice Callout */}
        <div className="p-3.5 bg-[#F7F4F2] rounded-xl border border-[#E7DAD8] text-xs text-[#78696B] flex items-start gap-2.5">
          <Info size={15} className="text-[#873F46] shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-bold text-[#302629] block">
              Persistence Audit &amp; Architecture Note
            </span>
            <p className="leading-relaxed">
              The IndiValidate FastAPI backend (<code className="font-mono text-[11px]">api.py</code>) currently executes pipeline runs statelessly in memory without server-side database persistence (<code className="font-mono text-[11px]">GET /api/history</code> is not yet implemented on the server). Run history is preserved locally in your browser session storage. To persist history across team members and browsers, adding an SQLite/PostgreSQL report store endpoint (<code className="font-mono text-[11px]">GET /api/analyses</code>) is recommended.
            </p>
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          7. Quick Start Idea Box
      ───────────────────────────────────────────────────────────── */}
      <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 sm:p-7 shadow-xs">
        <h2 className="text-lg font-bold text-[#302629] mb-1">
          Quick Concept Evaluation Dispatch
        </h2>
        <p className="text-xs text-[#78696B] mb-4">
          Quickly launch an empirical analysis with default parameters (10 personas, 3 worker concurrency).
        </p>
        <form onSubmit={handleStart} className="space-y-3">
          <div className="relative">
            <input
              type="text"
              value={quickIdea}
              onChange={(e) => setQuickIdea(e.target.value)}
              placeholder="Enter a new concept to test (e.g. Electric shuttle service connecting metro to IT parks in Pune)..."
              className="w-full px-4 py-3 text-sm bg-[#F7F4F2] border border-[#E7DAD8] rounded-xl text-[#302629] placeholder:text-[#78696B]/70 focus:outline-none focus:ring-2 focus:ring-[#873F46]/20 focus:border-[#873F46] focus:bg-[#FFFFFF] transition-all shadow-xs pr-36"
            />
            <button
              type="submit"
              disabled={!quickIdea.trim() || isAnalysisRunning}
              className="absolute right-1.5 top-1.5 bottom-1.5 px-4 bg-[#873F46] hover:bg-[#873F46]/90 disabled:bg-[#E7DAD8] disabled:text-[#78696B] disabled:cursor-not-allowed text-white rounded-lg text-xs font-bold flex items-center gap-1.5 transition-colors"
            >
              <span>Validate</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </form>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-[#78696B]">Preset ideas:</span>
          {sampleIdeas.map((idea, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setQuickIdea(idea)}
              className="text-xs bg-[#F7F4F2] hover:bg-[#F4E9E7] text-[#302629] hover:text-[#873F46] px-2.5 py-1 rounded-lg border border-[#E7DAD8] transition-colors text-left truncate max-w-xs"
            >
              {idea.slice(0, 36)}...
            </button>
          ))}
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          8. Epistemic Guardrails Note
      ───────────────────────────────────────────────────────────── */}
      <div className="p-4 bg-[#FAF2EA]/40 border border-[#C06E22]/20 rounded-xl text-xs text-[#78696B] flex items-start gap-2.5">
        <ShieldCheck size={16} className="text-[#C06E22] shrink-0 mt-0.5" />
        <div className="leading-relaxed">
          <strong className="text-[#302629]">Epistemic Guardrails:</strong> Synthetic personas are calibrated simulation archetypes on an ordinal 1–10 scale and must not be interpreted as real customer surveys, conversion percentages, or population adoption rates. Evidence coverage audits measure empirical data retrieval availability, not commercial viability. Zero empirical evidence reflects unvalidated hypotheses.
        </div>
      </div>
    </div>
  );
};

export default OverviewPage;
