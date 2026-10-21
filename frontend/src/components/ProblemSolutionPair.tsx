import React from 'react';
import { ArrowRight, AlertCircle, HelpCircle, CheckCircle2, FlaskConical } from 'lucide-react';
import { EvidenceStatus } from '../types';

export interface ProblemSolutionItem {
  id: string;
  problem: string;
  whyItMatters: string;
  proposedSolution: string;
  howToValidate: string;
  evidenceStatus?: EvidenceStatus;
  evidenceSource?: string;
  affectedSegment?: string;
}

interface ProblemSolutionPairProps {
  item: ProblemSolutionItem;
  className?: string;
}

export const ProblemSolutionPair: React.FC<ProblemSolutionPairProps> = ({
  item,
  className = '',
}) => {
  const isSupported = item.evidenceStatus === 'supported';

  return (
    <div
      className={`bg-[#171B20] rounded-2xl border border-[#2B3138] p-5 hover:border-[#3a4250] transition-all ${className}`}
    >
      {/* Top Header Row with Segment & Epistemic Status */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3.5 mb-4 border-b border-[#2B3138]">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[#F43F4F] bg-[rgba(244,63,79,0.1)] px-2.5 py-0.5 rounded-full border border-[rgba(244,63,79,0.2)]">
            {item.affectedSegment || 'Target Segment'}
          </span>
          <span className="text-[12px] font-mono text-[#7E8995]">
            {item.id}
          </span>
        </div>

        {/* Epistemic Evidence Status Badge */}
        {isSupported ? (
          <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-[#42C985] bg-[rgba(66,201,133,0.1)] px-2.5 py-1 rounded-full border border-[rgba(66,201,133,0.25)]">
            <CheckCircle2 className="w-3.5 h-3.5 text-[#42C985]" />
            <span>Corroborated by {item.evidenceSource || 'Empirical Data'}</span>
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-[#F4B942] bg-[rgba(244,185,66,0.1)] px-2.5 py-1 rounded-full border border-[rgba(244,185,66,0.25)]">
            <HelpCircle className="w-3.5 h-3.5 text-[#F4B942]" />
            <span>Hypothesis — Needs Empirical Validation</span>
          </span>
        )}
      </div>

      {/* 4-Step Problem → Solution Flow Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3.5 items-stretch relative">
        {/* Step 1: Problem */}
        <div className="bg-[rgba(244,63,79,0.07)] rounded-xl p-3.5 border border-[rgba(244,63,79,0.15)] flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-1.5 mb-1.5">
              <div className="w-5 h-5 rounded-full bg-[rgba(244,63,79,0.12)] text-[#F43F4F] flex items-center justify-center shrink-0">
                <AlertCircle className="w-3 h-3" />
              </div>
              <span className="text-[11px] font-bold text-[#F43F4F] uppercase tracking-wider">
                1. Customer Friction
              </span>
            </div>
            <h4 className="text-[14px] font-bold text-[#F5F5F5] leading-snug mb-1">
              {item.problem}
            </h4>
          </div>
          <span className="text-[10px] text-[#7E8995] font-mono mt-2">OBSERVED PAIN</span>
        </div>

        {/* Step 2: Why It Matters */}
        <div className="bg-[#1D2228] rounded-xl p-3.5 border border-[#2B3138] flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-1.5 mb-1.5">
              <span className="text-[11px] font-bold text-[#A0AAB5] uppercase tracking-wider">
                2. Why It Matters
              </span>
            </div>
            <p className="text-[13px] text-[#A0AAB5] leading-relaxed">
              {item.whyItMatters}
            </p>
          </div>
          <span className="text-[10px] text-[#7E8995] font-mono mt-2">BUSINESS / USER IMPACT</span>
        </div>

        {/* Step 3: Proposed Solution */}
        <div className="bg-[rgba(66,201,133,0.08)] rounded-xl p-3.5 border border-[rgba(66,201,133,0.2)] flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-1.5 mb-1.5">
              <span className="text-[11px] font-bold text-[#42C985] uppercase tracking-wider">
                3. Proposed Solution
              </span>
            </div>
            <p className="text-[13px] font-semibold text-[#42C985] leading-relaxed">
              {item.proposedSolution}
            </p>
          </div>
          <span className="text-[10px] text-[#42C985] font-mono mt-2">PRODUCT INTERVENTION</span>
        </div>

        {/* Step 4: How To Validate */}
        <div className="bg-[rgba(244,185,66,0.08)] rounded-xl p-3.5 border border-[rgba(244,185,66,0.2)] flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-1.5 mb-1.5">
              <div className="w-5 h-5 rounded-full bg-[rgba(244,185,66,0.15)] text-[#F4B942] flex items-center justify-center shrink-0">
                <FlaskConical className="w-3 h-3" />
              </div>
              <span className="text-[11px] font-bold text-[#F4B942] uppercase tracking-wider">
                4. How To Validate
              </span>
            </div>
            <p className="text-[12px] text-[#A0AAB5] leading-relaxed">
              {item.howToValidate}
            </p>
          </div>
          <span className="text-[10px] text-[#F4B942] font-mono mt-2">RECOMMENDED REAL-WORLD TEST</span>
        </div>
      </div>
    </div>
  );
};
