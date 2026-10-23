import React, { useEffect, useState } from 'react';
import { EventCluster, Article } from '../../types';
import { api } from '../../api/client';
import { FactChecks } from './FactChecks';
import { X, ExternalLink, Calendar, ShieldCheck, Newspaper, Hash } from 'lucide-react';

interface ClusterDetailModalProps {
  cluster: EventCluster | null;
  onClose: () => void;
  onOpenWarRoom: (cluster: EventCluster) => void;
}

export const ClusterDetailModal: React.FC<ClusterDetailModalProps> = ({
  cluster,
  onClose,
  onOpenWarRoom,
}) => {
  const [detail, setDetail] = useState<EventCluster | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!cluster) {
      setDetail(null);
      return;
    }

    setLoading(true);
    api
      .getClusterDetail(cluster.id)
      .then((data) => setDetail(data))
      .catch((err) => {
        console.error('Failed to load cluster detail:', err);
        setDetail(cluster);
      })
      .finally(() => setLoading(false));
  }, [cluster]);

  if (!cluster) return null;

  const current = detail || cluster;
  const articles: Article[] = current.articles || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-3xl max-h-[90vh] flex flex-col bg-[#0B101B] border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5 font-mono text-xs">
              <span className="px-2 py-0.5 rounded bg-cyan-950/70 text-cyan-300 border border-cyan-800/40">
                {current.region}
              </span>
              <span className="text-slate-400">ID: {current.id}</span>
            </div>
            <h2 className="font-display font-bold text-lg sm:text-xl text-white">
              {current.headline}
            </h2>
            {current.verification_label && (
              <p className="mt-1 text-xs font-mono text-amber-300">{current.verification_label}</p>
            )}
          </div>

          <button
            onClick={onClose}
            aria-label="Close"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {/* Summary */}
          {current.summary && (
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 text-sm text-slate-300 leading-relaxed">
              {current.summary}
            </div>
          )}

          {/* Strategic Metrics Matrix */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-[10px] text-slate-400 uppercase">Explainer Score</span>
              <p className="text-lg font-bold text-cyan-400 mt-0.5">{Math.round(current.explainer_score)}/100</p>
            </div>
            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-[10px] text-slate-400 uppercase">Severity</span>
              <p className="text-lg font-bold text-amber-400 mt-0.5 capitalize">{current.severity}</p>
            </div>
            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-[10px] text-slate-400 uppercase">Wire Reports</span>
              <p className="text-lg font-bold text-slate-200 mt-0.5">{current.article_count}</p>
            </div>
            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-[10px] text-slate-400 uppercase">Status</span>
              <p className="text-lg font-bold text-emerald-400 mt-0.5 capitalize">{current.status}</p>
            </div>
          </div>

          <FactChecks load={() => api.getFactChecks(current.id)} />

          {/* Backing Reporting Feeds */}
          <div>
            <h4 className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
              <Newspaper className="w-4 h-4 text-cyan-400" />
              <span>Backing Multi-Source Intelligence ({articles.length})</span>
            </h4>

            {loading ? (
              <div className="p-6 text-center text-slate-500 font-mono text-xs">Loading primary reports...</div>
            ) : articles.length === 0 ? (
              <div className="p-4 rounded-xl bg-slate-900/40 border border-dashed border-slate-800 text-xs text-slate-500 font-mono">
                No individual articles populated in cache for this cluster.
              </div>
            ) : (
              <div className="space-y-3">
                {articles.map((art) => (
                  <div
                    key={art.id}
                    className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800/80 hover:border-slate-700 transition"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 font-mono text-[10px] text-slate-400 mb-1">
                          <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-semibold">
                            {art.source_id}
                          </span>
                          <span>{new Date(art.published_at).toLocaleString()}</span>
                        </div>
                        <h5 className="font-semibold text-sm text-slate-100 hover:text-cyan-300 transition">
                          <a href={art.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5">
                            <span>{art.title}</span>
                            <ExternalLink className="w-3.5 h-3.5 shrink-0 opacity-60" />
                          </a>
                        </h5>
                        {art.summary && (
                          <p className="mt-1 text-xs text-slate-400 line-clamp-2 leading-relaxed">
                            {art.summary}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs font-mono text-slate-400 hover:text-white transition"
          >
            Close
          </button>

          <button
            onClick={() => {
              onClose();
              onOpenWarRoom(current);
            }}
            className="px-4 py-2 rounded-xl text-xs font-mono font-semibold bg-cyan-600 hover:bg-cyan-500 text-white shadow-md transition"
          >
            Launch in War Room
          </button>
        </div>
      </div>
    </div>
  );
};
