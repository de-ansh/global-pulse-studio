import React from 'react';
import { EventCluster } from '../../types';
import { Anchor, Users, Compass, ArrowRight, Layers, Clock } from 'lucide-react';

interface ClusterCardProps {
  cluster: EventCluster;
  onOpenWarRoom: (cluster: EventCluster) => void;
  onInspect: (cluster: EventCluster) => void;
  isCreatingProject: boolean;
}

export const ClusterCard: React.FC<ClusterCardProps> = ({
  cluster,
  onOpenWarRoom,
  onInspect,
  isCreatingProject,
}) => {
  const getSeverityStyle = (sev: string) => {
    switch (sev.toLowerCase()) {
      case 'crisis':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
      case 'escalating':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
      default:
        return 'bg-slate-500/10 text-slate-400 border-slate-500/30';
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 70) return 'text-rose-400 border-rose-500/40 bg-rose-500/10';
    if (score >= 45) return 'text-amber-400 border-amber-500/40 bg-amber-500/10';
    return 'text-cyan-400 border-cyan-500/40 bg-cyan-500/10';
  };

  return (
    <div className="group relative flex flex-col justify-between bg-slate-900/60 hover:bg-slate-900/90 border border-slate-800/80 hover:border-slate-700/80 rounded-2xl p-5 transition-all duration-300 shadow-lg hover:shadow-cyan-950/20">
      <div>
        {/* Top Badges & Explainer Score Meter */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
            <span className={`px-2 py-0.5 rounded-md uppercase font-semibold border ${getSeverityStyle(cluster.severity)}`}>
              {cluster.severity}
            </span>
            <span className="px-2 py-0.5 rounded-md bg-slate-800/80 text-slate-300 border border-slate-700/60">
              {cluster.region}
            </span>
            <span className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-800/80 text-slate-400 border border-slate-700/60">
              <Layers className="w-3 h-3 text-cyan-400" />
              <span>{cluster.article_count} {cluster.article_count === 1 ? 'report' : 'reports'}</span>
            </span>
          </div>

          {/* Explainer Score HUD Tag */}
          <div
            className={`flex items-center gap-1 px-2.5 py-1 rounded-xl font-mono text-xs font-bold border ${getScoreColor(
              cluster.explainer_score
            )}`}
            title="Explainer Score (0-100) indicates video essay viability based on chokepoint friction & geopolitical stakes"
          >
            <span className="text-[10px] text-slate-400 uppercase tracking-wider">Score</span>
            <span>{Math.round(cluster.explainer_score)}</span>
          </div>
        </div>

        {/* Headline */}
        <h3 className="font-display font-semibold text-base sm:text-lg text-white group-hover:text-cyan-300 transition line-clamp-2 leading-snug">
          {cluster.headline}
        </h3>

        {/* Summary Snippet */}
        {cluster.summary && (
          <p className="mt-2 text-xs text-slate-400 line-clamp-3 leading-relaxed">
            {cluster.summary}
          </p>
        )}

        {/* Tactical Indicators: Chokepoints, Actors, Keywords */}
        <div className="mt-4 space-y-2">
          {cluster.chokepoints && cluster.chokepoints.length > 0 && (
            <div className="flex items-center gap-1.5 flex-wrap">
              <Compass className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
              {cluster.chokepoints.map((chk, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 rounded bg-cyan-950/60 text-cyan-300 border border-cyan-800/40 text-[11px] font-mono"
                >
                  {chk}
                </span>
              ))}
            </div>
          )}

          {cluster.key_actors && cluster.key_actors.length > 0 && (
            <div className="flex items-center gap-1.5 flex-wrap">
              <Users className="w-3.5 h-3.5 text-purple-400 shrink-0" />
              {cluster.key_actors.slice(0, 4).map((actor, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 rounded bg-purple-950/60 text-purple-300 border border-purple-800/40 text-[11px] font-mono"
                >
                  {actor}
                </span>
              ))}
              {cluster.key_actors.length > 4 && (
                <span className="text-[10px] text-slate-500 font-mono">
                  +{cluster.key_actors.length - 4} more
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Footer Actions */}
      <div className="mt-5 pt-3.5 border-t border-slate-800/80 flex items-center justify-between gap-2">
        <button
          onClick={() => onInspect(cluster)}
          className="text-xs font-mono text-slate-400 hover:text-slate-200 transition underline underline-offset-4 decoration-slate-700"
        >
          Details
        </button>

        <button
          onClick={() => onOpenWarRoom(cluster)}
          disabled={isCreatingProject}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-cyan-600 hover:bg-cyan-500 text-white shadow-sm transition active:scale-95"
        >
          <span>Research</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};
