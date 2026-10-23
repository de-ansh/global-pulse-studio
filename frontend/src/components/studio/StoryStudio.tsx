import React, { useState, useEffect } from 'react';
import { Project, NarrativeAngleOption, ScriptOutline } from '../../types';
import { api } from '../../api/client';
import { ExportModal } from './ExportModal';
import { ScriptPanel } from './ScriptPanel';
import {
  Film,
  Sparkles,
  RefreshCw,
  FileDown,
  CheckCircle2,
  Video,
  HelpCircle,
  Clock,
  Compass,
  ArrowRight,
  FolderOpen
} from 'lucide-react';

interface StoryStudioProps {
  project: Project | null;
  onRefreshOutline: () => void;
  isGeneratingOutline: boolean;
  onSelectAngle: (angleTitle: string) => void;
  onSwitchToRadar: () => void;
}

export const StoryStudio: React.FC<StoryStudioProps> = ({
  project,
  onRefreshOutline,
  isGeneratingOutline,
  onSelectAngle,
  onSwitchToRadar,
}) => {
  const [angles, setAngles] = useState<NarrativeAngleOption[]>([]);
  const [loadingAngles, setLoadingAngles] = useState(false);
  const [exportMarkdown, setExportMarkdown] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    if (!project) {
      setAngles([]);
      return;
    }

    setLoadingAngles(true);
    api
      .getProjectAngles(project.id)
      .then((data) => setAngles(data))
      .catch((err) => console.error('Failed to load narrative angles:', err))
      .finally(() => setLoadingAngles(false));
  }, [project?.id]);

  if (!project) {
    return (
      <div className="p-12 text-center rounded-2xl bg-slate-900/40 border border-dashed border-slate-800 space-y-4 max-w-xl mx-auto my-12">
        <div className="w-12 h-12 rounded-full bg-purple-950/40 border border-purple-800/40 flex items-center justify-center mx-auto text-purple-400">
          <FolderOpen className="w-6 h-6" />
        </div>
        <div>
          <h3 className="font-display font-semibold text-lg text-slate-200">
            No Active Project Selected
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Choose an ongoing project from the navigation header, or discover an emerging crisis from the Event Radar.
          </p>
        </div>
        <button
          onClick={onSwitchToRadar}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-mono font-semibold bg-cyan-600 hover:bg-cyan-500 text-white shadow-lg transition"
        >
          <span>Open Event Radar</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    );
  }

  const outline: ScriptOutline | undefined = project.script_outline || undefined;

  const handleExport = async () => {
    setIsExporting(true);
    setExportError(null);
    try {
      const md = await api.exportMarkdown(project.id);
      setExportMarkdown(md);
    } catch (err) {
      console.error('Export failed:', err);
      setExportError(`Export failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-8">
      {exportError && (
        <div role="alert" className="p-3 rounded-xl bg-rose-950/80 border border-rose-800/80 text-rose-300 font-mono text-xs">
          {exportError}
        </div>
      )}

      {/* Studio Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm shadow-xl">
        <div>
          <div className="flex items-center gap-2 font-mono text-xs mb-1">
            <span className="px-2 py-0.5 rounded bg-purple-950/60 text-purple-300 border border-purple-800/40 font-semibold uppercase">
              {project.status}
            </span>
            <span className="text-slate-400">Target Duration: {project.target_duration_mins} mins</span>
          </div>
          <h2 className="font-display font-bold text-xl sm:text-2xl text-white">
            {project.title}
          </h2>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onRefreshOutline}
            disabled={isGeneratingOutline}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-mono font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isGeneratingOutline ? 'animate-spin' : ''}`} />
            <span>{isGeneratingOutline ? 'Generating...' : 'Re-synthesize 5 Acts'}</span>
          </button>

          <button
            onClick={handleExport}
            disabled={isExporting}
            className="flex items-center gap-2 px-4 py-1.5 rounded-xl text-xs font-mono font-semibold bg-cyan-600 hover:bg-cyan-500 text-white shadow-lg transition active:scale-95"
          >
            <FileDown className="w-3.5 h-3.5" />
            <span>{isExporting ? 'Exporting...' : 'Export Markdown'}</span>
          </button>
        </div>
      </div>

      {/* 4 Narrative Angle Synthesis Cards */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-purple-400" />
            <h3 className="font-display font-bold text-lg text-white">
              Narrative Angle Synthesis
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-400">
            Select a geopolitical lens to anchor documentary pacing
          </span>
        </div>
        <p className="text-[11px] font-mono text-amber-300/80">
          Template framings filled with the actors and chokepoints detected in coverage. They are writing prompts, not
          analysis of the reporting; verify every claim in the Claim Ledger before scripting.
        </p>

        {loadingAngles ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-44 rounded-2xl bg-slate-900/40 border border-slate-800 animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {angles.map((angle) => {
              const isSelected = project.selected_angle === angle.title;
              return (
                <div
                  key={angle.id}
                  onClick={() => onSelectAngle(angle.title)}
                  className={`relative p-4 rounded-2xl border transition-all duration-300 cursor-pointer flex flex-col justify-between ${
                    isSelected
                      ? 'bg-purple-950/40 border-purple-500/80 ring-1 ring-purple-500/50 shadow-[0_0_20px_rgba(168,85,247,0.15)]'
                      : 'bg-slate-900/60 border-slate-800/80 hover:border-slate-700/80 hover:bg-slate-900/90'
                  }`}
                >
                  {isSelected && (
                    <span className="absolute top-3 right-3 flex items-center gap-1 font-mono text-[10px] text-purple-300 font-semibold">
                      <CheckCircle2 className="w-3.5 h-3.5 text-purple-400" />
                      Active Lens
                    </span>
                  )}

                  <div>
                    <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400 block mb-1">
                      {angle.tone}
                    </span>
                    <h4 className="font-display font-bold text-sm sm:text-base text-white mb-2 leading-snug">
                      {angle.title}
                    </h4>
                    <p className="text-xs text-slate-300 line-clamp-3 leading-relaxed">
                      {angle.premise}
                    </p>
                  </div>

                  <div className="mt-3 pt-2.5 border-t border-slate-800/80 text-[11px] font-mono text-slate-400">
                    <span className="text-purple-400 font-semibold block text-[10px] uppercase mb-0.5">
                      Core Dramatic Tension:
                    </span>
                    <span className="line-clamp-2 text-slate-300">{angle.key_tension}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 5-Act Documentary Essay Structure */}
      {!outline ? (
        <div className="p-12 text-center rounded-2xl bg-slate-900/30 border border-dashed border-slate-800 space-y-4">
          <div className="w-12 h-12 rounded-full bg-slate-800/80 flex items-center justify-center mx-auto text-slate-500">
            <Film className="w-6 h-6" />
          </div>
          <div>
            <h4 className="font-display font-semibold text-base text-slate-300">
              5-Act Documentary Script Outline Not Generated Yet
            </h4>
            <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
              Select an angle and click &quot;Generate 5 Acts&quot; to synthesize act timecodes, inquiry questions, and B-roll/3D graphics visual prompts.
            </p>
          </div>
          <button
            onClick={onRefreshOutline}
            disabled={isGeneratingOutline}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-mono font-semibold bg-purple-600 hover:bg-purple-500 text-white shadow-lg transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isGeneratingOutline ? 'animate-spin' : ''}`} />
            <span>Generate 5 Acts Now</span>
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Hook Variants Carousel / Bar */}
          {outline.hook_variants && outline.hook_variants.length > 0 && (
            <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-3">
              <h4 className="font-display font-bold text-base text-white flex items-center gap-2">
                <Video className="w-4 h-4 text-cyan-400" />
                <span>Cold Open & Hook Variants (First 30 Seconds)</span>
              </h4>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {outline.hook_variants.map((hook, i) => (
                  <div key={i} className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
                    <span className="px-2 py-0.5 rounded bg-cyan-950/70 text-cyan-300 border border-cyan-800/40 text-[10px] font-mono uppercase font-semibold">
                      {hook.label}
                    </span>
                    <p className="text-xs text-slate-200 italic leading-relaxed font-serif">
                      &ldquo;{hook.narration}&rdquo;
                    </p>
                    <div className="text-[11px] font-mono text-slate-400 flex items-start gap-1.5 pt-1 border-t border-slate-900">
                      <span className="text-cyan-400 font-semibold shrink-0">Visual:</span>
                      <span>{hook.visual_cue}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Acts List */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-display font-bold text-lg text-white flex items-center gap-2">
                <Film className="w-4 h-4 text-purple-400" />
                <span>5-Act Documentary Essay Architecture</span>
              </h4>
              <span className="text-xs font-mono text-slate-400">
                Pacing calibrated for {project.target_duration_mins} minute runtime
              </span>
            </div>

            <div className="space-y-4">
              {outline.acts.map((act) => (
                <div
                  key={act.act_number}
                  className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 hover:border-slate-700/80 transition space-y-4"
                >
                  {/* Act Header */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-800">
                    <div className="flex items-center gap-3">
                      <span className="w-7 h-7 rounded-lg bg-purple-950/80 border border-purple-700/60 text-purple-300 font-mono font-bold text-xs flex items-center justify-center shrink-0">
                        {act.act_number}
                      </span>
                      <h5 className="font-display font-bold text-base sm:text-lg text-white">
                        {act.title}
                      </h5>
                    </div>

                    <div className="flex items-center gap-2 font-mono text-xs text-cyan-400">
                      <Clock className="w-3.5 h-3.5" />
                      <span>{act.target_timestamp}</span>
                    </div>
                  </div>

                  {/* Narration Lead */}
                  <div className="text-xs sm:text-sm text-slate-300 font-sans leading-relaxed">
                    <span className="font-mono text-[11px] uppercase tracking-wider text-slate-400 block mb-1">
                      Narration Spine:
                    </span>
                    {act.narration_lead}
                  </div>

                  {/* Questions & Visual Cues Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-xs">
                    {/* Inquiry Questions */}
                    <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800/80 space-y-2">
                      <span className="text-[10px] text-amber-400 uppercase tracking-wider font-semibold flex items-center gap-1.5">
                        <HelpCircle className="w-3.5 h-3.5" />
                        <span>Core Viewer Questions</span>
                      </span>
                      <ul className="space-y-1.5 text-slate-300">
                        {act.key_questions.map((q, idx) => (
                          <li key={idx} className="flex items-start gap-1.5 leading-relaxed">
                            <span className="text-amber-500">•</span>
                            <span>{q}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Visual & Map Cues */}
                    <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800/80 space-y-2">
                      <span className="text-[10px] text-cyan-400 uppercase tracking-wider font-semibold flex items-center gap-1.5">
                        <Compass className="w-3.5 h-3.5" />
                        <span>Visual B-Roll & 3D Graphics Prompts</span>
                      </span>
                      <ul className="space-y-1.5 text-slate-300">
                        {act.visual_cues.map((v, idx) => (
                          <li key={idx} className="flex items-start gap-1.5 leading-relaxed">
                            <span className="text-cyan-500">•</span>
                            <span>{v}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Cited narration script (Gemini) */}
      <ScriptPanel projectId={project.id} />

      {/* Export Markdown Modal */}
      <ExportModal
        markdown={exportMarkdown}
        projectTitle={project.title}
        onClose={() => setExportMarkdown(null)}
      />
    </div>
  );
};
