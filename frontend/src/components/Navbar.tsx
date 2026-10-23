import React from 'react';
import { Radio, ShieldAlert, Film, Globe2, RefreshCw, PlusCircle, ExternalLink, ChevronDown, Trash2 } from 'lucide-react';
import { Project } from '../types';

export type ActiveTab = 'radar' | 'india' | 'warroom' | 'studio' | 'sources';

interface NavbarProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
  isScanning: boolean;
  onScan: () => void;
  projects: Project[];
  activeProject: Project | null;
  onSelectProject: (projectId: string) => void;
  onNewProject: () => void;
  onDeleteProject: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  onTabChange,
  isScanning,
  onScan,
  projects,
  activeProject,
  onSelectProject,
  onNewProject,
  onDeleteProject,
}) => {
  return (
    <header className="sticky top-0 z-40 bg-[#070B12]/90 backdrop-blur-md border-b border-slate-800/80 px-4 sm:px-6 py-2.5">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
        {/* Brand & Live Telemetry */}
        <div className="flex items-center gap-3.5 shrink-0">
          <div className="relative flex items-center justify-center w-9 h-9 rounded-lg bg-cyan-950/60 border border-cyan-500/40 text-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.15)]">
            <Radio className="w-5 h-5 animate-pulse" />
            <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-emerald-500 ring-2 ring-[#070B12] animate-ping" />
            <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-emerald-500 ring-2 ring-[#070B12]" />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="font-display font-bold tracking-wider text-sm sm:text-base text-white">
                GLOBAL PULSE
              </span>
              <span className="text-[10px] uppercase tracking-widest font-mono px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                STUDIO OS
              </span>
            </div>
            <p className="text-[11px] text-slate-400 hidden md:block">
              Geopolitical Intelligence & Documentary Essay Platform
            </p>
          </div>
        </div>

        {/* Tactical Nav Tabs */}
        <nav className="flex items-center p-1 bg-slate-900/80 rounded-xl border border-slate-800/80 text-xs font-mono">
          <button
            onClick={() => onTabChange('radar')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'radar'
                ? 'bg-cyan-500/20 text-cyan-300 font-semibold border border-cyan-500/30 shadow-[0_0_10px_rgba(6,182,212,0.1)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Radio className="w-3.5 h-3.5" />
            <span>Radar</span>
          </button>

          <button
            onClick={() => onTabChange('india')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'india'
                ? 'bg-orange-500/20 text-orange-300 font-semibold border border-orange-500/30 shadow-[0_0_10px_rgba(249,115,22,0.2)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <span className="flex items-center gap-0.5" title="India Strategic Affairs Desk">
              <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
              <span className="w-1.5 h-1.5 rounded-full bg-white" />
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            </span>
            <span>India Desk</span>
          </button>

          <button
            onClick={() => onTabChange('warroom')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'warroom'
                ? 'bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/30 shadow-[0_0_10px_rgba(245,158,11,0.1)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>War Room</span>
            {activeProject && (
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            )}
          </button>

          <button
            onClick={() => onTabChange('studio')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'studio'
                ? 'bg-purple-500/20 text-purple-300 font-semibold border border-purple-500/30 shadow-[0_0_10px_rgba(168,85,247,0.1)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Film className="w-3.5 h-3.5" />
            <span>Story Studio</span>
          </button>

          <button
            onClick={() => onTabChange('sources')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'sources'
                ? 'bg-emerald-500/20 text-emerald-300 font-semibold border border-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.1)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Globe2 className="w-3.5 h-3.5" />
            <span>Feeds</span>
          </button>
        </nav>

        {/* Project Selector & Actions */}
        <div className="flex items-center gap-2.5">
          {/* Active Project Dropdown */}
          <div className="relative hidden lg:flex items-center">
            <select
              value={activeProject?.id || ''}
              onChange={(e) => {
                if (e.target.value === '__new__') {
                  onNewProject();
                } else if (e.target.value) {
                  onSelectProject(e.target.value);
                }
              }}
              className="appearance-none bg-slate-900 border border-slate-700/70 text-slate-200 text-xs font-mono rounded-lg pl-3 pr-8 py-1.5 focus:outline-none focus:border-cyan-500 cursor-pointer max-w-[200px] truncate"
            >
              <option value="" disabled>Select Research Project...</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title}
                </option>
              ))}
              <option value="__new__">+ New Project...</option>
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 pointer-events-none" />
          </div>

          {activeProject && (
            <button
              onClick={onDeleteProject}
              className="hidden lg:flex p-1.5 text-slate-400 hover:text-rose-400 transition"
              title="Delete active project"
              aria-label="Delete active project"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}

          {/* Scan Feeds Button */}
          <button
            onClick={onScan}
            disabled={isScanning}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all shadow-sm ${
              isScanning
                ? 'bg-slate-800 text-slate-400 cursor-not-allowed border border-slate-700'
                : 'bg-emerald-600 hover:bg-emerald-500 text-white border border-emerald-500/40 shadow-[0_0_12px_rgba(16,185,129,0.25)] active:scale-95'
            }`}
            title="Crawl all active feeds and recluster events"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
            <span>{isScanning ? 'Crawling...' : 'Scan Feeds'}</span>
          </button>

          {/* New Project Quick Button */}
          <button
            onClick={onNewProject}
            className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono bg-slate-800/80 hover:bg-slate-700/80 text-slate-200 border border-slate-700/70 transition"
            title="Create blank research project"
          >
            <PlusCircle className="w-3.5 h-3.5 text-cyan-400" />
            <span>New Brief</span>
          </button>

          {/* API Docs Link */}
          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="p-1.5 text-slate-400 hover:text-cyan-400 transition"
            title="Swagger API Documentation"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </div>
    </header>
  );
};
