import React, { useEffect, useRef, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { OverviewPage } from './pages/OverviewPage';
import { NewAnalysisPage } from './pages/NewAnalysisPage';
import { AnalysisProgressPage } from './pages/AnalysisProgressPage';
import { PersonasPage } from './pages/PersonasPage';
import { MarketInsightsPage } from './pages/MarketInsightsPage';
import { ReportsPage } from './pages/ReportsPage';
import { PersonaDetailModal } from './components/PersonaDetailModal';
import { LandingPage } from './pages/LandingPage';
import { AnalyzeRequest, AnalysisRunRecord, AnalysisRunStatus, MarketValidationReport, PageId, PersonaProfile } from './types';
import { analyzeMarketIdea, checkBackendHealth } from './services/api';
import { SAMPLE_MARKET_REPORT } from './data/sampleReport';

interface SubmittedRequest {
  idea: string;
  geography: string | null;
}

const STORAGE_KEY = 'indivalidate_active_report';
const HISTORY_STORAGE_KEY = 'indivalidate_analysis_history';

const createRunRecordFromReport = (rep: MarketValidationReport, runStatus: AnalysisRunStatus = 'completed'): AnalysisRunRecord => {
  const cov = rep.evidence_coverage_audit;
  const targetLoc =
    typeof rep.idea_and_context?.target_geography?.location === 'string'
      ? rep.idea_and_context.target_geography.location
      : typeof rep.idea_and_context?.target_geography?.city === 'string'
      ? rep.idea_and_context.target_geography.city
      : null;

  return {
    id: rep.report_id || `MVR-${Date.now().toString(36).toUpperCase()}`,
    idea: rep.idea_and_context?.business_idea || 'Market Validation Analysis',
    geography: targetLoc,
    timestamp: rep.generated_at || new Date().toISOString(),
    status: runStatus,
    evidenceCoverageRatio: cov?.evidence_coverage_ratio ?? -1,
    supportedFindingsCount: cov?.supported_count ?? 0,
    totalFindingsCount: cov?.total_findings_evaluated ?? 0,
    report: rep,
  };
};

// The dashboard shell — all app pages live inside this
const DashboardShell: React.FC = () => {
  const [activePage, setActivePage] = useState<PageId>('overview');
  const [report, setReport] = useState<MarketValidationReport | null>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        return JSON.parse(saved);
      }
    } catch {
      // Fallback
    }
    return SAMPLE_MARKET_REPORT;
  });

  const [history, setHistory] = useState<AnalysisRunRecord[]>(() => {
    try {
      const savedHistory = localStorage.getItem(HISTORY_STORAGE_KEY);
      if (savedHistory) {
        const parsed = JSON.parse(savedHistory);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed;
        }
      }
    } catch {
      // Ignored
    }
    // Seed with initial report if available
    const initialReport = (() => {
      try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) return JSON.parse(saved);
      } catch {
        // Ignored
      }
      return SAMPLE_MARKET_REPORT;
    })();

    if (initialReport) {
      return [createRunRecordFromReport(initialReport, 'completed')];
    }
    return [];
  });

  const [isBackendOnline, setIsBackendOnline] = useState<boolean | null>(null);
  const [isAnalysisRunning, setIsAnalysisRunning] = useState<boolean>(false);
  const [activeIdeaText, setActiveIdeaText] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isOpenMobile, setIsOpenMobile] = useState<boolean>(false);
  const [activeModalPersona, setActiveModalPersona] = useState<PersonaProfile | null>(null);
  // Inline results for NewAnalysisPage — cleared on new submission to prevent stale display
  const [lastAnalysisResult, setLastAnalysisResult] = useState<MarketValidationReport | null>(null);
  const [lastSubmittedRequest, setLastSubmittedRequest] = useState<SubmittedRequest | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Read initial page from sessionStorage (set by landing page CTA)
  useEffect(() => {
    const initial = sessionStorage.getItem('indivalidate_initial_page') as PageId | null;
    if (initial) {
      setActivePage(initial);
      sessionStorage.removeItem('indivalidate_initial_page');
    }
  }, []);

  useEffect(() => {
    let isMounted = true;

    const verifyHealth = async () => {
      try {
        await checkBackendHealth();
        if (isMounted) setIsBackendOnline(true);
      } catch {
        if (isMounted) setIsBackendOnline(false);
      }
    };

    verifyHealth();
    const interval = setInterval(verifyHealth, 15000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleStartAnalysis = async (request: AnalyzeRequest) => {
    setActiveIdeaText(request.idea);
    setIsAnalysisRunning(true);
    setErrorMessage(null);
    // Clear any previous inline result so stale data is never shown for new idea
    setLastAnalysisResult(null);
    setLastSubmittedRequest(null);
    setActivePage('progress');

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const newReport = await analyzeMarketIdea(request, controller.signal);
      setReport(newReport);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(newReport));
      } catch {
        // localStorage quota full or disabled
      }
      // Track in historical runs
      const issues = (newReport.diagnostics?.issues as unknown[]) || [];
      const runRecord = createRunRecordFromReport(
        newReport,
        issues.length > 0 ? 'completed_with_failures' : 'completed'
      );
      setHistory((prev) => {
        const filtered = prev.filter((item) => item.id !== runRecord.id);
        const updated = [runRecord, ...filtered].slice(0, 20);
        try {
          localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(updated));
        } catch {
          // Ignored
        }
        return updated;
      });

      setIsAnalysisRunning(false);
      // Extract geography from founder_context if provided
      const geo = request.founder_context?.launch_geography ?? null;
      setLastSubmittedRequest({ idea: request.idea, geography: geo });
      setLastAnalysisResult(newReport);
      // Stay on new-analysis so the user can see inline results
      setActivePage('new-analysis');
    } catch (err: unknown) {
      setIsAnalysisRunning(false);
      const msg = err instanceof Error ? err.message : 'Unknown pipeline error occurred';
      setErrorMessage(msg);

      // Track failed run in history
      const failedRecord: AnalysisRunRecord = {
        id: `MVR-ERR-${Date.now().toString(36).toUpperCase()}`,
        idea: request.idea,
        geography: request.founder_context?.launch_geography ?? null,
        timestamp: new Date().toISOString(),
        status: 'failed',
        evidenceCoverageRatio: -1,
        supportedFindingsCount: 0,
        totalFindingsCount: 0,
        report: null,
      };
      setHistory((prev) => {
        const updated = [failedRecord, ...prev].slice(0, 20);
        try {
          localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(updated));
        } catch {
          // Ignored
        }
        return updated;
      });

      // Return to new-analysis so error is shown with retained idea
      setActivePage('new-analysis');
    } finally {
      abortControllerRef.current = null;
    }
  };

  const handleCancelAnalysis = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsAnalysisRunning(false);
    setErrorMessage('Analysis was cancelled by the user.');
  };

  const handleQuickStart = (idea: string) => {
    handleStartAnalysis({ idea, persona_count: 10, evaluation_concurrency: 3 });
  };

  const handleLoadSample = () => {
    setReport(SAMPLE_MARKET_REPORT);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(SAMPLE_MARKET_REPORT));
    } catch {
      // Ignored
    }
    const sampleRecord = createRunRecordFromReport(SAMPLE_MARKET_REPORT, 'completed');
    setHistory((prev) => {
      const filtered = prev.filter((item) => item.id !== sampleRecord.id);
      const updated = [sampleRecord, ...filtered].slice(0, 20);
      try {
        localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(updated));
      } catch {
        // Ignored
      }
      return updated;
    });
    setErrorMessage(null);
    setActivePage('overview');
  };

  const handleSelectReport = (selectedReport: MarketValidationReport) => {
    setReport(selectedReport);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(selectedReport));
    } catch {
      // Ignored
    }
    setActivePage('reports');
  };

  return (
    <div className="dash-root min-h-screen bg-[#0D1012] flex flex-col lg:flex-row antialiased text-[#F5F5F5] print:min-h-0 print:bg-white print:block print:text-slate-900">
      {/* Persistent Left Sidebar */}
      <Sidebar
        activePage={activePage}
        onSelectPage={setActivePage}
        isBackendOnline={isBackendOnline}
        isAnalysisRunning={isAnalysisRunning}
        isOpenMobile={isOpenMobile}
        onToggleMobile={() => setIsOpenMobile(!isOpenMobile)}
      />

      {/* Main Content Area */}
      <div className="flex-1 lg:pl-64 flex flex-col min-w-0 bg-[#0D1012] print:pl-0 print:bg-white print:block">
        <Header
          activePage={activePage}
          onNavigate={setActivePage}
          report={report}
          onLoadSample={handleLoadSample}
          onToggleMobile={() => setIsOpenMobile(!isOpenMobile)}
          isBackendOnline={isBackendOnline}
        />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto bg-[#0D1012] print:p-0 print:max-w-none print:w-full print:bg-white">
          {activePage === 'overview' && (
            <OverviewPage
              report={report}
              onNavigate={setActivePage}
              onQuickStart={handleQuickStart}
              onLoadSample={handleLoadSample}
              isAnalysisRunning={isAnalysisRunning}
              activeIdeaText={activeIdeaText}
              errorMessage={errorMessage}
              history={history}
              onSelectReport={handleSelectReport}
            />
          )}

          {activePage === 'new-analysis' && (
            <NewAnalysisPage
              onSubmit={handleStartAnalysis}
              isLoading={isAnalysisRunning}
              errorMessage={errorMessage}
              onClearError={() => setErrorMessage(null)}
              lastResult={lastAnalysisResult}
              lastSubmittedIdea={lastSubmittedRequest?.idea ?? null}
              lastSubmittedGeography={lastSubmittedRequest?.geography ?? null}
              onViewFullReport={setActivePage}
              onClearResult={() => {
                setLastAnalysisResult(null);
                setLastSubmittedRequest(null);
              }}
            />
          )}

          {activePage === 'progress' && (
            <AnalysisProgressPage
              isRunning={isAnalysisRunning}
              ideaText={activeIdeaText}
              errorMessage={errorMessage}
              onCancel={handleCancelAnalysis}
              onRetry={() => {
                if (activeIdeaText) {
                  handleStartAnalysis({ idea: activeIdeaText });
                } else {
                  setActivePage('new-analysis');
                }
              }}
              onNavigate={setActivePage}
            />
          )}

          {activePage === 'personas' && (
            <PersonasPage
              report={report}
              onNavigateToNew={() => setActivePage('new-analysis')}
              selectedPersona={activeModalPersona}
              onSelectPersona={(persona) => setActiveModalPersona(persona)}
            />
          )}

          {activePage === 'market-insights' && (
            <MarketInsightsPage
              report={report}
              onNavigateToNew={() => setActivePage('new-analysis')}
            />
          )}

          {activePage === 'reports' && (
            <ReportsPage
              report={report}
              onNavigateToNew={() => setActivePage('new-analysis')}
              onLoadSample={handleLoadSample}
            />
          )}
        </main>
      </div>

      {/* Global Persona Detail Modal */}
      {activeModalPersona && (
        <PersonaDetailModal
          persona={activeModalPersona}
          onClose={() => setActiveModalPersona(null)}
        />
      )}
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <Routes>
      {/* Public landing page */}
      <Route path="/" element={<LandingPage />} />

      {/* Application dashboard — all sub-pages handled internally via state */}
      <Route path="/app" element={<DashboardShell />} />
      <Route path="/app/*" element={<DashboardShell />} />

      {/* Fallback redirect */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export default App;
