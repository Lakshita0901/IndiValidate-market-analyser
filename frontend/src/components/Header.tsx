import React from 'react';
import { Menu, PlusCircle, Sparkles, Download, FileCode, Check } from 'lucide-react';
import { MarketValidationReport, PageId } from '../types';
import { downloadFile, generateReportMarkdown } from '../utils/markdownExporter';

interface HeaderProps {
  activePage: PageId;
  onNavigate: (page: PageId) => void;
  report: MarketValidationReport | null;
  onLoadSample: () => void;
  onToggleMobile: () => void;
  isBackendOnline: boolean | null;
}

export const Header: React.FC<HeaderProps> = ({
  activePage,
  onNavigate,
  report,
  onLoadSample,
  onToggleMobile,
}) => {
  const [copied, setCopied] = React.useState(false);

  const pageTitles: Record<PageId, { title: string; subtitle: string }> = {
    overview: {
      title: 'Validation Dashboard',
      subtitle: 'Multi-persona market demand and empirical risk analysis',
    },
    'new-analysis': {
      title: 'Run New Market Validation',
      subtitle: 'Configure target proposal, optional founder intake, and bounded multi-agent evaluation',
    },
    progress: {
      title: 'Execution & Pipeline Telemetry',
      subtitle: 'Real-time multi-stage validation graph execution monitor',
    },
    personas: {
      title: 'Simulated Personas & Segments',
      subtitle: 'Calibrated synthetic customer archetypes and segment evaluations',
    },
    'market-insights': {
      title: 'Market Insights & Evidence Audit',
      subtitle: 'Empirical coverage, feature prioritization, risks, and research question grounding',
    },
    reports: {
      title: 'Full Market Report & Export',
      subtitle: 'Audit-ready validation report with empirical citations and research questions analysis',
    },
  };

  const current = pageTitles[activePage] || { title: 'Dashboard', subtitle: '' };

  const handleDownloadMarkdown = () => {
    if (!report) return;
    const md = generateReportMarkdown(report);
    downloadFile(md, `${report.report_id || 'validation_report'}.md`, 'text/markdown');
  };

  const handleDownloadJSON = () => {
    if (!report) return;
    const jsonStr = JSON.stringify(report, null, 2);
    downloadFile(jsonStr, `${report.report_id || 'validation_report'}.json`, 'application/json');
  };

  const handleCopyMarkdown = () => {
    if (!report) return;
    const md = generateReportMarkdown(report);
    navigator.clipboard.writeText(md).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <header className="h-16 bg-[#101316] border-b border-[#2B3138] px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30 shadow-lg print:hidden">
      {/* Left: Mobile Toggle & Page Info */}
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleMobile}
          className="lg:hidden p-2 text-[#7E8995] hover:text-[#F5F5F5] hover:bg-[#1D2228] rounded-xl transition-colors"
          aria-label="Open sidebar"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-base sm:text-lg font-bold text-[#F5F5F5] leading-tight">
            {current.title}
          </h1>
          <p className="text-xs text-[#7E8995] hidden sm:block">
            {current.subtitle}
          </p>
        </div>
      </div>

      {/* Right: Quick Actions */}
      <div className="flex items-center gap-2 sm:gap-2.5">
        {report && (
          <div className="hidden md:flex items-center gap-1.5 border border-[#2B3138] bg-[#1D2228] px-3 py-1 rounded-lg text-xs font-medium text-[#A0AAB5]">
            <span className="w-2 h-2 rounded-full bg-[#F43F4F]" />
            <span className="truncate max-w-[200px]">
              {report.idea_and_context?.business_idea || report.report_id}
            </span>
          </div>
        )}

        {report && (
          <div className="flex items-center gap-1.5">
            <button
              onClick={handleCopyMarkdown}
              title="Copy Markdown Report to clipboard"
              className="p-1.5 sm:px-2.5 sm:py-1.5 border border-[#2B3138] hover:bg-[#1D2228] text-[#7E8995] hover:text-[#F5F5F5] rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-[#42C985]" /> : <FileCode className="w-3.5 h-3.5" />}
              <span className="hidden sm:inline">{copied ? 'Copied' : 'Copy MD'}</span>
            </button>
            <button
              onClick={handleDownloadMarkdown}
              title="Download Markdown Report"
              className="p-1.5 sm:px-2.5 sm:py-1.5 border border-[#2B3138] hover:bg-[#1D2228] text-[#7E8995] hover:text-[#F5F5F5] rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Export</span>
            </button>
          </div>
        )}

        <button
          onClick={onLoadSample}
          title="Load demonstration report from local sample data"
          className="px-3 py-1.5 bg-[rgba(244,63,79,0.1)] hover:bg-[rgba(244,63,79,0.18)] text-[#F43F4F] border border-[rgba(244,63,79,0.25)] rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors"
        >
          <Sparkles className="w-3.5 h-3.5 text-[#F43F4F]" />
          <span className="hidden sm:inline">Load Sample</span>
        </button>

        {activePage !== 'new-analysis' && (
          <button
            onClick={() => onNavigate('new-analysis')}
            className="px-3.5 py-1.5 bg-[#F43F4F] hover:bg-[#e83545] text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-md transition-colors"
          >
            <PlusCircle className="w-3.5 h-3.5 text-white" />
            <span>New Analysis</span>
          </button>
        )}
      </div>
    </header>
  );
};

export default Header;
