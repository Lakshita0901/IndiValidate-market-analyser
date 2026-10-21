import React from 'react';
import {
  LayoutDashboard,
  PlusCircle,
  Activity,
  Users,
  LineChart,
  FileText,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  X,
  Compass
} from 'lucide-react';
import { PageId } from '../types';

interface SidebarProps {
  activePage: PageId;
  onSelectPage: (page: PageId) => void;
  isBackendOnline: boolean | null;
  isAnalysisRunning: boolean;
  isOpenMobile: boolean;
  onToggleMobile: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activePage,
  onSelectPage,
  isBackendOnline,
  isAnalysisRunning,
  isOpenMobile,
  onToggleMobile,
}) => {
  const navItems: { id: PageId; label: string; icon: React.ReactNode; badge?: string }[] = [
    { id: 'overview', label: 'Overview', icon: <LayoutDashboard className="w-5 h-5" /> },
    { id: 'new-analysis', label: 'New Analysis', icon: <PlusCircle className="w-5 h-5" /> },
    {
      id: 'progress',
      label: 'Live Progress',
      icon: <Activity className={`w-5 h-5 ${isAnalysisRunning ? 'animate-pulse text-[#F43F4F]' : ''}`} />,
      badge: isAnalysisRunning ? 'Running' : undefined,
    },
    { id: 'personas', label: 'Personas & Segments', icon: <Users className="w-5 h-5" /> },
    { id: 'market-insights', label: 'Market Insights', icon: <LineChart className="w-5 h-5" /> },
    { id: 'reports', label: 'Full Report & Export', icon: <FileText className="w-5 h-5" /> },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpenMobile && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden backdrop-blur-sm"
          onClick={onToggleMobile}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 bg-[#101316] border-r border-[#2B3138] flex flex-col transition-transform duration-200 ease-in-out lg:translate-x-0 ${
          isOpenMobile ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand Header */}
        <div className="h-16 px-5 border-b border-[#2B3138] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-[#F43F4F] text-white flex items-center justify-center font-bold text-lg shadow-md">
              <Compass className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="font-bold text-[#F5F5F5] tracking-tight text-base block leading-tight">
                IndiValidate
              </span>
              <span className="text-[11px] font-semibold text-[#F43F4F] uppercase tracking-wider block">
                Market Analyzer
              </span>
            </div>
          </div>
          <button
            onClick={onToggleMobile}
            className="lg:hidden p-1.5 text-[#7E8995] hover:text-[#F5F5F5] rounded-md transition-colors"
            aria-label="Close sidebar"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          <div className="px-3 pb-2 text-[11px] font-bold text-[#7E8995] uppercase tracking-wider">
            Platform Navigation
          </div>
          {navItems.map((item) => {
            const isActive = activePage === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  onSelectPage(item.id);
                  if (isOpenMobile) onToggleMobile();
                }}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-[rgba(244,63,79,0.12)] text-[#F43F4F] font-semibold border border-[rgba(244,63,79,0.2)]'
                    : 'text-[#A0AAB5] hover:bg-[#1D2228] hover:text-[#F5F5F5] border border-transparent'
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className={isActive ? 'text-[#F43F4F]' : 'text-[#7E8995]'}>
                    {item.icon}
                  </span>
                  <span>{item.label}</span>
                </div>
                {isActive && (
                  <span className="w-1.5 h-1.5 rounded-full bg-[#F43F4F]" />
                )}
                {item.badge && !isActive && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-[rgba(244,63,79,0.15)] text-[#F43F4F] animate-pulse">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Epistemic Rule Reminder */}
        <div className="p-3.5 mx-3 mb-3 bg-[#171B20] rounded-xl border border-[#2B3138] text-xs text-[#7E8995]">
          <div className="flex items-start gap-1.5 font-bold text-[#A0AAB5] mb-1">
            <HelpCircle className="w-3.5 h-3.5 text-[#F43F4F] shrink-0 mt-0.5" />
            <span>Epistemic Guardrails</span>
          </div>
          <p className="text-[11px] leading-relaxed text-[#7E8995]">
            Personas are synthetic simulation archetypes. Model reasoning is strictly separated from empirical government and community evidence.
          </p>
        </div>

        {/* Backend API Connection Status Footer */}
        <div className="p-3.5 border-t border-[#2B3138] bg-[#101316]">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              {isBackendOnline === true ? (
                <CheckCircle2 className="w-4 h-4 text-[#42C985]" />
              ) : isBackendOnline === false ? (
                <AlertCircle className="w-4 h-4 text-[#F43F4F]" />
              ) : (
                <div className="w-2 h-2 rounded-full bg-[#F4B942] animate-ping" />
              )}
              <span className="font-semibold text-[#A0AAB5]">FastAPI Backend</span>
            </div>
            <span
              className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${
                isBackendOnline === true
                  ? 'bg-[rgba(66,201,133,0.1)] text-[#42C985] border-[rgba(66,201,133,0.25)]'
                  : isBackendOnline === false
                  ? 'bg-[rgba(244,63,79,0.1)] text-[#F43F4F] border-[rgba(244,63,79,0.25)]'
                  : 'bg-[rgba(244,185,66,0.1)] text-[#F4B942] border-[rgba(244,185,66,0.25)]'
              }`}
            >
              {isBackendOnline === true
                ? 'Online: 8000'
                : isBackendOnline === false
                ? 'Offline'
                : 'Checking'}
            </span>
          </div>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;

