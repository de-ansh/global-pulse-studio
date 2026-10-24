import React, { useState } from 'react';
import { Project, Dossier } from '../../types';
import { ClaimLedger } from './ClaimLedger';
import { AI_DISABLED_HINT, useFeatures } from '../../features';
import {
  ShieldAlert,
  Clock,
  MapPin,
  Scale,
  BookOpen,
  RefreshCw,
  ArrowRight,
  ExternalLink,
  Users,
  Compass,
  AlertTriangle,
  FolderOpen
} from 'lucide-react';

interface WarRoomProps {
  project: Project | null;
  onRefreshDossier: () => void;
  isRefreshing: boolean;
  onProceedToStudio: () => void;
  onUpdateDuration: (duration: number) => void;
  onSwitchToRadar: () => void;
  onFindContradictions: () => void;
  isFindingContradictions: boolean;
}

export const WarRoom: React.FC<WarRoomProps> = ({
  project,
  onRefreshDossier,
  isRefreshing,
  onProceedToStudio,
  onUpdateDuration,
  onSwitchToRadar,
  onFindContradictions,
  isFindingContradictions,
}) => {
  const [selectedDuration, setSelectedDuration] = useState<number>(
    project?.target_duration_mins || 18
  );

  const features = useFeatures(); // before the early return: hooks must run on every render

  if (!project) {
    return (
      <div className="p-12 text-center rounded-2xl bg-slate-900/40 border border-dashed border-slate-800 space-y-4 max-w-xl mx-auto my-12">
        <div className="w-12 h-12 rounded-full bg-amber-950/40 border border-amber-800/40 flex items-center justify-center mx-auto text-amber-400">
          <FolderOpen className="w-6 h-6" />
        </div>
        <div>
          <h3 className="font-display font-semibold text-lg text-slate-200">
            No Active Research Workspace Selected
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

  const dossier: Dossier | undefined = project.dossier || undefined;
  const aiVerified = !!dossier?.contradictions.some((c) => c.method === 'ai_verified');

  return (
    <div className="space-y-6">
      {/* Workspace Header & Action Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm shadow-xl">
        <div>
          <div className="flex items-center gap-2 font-mono text-xs mb-1">
            <span className="px-2 py-0.5 rounded bg-amber-950/60 text-amber-300 border border-amber-800/40 font-semibold uppercase">
              {project.status}
            </span>
            <span className="text-slate-400">Step 2 of 3 · Research and verify</span>
          </div>
          <h2 className="font-display font-bold text-xl sm:text-2xl text-white">
            {project.title}
          </h2>
        </div>

        {/* Controls: Target Duration & Dossier Sync */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs font-mono">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400">Video length:</span>
            <select
              value={selectedDuration}
              onChange={(e) => {
                const val = Number(e.target.value);
                setSelectedDuration(val);
                onUpdateDuration(val);
              }}
              className="bg-transparent text-cyan-300 font-bold focus:outline-none cursor-pointer"
            >
              <option value="12" className="bg-slate-900">12 min</option>
              <option value="18" className="bg-slate-900">18 min</option>
              <option value="25" className="bg-slate-900">25 min</option>
              <option value="35" className="bg-slate-900">35 min</option>
            </select>
          </div>

          <button
            onClick={onRefreshDossier}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-mono font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>{isRefreshing ? 'Refreshing...' : 'Refresh research'}</span>
          </button>

          <button
            onClick={onProceedToStudio}
            className="flex items-center gap-2 px-4 py-1.5 rounded-xl text-xs font-mono font-semibold bg-purple-600 hover:bg-purple-500 text-white shadow-lg transition active:scale-95"
          >
            <span>Next: write the script</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Dossier Modules Grid */}
      {!dossier ? (
        <div className="p-12 text-center rounded-2xl bg-slate-900/30 border border-dashed border-slate-800 space-y-4">
          <div className="w-12 h-12 rounded-full bg-slate-800/80 flex items-center justify-center mx-auto text-slate-500">
            <BookOpen className="w-6 h-6" />
          </div>
          <div>
            <h4 className="font-display font-semibold text-base text-slate-300">
              No research yet
            </h4>
            <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
              Build a timeline, stakeholder list and source list from this story&apos;s coverage.
            </p>
          </div>
          <button
            onClick={onRefreshDossier}
            disabled={isRefreshing}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-mono font-semibold bg-amber-600 hover:bg-amber-500 text-white shadow-lg transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>Build research</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Column 1: Escalation Timeline (Spans 2 cols on wide screens) */}
          <div className="lg:col-span-2 space-y-6">
            {/* Timeline */}
            <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80">
              <h3 className="font-display font-bold text-base text-white flex items-center gap-2 mb-4">
                <Clock className="w-4 h-4 text-cyan-400" />
                <span>Timeline</span>
                <span className="text-xs font-mono font-normal text-slate-400 ml-auto">
                  {dossier.timeline_events.length} Milestones
                </span>
              </h3>

              {dossier.timeline_events.length === 0 ? (
                <p className="text-xs font-mono text-slate-500">No timeline entries recorded.</p>
              ) : (
                <div className="relative pl-6 space-y-4 before:content-[''] before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
                  {dossier.timeline_events.map((item, idx) => (
                    <div key={idx} className="relative group">
                      <span className="absolute -left-6 top-1.5 w-2.5 h-2.5 rounded-full bg-cyan-500 ring-4 ring-slate-900" />
                      <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 hover:border-slate-700 transition">
                        <div className="flex items-center gap-2 font-mono text-[10px] text-slate-400 mb-1">
                          <span className="text-cyan-400 font-semibold">{item.date}</span>
                          <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                            {item.source}
                          </span>
                        </div>
                        <h4 className="font-semibold text-xs sm:text-sm text-slate-200">
                          {item.event}
                        </h4>
                        {item.url && (
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-[11px] font-mono text-slate-500 hover:text-cyan-400 mt-2 transition"
                          >
                            <span>Primary wire source</span>
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Contradictions & Narrative Friction Matrix */}
            <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80">
              <h3 className="font-display font-bold text-base text-white flex items-center gap-2 mb-4">
                <Scale className="w-4 h-4 text-amber-400" />
                <span>{aiVerified ? 'Verified Disagreements' : 'Framing Comparison'}</span>
                <button
                  onClick={onFindContradictions}
                  disabled={isFindingContradictions || !features.ai}
                  title={features.ai ? undefined : AI_DISABLED_HINT}
                  className="ml-auto px-2.5 py-1 rounded-lg text-[11px] font-mono font-normal bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition disabled:opacity-50"
                >
                  {isFindingContradictions ? 'Comparing reports...' : aiVerified ? 'Re-compare with AI' : 'Find real disagreements (AI)'}
                </button>
              </h3>
              <p className="text-xs text-slate-400 mb-4">
                {aiVerified
                  ? 'Factual conflicts between reports found by AI. Both quotes were checked word-for-word against each report; read them in context before scripting a conflict.'
                  : 'Headlines on this story from different media ecosystems, paired automatically. These are not verified contradictions. Read both articles before scripting a conflict.'}
              </p>

              <div className="space-y-4">
                {dossier.contradictions.length === 0 && (
                  <p className="p-4 rounded-xl bg-slate-950/60 border border-dashed border-slate-800 text-xs text-slate-500 font-mono">
                    No disagreements listed. Use &quot;Find real disagreements (AI)&quot; to compare this event&apos;s reports; it needs at least two.
                  </p>
                )}
                {dossier.contradictions.map((c, idx) => (
                  <div key={idx} className="p-4 rounded-xl bg-slate-950/80 border border-slate-800/80 space-y-3">
                    <div className="flex items-center gap-2 text-xs font-mono font-semibold text-amber-300">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      <span>{c.issue}</span>
                    </div>

                    {c.explanation && <p className="text-xs text-slate-400">{c.explanation}</p>}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 font-mono text-xs">
                      {[
                        { label: 'Perspective A', labelClass: 'text-slate-400', text: c.side_a, side: c.a },
                        { label: 'Perspective B', labelClass: 'text-cyan-400', text: c.side_b, side: c.b },
                      ].map(({ label, labelClass, text, side }) => (
                        <div key={label} className="min-w-0 p-3 rounded-lg bg-slate-900/90 border border-slate-800">
                          <span className={`text-[10px] ${labelClass} uppercase tracking-wider block mb-1`}>{label}</span>
                          <p className="text-slate-300 font-sans leading-relaxed">{text}</p>
                          {side?.url && (
                            <a href={side.url} target="_blank" rel="noreferrer" title={side.title} className="mt-1.5 flex max-w-full items-center gap-1 text-[10px] text-cyan-400 hover:text-cyan-300">
                              <ExternalLink className="w-3 h-3 shrink-0" />
                              <span className="truncate min-w-0">{side.title}</span>
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Column 2: Stakeholders, Geography, Citations */}
          <div className="space-y-6">
            {/* Stakeholders Matrix */}
            <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80">
              <h3 className="font-display font-bold text-base text-white flex items-center gap-2 mb-3">
                <Users className="w-4 h-4 text-purple-400" />
                <span>Who&apos;s involved</span>
              </h3>

              <div className="space-y-2.5">
                {dossier.stakeholders.map((s, idx) => (
                  <div key={idx} className="p-3 rounded-xl bg-slate-950/70 border border-slate-800">
                    <h5 className="font-semibold text-xs text-purple-300 font-mono">{s.actor}</h5>
                    <p className="text-[11px] text-slate-400 mt-0.5">{s.role}</p>
                    {s.example_headline && (
                      <p className="mt-1.5 text-[10px] font-mono text-slate-500 line-clamp-2">
                        <span className="text-slate-400">e.g. </span>
                        <span className="text-slate-300">{s.example_headline}</span>
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Strategic Geography */}
            <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80">
              <h3 className="font-display font-bold text-base text-white flex items-center gap-2 mb-3">
                <Compass className="w-4 h-4 text-cyan-400" />
                <span>Places</span>
              </h3>

              <div className="space-y-3 font-mono text-xs">
                <div>
                  <span className="text-[10px] text-slate-400 uppercase tracking-wider block mb-1">
                    Chokepoints
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {dossier.geography.chokepoints.length === 0 ? (
                      <span className="text-slate-500 text-[11px]">No specific chokepoints tagged.</span>
                    ) : (
                      dossier.geography.chokepoints.map((chk, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 rounded bg-cyan-950/70 text-cyan-300 border border-cyan-800/40 text-[11px]"
                        >
                          {chk}
                        </span>
                      ))
                    )}
                  </div>
                </div>

                <div>
                  <span className="text-[10px] text-slate-400 uppercase tracking-wider block mb-1">
                    Corridors
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {dossier.geography.key_corridors.length === 0 && (
                      <span className="text-slate-500 text-[11px]">No corridors tagged.</span>
                    )}
                    {dossier.geography.key_corridors.map((c, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 text-[11px]"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Primary Citations */}
            <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80">
              <h3 className="font-display font-bold text-base text-white flex items-center gap-2 mb-3">
                <BookOpen className="w-4 h-4 text-emerald-400" />
                <span>Sources ({dossier.citations.length})</span>
              </h3>

              <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                {dossier.citations.map((c, i) => (
                  <a
                    key={i}
                    href={c.url}
                    target="_blank"
                    rel="noreferrer"
                    className="block p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 hover:border-slate-700 transition group"
                  >
                    <div className="font-semibold text-xs text-slate-300 group-hover:text-cyan-300 transition line-clamp-1">
                      {c.title}
                    </div>
                    <div className="flex items-center gap-2 font-mono text-[10px] text-slate-500 mt-1">
                      <span>{c.source_id}</span>
                      <span>{c.published_at.slice(0, 10)}</span>
                    </div>
                  </a>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      <ClaimLedger projectId={project.id} />

      <div className="flex justify-end">
        <button
          onClick={onProceedToStudio}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-purple-600 hover:bg-purple-500 text-white transition"
        >
          <span>Next: write the script</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
