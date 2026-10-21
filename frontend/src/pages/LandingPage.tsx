import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Compass,
  ArrowRight,
  TrendingUp,
  Users,
  ShieldAlert,
  Microscope,
  BarChart3,
  FileText,
  CheckCircle,
  AlertTriangle,
  Info,
  ChevronRight,
  Star,
  Zap,
  Target,
  Search,
  FlaskConical,
  Menu,
  X,
  ArrowUpRight,
  Lightbulb,
  CircleDot,
  Clock,
  BookOpen,
  Layers
} from 'lucide-react';

/* ─── helper: simple intersection observer for scroll animations ─── */
function useInView(threshold = 0.15) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setInView(true); obs.disconnect(); } },
      { threshold }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, inView };
}

/* ─── Dashboard mockup card components (product previews) ─── */
const MockOverviewCard: React.FC = () => (
  <div className="lp-card p-5 space-y-4">
    <div className="flex items-center justify-between">
      <span className="text-xs font-bold text-[#9CA8B5] uppercase tracking-widest">Market Overview</span>
      <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#F43F4F]/10 text-[#F43F4F] font-semibold border border-[#F43F4F]/20">Demo</span>
    </div>
    <div className="text-sm font-semibold text-[#F8F8F8]">EV Fleet Charging Hub — Ahmedabad</div>
    <div className="grid grid-cols-2 gap-2">
      {[
        { label: 'Market Opportunity', val: 'Moderate–High', color: '#4ADE80' },
        { label: 'Evidence Coverage', val: '62%', color: '#60A5FA' },
        { label: 'Customer Segments', val: '4 Defined', color: '#FBBF24' },
        { label: 'Key Risks', val: '3 Flagged', color: '#F43F4F' },
      ].map(m => (
        <div key={m.label} className="bg-[#0D1012] rounded-xl p-3 border border-[#292F35]">
          <div className="text-[10px] text-[#9CA8B5] mb-1">{m.label}</div>
          <div className="text-sm font-bold" style={{ color: m.color }}>{m.val}</div>
        </div>
      ))}
    </div>
    <div className="space-y-1.5">
      <div className="text-[11px] text-[#9CA8B5] font-semibold uppercase tracking-wider">Next Steps</div>
      {['Interview 5 fleet managers', 'Survey on pricing sensitivity', 'Test pilot reservation flow'].map(s => (
        <div key={s} className="flex items-center gap-2 text-xs text-[#F8F8F8]">
          <CheckCircle className="w-3 h-3 text-[#4ADE80] shrink-0" />
          <span>{s}</span>
        </div>
      ))}
    </div>
  </div>
);

const MockPersonaCard: React.FC = () => (
  <div className="lp-card p-5 space-y-3">
    <div className="flex items-center justify-between">
      <span className="text-xs font-bold text-[#9CA8B5] uppercase tracking-widest">Persona Comparison</span>
      <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#60A5FA]/10 text-[#60A5FA] font-semibold border border-[#60A5FA]/20">Demo</span>
    </div>
    {[
      { name: 'Priya S.', role: 'Fleet Manager', interest: 82, intent: 74, barrier: 31 },
      { name: 'Arjun M.', role: 'Logistics Head', interest: 68, intent: 55, barrier: 52 },
      { name: 'Kavita R.', role: 'EV Depot Operator', interest: 91, intent: 85, barrier: 22 },
    ].map(p => (
      <div key={p.name} className="bg-[#0D1012] rounded-xl p-3 border border-[#292F35]">
        <div className="flex items-center justify-between mb-2">
          <div>
            <div className="text-xs font-bold text-[#F8F8F8]">{p.name}</div>
            <div className="text-[10px] text-[#9CA8B5]">{p.role}</div>
          </div>
          <div className="text-right">
            <div className="text-xs font-bold text-[#4ADE80]">{p.interest}%</div>
            <div className="text-[10px] text-[#9CA8B5]">Interest</div>
          </div>
        </div>
        <div className="flex gap-2 text-[10px]">
          <span className="px-1.5 py-0.5 rounded bg-[#60A5FA]/10 text-[#60A5FA]">Intent {p.intent}%</span>
          <span className="px-1.5 py-0.5 rounded bg-[#FBBF24]/10 text-[#FBBF24]">Barrier {p.barrier}%</span>
        </div>
      </div>
    ))}
  </div>
);

const MockMarketCard: React.FC = () => (
  <div className="lp-card p-5 space-y-3">
    <div className="flex items-center justify-between">
      <span className="text-xs font-bold text-[#9CA8B5] uppercase tracking-widest">Market Signals</span>
      <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#4ADE80]/10 text-[#4ADE80] font-semibold border border-[#4ADE80]/20">Demo</span>
    </div>
    <div className="space-y-2">
      {[
        { label: 'EV adoption growing 38% YoY in Tier-1 cities', type: 'positive' },
        { label: 'Queue times average 55 min at public stations', type: 'positive' },
        { label: 'Depot charging requires 8–12hr overnight window', type: 'risk' },
        { label: 'Regulatory framework for commercial EV charging not settled', type: 'risk' },
        { label: 'Fleet managers cite charging as #2 operational pain point', type: 'evidence' },
      ].map(s => (
        <div key={s.label} className="flex items-start gap-2 text-xs">
          <span className={`mt-0.5 w-2 h-2 rounded-full shrink-0 ${s.type === 'positive' ? 'bg-[#4ADE80]' : s.type === 'risk' ? 'bg-[#F43F4F]' : 'bg-[#60A5FA]'}`} />
          <span className="text-[#9CA8B5]">{s.label}</span>
        </div>
      ))}
    </div>
  </div>
);

const MockReportCard: React.FC = () => (
  <div className="lp-card p-5 space-y-3">
    <div className="flex items-center justify-between">
      <span className="text-xs font-bold text-[#9CA8B5] uppercase tracking-widest">Validation Report</span>
      <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#873F46]/20 text-[#F43F4F] font-semibold border border-[#F43F4F]/20">Demo</span>
    </div>
    <div className="space-y-2">
      <div className="bg-[#4ADE80]/5 border border-[#4ADE80]/20 rounded-xl p-3">
        <div className="text-[10px] font-bold text-[#4ADE80] uppercase mb-1">Promising Signal</div>
        <div className="text-xs text-[#F8F8F8]">Fleet operators show high willingness to pay for reliable fast-charging reservation</div>
      </div>
      <div className="bg-[#F43F4F]/5 border border-[#F43F4F]/20 rounded-xl p-3">
        <div className="text-[10px] font-bold text-[#F43F4F] uppercase mb-1">Key Risk</div>
        <div className="text-xs text-[#F8F8F8]">Grid infrastructure costs may make unit economics challenging below 20-van fleets</div>
      </div>
      <div className="bg-[#60A5FA]/5 border border-[#60A5FA]/20 rounded-xl p-3">
        <div className="text-[10px] font-bold text-[#60A5FA] uppercase mb-1">Validate Next</div>
        <div className="text-xs text-[#F8F8F8]">Run 5 structured interviews with fleet managers on reservation willingness</div>
      </div>
    </div>
  </div>
);

/* ─── Main Landing Page ─── */
export const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  const goToApp = () => {
    navigate('/app');
    // After navigating to /app the DashboardShell will show 'overview' by default.
    // To land on new-analysis we store the desired page in sessionStorage so DashboardShell can pick it up.
    sessionStorage.setItem('indivalidate_initial_page', 'new-analysis');
  };

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
    setMobileMenuOpen(false);
  };

  /* section animation hooks */
  const heroAnim = useInView(0.05);
  const problemAnim = useInView();
  const transitionAnim = useInView();
  const solutionAnim = useInView();
  const behindAnim = useInView();
  const howAnim = useInView();
  const showcaseAnim = useInView();
  const trustAnim = useInView();
  const finalCtaAnim = useInView();

  return (
    <div className="lp-root">
      {/* ═══════════════════════════════════════
          NAVBAR
      ═══════════════════════════════════════ */}
      <nav className={`lp-nav ${scrolled ? 'lp-nav--scrolled' : ''}`} aria-label="Main navigation">
        <div className="lp-container lp-nav__inner">
          {/* Brand */}
          <a href="/" className="lp-brand" aria-label="IndiValidate home">
            <div className="lp-brand__icon">
              <Compass className="w-5 h-5 text-white" />
            </div>
            <span className="lp-brand__name">
              IndiValidate<span className="lp-brand__dot">.</span>
            </span>
          </a>

          {/* Desktop nav links */}
          <div className="lp-nav__links">
            <button onClick={() => scrollTo('how-it-works')} className="lp-nav__link">How It Works</button>
            <button onClick={() => scrollTo('features')} className="lp-nav__link">Features</button>
            <button onClick={goToApp} id="nav-cta-btn" className="lp-btn lp-btn--primary lp-btn--sm">
              Know About Your Startup
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>

          {/* Mobile toggle */}
          <button
            className="lp-nav__mobile-toggle"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <div className="lp-nav__mobile-menu">
            <button onClick={() => scrollTo('how-it-works')} className="lp-nav__mobile-link">How It Works</button>
            <button onClick={() => scrollTo('features')} className="lp-nav__mobile-link">Features</button>
            <button onClick={goToApp} id="nav-cta-mobile-btn" className="lp-btn lp-btn--primary w-full justify-center mt-2">
              Know About Your Startup
            </button>
          </div>
        )}
      </nav>

      {/* ═══════════════════════════════════════
          SECTION A — HERO
      ═══════════════════════════════════════ */}
      <section className="lp-hero" aria-labelledby="hero-heading">
        {/* Background glow orbs */}
        <div className="lp-hero__glow lp-hero__glow--red" aria-hidden="true" />
        <div className="lp-hero__glow lp-hero__glow--blue" aria-hidden="true" />

        <div className="lp-container lp-hero__inner">
          {/* Left: copy */}
          <div
            ref={heroAnim.ref}
            className={`lp-hero__copy lp-anim ${heroAnim.inView ? 'lp-anim--visible' : ''}`}
          >
            {/* Eyebrow */}
            <div className="lp-eyebrow" role="doc-subtitle">
              <span className="lp-eyebrow__dash" aria-hidden="true" />
              AI-POWERED STARTUP MARKET VALIDATION
            </div>

            {/* Headline */}
            <h1 id="hero-heading" className="lp-hero__h1">
              STOP BUILDING.<br />
              <span className="lp-text--accent">START VALIDATING.</span>
            </h1>

            {/* Supporting text */}
            <p className="lp-hero__body">
              Turn your startup idea into a structured market assessment. Explore customer needs, evaluate market signals, and identify what you should validate before investing further.
            </p>

            {/* CTA */}
            <div className="lp-hero__cta-group">
              <button
                id="hero-cta-btn"
                onClick={goToApp}
                className="lp-btn lp-btn--primary lp-btn--lg"
              >
                Know About Your Startup
                <ArrowRight className="w-5 h-5" />
              </button>
              <p className="lp-hero__cta-label">Research-backed signals. Clear next steps.</p>
            </div>
          </div>

          {/* Right: product preview */}
          <div
            className={`lp-hero__visual lp-anim lp-anim--delay-2 ${heroAnim.inView ? 'lp-anim--visible' : ''}`}
            aria-label="IndiValidate dashboard preview"
          >
            <div className="lp-hero__visual-grid">
              <MockOverviewCard />
              <MockPersonaCard />
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          SECTION B — THE PROBLEM
      ═══════════════════════════════════════ */}
      <section className="lp-section lp-section--alt" id="problem" aria-labelledby="problem-heading">
        <div className="lp-container">
          {/* Status badge */}
          <div className="lp-section__badge lp-section__badge--red">
            <CircleDot className="w-3 h-3" />
            STATUS: UNVALIDATED ASSUMPTION
          </div>

          <div
            ref={problemAnim.ref}
            className={`lp-anim ${problemAnim.inView ? 'lp-anim--visible' : ''}`}
          >
            <h2 id="problem-heading" className="lp-section__h2 text-center">
              Building for a Market You<br />Haven't Validated?
            </h2>
          </div>

          <div className="lp-problem__grid">
            {/* Card 01 */}
            <div className={`lp-card lp-card--problem lp-anim lp-anim--delay-1 ${problemAnim.inView ? 'lp-anim--visible' : ''}`}>
              <div className="lp-card__number-badge lp-card__number-badge--red">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <div className="lp-card__num">01</div>
              <h3 className="lp-card__title">Building on Assumptions</h3>
              <p className="lp-card__body">
                An idea can sound promising without solving a problem customers urgently need to fix. Without structured exploration, you may invest months building something the market doesn't yet want.
              </p>
            </div>

            {/* Card 02 */}
            <div className={`lp-card lp-card--problem lp-anim lp-anim--delay-2 ${problemAnim.inView ? 'lp-anim--visible' : ''}`}>
              <div className="lp-card__number-badge lp-card__number-badge--blue">
                <Users className="w-5 h-5" />
              </div>
              <div className="lp-card__num">02</div>
              <h3 className="lp-card__title">Finding the Right Customers</h3>
              <p className="lp-card__body">
                Without structured research, it is difficult to identify the right customer segments, competing alternatives, and adoption barriers. Real demand often looks different from initial intuition.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          SECTION C — TRANSITION STATEMENT
      ═══════════════════════════════════════ */}
      <section className="lp-section lp-section--transition">
        <div className="lp-container">
          <div
            ref={transitionAnim.ref}
            className={`lp-transition-block lp-anim ${transitionAnim.inView ? 'lp-anim--visible' : ''}`}
          >
            <h2 className="lp-transition__h2">
              What if you could{' '}
              <span className="lp-text--accent">challenge your assumptions</span>{' '}
              before committing to your idea?
            </h2>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          SECTION D — THE SOLUTION / FEATURES
      ═══════════════════════════════════════ */}
      <section className="lp-section" id="features" aria-labelledby="solution-heading">
        <div className="lp-container">
          <div className="lp-section__badge lp-section__badge--blue">THE SOLUTION</div>

          <div
            ref={solutionAnim.ref}
            className={`lp-anim ${solutionAnim.inView ? 'lp-anim--visible' : ''}`}
          >
            <h2 id="solution-heading" className="lp-section__h2 text-center">
              Turn Startup Uncertainty Into<br />Clearer Decisions.
            </h2>
            <p className="lp-section__subtext">
              IndiValidate combines available research, customer hypotheses, and AI-assisted analysis to help you understand what looks promising, what remains uncertain, and what to test next.
            </p>
          </div>

          <div className="lp-features__grid">
            {[
              {
                icon: <Search className="w-6 h-6" />,
                num: '01',
                title: 'Explore Market Signals',
                body: 'Bring together available research and market indicators relevant to the startup idea. See what evidence exists, where gaps remain, and which signals deserve attention.',
                color: '#60A5FA',
                delay: 'lp-anim--delay-1',
              },
              {
                icon: <Users className="w-6 h-6" />,
                num: '02',
                title: 'Understand Customer Segments',
                body: 'Explore generated customer personas, their needs, motivations, and potential adoption barriers. Compare how different segments might respond to the same idea.',
                color: '#4ADE80',
                delay: 'lp-anim--delay-2',
              },
              {
                icon: <Target className="w-6 h-6" />,
                num: '03',
                title: 'Identify Opportunities and Risks',
                body: 'Compare promising signals against missing evidence, competitive alternatives, and unresolved assumptions. Understand what looks strong and what still needs confirmation.',
                color: '#FBBF24',
                delay: 'lp-anim--delay-3',
              },
              {
                icon: <FlaskConical className="w-6 h-6" />,
                num: '04',
                title: 'Decide What to Validate Next',
                body: 'Turn the analysis into concrete questions, experiments, and next steps for real-world validation. Leave with a prioritized agenda for interviews, surveys, or prototypes.',
                color: '#F43F4F',
                delay: 'lp-anim--delay-4',
              },
            ].map(f => (
              <div
                key={f.num}
                className={`lp-feature-card lp-anim ${f.delay} ${solutionAnim.inView ? 'lp-anim--visible' : ''}`}
              >
                <div className="lp-feature-card__icon" style={{ backgroundColor: `${f.color}15`, border: `1px solid ${f.color}25` }}>
                  <span style={{ color: f.color }}>{f.icon}</span>
                </div>
                <div className="lp-feature-card__num" style={{ color: f.color }}>{f.num}</div>
                <h3 className="lp-feature-card__title">{f.title}</h3>
                <p className="lp-feature-card__body">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          SECTION E — BEHIND THE ANALYSIS
      ═══════════════════════════════════════ */}
      <section className="lp-section lp-section--alt" aria-labelledby="behind-heading">
        <div className="lp-container">
          <div className="lp-section__badge lp-section__badge--default">BEHIND THE ANALYSIS</div>

          <div
            ref={behindAnim.ref}
            className={`lp-anim ${behindAnim.inView ? 'lp-anim--visible' : ''}`}
          >
            <h2 id="behind-heading" className="lp-section__h2 text-center">
              Understand the Signals Behind<br />Your Startup Idea.
            </h2>
          </div>

          {/* Sub-section 1: text left, visual right */}
          <div className={`lp-alternating lp-anim lp-anim--delay-1 ${behindAnim.inView ? 'lp-anim--visible' : ''}`}>
            <div className="lp-alternating__copy">
              <div className="lp-eyebrow lp-eyebrow--sm">
                <BookOpen className="w-4 h-4 text-[#60A5FA]" />
                MARKET RESEARCH & EVIDENCE
              </div>
              <h3 className="lp-alternating__h3">Context from Available Sources</h3>
              <p className="lp-alternating__body">
                IndiValidate draws on available research to surface context around market demand, customer needs, and alternative solutions. Rather than relying on intuition alone, you can see what sources suggest — and where evidence is thin or missing.
              </p>
              <ul className="lp-check-list">
                {[
                  'Market size indicators and demand signals',
                  'Competitive landscape and alternatives',
                  'Evidence gaps and unsupported assumptions',
                  'Source traceability for each finding',
                ].map(i => (
                  <li key={i} className="lp-check-list__item">
                    <CheckCircle className="w-4 h-4 text-[#60A5FA] shrink-0" />
                    {i}
                  </li>
                ))}
              </ul>
            </div>
            <div className="lp-alternating__visual">
              <MockMarketCard />
            </div>
          </div>

          {/* Sub-section 2: visual left, text right */}
          <div className={`lp-alternating lp-alternating--reversed lp-anim lp-anim--delay-1 ${behindAnim.inView ? 'lp-anim--visible' : ''}`}>
            <div className="lp-alternating__visual">
              <MockPersonaCard />
            </div>
            <div className="lp-alternating__copy">
              <div className="lp-eyebrow lp-eyebrow--sm">
                <Users className="w-4 h-4 text-[#4ADE80]" />
                MULTI-PERSONA CUSTOMER ANALYSIS
              </div>
              <h3 className="lp-alternating__h3">Explore Different Customer Perspectives</h3>
              <p className="lp-alternating__body">
                Generated personas help you examine how different types of customers might respond to your idea — their motivations, likely objections, pricing sensitivities, and adoption barriers. Each persona is clearly marked as a simulation, not an actual interviewed customer.
              </p>
              <ul className="lp-check-list">
                {[
                  'Multiple segment archetypes per analysis',
                  'Interest, intent, and barrier scores per persona',
                  'Feature preferences and main objections',
                  'Pricing concern analysis per segment',
                ].map(i => (
                  <li key={i} className="lp-check-list__item">
                    <CheckCircle className="w-4 h-4 text-[#4ADE80] shrink-0" />
                    {i}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Sub-section 3: text left, visual right */}
          <div className={`lp-alternating lp-anim lp-anim--delay-1 ${behindAnim.inView ? 'lp-anim--visible' : ''}`}>
            <div className="lp-alternating__copy">
              <div className="lp-eyebrow lp-eyebrow--sm">
                <Target className="w-4 h-4 text-[#F43F4F]" />
                RISKS, OPPORTUNITIES & NEXT STEPS
              </div>
              <h3 className="lp-alternating__h3">From Uncertainty to Actionable Questions</h3>
              <p className="lp-alternating__body">
                The analysis organizes promising signals alongside key risks and evidence gaps. Instead of a generic summary, you receive a prioritized set of questions and experiments designed to address the most critical unknowns about your idea.
              </p>
              <ul className="lp-check-list">
                {[
                  'Categorized promising findings with evidence status',
                  'Flagged risks and competitive barriers',
                  'Recommended validation experiments',
                  'Structured next steps for each priority area',
                ].map(i => (
                  <li key={i} className="lp-check-list__item">
                    <CheckCircle className="w-4 h-4 text-[#F43F4F] shrink-0" />
                    {i}
                  </li>
                ))}
              </ul>
            </div>
            <div className="lp-alternating__visual">
              <MockReportCard />
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          SECTION F — HOW IT WORKS
      ═══════════════════════════════════════ */}
      <section className="lp-section" id="how-it-works" aria-labelledby="how-heading">
        <div className="lp-container">
          <div className="lp-section__badge lp-section__badge--default">HOW IT WORKS</div>

          <div
            ref={howAnim.ref}
            className={`lp-anim ${howAnim.inView ? 'lp-anim--visible' : ''}`}
          >
            <h2 id="how-heading" className="lp-section__h2 text-center">
              Three Steps from Idea<br />to Structured Validation.
            </h2>
          </div>

          <div className="lp-steps">
            {[
              {
                num: '01',
                icon: <Lightbulb className="w-7 h-7" />,
                title: 'Describe Your Idea',
                body: 'Enter the startup idea, target market, customer problem, and relevant context. Optionally add pricing, geography, and what you already know about your customers.',
                delay: 'lp-anim--delay-1',
              },
              {
                num: '02',
                icon: <Layers className="w-7 h-7" />,
                title: 'Analyze the Market',
                body: 'The system organizes available research, evaluates generated customer personas, and identifies signals, gaps, and potential risks across customer segments.',
                delay: 'lp-anim--delay-2',
              },
              {
                num: '03',
                icon: <FlaskConical className="w-7 h-7" />,
                title: 'Decide What to Test',
                body: 'Review the findings and use the suggested next steps to guide interviews, surveys, experiments, or other real-world validation activities.',
                delay: 'lp-anim--delay-3',
              },
            ].map((step, i) => (
              <React.Fragment key={step.num}>
                <div className={`lp-step lp-anim ${step.delay} ${howAnim.inView ? 'lp-anim--visible' : ''}`}>
                  <div className="lp-step__icon-wrap">
                    <span className="lp-step__icon">{step.icon}</span>
                    <div className="lp-step__num">{step.num}</div>
                  </div>
                  <h3 className="lp-step__title">{step.title}</h3>
                  <p className="lp-step__body">{step.body}</p>
                </div>
                {i < 2 && <div className="lp-step__connector" aria-hidden="true"><ChevronRight className="w-5 h-5 text-[#292F35]" /></div>}
              </React.Fragment>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          SECTION G — PRODUCT SHOWCASE
      ═══════════════════════════════════════ */}
      <section className="lp-section lp-section--alt" aria-labelledby="showcase-heading">
        <div className="lp-container">
          <div
            ref={showcaseAnim.ref}
            className={`lp-anim ${showcaseAnim.inView ? 'lp-anim--visible' : ''}`}
          >
            <h2 id="showcase-heading" className="lp-section__h2 text-center">
              From a Startup Idea to a<br />Structured Validation Report.
            </h2>
            <p className="lp-section__subtext">
              Each analysis delivers a complete picture — market signals, persona insights, opportunities, risks, and recommended next steps — all in one structured report.
            </p>
          </div>

          <div className={`lp-showcase__grid lp-anim lp-anim--delay-1 ${showcaseAnim.inView ? 'lp-anim--visible' : ''}`}>
            <MockOverviewCard />
            <MockPersonaCard />
            <MockMarketCard />
            <MockReportCard />
          </div>

          <div className={`lp-section__cta-center lp-anim lp-anim--delay-2 ${showcaseAnim.inView ? 'lp-anim--visible' : ''}`}>
            <button id="showcase-cta-btn" onClick={goToApp} className="lp-btn lp-btn--primary lp-btn--lg">
              Know About Your Startup
              <ArrowRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          SECTION H — LIMITATIONS & TRUST
      ═══════════════════════════════════════ */}
      <section className="lp-section" aria-labelledby="trust-heading">
        <div className="lp-container">
          <div
            ref={trustAnim.ref}
            className={`lp-trust lp-anim ${trustAnim.inView ? 'lp-anim--visible' : ''}`}
          >
            <div className="lp-trust__header">
              <Info className="w-5 h-5 text-[#9CA8B5]" />
              <h2 id="trust-heading" className="lp-trust__heading">Designed for Clarity, Not False Confidence</h2>
            </div>
            <div className="lp-trust__grid">
              {[
                {
                  icon: <Users className="w-4 h-4" />,
                  title: 'Simulated Personas',
                  body: 'Customer personas are AI-generated archetypes, not actual interviewed customers. They are useful for exploring hypotheses, not for replacing real customer conversations.',
                },
                {
                  icon: <BookOpen className="w-4 h-4" />,
                  title: 'Evidence Dependent',
                  body: 'Findings depend on the availability and relevance of underlying research sources. Where evidence is thin, the analysis will flag it rather than fill gaps with speculation.',
                },
                {
                  icon: <BarChart3 className="w-4 h-4" />,
                  title: 'Analytical Aid',
                  body: 'Scores and assessments are decision-support tools, not guarantees of commercial success. No analysis can predict whether a startup will succeed in the real world.',
                },
                {
                  icon: <FlaskConical className="w-4 h-4" />,
                  title: 'Real Validation Still Matters',
                  body: 'Customer interviews, surveys, and experiments remain essential for confirming demand. IndiValidate helps you prepare smarter questions and prioritize what to test first.',
                },
              ].map(t => (
                <div key={t.title} className="lp-trust__item">
                  <div className="lp-trust__item-icon">{t.icon}</div>
                  <div>
                    <div className="lp-trust__item-title">{t.title}</div>
                    <div className="lp-trust__item-body">{t.body}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          SECTION I — FINAL CTA
      ═══════════════════════════════════════ */}
      <section className="lp-final-cta" aria-labelledby="final-cta-heading">
        <div className="lp-final-cta__glow" aria-hidden="true" />
        <div className="lp-container">
          <div
            ref={finalCtaAnim.ref}
            className={`lp-final-cta__inner lp-anim ${finalCtaAnim.inView ? 'lp-anim--visible' : ''}`}
          >
            <h2 id="final-cta-heading" className="lp-final-cta__h2">
              Your Next Startup Decision Should Be<br />
              <span className="lp-text--accent">More Than a Guess.</span>
            </h2>
            <p className="lp-final-cta__body">
              Explore the signals, question the assumptions, and identify what to validate next.
            </p>
            <button id="final-cta-btn" onClick={goToApp} className="lp-btn lp-btn--primary lp-btn--xl">
              Know About Your Startup
              <ArrowUpRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          SECTION J — FOOTER
      ═══════════════════════════════════════ */}
      <footer className="lp-footer" role="contentinfo">
        <div className="lp-container">
          <div className="lp-footer__inner">
            {/* Brand */}
            <div className="lp-footer__brand">
              <div className="lp-brand">
                <div className="lp-brand__icon">
                  <Compass className="w-5 h-5 text-white" />
                </div>
                <span className="lp-brand__name">
                  IndiValidate<span className="lp-brand__dot">.</span>
                </span>
              </div>
              <p className="lp-footer__desc">
                AI-assisted market validation for early-stage startup ideas. Understand signals, explore customer perspectives, and decide what to test next.
              </p>
              <p className="lp-footer__disclaimer">
                Analysis supports decision-making and does not guarantee market success.
              </p>
            </div>

            {/* Links */}
            <div className="lp-footer__links">
              <div className="lp-footer__link-col">
                <div className="lp-footer__link-heading">Navigate</div>
                <button onClick={() => scrollTo('how-it-works')} className="lp-footer__link">How It Works</button>
                <button onClick={() => scrollTo('features')} className="lp-footer__link">Features</button>
                <button onClick={goToApp} className="lp-footer__link">Open Application</button>
              </div>
              <div className="lp-footer__link-col">
                <div className="lp-footer__link-heading">Application</div>
                <button onClick={goToApp} className="lp-footer__link">New Analysis</button>
                <button onClick={goToApp} className="lp-footer__link">Personas &amp; Segments</button>
                <button onClick={goToApp} className="lp-footer__link">Market Insights</button>
                <button onClick={goToApp} className="lp-footer__link">Full Report</button>
              </div>
            </div>
          </div>

          <div className="lp-footer__bottom">
            <span>© {new Date().getFullYear()} IndiValidate. All rights reserved.</span>
            <span className="lp-footer__bottom-note">Findings are analytical aids, not guarantees of commercial success.</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
