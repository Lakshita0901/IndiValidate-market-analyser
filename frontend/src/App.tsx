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
import { AnalyzeRequest, MarketValidationReport, PageId, PersonaProfile } from './types';
import { analyzeMarketIdea, checkBackendHealth } from './services/api';
import { SAMPLE_MARKET_REPORT } from './data/sampleReport';

const STORAGE_KEY = 'indivalidate_active_report';

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

  const [isBackendOnline, setIsBackendOnline] = useState<boolean | null>(null);
  const [isAnalysisRunning, setIsAnalysisRunning] = useState<boolean>(false);
  const [activeIdeaText, setActiveIdeaText] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isOpenMobile, setIsOpenMobile] = useState<boolean>(false);
  const [activeModalPersona, setActiveModalPersona] = useState<PersonaProfile | null>(null);

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
      setIsAnalysisRunning(false);
      setActivePage('overview');
    } catch (err: unknown) {
      setIsAnalysisRunning(false);
      const msg = err instanceof Error ? err.message : 'Unknown pipeline error occurred';
      setErrorMessage(msg);
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
    setErrorMessage(null);
    setActivePage('overview');
  };

  return (
    <div className="dash-root min-h-screen bg-[#0D1012] flex flex-col lg:flex-row antialiased text-[#F5F5F5]">
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
      <div className="flex-1 lg:pl-64 flex flex-col min-w-0 bg-[#0D1012]">
        <Header
          activePage={activePage}
          onNavigate={setActivePage}
          report={report}
          onLoadSample={handleLoadSample}
          onToggleMobile={() => setIsOpenMobile(!isOpenMobile)}
          isBackendOnline={isBackendOnline}
        />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto bg-[#0D1012]">
          {activePage === 'overview' && (
            <OverviewPage
              report={report}
              onNavigate={setActivePage}
              onQuickStart={handleQuickStart}
              onLoadSample={handleLoadSample}
              onSelectPersona={(persona) => setActiveModalPersona(persona)}
            />
          )}

          {activePage === 'new-analysis' && (
            <NewAnalysisPage
              onSubmit={handleStartAnalysis}
              isLoading={isAnalysisRunning}
              errorMessage={errorMessage}
              onClearError={() => setErrorMessage(null)}
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
