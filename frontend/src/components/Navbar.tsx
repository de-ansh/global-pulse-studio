import React from 'react';
import { Radio, RefreshCw, Plus, ChevronDown, Trash2, Settings } from 'lucide-react';
import { Project } from '../types';

// Internal ids are kept stable so existing #/warroom/... links keep working; labels follow the 3-step flow.
export type ActiveTab = 'radar' | 'warroom' | 'studio' | 'sources';

const STEPS: { tab: ActiveTab; label: string; needsProject: boolean }[] = [
  { tab: 'radar', label: 'Discover', needsProject: false },
  { tab: 'warroom', label: 'Research', needsProject: true },
  { tab: 'studio', label: 'Script', needsProject: true },
];

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
}) => (
  <header className="sticky top-0 z-40 bg-[#070B12]/90 backdrop-blur-md border-b border-slate-800/80 px-4 sm:px-6 py-2.5">
    <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-2.5 shrink-0">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-cyan-950/60 border border-cyan-500/40 text-cyan-400">
          <Radio className="w-4 h-4" />
        </div>
        <span className="font-display font-bold tracking-wide text-sm sm:text-base text-white">Global Pulse</span>
      </div>

      <nav aria-label="Workflow steps" className="flex items-center p-1 bg-slate-900/80 rounded-xl border border-slate-800/80 text-xs">
        {STEPS.map(({ tab, label, needsProject }, i) => {
          const active = activeTab === tab;
          const locked = needsProject && !activeProject;
          return (
            <button
              key={tab}
              onClick={() => onTabChange(tab)}
              aria-current={active ? 'step' : undefined}
              title={locked ? 'Pick a story on Discover first' : undefined}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition ${
                active ? 'bg-cyan-500/20 text-cyan-200 font-semibold' : locked ? 'text-slate-600' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span
                className={`flex items-center justify-center w-4 h-4 rounded-full text-[10px] font-bold ${
                  active ? 'bg-cyan-400 text-slate-950' : 'bg-slate-800 text-slate-400'
                }`}
              >
                {i + 1}
              </span>
              <span>{label}</span>
            </button>
          );
        })}
      </nav>

      <div className="flex items-center gap-2">
        <div className="relative hidden md:flex items-center">
          <label htmlFor="project-picker" className="sr-only">Current project</label>
          <select
            id="project-picker"
            value={activeProject?.id || ''}
            onChange={(e) => e.target.value && onSelectProject(e.target.value)}
            className="appearance-none bg-slate-900 border border-slate-700/70 text-slate-200 text-xs rounded-lg pl-3 pr-8 py-1.5 focus:outline-none focus:border-cyan-500 cursor-pointer max-w-[220px] truncate"
          >
            <option value="" disabled>No project yet</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.title}</option>
            ))}
          </select>
          <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 pointer-events-none" />
        </div>
        {activeProject && (
          <button
            onClick={onDeleteProject}
            className="hidden md:flex p-1.5 text-slate-500 hover:text-rose-400 transition"
            title="Delete this project"
            aria-label="Delete this project"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
        <button
          onClick={onNewProject}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
          title="Start a project on any topic"
        >
          <Plus className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">New project</span>
        </button>
        <button
          onClick={onScan}
          disabled={isScanning}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white transition disabled:bg-slate-800 disabled:text-slate-400"
          title="Fetch the latest news from all feeds"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
          <span>{isScanning ? 'Fetching...' : 'Fetch news'}</span>
        </button>
        <button
          onClick={() => onTabChange('sources')}
          aria-current={activeTab === 'sources' ? 'page' : undefined}
          className={`p-1.5 rounded-lg transition ${activeTab === 'sources' ? 'text-cyan-300 bg-slate-800' : 'text-slate-400 hover:text-slate-200'}`}
          title="News feeds & settings"
          aria-label="News feeds & settings"
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </div>
  </header>
);
