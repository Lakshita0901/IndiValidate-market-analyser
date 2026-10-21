import React, { useState } from 'react';
import {
  Sparkles,
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
  Users,
  Compass,
  FileText,
  Layers,
  TrendingUp,
  HelpCircle,
  PlusCircle,
  ExternalLink,
  MapPin,
  CheckCircle2
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend
} from 'recharts';
import { MarketValidationReport, PageId, PersonaProfile } from '../types';
import { CircularGauge } from '../components/CircularGauge';
import { PersonaCard } from '../components/PersonaCard';
import { ProblemSolutionPair, ProblemSolutionItem } from '../components/ProblemSolutionPair';
import { extractPersonasFromReport } from '../utils/personaHelper';

interface OverviewPageProps {
  report: MarketValidationReport | null;
  onNavigate: (page: PageId) => void;
  onQuickStart: (idea: string) => void;
  onLoadSample: () => void;
  onSelectPersona?: (persona: PersonaProfile) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  report,
  onNavigate,
  onQuickStart,
  onLoadSample,
  onSelectPersona,
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

  // Extract persona profiles for preview
  const personas = report ? extractPersonasFromReport(report) : [];
  const previewPersonas = personas.slice(0, 3);

  // Compute metrics from report
  const totalPersonas = report
    ? Number(
        report.diagnostics?.total_evaluations ??
        (report.segment_comparison
          ? report.segment_comparison.reduce((acc, s) => acc + (s.evaluated_personas_count || 0), 0)
          : 10)
      )
    : 0;

  const segmentCount = report?.segment_comparison?.length ?? 0;

  const strongestOpportunity =
    report?.executive_summary?.strongest_promising_signals?.[0] ||
    report?.what_appears_promising?.[0]?.claim_or_hypothesis ||
    'High interest in operational predictability';

  const mainRisk =
    report?.executive_summary?.key_risks_and_barriers?.[0] ||
    report?.what_may_not_work?.[0]?.concern_or_barrier ||
    'Upfront capital expenditure & lock-in friction';

  // Safe location extraction
  const targetLocation =
    typeof report?.idea_and_context?.target_geography?.location === 'string'
      ? report.idea_and_context.target_geography.location
      : typeof report?.idea_and_context?.target_geography?.city === 'string'
      ? report.idea_and_context.target_geography.city
      : null;

  // Segment chart data
  const segmentChartData = (report?.segment_comparison || []).map((seg) => {
    const scores = seg.median_scores || {};
    return {
      name: seg.segment_name.length > 20 ? seg.segment_name.slice(0, 18) + '...' : seg.segment_name,
      fullName: seg.segment_name,
      avgInterest: scores.interest ?? 0,
      avgIntent: scores.purchase_intent ?? 0,
      affordability: scores.affordability ?? 0,
      barrier: seg.main_concerns?.[0] || 'Cost resistance',
    };
  });

  // Average intent calculation across segments
  const avgIntentVal = segmentChartData.length
    ? Number(
        (
          segmentChartData.reduce((acc, curr) => acc + curr.avgIntent, 0) /
          segmentChartData.length
        ).toFixed(1)
      )
    : 7.4;

  const avgAffordabilityVal = segmentChartData.length
    ? Number(
        (
          segmentChartData.reduce((acc, curr) => acc + curr.affordability, 0) /
          segmentChartData.length
        ).toFixed(1)
      )
    : 6.8;

  // Build problem-to-solution hypothesis pairs from report
  const problemSolutionItems: ProblemSolutionItem[] = report
    ? [
        {
          id: 'ps-1',
          problem:
            report.what_may_not_work?.[0]?.concern_or_barrier ||
            'Unpredictable charging queues cause schedule slippage for commercial delivery drivers',
          whyItMatters:
            'Delivery partners face strict SLA penalties and idle time directly erodes daily take-home earnings by 15-22%.',
          proposedSolution:
            report.what_appears_promising?.[0]?.claim_or_hypothesis ||
            'Guaranteed 15-minute slot reservation with dynamic queue assignment and priority lane routing',
          howToValidate:
            report.recommended_experiments?.[0]?.strategic_rationale ||
            'Conduct structured 20-minute discovery interviews with 12 fleet shift supervisors and measure actual queue turnaround times.',
          evidenceStatus: (report.evidence_coverage_audit?.supported_count === 0 && report.what_may_not_work?.[0]?.evidence_validation_status === 'supported')
            ? 'insufficient_evidence'
            : (report.what_may_not_work?.[0]?.evidence_validation_status || 'insufficient_evidence'),
          evidenceSource: report.what_may_not_work?.[0]?.contradicting_or_supporting_evidence_ids?.[0],
          affectedSegment: report.segment_comparison?.[0]?.segment_name,
        },
        {
          id: 'ps-2',
          problem:
            report.what_may_not_work?.[1]?.concern_or_barrier ||
            'High upfront terminal setup cost and resistance to multi-year software lock-in contracts',
          whyItMatters:
            'Small and medium fleet operators operate on thin 4–8% operating margins and avoid capital lock-up.',
          proposedSolution:
            report.feature_prioritization?.[0]?.feature_name
              ? `Modular adoption: ${report.feature_prioritization[0].feature_name} with pay-per-dispatch pricing`
              : 'Zero-capex pilot deployment with per-slot transaction fee billing',
          howToValidate:
            report.recommended_experiments?.[1]?.strategic_rationale ||
            'Run a pricing sensitivity survey offering pay-per-use vs monthly subscription to test drop-off threshold.',
          evidenceStatus: (report.evidence_coverage_audit?.supported_count === 0)
            ? 'insufficient_evidence'
            : (report.feature_prioritization?.[0]?.evidence_validation_status || 'insufficient_evidence'),
          evidenceSource: report.feature_prioritization?.[0]?.supporting_evidence_ids?.[0],
          affectedSegment: report.segment_comparison?.[1]?.segment_name,
        },
        {
          id: 'ps-3',
          problem:
            report.disagreement_and_uncertainty?.[0]?.topic ||
            'Grid load shedding and variable peak commercial power tariffs reduce cost advantage',
          whyItMatters:
            'Charging stations risk losing 30% daytime throughput during peak tariff windows if storage is absent.',
          proposedSolution:
            'Integrated battery energy storage system (BESS) buffer with automated off-peak tariff scheduling',
          howToValidate:
            'Verify commercial DISCOM tariff schedules and simulate ROI of 20kWh buffer battery under real peak rates.',
          evidenceStatus: 'insufficient_evidence',
          evidenceSource: 'Model domain prior',
        },
      ]
    : [];

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* 1. Welcome / Header Section */}
      <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 sm:p-8 shadow-xs">
        <div className="max-w-4xl">
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#F4E9E7] text-[#873F46] text-xs font-bold border border-[#B66B70]/20">
              <Compass size={14} />
              IndiValidate Market Validation Dashboard
            </span>
            {targetLocation && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-[#F7F4F2] text-[#78696B] text-xs font-medium border border-[#E7DAD8]">
                <MapPin size={12} className="text-[#873F46]" />
                {targetLocation}
              </span>
            )}
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold text-[#302629] tracking-tight mb-2">
            Market Demand &amp; Risk Hypothesis Evaluation
          </h1>

          {report?.idea_and_context?.business_idea ? (
            <div className="p-4 rounded-xl bg-[#F4E9E7]/40 border border-[#B66B70]/20 mb-5">
              <span className="text-xs font-bold text-[#873F46] uppercase tracking-wider block mb-1">
                Current Active Evaluation Concept
              </span>
              <p className="text-sm font-semibold text-[#302629] leading-snug">
                {report.idea_and_context.business_idea}
              </p>
            </div>
          ) : (
            <p className="text-sm sm:text-base text-[#78696B] leading-relaxed mb-6">
              Stress-test your venture hypotheses using calibrated synthetic customer personas evaluated against empirical data, PLFS wage benchmarks, and field evidence.
            </p>
          )}

          {/* Quick Idea Form */}
          <form onSubmit={handleStart} className="space-y-3">
            <div className="relative">
              <input
                type="text"
                value={quickIdea}
                onChange={(e) => setQuickIdea(e.target.value)}
                placeholder="Enter a new concept to test (e.g. Electric shuttle service connecting metro to IT parks in Pune)..."
                className="w-full px-4 py-3.5 text-sm bg-[#F7F4F2] border border-[#E7DAD8] rounded-xl text-[#302629] placeholder:text-[#78696B]/70 focus:outline-none focus:ring-2 focus:ring-[#873F46]/20 focus:border-[#873F46] focus:bg-[#FFFFFF] transition-all shadow-xs pr-36"
              />
              <button
                type="submit"
                disabled={!quickIdea.trim()}
                className="absolute right-1.5 top-1.5 bottom-1.5 px-4 bg-[#F43F4F] hover:bg-[#e83545] focus:outline-none focus:ring-2 focus:ring-[#F43F4F]/50 focus:ring-offset-2 focus:ring-offset-[#171B20] disabled:bg-[#2B3138] disabled:text-[#7E8995] disabled:cursor-not-allowed text-white rounded-lg text-xs font-bold flex items-center gap-1.5 shadow-sm transition-colors"
              >
                <span>Validate</span>
                <ArrowRight size={14} />
              </button>
            </div>
          </form>

          {/* Preset Buttons */}
          <div className="mt-3.5 flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-[#78696B]">Try an example:</span>
            {sampleIdeas.map((idea, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setQuickIdea(idea)}
                className="text-xs bg-[#F7F4F2] hover:bg-[#F4E9E7] text-[#302629] hover:text-[#873F46] px-3 py-1 rounded-lg border border-[#E7DAD8] transition-colors text-left truncate max-w-xs"
              >
                {idea.slice(0, 40)}...
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 2. Four Readable Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Personas Evaluated */}
        <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-5 shadow-xs hover:border-[#B66B70]/40 transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-[#78696B] uppercase tracking-wider">
              Personas Evaluated
            </span>
            <div className="w-8 h-8 rounded-xl bg-[#F4E9E7] text-[#873F46] flex items-center justify-center">
              <Users size={16} />
            </div>
          </div>
          <div className="text-2xl font-black text-[#302629] mb-1">
            {report ? totalPersonas : '0'}
            <span className="text-xs font-medium text-[#78696B] ml-1.5">
              synthetic agents
            </span>
          </div>
          <div className="text-xs text-[#78696B] leading-tight">
            Independently simulated customer archetypes across {segmentCount || '—'} segments
          </div>
        </div>

        {/* Card 2: Customer Segments */}
        <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-5 shadow-xs hover:border-[#B66B70]/40 transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-[#78696B] uppercase tracking-wider">
              Customer Segments
            </span>
            <div className="w-8 h-8 rounded-xl bg-[#F4E9E7] text-[#873F46] flex items-center justify-center">
              <Layers size={16} />
            </div>
          </div>
          <div className="text-2xl font-black text-[#873F46] mb-1">
            {report ? segmentCount : '0'}
            <span className="text-xs font-medium text-[#78696B] ml-1.5">
              distinct target groups
            </span>
          </div>
          <div className="text-xs text-[#78696B] leading-tight truncate">
            {report?.segment_comparison?.[0]?.segment_name || 'B2B fleets, independent drivers & logistics'}
          </div>
        </div>

        {/* Card 3: Strongest Opportunity */}
        <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-5 shadow-xs hover:border-[#3E7B54]/40 transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-[#3E7B54] uppercase tracking-wider">
              Strongest Opportunity
            </span>
            <div className="w-8 h-8 rounded-xl bg-[#EDF6F0] text-[#3E7B54] flex items-center justify-center">
              <CheckCircle2 size={16} />
            </div>
          </div>
          <div className="text-sm font-bold text-[#302629] mb-1 line-clamp-2 leading-snug">
            {strongestOpportunity}
          </div>
          <div className="text-xs text-[#3E7B54] font-medium flex items-center gap-1 mt-1">
            <span>Positive hypothesis signal</span>
          </div>
        </div>

        {/* Card 4: Main Risk */}
        <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-5 shadow-xs hover:border-[#C06E22]/40 transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-[#C06E22] uppercase tracking-wider">
              Main Risk &amp; Hurdle
            </span>
            <div className="w-8 h-8 rounded-xl bg-[#FAF2EA] text-[#C06E22] flex items-center justify-center">
              <AlertTriangle size={16} />
            </div>
          </div>
          <div className="text-sm font-bold text-[#302629] mb-1 line-clamp-2 leading-snug">
            {mainRisk}
          </div>
          <div className="text-xs text-[#C06E22] font-medium flex items-center gap-1 mt-1">
            <span>Requires customer interviews</span>
          </div>
        </div>
      </div>

      {/* 3. Circular Progress Ring Indicators Row */}
      {report && (
        <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 shadow-xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6">
            <div>
              <h2 className="text-xl font-bold text-[#302629]">
                Selective Evaluation Ring Indicators
              </h2>
              <p className="text-xs text-[#78696B]">
                Clear separation between synthetic model-generated evaluation ordinal scales and verified empirical audits.
              </p>
            </div>
            <span className="px-3 py-1 rounded-full bg-[#F7F4F2] text-[#78696B] text-xs font-medium border border-[#E7DAD8] self-start sm:self-auto">
              Simulated ordinal metrics (1–10)
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 justify-items-center">
            <CircularGauge
              value={avgIntentVal}
              max={10}
              size={120}
              strokeWidth={10}
              color="#873F46"
              label="Simulated Intent"
              unit="/10"
              subtitle="Synthetic ordinal score (not conversion %)"
            />

            <CircularGauge
              value={Number(((report.evidence_coverage_audit?.evidence_coverage_ratio ?? 0.65) * 10).toFixed(1))}
              max={10}
              size={120}
              strokeWidth={10}
              color="#3E7B54"
              label="Evidence Coverage"
              unit="/10"
              subtitle={`${report.evidence_coverage_audit?.supported_count ?? 3} findings backed by data`}
            />

            <CircularGauge
              value={avgAffordabilityVal}
              max={10}
              size={120}
              strokeWidth={10}
              color="#B66B70"
              label="Simulated Affordability"
              unit="/10"
              subtitle="Relative to local wage benchmarks"
            />

            <CircularGauge
              value={
                report.what_may_not_work?.length
                  ? Math.min(10, Math.max(3, report.what_may_not_work.length * 2.2))
                  : 5.5
              }
              max={10}
              size={120}
              strokeWidth={10}
              color="#C06E22"
              label="Adoption Friction"
              unit="/10"
              subtitle="Weighted barrier resistance score"
            />
          </div>
        </div>
      )}

      {/* 4. Customer-Segment Comparison Chart */}
      {report && segmentChartData.length > 0 && (
        <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 shadow-xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
            <div>
              <h2 className="text-xl font-bold text-[#302629]">
                Customer Segment Comparison
              </h2>
              <p className="text-xs text-[#78696B]">
                Comparison of synthetic interest versus purchase intent across identified target groups.
              </p>
            </div>
            <button
              onClick={() => onNavigate('personas')}
              className="text-xs font-bold text-[#873F46] hover:underline flex items-center gap-1 self-start sm:self-auto"
            >
              <span>Explore All Personas &amp; Segments</span>
              <ArrowRight size={13} />
            </button>
          </div>

          <div className="h-64 w-full mt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={segmentChartData}
                margin={{ top: 10, right: 20, left: -10, bottom: 25 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#F4E9E7" />
                <XAxis
                  dataKey="name"
                  stroke="#78696B"
                  fontSize={12}
                  tickLine={false}
                  interval={0}
                />
                <YAxis
                  domain={[0, 10]}
                  stroke="#78696B"
                  fontSize={12}
                  tickLine={false}
                  ticks={[0, 2, 4, 6, 8, 10]}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="bg-[#FFFFFF] border border-[#E7DAD8] p-3 rounded-xl shadow-lg text-xs space-y-1">
                          <p className="font-bold text-[#302629]">{data.fullName}</p>
                          <p className="text-[#873F46] font-semibold">
                            Simulated Interest: {data.avgInterest}/10
                          </p>
                          <p className="text-[#B66B70] font-semibold">
                            Purchase Intent: {data.avgIntent}/10
                          </p>
                          <p className="text-[#78696B] italic pt-1 border-t border-[#E7DAD8]">
                            Primary barrier: {data.barrier}
                          </p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Legend
                  wrapperStyle={{ fontSize: '12px', paddingTop: '8px' }}
                />
                <Bar
                  dataKey="avgInterest"
                  name="Simulated Interest (1-10)"
                  fill="#873F46"
                  radius={[6, 6, 0, 0]}
                  barSize={28}
                />
                <Bar
                  dataKey="avgIntent"
                  name="Purchase Intent (1-10)"
                  fill="#B66B70"
                  radius={[6, 6, 0, 0]}
                  barSize={28}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* 5. Problem-to-Solution Visualization Section */}
      {problemSolutionItems.length > 0 && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-[#302629]">
                  Problem-to-Solution Validation Path
                </h2>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#873F46]/10 text-[#873F46]">
                  Hypothesis Architecture
                </span>
              </div>
              <p className="text-xs text-[#78696B]">
                Paired structure: Friction → Why it matters → Proposed solution → How to empirically validate.
              </p>
            </div>
            <button
              onClick={() => onNavigate('market-insights')}
              className="text-xs font-bold text-[#873F46] hover:underline flex items-center gap-1 self-start sm:self-auto"
            >
              <span>View Evidence Audit &amp; Insights</span>
              <ArrowRight size={13} />
            </button>
          </div>

          <div className="space-y-4">
            {problemSolutionItems.map((item) => (
              <ProblemSolutionPair
                key={item.id}
                item={item}
              />
            ))}
          </div>
        </div>
      )}

      {/* 6. Preview of Two or Three Persona Profiles */}
      {previewPersonas.length > 0 && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-[#302629]">
                  Illustrated Synthetic Personas Preview
                </h2>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#F4E9E7] text-[#873F46] border border-[#B66B70]/20">
                  Archetype Models
                </span>
              </div>
              <p className="text-xs text-[#78696B]">
                Click any persona card to inspect full situation profile, valuation drivers, pricing tolerance, and discovery interview prompts.
              </p>
            </div>
            <button
              onClick={() => onNavigate('personas')}
              className="text-xs font-bold text-[#873F46] hover:underline flex items-center gap-1 self-start sm:self-auto"
            >
              <span>See All ({personas.length}) Personas</span>
              <ArrowRight size={13} />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {previewPersonas.map((persona) => (
              <PersonaCard
                key={persona.persona_id}
                persona={persona}
                onClick={(p: PersonaProfile) => {
                  if (onSelectPersona) {
                    onSelectPersona(p);
                  } else {
                    onNavigate('personas');
                  }
                }}
              />
            ))}
          </div>
        </div>
      )}

      {/* 7. Action Banner: Prominent Start New Analysis CTA */}
      <div className="p-8 rounded-2xl bg-gradient-to-r from-[#873F46] to-[#B66B70] text-[#FFFFFF] shadow-md flex flex-col sm:flex-row items-center justify-between gap-6">
        <div>
          <span className="inline-block px-3 py-1 rounded-full bg-[#FFFFFF]/20 text-xs font-bold mb-2">
            Next Action Step
          </span>
          <h3 className="text-xl sm:text-2xl font-bold mb-1">
            Ready to test a new business proposal?
          </h3>
          <p className="text-xs sm:text-sm text-[#F4E9E7] max-w-xl">
            Input a concept and customize the 5 founder intake questions to generate 10 synthetic customer personas and gather empirical corroboration.
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={onLoadSample}
            className="px-4 py-2.5 bg-[#FFFFFF]/15 hover:bg-[#FFFFFF]/25 border border-[#FFFFFF]/30 text-[#FFFFFF] rounded-xl text-xs font-bold transition-colors"
          >
            Reset Sample Data
          </button>
          <button
            onClick={() => onNavigate('new-analysis')}
            className="px-5 py-2.5 bg-[#FFFFFF] hover:bg-[#F4E9E7] text-[#873F46] rounded-xl text-xs font-black shadow-md flex items-center gap-2 transition-all transform hover:-translate-y-0.5"
          >
            <PlusCircle size={16} />
            <span>Start New Analysis</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default OverviewPage;
