import React from 'react';
import {
  MapPin,
  Briefcase,
  AlertTriangle,
  Sparkles,
  ShieldAlert,
  ChevronRight,
  TrendingUp,
} from 'lucide-react';
import { PersonaProfile } from '../types';
import { PersonaAvatar } from './PersonaAvatar';

interface PersonaCardProps {
  persona: PersonaProfile;
  onClick: (persona: PersonaProfile) => void;
  className?: string;
}

export const PersonaCard: React.FC<PersonaCardProps> = ({
  persona,
  onClick,
  className = '',
}) => {
  const scores = persona.scores;

  return (
    <div
      onClick={() => onClick(persona)}
      className={`bg-[#171B20] rounded-2xl border border-[#2B3138] p-5.5 hover:border-[#F43F4F] hover:shadow-lg hover:shadow-black/20 transition-all cursor-pointer flex flex-col justify-between group relative ${className}`}
    >
      <div>
        {/* Top Header: Avatar + Identity + Synthetic Pill */}
        <div className="flex items-start gap-3.5 mb-3.5">
          <PersonaAvatar
            seed={persona.avatarSeed || persona.persona_id}
            name={persona.name}
            size="lg"
          />

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2 mb-0.5">
              <span className="text-[10px] font-bold text-[#F43F4F] bg-[rgba(244,63,79,0.12)] px-2 py-0.5 rounded-full uppercase tracking-wider border border-[rgba(244,63,79,0.2)]">
                Synthetic Persona
              </span>
              <span className="text-[11px] font-mono text-[#7E8995]">
                {persona.persona_id}
              </span>
            </div>

            <h3 className="text-[17px] font-bold text-[#F5F5F5] group-hover:text-[#F43F4F] transition-colors leading-tight truncate">
              {persona.name}
            </h3>

            <p className="text-[13px] font-medium text-[#A0AAB5] flex items-center gap-1.5 mt-0.5 truncate">
              <Briefcase className="w-3.5 h-3.5 shrink-0 text-[#7E8995]" />
              <span className="truncate">{persona.occupation}</span>
            </p>

            {persona.location && (
              <p className="text-[12px] text-[#7E8995] flex items-center gap-1 mt-0.5">
                <MapPin className="w-3 h-3 shrink-0 text-[#7E8995]" />
                <span className="truncate">{persona.location}</span>
              </p>
            )}
          </div>
        </div>

        {/* Target Segment Banner */}
        <div className="bg-[#1D2228] rounded-lg px-3 py-1.5 mb-3 border border-[#2B3138] flex items-center justify-between text-[11px]">
          <span className="font-semibold text-[#F43F4F] uppercase tracking-wider">
            Segment
          </span>
          <span className="font-medium text-[#A0AAB5] truncate max-w-[200px]">
            {persona.segment}
          </span>
        </div>

        {/* Short Customer Description */}
        <p className="text-[13px] text-[#A0AAB5] leading-relaxed line-clamp-2 mb-3.5">
          {persona.customer_description}
        </p>

        {/* Simulation Evaluation Score Badges */}
        <div className="grid grid-cols-3 gap-2 py-2.5 px-3 bg-[#1D2228] rounded-xl border border-[#2B3138] mb-3.5 text-center">
          <div>
            <span className="text-[10px] font-semibold text-[#7E8995] uppercase tracking-wider block">
              Interest
            </span>
            <span className="text-[15px] font-bold text-[#F43F4F]">
              {scores.interest_score}/10
            </span>
          </div>
          <div className="border-x border-[#2B3138]">
            <span className="text-[10px] font-semibold text-[#7E8995] uppercase tracking-wider block">
              Intent
            </span>
            <span className="text-[15px] font-bold text-[#42C985]">
              {scores.simulated_purchase_intent}/10
            </span>
          </div>
          <div>
            <span className="text-[10px] font-semibold text-[#7E8995] uppercase tracking-wider block">
              Barrier
            </span>
            <span className="text-[15px] font-bold text-[#F4B942]">
              {scores.adoption_barrier_score}/10
            </span>
          </div>
        </div>

        {/* Top 3 Customer Problems */}
        <div className="space-y-2 mb-3.5">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[#F5F5F5] block">
            Top 3 Problems (Pain Points)
          </span>
          <div className="space-y-1.5">
            {persona.top_problems.slice(0, 3).map((prob, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2 text-[12px] text-[#A0AAB5] bg-[#1D2228] rounded-lg p-2 border border-[#2B3138]"
              >
                <div className="w-4 h-4 rounded-full bg-[rgba(244,185,66,0.1)] text-[#F4B942] flex items-center justify-center shrink-0 mt-0.5">
                  <span className="text-[10px] font-bold">{idx + 1}</span>
                </div>
                <span className="leading-snug line-clamp-2">{prob.problem}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Desired Features Tags */}
        {persona.desired_features && persona.desired_features.length > 0 && (
          <div className="mb-3.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#F5F5F5] block mb-1.5">
              Desired Capabilities
            </span>
            <div className="flex flex-wrap gap-1.5">
              {persona.desired_features.slice(0, 3).map((feat, idx) => (
                <span
                  key={idx}
                  className="text-[11px] font-medium text-[#F43F4F] bg-[rgba(244,63,79,0.1)] px-2 py-0.5 rounded-md flex items-center gap-1 border border-[rgba(244,63,79,0.2)]"
                >
                  <Sparkles className="w-2.5 h-2.5 text-[#B66B70]" />
                  <span className="truncate max-w-[170px]">{feat}</span>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Main Objection or Barrier */}
        <div className="bg-[rgba(244,185,66,0.08)] p-3 rounded-xl border border-[rgba(244,185,66,0.2)] mb-2 text-[12px]">
          <span className="font-bold text-[#F4B942] block mb-0.5 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 text-[#F4B942]" />
            <span>Primary Adoption Barrier</span>
          </span>
          <p className="text-[#A0AAB5] leading-snug line-clamp-2">
            {persona.main_objection}
          </p>
        </div>
      </div>

      {/* Footer Interactive CTA */}
      <div className="pt-3 border-t border-[#2B3138] flex items-center justify-between text-[12px] font-bold text-[#F43F4F] group-hover:text-[#ff6b78]">
        <span>View Full Hypothesis Profile</span>
        <ChevronRight className="w-4 h-4 transform group-hover:translate-x-1 transition-transform" />
      </div>
    </div>
  );
};
