import React, { useEffect } from 'react';
import {
  X,
  AlertTriangle,
  HelpCircle,
  DollarSign,
  FileText,
  Lightbulb,
  CheckCircle2,
  ShieldAlert,
  MapPin,
  Briefcase,
  Layers,
  MessageSquareQuote,
  Sparkles
} from 'lucide-react';
import { PersonaProfile } from '../types';
import { PersonaAvatar } from './PersonaAvatar';

interface PersonaDetailModalProps {
  persona: PersonaProfile | null;
  onClose: () => void;
}

export const PersonaDetailModal: React.FC<PersonaDetailModalProps> = ({ persona, onClose }) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    if (persona) {
      window.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'unset';
    };
  }, [persona, onClose]);

  if (!persona) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/70 backdrop-blur-sm animate-fadeIn"
      onClick={onClose}
      aria-modal="true"
      role="dialog"
      aria-labelledby="persona-modal-title"
    >
      <div
        className="bg-[#171B20] border border-[#2B3138] rounded-2xl shadow-2xl shadow-black/50 max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden text-[#F5F5F5]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Banner */}
        <div className="relative px-6 py-5 bg-[#1D2228] border-b border-[#2B3138] flex items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="relative">
              <PersonaAvatar
                seed={persona.persona_id || persona.name}
                name={persona.name}
                size="xl"
              />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <h2 id="persona-modal-title" className="text-2xl font-bold text-[#F5F5F5]">
                  {persona.name}
                </h2>
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[rgba(244,63,79,0.1)] text-[#F43F4F] border border-[rgba(244,63,79,0.2)]">
                  <Sparkles size={11} />
                  Synthetic persona hypothesis
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-3 text-sm text-[#7E8995]">
                <span className="flex items-center gap-1 font-medium text-[#F5F5F5]">
                  <Briefcase size={14} className="text-[#873F46]" />
                  {persona.occupation}
                </span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <Layers size={14} className="text-[#B66B70]" />
                  {persona.segment}
                </span>
                {persona.location && (
                  <>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <MapPin size={14} className="text-[#B66B70]" />
                      {persona.location}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-[#7E8995] hover:text-[#F5F5F5] hover:bg-[#2B3138] rounded-xl border border-transparent hover:border-[#3a4250] transition-colors"
            aria-label="Close modal"
          >
            <X size={20} />
          </button>
        </div>

        {/* Modal Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Synthetic Metric Strip */}
          <div className="p-4 rounded-xl bg-[#1D2228] border border-[#2B3138]">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-[#7E8995]">
                Simulated Persona Evaluation Scores
              </span>
              <span className="text-xs text-[#7E8995] italic">
                Ordinal simulation (1–10 scale) • Not verified conversion KPIs
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              <div className="bg-[#171B20] p-2.5 rounded-lg border border-[#2B3138] text-center">
                <span className="text-xs text-[#7E8995] block">Topic Interest</span>
                <span className="text-lg font-bold text-[#F43F4F]">{persona.scores.interest_score}/10</span>
              </div>
              <div className="bg-[#171B20] p-2.5 rounded-lg border border-[#2B3138] text-center">
                <span className="text-xs text-[#7E8995] block">Purchase Intent</span>
                <span className="text-lg font-bold text-[#F43F4F]">{persona.scores.simulated_purchase_intent}/10</span>
              </div>
              <div className="bg-[#171B20] p-2.5 rounded-lg border border-[#2B3138] text-center">
                <span className="text-xs text-[#7E8995] block">Perceived Value</span>
                <span className="text-lg font-bold text-[#F5F5F5]">{persona.scores.perceived_value_score}/10</span>
              </div>
              <div className="bg-[#171B20] p-2.5 rounded-lg border border-[#2B3138] text-center">
                <span className="text-xs text-[#7E8995] block">Affordability</span>
                <span className="text-lg font-bold text-[#42C985]">{persona.scores.affordability_score}/10</span>
              </div>
              <div className="bg-[#171B20] p-2.5 rounded-lg border border-[#2B3138] text-center col-span-2 sm:col-span-1">
                <span className="text-xs text-[#7E8995] block">Adoption Barrier</span>
                <span className="text-lg font-bold text-[#F4B942]">{persona.scores.adoption_barrier_score}/10</span>
              </div>
            </div>
          </div>

          {/* Customer Situation & Description */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl border border-[#2B3138] bg-[#1D2228]">
              <h3 className="text-sm font-bold uppercase tracking-wider text-[#F43F4F] mb-2 flex items-center gap-1.5">
                <FileText size={16} />
                Customer Situation
              </h3>
              <p className="text-sm text-[#A0AAB5] leading-relaxed">
                {persona.situation || persona.customer_description}
              </p>
            </div>

            <div className="p-4 rounded-xl border border-[rgba(244,185,66,0.2)] bg-[rgba(244,185,66,0.07)]">
              <h3 className="text-sm font-bold uppercase tracking-wider text-[#F4B942] mb-2 flex items-center gap-1.5">
                <ShieldAlert size={16} />
                Primary Adoption Barrier
              </h3>
              <p className="text-sm text-[#A0AAB5] leading-relaxed font-medium">
                {persona.main_objection}
              </p>
            </div>
          </div>

          {/* Pain Points & Why They Matter */}
          <div className="p-4 rounded-xl border border-[#2B3138] bg-[#1D2228]">
            <h3 className="text-base font-bold text-[#F5F5F5] mb-3 flex items-center gap-2">
              <AlertTriangle size={18} className="text-[#F43F4F]" />
              Pain Points & Why They Matter
            </h3>
            <div className="space-y-3">
              {persona.top_problems.map((prob, idx) => (
                <div key={idx} className="p-3 rounded-lg bg-[#171B20] border border-[#2B3138]">
                  <div className="text-sm font-semibold text-[#F43F4F] flex items-center gap-2">
                    <span className="flex-shrink-0 w-5 h-5 rounded-full bg-[rgba(244,63,79,0.12)] text-[#F43F4F] flex items-center justify-center text-xs font-bold">
                      {idx + 1}
                    </span>
                    {prob.problem}
                  </div>
                  <div className="mt-1 ml-7 text-xs text-[#7E8995]">
                    <span className="font-medium text-[#A0AAB5]">Why it matters:</span> {prob.whyItMatters}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Proposed Solutions & Desired Features */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl border border-[#2B3138] bg-[#1D2228]">
              <h3 className="text-sm font-bold uppercase tracking-wider text-[#42C985] mb-3 flex items-center gap-1.5">
                <CheckCircle2 size={16} />
                Proposed Product Solutions
              </h3>
              <ul className="space-y-2 text-sm text-[#A0AAB5]">
                {persona.proposed_solutions.map((sol, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-[#42C985] font-bold">✓</span>
                    <span>{sol}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="p-4 rounded-xl border border-[#2B3138] bg-[#1D2228]">
              <h3 className="text-sm font-bold uppercase tracking-wider text-[#F43F4F] mb-3 flex items-center gap-1.5">
                <Lightbulb size={16} />
                Features Most Valued
              </h3>
              <div className="flex flex-wrap gap-2">
                {persona.desired_features.map((feat, idx) => (
                  <span
                    key={idx}
                    className="px-2.5 py-1 rounded-md text-xs font-medium bg-[rgba(244,63,79,0.1)] text-[#F43F4F] border border-[rgba(244,63,79,0.2)]"
                  >
                    {feat}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Pricing & Rejection Concerns */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl border border-[#2B3138] bg-[#1D2228]">
              <h3 className="text-sm font-bold uppercase tracking-wider text-[#F5F5F5] mb-2 flex items-center gap-1.5">
                <DollarSign size={16} className="text-[#873F46]" />
                Pricing Concerns
              </h3>
              <p className="text-sm text-[#7E8995] leading-relaxed">
                {persona.pricing_concerns}
              </p>
            </div>

            <div className="p-4 rounded-xl border border-[#2B3138] bg-[#1D2228]">
              <h3 className="text-sm font-bold uppercase tracking-wider text-[#F43F4F] mb-2 flex items-center gap-1.5">
                <ShieldAlert size={16} />
                Reasons They May Reject Product
              </h3>
              <ul className="space-y-1.5 text-sm text-[#7E8995]">
                {persona.rejection_reasons.map((reason, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-[#F43F4F] font-bold">•</span>
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Supporting Evidence and its Source */}
          <div className="p-4 rounded-xl border border-[#2B3138] bg-[#1D2228]">
            <h3 className="text-sm font-bold uppercase tracking-wider text-[#F5F5F5] mb-2 flex items-center gap-1.5">
              <FileText size={16} className="text-[#873F46]" />
              Supporting Evidence &amp; Sources
            </h3>
            {persona.supporting_evidence.length > 0 ? (
              <div className="space-y-2">
                {persona.supporting_evidence.map((ev, idx) => (
                  <div key={idx} className="p-3 bg-[#171B20] rounded-lg border border-[#2B3138] text-xs">
                    <div className="font-semibold text-[#F43F4F] mb-1 flex items-center gap-1.5">
                      <span className="px-1.5 py-0.5 rounded bg-[rgba(244,63,79,0.1)] text-[10px] font-mono">
                        {ev.id}
                      </span>
                      <span>Source: {ev.source}</span>
                    </div>
                    <p className="text-[#A0AAB5]">{ev.text}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[#7E8995] italic">
                Synthetic persona archetype formulated from market domain priors. No external empiric citation ID directly linked.
              </p>
            )}
          </div>

          {/* Questions to Ask Real Customers */}
          <div className="p-4 rounded-xl border border-[rgba(244,63,79,0.2)] bg-[rgba(244,63,79,0.07)]">
            <h3 className="text-sm font-bold uppercase tracking-wider text-[#F43F4F] mb-2 flex items-center gap-1.5">
              <MessageSquareQuote size={16} />
              Questions to Ask Real Customers to Validate
            </h3>
            <p className="text-xs text-[#7E8995] mb-3">
              Use these interview prompts during customer discovery calls to ground or refute this persona hypothesis.
            </p>
            <div className="space-y-2">
              {persona.validation_questions.map((q, idx) => (
                <div key={idx} className="flex items-start gap-2 text-sm text-[#A0AAB5]">
                  <span className="font-bold text-[#F43F4F] flex-shrink-0">{idx + 1}.</span>
                  <span>{q}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 bg-[#1D2228] border-t border-[#2B3138] flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl text-sm font-semibold bg-[#F43F4F] text-white hover:bg-[#e83545] transition-colors shadow-md"
          >
            Close Profile
          </button>
        </div>
      </div>
    </div>
  );
};

export default PersonaDetailModal;
