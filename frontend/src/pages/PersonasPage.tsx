import React, { useState } from 'react';
import {
  Users,
  ShieldAlert,
  BarChart2,
  CheckCircle,
  AlertTriangle,
  Lightbulb,
  ExternalLink,
  Target,
  Sparkles,
  Filter,
  Layers
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import { MarketValidationReport, PersonaProfile } from '../types';
import { PersonaCard } from '../components/PersonaCard';
import { PersonaDetailModal } from '../components/PersonaDetailModal';
import { extractPersonasFromReport } from '../utils/personaHelper';

interface PersonasPageProps {
  report: MarketValidationReport | null;
  onNavigateToNew: () => void;
  selectedPersona?: PersonaProfile | null;
  onSelectPersona?: (persona: PersonaProfile | null) => void;
}

export const PersonasPage: React.FC<PersonasPageProps> = ({
  report,
  onNavigateToNew,
  selectedPersona: externalSelectedPersona,
  onSelectPersona: externalOnSelectPersona,
}) => {
  const [internalSelectedPersona, setInternalSelectedPersona] = useState<PersonaProfile | null>(null);
  const [selectedSegmentFilter, setSelectedSegmentFilter] = useState<string>('all');

  const activeSelectedPersona = externalSelectedPersona !== undefined ? externalSelectedPersona : internalSelectedPersona;
  const handleSelectPersona = (p: PersonaProfile | null) => {
    if (externalOnSelectPersona) {
      externalOnSelectPersona(p);
    } else {
      setInternalSelectedPersona(p);
    }
  };

  if (!report) {
    return (
      <div className="bg-[#FFFFFF] border border-dashed border-[#E7DAD8] rounded-2xl p-12 text-center max-w-lg mx-auto">
        <Users className="w-12 h-12 text-[#B66B70] mx-auto mb-3 opacity-60" />
        <h3 className="text-lg font-bold text-[#302629] mb-1">No Persona Data Available</h3>
        <p className="text-xs text-[#78696B] mb-5 leading-relaxed">
          Run an analysis or load the sample report to inspect synthetic customer profiles, illustrated avatars, and segment evaluations.
        </p>
        <button
          onClick={onNavigateToNew}
          className="px-5 py-2.5 bg-[#873F46] hover:bg-[#873F46]/90 text-white rounded-xl text-xs font-bold shadow-xs transition-colors"
        >
          Start New Validation
        </button>
      </div>
    );
  }

  const personas = extractPersonasFromReport(report);
  const segments = report.segment_comparison || [];
  const useCases = report.idea_and_context?.intended_use_cases || [];

  // Filter personas by segment
  const filteredPersonas = selectedSegmentFilter === 'all'
    ? personas
    : personas.filter((p) => p.segment.toLowerCase().includes(selectedSegmentFilter.toLowerCase()));

  // Get distinct segment names for filter pills
  const segmentNames = Array.from(new Set(personas.map((p) => p.segment)));

  // Prepare Recharts comparison data in burgundy theme
  const chartData = segments.map((seg) => {
    const scores = seg.median_scores || {};
    return {
      segment: seg.segment_name.length > 20 ? `${seg.segment_name.slice(0, 18)}...` : seg.segment_name,
      fullName: seg.segment_name,
      Interest: scores.interest ?? 0,
      'Purchase Intent': scores.purchase_intent ?? 0,
      'Perceived Value': scores.perceived_value ?? 0,
      Affordability: scores.affordability ?? 0,
      'Adoption Barrier': scores.adoption_barrier ?? 0,
    };
  });

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Strict Epistemic Boundaries Banner */}
      <div className="bg-[#FAF2EA] border border-[#C06E22]/30 rounded-2xl p-4 sm:p-5 text-[#302629] flex items-start gap-3.5 shadow-2xs">
        <ShieldAlert className="w-5 h-5 text-[#C06E22] shrink-0 mt-0.5" />
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h2 className="text-xs font-extrabold uppercase tracking-wider text-[#C06E22]">
              Synthetic Multi-Agent Simulation Notice
            </h2>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#C06E22]/15 text-[#C06E22]">
              Epistemic Boundary
            </span>
          </div>
          <p className="text-xs leading-relaxed text-[#78696B]">
            Persona profiles, illustrated avatars, and simulated intent scores represent <strong className="text-[#302629]">fictional hypothesis archetypes</strong> synthesized to stress-test value propositions against local wage and operational parameters. They do <strong>NOT</strong> depict actual interviewed human subjects or guaranteed market conversion KPIs.
          </p>
        </div>
      </div>

      {/* Personas Grid Section */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-[#E7DAD8]">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-2xl font-bold text-[#302629]">
                Illustrated Customer Persona Archetypes
              </h2>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#873F46]/10 text-[#873F46]">
                {filteredPersonas.length} Archetypes
              </span>
            </div>
            <p className="text-xs text-[#78696B] mt-0.5">
              Click any persona card to inspect full situational context, valuation drivers, pricing objections, and real-customer discovery interview prompts.
            </p>
          </div>

          {/* Segment Filter Pills */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-[#78696B] font-medium mr-1 flex items-center gap-1">
              <Filter size={12} /> Filter:
            </span>
            <button
              onClick={() => setSelectedSegmentFilter('all')}
              className={`px-3 py-1 rounded-lg text-xs font-bold transition-colors ${
                selectedSegmentFilter === 'all'
                  ? 'bg-[#873F46] text-[#FFFFFF]'
                  : 'bg-[#FFFFFF] text-[#78696B] hover:text-[#302629] border border-[#E7DAD8]'
              }`}
            >
              All ({personas.length})
            </button>
            {segmentNames.map((seg, idx) => (
              <button
                key={idx}
                onClick={() => setSelectedSegmentFilter(seg)}
                className={`px-3 py-1 rounded-lg text-xs font-bold transition-colors truncate max-w-[180px] ${
                  selectedSegmentFilter === seg
                    ? 'bg-[#873F46] text-[#FFFFFF]'
                    : 'bg-[#FFFFFF] text-[#78696B] hover:text-[#302629] border border-[#E7DAD8]'
                }`}
                title={seg}
              >
                {seg.split(' ')[0]}...
              </button>
            ))}
          </div>
        </div>

        {/* Persona Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredPersonas.map((persona) => (
            <PersonaCard
              key={persona.persona_id}
              persona={persona}
              onClick={(p: PersonaProfile) => handleSelectPersona(p)}
            />
          ))}
        </div>
      </div>

      {/* Segment Score Comparison Chart */}
      {chartData.length > 0 && (
        <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 shadow-xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 pb-3 border-b border-[#E7DAD8]">
            <div>
              <h3 className="text-lg font-bold text-[#302629]">
                Segment Median Evaluation Scores (Scale: 1 – 10)
              </h3>
              <p className="text-xs text-[#78696B]">
                Comparing synthetic intent, perceived value, affordability, and adoption barriers across identified market segments.
              </p>
            </div>
            <span className="text-xs font-semibold bg-[#F7F4F2] text-[#78696B] px-3 py-1 rounded-full border border-[#E7DAD8] self-start sm:self-auto">
              Simulated Ordinal Scale
            </span>
          </div>

          <div className="h-64 sm:h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F4E9E7" />
                <XAxis
                  dataKey="segment"
                  tick={{ fontSize: 11, fill: '#78696B' }}
                  tickLine={false}
                  interval={0}
                />
                <YAxis
                  domain={[0, 10]}
                  tick={{ fontSize: 11, fill: '#78696B' }}
                  tickLine={false}
                  axisLine={false}
                  ticks={[0, 2, 4, 6, 8, 10]}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#FFFFFF',
                    border: '1px solid #E7DAD8',
                    borderRadius: '12px',
                    fontSize: '12px',
                    boxShadow: '0 4px 12px rgba(48, 38, 41, 0.08)',
                  }}
                  formatter={(value: any, name: any) => [`${value}/10`, name]}
                />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                <Bar dataKey="Interest" fill="#873F46" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Purchase Intent" fill="#B66B70" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Perceived Value" fill="#302629" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Affordability" fill="#3E7B54" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Adoption Barrier" fill="#C06E22" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Evaluated Customer Segments Breakdown Cards */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold text-[#302629]">
            Evaluated Customer Segments ({segments.length})
          </h3>
          <span className="text-xs text-[#78696B]">
            Total Synthetic Archetypes: {String(report.diagnostics?.total_personas ?? 10)}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {segments.map((seg, idx) => {
            const ms = seg.median_scores || {};
            return (
              <div
                key={idx}
                className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 shadow-xs flex flex-col justify-between space-y-4 hover:border-[#B66B70]/40 transition-all"
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div>
                      <span className="text-xs font-bold text-[#873F46] uppercase tracking-wider block">
                        Segment {idx + 1}
                      </span>
                      <h4 className="text-base font-bold text-[#302629]">
                        {seg.segment_name}
                      </h4>
                    </div>
                    <div className="text-right shrink-0">
                      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold bg-[#F4E9E7] text-[#873F46] border border-[#B66B70]/20">
                        {seg.evaluated_personas_count} / {seg.persona_count} evaluated
                      </span>
                    </div>
                  </div>

                  {/* Score Pills Grid */}
                  <div className="grid grid-cols-5 gap-2 py-3 my-2 border-y border-[#E7DAD8] text-center">
                    <div className="p-2 rounded-xl bg-[#F7F4F2]">
                      <span className="text-[10px] text-[#78696B] font-medium block">Interest</span>
                      <span className="text-sm font-bold text-[#873F46]">
                        {ms.interest !== undefined && ms.interest !== null ? `${ms.interest}/10` : '-'}
                      </span>
                    </div>
                    <div className="p-2 rounded-xl bg-[#F7F4F2]">
                      <span className="text-[10px] text-[#78696B] font-medium block">Intent</span>
                      <span className="text-sm font-bold text-[#873F46]">
                        {ms.purchase_intent !== undefined && ms.purchase_intent !== null ? `${ms.purchase_intent}/10` : '-'}
                      </span>
                    </div>
                    <div className="p-2 rounded-xl bg-[#F7F4F2]">
                      <span className="text-[10px] text-[#78696B] font-medium block">Value</span>
                      <span className="text-sm font-bold text-[#302629]">
                        {ms.perceived_value !== undefined && ms.perceived_value !== null ? `${ms.perceived_value}/10` : '-'}
                      </span>
                    </div>
                    <div className="p-2 rounded-xl bg-[#F7F4F2]">
                      <span className="text-[10px] text-[#78696B] font-medium block">Afford.</span>
                      <span className="text-sm font-bold text-[#3E7B54]">
                        {ms.affordability !== undefined && ms.affordability !== null ? `${ms.affordability}/10` : '-'}
                      </span>
                    </div>
                    <div className="p-2 rounded-xl bg-[#F7F4F2]">
                      <span className="text-[10px] text-[#78696B] font-medium block">Barrier</span>
                      <span className="text-sm font-bold text-[#C06E22]">
                        {ms.adoption_barrier !== undefined && ms.adoption_barrier !== null ? `${ms.adoption_barrier}/10` : '-'}
                      </span>
                    </div>
                  </div>

                  {/* Narrative Summary */}
                  {seg.affordability_and_adoption_summary && (
                    <p className="text-xs text-[#78696B] leading-relaxed mb-3">
                      {seg.affordability_and_adoption_summary}
                    </p>
                  )}

                  {/* Valued Features vs Concerns */}
                  <div className="space-y-2.5 text-xs">
                    {seg.valued_features && seg.valued_features.length > 0 && (
                      <div>
                        <span className="text-xs font-bold text-[#302629] mb-1 flex items-center gap-1.5">
                          <CheckCircle className="w-3.5 h-3.5 text-[#3E7B54]" />
                          <span>Valued Capabilities</span>
                        </span>
                        <ul className="list-disc list-inside text-[#78696B] space-y-0.5 text-xs pl-1">
                          {seg.valued_features.slice(0, 3).map((f, i) => (
                            <li key={i}>{f}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {seg.main_concerns && seg.main_concerns.length > 0 && (
                      <div>
                        <span className="text-xs font-bold text-[#302629] mb-1 flex items-center gap-1.5">
                          <AlertTriangle className="w-3.5 h-3.5 text-[#C06E22]" />
                          <span>Primary Objections</span>
                        </span>
                        <ul className="list-disc list-inside text-[#78696B] space-y-0.5 text-xs pl-1">
                          {seg.main_concerns.slice(0, 3).map((c, i) => (
                            <li key={i}>{c}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>

                {/* Validation Recommendation */}
                {seg.suggested_validation_experiment && (
                  <div className="bg-[#F7F4F2] p-3 rounded-xl border border-[#E7DAD8] text-xs">
                    <span className="font-bold text-[#873F46] block mb-0.5">
                      Suggested Real-World Empirical Test:
                    </span>
                    <span className="text-xs text-[#78696B] leading-relaxed">
                      {seg.suggested_validation_experiment}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Intended Use Cases */}
      {useCases.length > 0 && (
        <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 shadow-xs space-y-4">
          <div>
            <h3 className="text-lg font-bold text-[#302629] mb-0.5">
              Simulated Usage Scenarios
            </h3>
            <p className="text-xs text-[#78696B]">
              Operational workflows synthesized from proposal constraints
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {useCases.map((uc, i) => (
              <div
                key={i}
                className="p-4 rounded-xl bg-[#F7F4F2] border border-[#E7DAD8] text-xs text-[#302629] space-y-1"
              >
                <div className="flex items-center gap-1.5 font-bold text-[#873F46]">
                  <Target className="w-4 h-4 text-[#873F46]" />
                  <span>Persona Scenario #{i + 1}</span>
                </div>
                <p className="text-[#78696B] leading-relaxed text-xs">{uc}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Persona Detail Modal */}
      {activeSelectedPersona && (
        <PersonaDetailModal
          persona={activeSelectedPersona}
          onClose={() => handleSelectPersona(null)}
        />
      )}
    </div>
  );
};

export default PersonasPage;
