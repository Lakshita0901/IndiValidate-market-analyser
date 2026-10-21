import React, { useRef, useState } from 'react';
import {
  Sparkles,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  HelpCircle,
  Sliders,
  Play,
  RotateCcw,
  CheckCircle2,
  Compass,
  Layers,
  ArrowRight
} from 'lucide-react';
import {
  AnalyzeRequest,
  FounderContext,
  GeographicScope,
  MarketValidationReport,
  PageId,
  PricingModel,
  ValidationStage
} from '../types';
import { AnalysisResults } from '../components/AnalysisResults';

interface NewAnalysisPageProps {
  onSubmit: (request: AnalyzeRequest) => void;
  isLoading: boolean;
  errorMessage: string | null;
  onClearError: () => void;
  // Inline result state passed from App.tsx
  lastResult?: MarketValidationReport | null;
  lastSubmittedIdea?: string | null;
  lastSubmittedGeography?: string | null;
  onViewFullReport?: (page: PageId) => void;
  onClearResult?: () => void;
}

export const NewAnalysisPage: React.FC<NewAnalysisPageProps> = ({
  onSubmit,
  isLoading,
  errorMessage,
  onClearError,
  lastResult,
  lastSubmittedIdea,
  lastSubmittedGeography,
  onViewFullReport,
  onClearResult,
}) => {
  const formRef = useRef<HTMLDivElement>(null);
  // Primary Idea Input
  const [idea, setIdea] = useState(
    'Smart EV fleet charging hub and reservation software in Ahmedabad with peak-shaving power storage'
  );

  // Advanced Configuration (matching backend defaults)
  const [personaCount, setPersonaCount] = useState<number>(10);
  const [concurrency, setConcurrency] = useState<number>(3);
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);

  // Optional Founder Intake Toggle
  const [enableIntake, setEnableIntake] = useState<boolean>(false);

  // 5-Question Founder Intake State
  const [customerCategory, setCustomerCategory] = useState('Commercial EV fleet operators');
  const [customerDescription, setCustomerDescription] = useState('Fleet managers and dispatch operators running 5 to 50 electric delivery vans');
  const [problemDescription, setProblemDescription] = useState('Frequent 45-90 minute public charger queues causing delivery delays and lost route revenue');
  const [launchGeography, setLaunchGeography] = useState('Ahmedabad');
  const [geographicScope, setGeographicScope] = useState<GeographicScope>('local_city');
  const [knownAlternatives, setKnownAlternatives] = useState('Public charging stations, depot overnight AC charging, diesel generators');
  const [pricingModel, setPricingModel] = useState<PricingModel>('subscription');
  const [expectedPrice, setExpectedPrice] = useState('INR 3,000/month per vehicle');
  const [validationStage, setValidationStage] = useState<ValidationStage>('interviews_or_surveys');
  const [validationNotes, setValidationNotes] = useState('Spoke with 6 fleet managers in Naroda industrial zone who expressed acute frustration with queue delays');
  const [validationSampleSize, setValidationSampleSize] = useState<number | ''>(6);

  // Form Validation State
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onClearError();
    setValidationError(null);

    const trimmedIdea = idea.trim();
    if (!trimmedIdea) {
      setValidationError('Please enter a business idea to evaluate.');
      return;
    }

    let founderContextPayload: FounderContext | null = null;

    if (enableIntake) {
      if (!customerCategory.trim()) {
        setValidationError('Question 1 (Customer Category) is required when founder intake is enabled.');
        return;
      }
      if (!problemDescription.trim()) {
        setValidationError('Question 3 (Problem Description) is required when founder intake is enabled.');
        return;
      }

      // Split alternatives by comma
      const altsArray = knownAlternatives
        ? knownAlternatives
            .split(',')
            .map((s) => s.trim())
            .filter((s) => s.length > 0)
        : [];

      founderContextPayload = {
        customer_category: customerCategory.trim(),
        customer_description: customerDescription.trim() || null,
        problem_description: problemDescription.trim(),
        launch_geography: launchGeography.trim() || null,
        geographic_scope: geographicScope,
        known_alternatives: altsArray,
        pricing_model: pricingModel,
        expected_price: expectedPrice.trim() || null,
        validation_stage: validationStage || null,
        validation_notes: validationNotes.trim() || null,
        validation_sample_size: typeof validationSampleSize === 'number' ? validationSampleSize : null,
      };
    }

    const request: AnalyzeRequest = {
      idea: trimmedIdea,
      founder_context: founderContextPayload,
      persona_count: personaCount,
      evaluation_concurrency: concurrency,
    };

    onSubmit(request);
  };

  const handleReset = () => {
    setIdea('');
    setEnableIntake(false);
    setCustomerCategory('');
    setCustomerDescription('');
    setProblemDescription('');
    setLaunchGeography('');
    setGeographicScope('not_decided');
    setKnownAlternatives('');
    setPricingModel('not_decided');
    setExpectedPrice('');
    setValidationStage('idea_only');
    setValidationNotes('');
    setValidationSampleSize('');
    setPersonaCount(10);
    setConcurrency(3);
    setValidationError(null);
    onClearError();
    // Clear previous inline results so the user sees a fresh form
    onClearResult?.();
    // Scroll back to top of form
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fadeIn">
      {/* Title Header */}
      <div ref={formRef}>
        <h1 className="text-[30px] font-extrabold text-[#302629] tracking-tight leading-tight">
          {lastResult ? 'Analysis Results' : 'Configure Market Validation Analysis'}
        </h1>
        <p className="text-sm text-[#78696B] mt-1">
          {lastResult
            ? 'Your analysis is complete. Review results below or start a new analysis.'
            : 'Specify your market concept and optional founder intake assumptions to generate and stress-test synthetic customer archetypes.'}
        </p>
      </div>

      {/* ── Input Form (always visible, acts as reset anchor) ── */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Main Card: Idea Input */}
        <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl p-6 sm:p-7 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-[#E7DAD8] pb-3.5">
            <div>
              <h2 className="text-lg font-bold text-[#302629]">
                1. Target Business Proposal
              </h2>
              <p className="text-xs text-[#78696B]">
                Provide the core value proposition, product concept, or startup idea to analyze.
              </p>
            </div>
            <span className="text-xs font-bold text-[#873F46] bg-[#F4E9E7] px-3 py-1 rounded-full border border-[#B66B70]/20">
              Required
            </span>
          </div>

          <div>
            <textarea
              rows={4}
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
              placeholder="e.g. Smart electric shuttle service connecting metro stations to IT parks in Pune with automated QR ticketing and guaranteed rush-hour frequency..."
              className="w-full px-4 py-3.5 text-sm bg-[#F7F4F2] border border-[#E7DAD8] rounded-xl text-[#302629] placeholder:text-[#78696B]/60 focus:outline-none focus:ring-2 focus:ring-[#873F46]/20 focus:border-[#873F46] focus:bg-[#FFFFFF] transition-all shadow-xs leading-relaxed"
            />
            <div className="flex justify-between items-center mt-2 text-xs text-[#78696B]">
              <span>Be specific about customer workflow, location hints, or pricing if known.</span>
              <span className="font-mono">{idea.length} characters</span>
            </div>
          </div>
        </div>

        {/* Founder Intake Accordion */}
        <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl overflow-hidden shadow-xs">
          <div className="p-5 sm:p-6 border-b border-[#E7DAD8] flex items-center justify-between bg-[#F7F4F2]/50">
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="enable-intake"
                checked={enableIntake}
                onChange={(e) => setEnableIntake(e.target.checked)}
                className="w-4 h-4 text-[#873F46] rounded border-[#E7DAD8] focus:ring-[#873F46] cursor-pointer"
              />
              <label htmlFor="enable-intake" className="cursor-pointer select-none">
                <span className="text-base font-bold text-[#302629] block">
                  2. Optional 5-Question Founder Intake
                </span>
                <span className="text-xs text-[#78696B] block">
                  Calibrate research keywords and persona archetypes with your target customer and pricing hypothesis.
                </span>
              </label>
            </div>
            <span
              className={`text-xs px-3 py-1 rounded-full font-bold border ${
                enableIntake
                  ? 'bg-[#F4E9E7] text-[#873F46] border-[#B66B70]/30'
                  : 'bg-[#F7F4F2] text-[#78696B] border-[#E7DAD8]'
              }`}
            >
              {enableIntake ? 'Intake Enabled' : 'Skipped'}
            </span>
          </div>

          {enableIntake && (
            <div className="p-6 sm:p-7 space-y-6 bg-[#FFFFFF] divide-y divide-[#E7DAD8]">
              {/* Question 1: Customer Category & Description */}
              <div className="pt-2 first:pt-0 space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-[#873F46] uppercase tracking-wider">
                    [1/5] Target Customer Category &amp; Profile
                  </label>
                  <span className="text-xs text-[#873F46] font-semibold">Category Required</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-[#302629] mb-1.5">
                      Customer Category *
                    </label>
                    <input
                      type="text"
                      value={customerCategory}
                      onChange={(e) => setCustomerCategory(e.target.value)}
                      placeholder="e.g. Commercial EV fleet operators"
                      className="w-full px-3.5 py-2.5 text-xs bg-[#F7F4F2] border border-[#E7DAD8] rounded-xl text-[#302629] focus:bg-[#FFFFFF] focus:outline-none focus:border-[#873F46] transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-[#302629] mb-1.5">
                      Specific Description (Optional)
                    </label>
                    <input
                      type="text"
                      value={customerDescription}
                      onChange={(e) => setCustomerDescription(e.target.value)}
                      placeholder="e.g. Fleet owners running 5 to 50 vehicles"
                      className="w-full px-3.5 py-2.5 text-xs bg-[#F7F4F2] border border-[#E7DAD8] rounded-xl text-[#302629] focus:bg-[#FFFFFF] focus:outline-none focus:border-[#873F46] transition-colors"
                    />
                  </div>
                </div>
              </div>

              {/* Question 2: Problem Description */}
              <div className="pt-5 space-y-2.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-[#873F46] uppercase tracking-wider">
                    [2/5] Core Customer Problem *
                  </label>
                  <span className="text-xs text-[#873F46] font-semibold">Required</span>
                </div>
                <textarea
                  rows={2}
                  value={problemDescription}
                  onChange={(e) => setProblemDescription(e.target.value)}
                  placeholder="e.g. Unpredictable charging station queues lead to driver downtime and missed delivery commitments..."
                  className="w-full px-3.5 py-2.5 text-xs bg-[#F7F4F2] border border-[#E7DAD8] rounded-xl text-[#302629] focus:bg-[#FFFFFF] focus:outline-none focus:border-[#873F46] leading-relaxed transition-colors"
                />
              </div>

              {/* Question 3: Launch Geography & Scope */}
              <div className="pt-5 space-y-3">
                <label className="text-xs font-bold text-[#873F46] uppercase tracking-wider block">
                  [3/5] Target Geography &amp; Geographic Scope
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-[#302629] mb-1.5">
                      Launch City or State (Optional)
                    </label>
                    <input
                      type="text"
                      value={launchGeography}
                      onChange={(e) => setLaunchGeography(e.target.value)}
                      placeholder="e.g. Ahmedabad, Gujarat"
                      className="w-full px-3.5 py-2.5 text-xs bg-[#F7F4F2] border border-[#E7DAD8] rounded-xl text-[#302629] focus:bg-[#FFFFFF] focus:outline-none focus:border-[#873F46] transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-[#302629] mb-1.5">
                      Intended Geographic Reach
                    </label>
                    <select
                      value={geographicScope}
                      onChange={(e) => setGeographicScope(e.target.value as GeographicScope)}
                      className="w-full px-3.5 py-2.5 text-xs bg-[#F7F4F2] border border-[#E7DAD8] rounded-xl text-[#302629] focus:bg-[#FFFFFF] focus:outline-none focus:border-[#873F46] transition-colors"
                    >
                      <option value="local_city">Local City / District</option>
                      <option value="regional_state">Regional / State</option>
                      <option value="national">National (Pan-India)</option>
                      <option value="multi_national">Multi-National</option>
                      <option value="not_decided">Not Decided</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Question 4: Known Alternatives & Competitors */}
              <div className="pt-5 space-y-2.5">
                <label className="text-xs font-bold text-[#873F46] uppercase tracking-wider block">
                  [4/5] Known Alternatives &amp; Workarounds
                </label>
                <input
                  type="text"
                  value={knownAlternatives}
                  onChange={(e) => setKnownAlternatives(e.target.value)}
                  placeholder="Comma-separated: Public charging stations, diesel generators, overnight AC yards"
                  className="w-full px-3.5 py-2.5 text-xs bg-[#F7F4F2] border border-[#E7DAD8] rounded-xl text-[#302629] focus:bg-[#FFFFFF] focus:outline-none focus:border-[#873F46] transition-colors"
                />
                <span className="text-xs text-[#78696B] block">
                  Separate multiple workarounds with commas. Used to calibrate competitive friction.
                </span>
              </div>

              {/* Question 5: Pricing Hypothesis & Prior Validation */}
              <div className="pt-5 space-y-3">
                <label className="text-xs font-bold text-[#873F46] uppercase tracking-wider block">
                  [5/5] Monetization Model &amp; Prior Validation
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-[#302629] mb-1.5">
                      Pricing Model
                    </label>
                    <select
                      value={pricingModel}
                      onChange={(e) => setPricingModel(e.target.value as PricingModel)}
                      className="w-full px-3.5 py-2.5 text-xs bg-[#F7F4F2] border border-[#E7DAD8] rounded-xl text-[#302629] focus:bg-[#FFFFFF] focus:outline-none focus:border-[#873F46] transition-colors"
                    >
                      <option value="subscription">Subscription (Monthly/Annual)</option>
                      <option value="usage_based">Usage-based / Per Unit</option>
                      <option value="one_time_purchase">One-Time Purchase</option>
                      <option value="freemium">Freemium</option>
                      <option value="marketplace_commission">Marketplace Commission</option>
                      <option value="free">Free / Ad-supported</option>
                      <option value="not_decided">Not Decided</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-[#302629] mb-1.5">
                      Expected Price Point
                    </label>
                    <input
                      type="text"
                      value={expectedPrice}
                      onChange={(e) => setExpectedPrice(e.target.value)}
                      placeholder="e.g. INR 3,000/month per vehicle"
                      className="w-full px-3.5 py-2.5 text-xs bg-[#F7F4F2] border border-[#E7DAD8] rounded-xl text-[#302629] focus:bg-[#FFFFFF] focus:outline-none focus:border-[#873F46] transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-[#302629] mb-1.5">
                      Validation Stage
                    </label>
                    <select
                      value={validationStage}
                      onChange={(e) => setValidationStage(e.target.value as ValidationStage)}
                      className="w-full px-3.5 py-2.5 text-xs bg-[#F7F4F2] border border-[#E7DAD8] rounded-xl text-[#302629] focus:bg-[#FFFFFF] focus:outline-none focus:border-[#873F46] transition-colors"
                    >
                      <option value="idea_only">Idea Only (No customer talks)</option>
                      <option value="informal_conversations">Informal Conversations</option>
                      <option value="interviews_or_surveys">Structured Interviews / Surveys</option>
                      <option value="prototype_or_pilot">Prototype or Pilot in Progress</option>
                      <option value="paying_customers">Paying Customers Secured</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 pt-2">
                  <div className="sm:col-span-3">
                    <label className="block text-xs font-bold text-[#302629] mb-1.5">
                      Validation Notes / Qualitative Feedback (Optional)
                    </label>
                    <input
                      type="text"
                      value={validationNotes}
                      onChange={(e) => setValidationNotes(e.target.value)}
                      placeholder="e.g. 6 dispatchers confirmed queue anxiety; 2 requested multi-vehicle discount"
                      className="w-full px-3.5 py-2.5 text-xs bg-[#F7F4F2] border border-[#E7DAD8] rounded-xl text-[#302629] focus:bg-[#FFFFFF] focus:outline-none focus:border-[#873F46] transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-[#302629] mb-1.5">
                      Sample Size (Count)
                    </label>
                    <input
                      type="number"
                      min={0}
                      value={validationSampleSize}
                      onChange={(e) =>
                        setValidationSampleSize(e.target.value === '' ? '' : parseInt(e.target.value, 10))
                      }
                      placeholder="e.g. 6"
                      className="w-full px-3.5 py-2.5 text-xs bg-[#F7F4F2] border border-[#E7DAD8] rounded-xl text-[#302629] focus:bg-[#FFFFFF] focus:outline-none focus:border-[#873F46] transition-colors"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Advanced Execution Settings */}
        <div className="bg-[#FFFFFF] border border-[#E7DAD8] rounded-2xl overflow-hidden shadow-xs">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="w-full p-5 flex items-center justify-between text-left hover:bg-[#F7F4F2]/50 transition-colors"
          >
            <div className="flex items-center gap-2.5">
              <Sliders className="w-4 h-4 text-[#873F46]" />
              <span className="text-base font-bold text-[#302629]">
                Advanced Pipeline Settings
              </span>
              <span className="text-xs text-[#78696B]">
                (Persona count: {personaCount}, Concurrency: {concurrency})
              </span>
            </div>
            {showAdvanced ? (
              <ChevronUp className="w-4 h-4 text-[#78696B]" />
            ) : (
              <ChevronDown className="w-4 h-4 text-[#78696B]" />
            )}
          </button>

          {showAdvanced && (
            <div className="p-6 border-t border-[#E7DAD8] bg-[#F7F4F2]/40 grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div>
                <div className="flex justify-between text-xs font-bold mb-1.5">
                  <label htmlFor="persona-count-input" className="text-[#302629]">Target Persona Count</label>
                  <span className="text-[#873F46] font-mono">{personaCount} personas</span>
                </div>
                <input
                  id="persona-count-input"
                  type="range"
                  min={2}
                  max={20}
                  step={1}
                  value={personaCount}
                  onChange={(e) => setPersonaCount(parseInt(e.target.value, 10))}
                  className="w-full accent-[#873F46] cursor-pointer"
                />
                <span className="text-xs text-[#78696B] block mt-1.5">
                  Default: 10 personas. Synthesized across target customer demographics.
                </span>
              </div>

              <div>
                <div className="flex justify-between text-xs font-bold mb-1.5">
                  <label htmlFor="eval-concurrency-input" className="text-[#302629]">Evaluation Concurrency</label>
                  <span className="text-[#873F46] font-mono">{concurrency} workers</span>
                </div>
                <input
                  id="eval-concurrency-input"
                  type="range"
                  min={1}
                  max={5}
                  step={1}
                  value={concurrency}
                  onChange={(e) => setConcurrency(parseInt(e.target.value, 10))}
                  className="w-full accent-[#873F46] cursor-pointer"
                />
                <span className="text-xs text-[#78696B] block mt-1.5">
                  Default: 3 concurrent evaluations. Bounded to respect API rate limits.
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Validation Error Banner */}
        {validationError && (
          <div className="p-4 bg-[#FAF2EA] border border-[#C06E22]/30 text-[#C06E22] rounded-xl text-xs font-semibold flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{validationError}</span>
          </div>
        )}

        {/* API Error Banner */}
        {errorMessage && (
          <div className="p-5 bg-[#F4E9E7] border border-[#873F46]/30 text-[#873F46] rounded-xl text-xs space-y-1.5">
            <div className="flex items-center gap-2 font-bold text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>Pipeline Execution Failed</span>
            </div>
            <p className="text-xs text-[#302629] leading-relaxed pl-6">{errorMessage}</p>
          </div>
        )}

        {/* Submission Actions */}
        <div className="flex items-center justify-between pt-2">
          <button
            type="button"
            onClick={handleReset}
            disabled={isLoading}
            className="px-4 py-2 text-xs font-bold text-[#78696B] hover:text-[#302629] hover:bg-[#FFFFFF] border border-[#E7DAD8] rounded-xl transition-colors flex items-center gap-1.5"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset Inputs</span>
          </button>

          <button
            type="submit"
            disabled={isLoading}
            className="px-7 py-3 bg-[#873F46] hover:bg-[#873F46]/90 disabled:bg-[#E7DAD8] text-[#FFFFFF] rounded-xl text-sm font-bold flex items-center gap-2.5 shadow-xs transition-all transform hover:-translate-y-0.5"
          >
            {isLoading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Dispatching Analysis...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" />
                <span>Start Multi-Persona Validation</span>
              </>
            )}
          </button>
        </div>
      </form>

      {/* ── Inline Analysis Results ── */}
      {lastResult && lastSubmittedIdea && (
        <AnalysisResults
          report={lastResult}
          submittedIdea={lastSubmittedIdea}
          submittedGeography={lastSubmittedGeography ?? null}
          onViewFullReport={(page: PageId) => onViewFullReport?.(page)}
          onNewAnalysis={handleReset}
        />
      )}
    </div>
  );
};

export default NewAnalysisPage;
