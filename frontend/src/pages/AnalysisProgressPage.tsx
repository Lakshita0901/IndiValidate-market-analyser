import React, { useEffect, useState } from 'react';
import {
  Activity,
  Clock,
  AlertCircle,
  RotateCcw,
  StopCircle,
  Layers,
  Database,
  Users,
  Cpu,
  FileCheck2,
  HelpCircle,
  Compass
} from 'lucide-react';
import { PageId } from '../types';

interface AnalysisProgressPageProps {
  isRunning: boolean;
  ideaText: string;
  errorMessage: string | null;
  onCancel: () => void;
  onRetry: () => void;
  onNavigate: (page: PageId) => void;
}

export const AnalysisProgressPage: React.FC<AnalysisProgressPageProps> = ({
  isRunning,
  ideaText,
  errorMessage,
  onCancel,
  onRetry,
  onNavigate,
}) => {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    let interval: number | undefined;
    if (isRunning) {
      setElapsedSeconds(0);
      interval = window.setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isRunning]);

  const formatTime = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  const stages = [
    {
      num: '01',
      title: 'Idea Pre-processing & Routing',
      desc: 'Normalizes idea semantics, extracts research keywords, and determines regional vs national context.',
      icon: <Layers className="w-4 h-4 text-[#873F46]" />,
    },
    {
      num: '02',
      title: 'Multi-Source Empirical Research',
      desc: 'Retrieves official Census 2011 demographics, PLFS 2025 wage microdata, Reddit discussions, and Google Trends.',
      icon: <Database className="w-4 h-4 text-[#3E7B54]" />,
    },
    {
      num: '03',
      title: 'Archetype Calibration & Persona Generation',
      desc: 'Synthesizes 10 grounded buyer personas representing distinct socioeconomic and operational profiles.',
      icon: <Users className="w-4 h-4 text-[#873F46]" />,
    },
    {
      num: '04',
      title: 'Bounded Multi-Agent Evaluation',
      desc: 'Simulates purchase intent, perceived value, affordability, and friction points across 3 concurrent worker threads.',
      icon: <Cpu className="w-4 h-4 text-[#B66B70]" />,
    },
    {
      num: '05',
      title: 'Evidence Audit & LLM Fallback Answering',
      desc: 'Computes evidence coverage ratio, audits contradictions, and generates independent model-knowledge fallback answers.',
      icon: <FileCheck2 className="w-4 h-4 text-[#C06E22]" />,
    },
  ];

  return (
    <div className="max-w-3xl mx-auto space-y-8 animate-fadeIn">
      {/* Title */}
      <div>
        <h1 className="text-[30px] font-extrabold text-[#302629] tracking-tight leading-tight">
          Execution &amp; Pipeline Telemetry
        </h1>
        <p className="text-sm text-[#78696B] mt-1">
          Real-time multi-stage validation graph execution monitor and safe rate-limit recovery.
        </p>
      </div>

      {/* Status Card */}
      <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 sm:p-8 shadow-xs">
        {isRunning ? (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#E7DAD8] pb-5">
              <div className="flex items-center gap-3.5">
                <div className="w-11 h-11 rounded-2xl bg-[#F4E9E7] border border-[#B66B70]/30 flex items-center justify-center shrink-0">
                  <Activity className="w-5 h-5 text-[#873F46] animate-spin" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-[#873F46]">
                      Live Analysis Running
                    </span>
                    <span className="w-2 h-2 rounded-full bg-[#873F46] animate-ping" />
                  </div>
                  <h2 className="text-base sm:text-lg font-bold text-[#302629] leading-tight">
                    Evaluating Proposal via LangGraph
                  </h2>
                </div>
              </div>

              {/* Elapsed Timer Display */}
              <div className="flex items-center gap-2 bg-[#F7F4F2] border border-[#E7DAD8] px-4 py-2 rounded-xl self-start sm:self-auto">
                <Clock className="w-4 h-4 text-[#78696B]" />
                <span className="text-xs text-[#78696B] font-medium">Elapsed:</span>
                <span className="font-mono font-bold text-sm text-[#302629]">
                  {formatTime(elapsedSeconds)}
                </span>
              </div>
            </div>

            {/* Target Concept Display */}
            <div className="bg-[#F7F4F2] rounded-xl p-4 sm:p-5 border border-[#E7DAD8] text-xs">
              <span className="font-bold text-[#78696B] block mb-1">
                Concept under evaluation:
              </span>
              <p className="text-[#302629] font-medium leading-relaxed italic text-sm">
                "{ideaText || 'Active business idea'}"
              </p>
            </div>

            {/* Note on Real Progress Telemetry */}
            <div className="p-4 bg-[#F4E9E7]/50 border border-[#B66B70]/30 rounded-xl text-xs text-[#302629] flex items-start gap-3">
              <HelpCircle className="w-4 h-4 text-[#873F46] shrink-0 mt-0.5" />
              <div className="space-y-1">
                <span className="font-bold text-[#873F46] block">Synchronous Graph Execution Notice</span>
                <p className="text-xs leading-relaxed text-[#78696B]">
                  The backend executes a full multi-stage LangGraph workflow including 10 independent simulated persona evaluations with bounded concurrency (3 concurrent workers). Typical execution takes approximately 30 to 75 seconds.
                </p>
              </div>
            </div>

            {/* Pipeline Stage Architecture Steps */}
            <div className="space-y-3 pt-2">
              <h3 className="text-xs font-bold text-[#78696B] uppercase tracking-wider">
                Pipeline Workflow Architecture
              </h3>
              <div className="space-y-3">
                {stages.map((st, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-3.5 p-3.5 rounded-xl border border-[#E7DAD8] bg-[#FFFFFF] hover:bg-[#F7F4F2]/50 transition-colors"
                  >
                    <div className="w-8 h-8 rounded-xl bg-[#F7F4F2] border border-[#E7DAD8] flex items-center justify-center shrink-0 mt-0.5">
                      {st.icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-mono text-[#873F46] font-bold">
                          STAGE {st.num}
                        </span>
                        <span className="text-xs font-bold text-[#302629] truncate">
                          {st.title}
                        </span>
                      </div>
                      <p className="text-xs text-[#78696B] mt-0.5 leading-relaxed">
                        {st.desc}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Cancellation Action */}
            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={onCancel}
                className="px-4 py-2 border border-[#E7DAD8] hover:bg-[#F7F4F2] text-[#78696B] hover:text-[#302629] rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors"
              >
                <StopCircle className="w-4 h-4 text-[#78696B]" />
                <span>Cancel Execution</span>
              </button>
            </div>
          </div>
        ) : errorMessage ? (
          /* Error State */
          <div className="space-y-5 text-center py-4">
            <div className={`w-14 h-14 rounded-2xl ${errorMessage.toLowerCase().includes('rate limit') ? 'bg-[#FAF2EA] text-[#C06E22] border border-[#C06E22]/30' : 'bg-[#F4E9E7] text-[#873F46] border border-[#873F46]/30'} mx-auto flex items-center justify-center`}>
              <AlertCircle className="w-7 h-7" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-[#302629] mb-1">
                {errorMessage.toLowerCase().includes('rate limit') ? 'Rate Limit Reached' : 'Pipeline Execution Stopped'}
              </h2>
              <p className={`text-xs ${errorMessage.toLowerCase().includes('rate limit') ? 'text-[#C06E22] bg-[#FAF2EA] border-[#C06E22]/30' : 'text-[#873F46] bg-[#F4E9E7] border-[#873F46]/30'} max-w-lg mx-auto p-4 rounded-xl border mt-2 text-left leading-relaxed`}>
                {errorMessage}
              </p>
              {errorMessage.toLowerCase().includes('rate limit') && (
                <div className="mt-3 p-3.5 bg-[#EDF6F0] border border-[#3E7B54]/20 rounded-xl text-xs text-[#3E7B54] max-w-lg mx-auto text-left flex items-start gap-2.5">
                  <FileCheck2 className="w-4 h-4 text-[#3E7B54] shrink-0 mt-0.5" />
                  <span>
                    <strong>Stage Preservation Active:</strong> Completed research and persona stages are safely cached. Clicking <em>Retry Analysis</em> will resume without re-running finished steps.
                  </span>
                </div>
              )}
            </div>
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                onClick={onRetry}
                className="px-5 py-2.5 bg-[#873F46] hover:bg-[#873F46]/90 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-xs transition-colors"
              >
                <RotateCcw className="w-4 h-4" />
                <span>Retry Analysis</span>
              </button>
              <button
                onClick={() => onNavigate('new-analysis')}
                className="px-5 py-2.5 bg-[#F7F4F2] hover:bg-[#F4E9E7] text-[#302629] rounded-xl text-xs font-bold border border-[#E7DAD8] transition-colors"
              >
                Edit Proposal Inputs
              </button>
            </div>
          </div>
        ) : (
          /* Idle / Ready State */
          <div className="text-center py-10 space-y-4">
            <div className="w-14 h-14 rounded-2xl bg-[#F7F4F2] border border-[#E7DAD8] text-[#873F46] mx-auto flex items-center justify-center">
              <Compass className="w-7 h-7" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-[#302629] mb-1">
                No Active Analysis Running
              </h2>
              <p className="text-xs text-[#78696B] max-w-md mx-auto">
                Submit a new business proposal from the New Analysis form to observe live graph execution.
              </p>
            </div>
            <button
              onClick={() => onNavigate('new-analysis')}
              className="px-5 py-2.5 bg-[#873F46] hover:bg-[#873F46]/90 text-white rounded-xl text-xs font-bold shadow-xs transition-colors"
            >
              Start New Analysis
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default AnalysisProgressPage;
