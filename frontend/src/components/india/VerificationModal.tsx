import React from 'react';
import { EventCluster } from '../../types';
import { api } from '../../api/client';
import { FactChecks } from '../radar/FactChecks';
import {
  X,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Layers,
  ArrowRight,
  BookOpen,
  Compass
} from 'lucide-react';

interface VerificationModalProps {
  cluster: EventCluster | null;
  onClose: () => void;
  onOpenWarRoom: (cluster: EventCluster) => void;
}

export const VerificationModal: React.FC<VerificationModalProps> = ({
  cluster,
  onClose,
  onOpenWarRoom,
}) => {
  if (!cluster) return null;

  const level = cluster.triangulation_level || 'unverified';
  const sourceCount = cluster.source_count || 1;
  const sources = cluster.source_names || [];
  const checklist = cluster.verification_checklist || [];
  const articles = cluster.articles || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-3xl max-h-[90vh] flex flex-col bg-[#0A0F1A] border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5 font-mono text-xs">
              <span
                className={`flex items-center gap-1 px-2.5 py-0.5 rounded-full font-bold uppercase ${
                  level === 'triangulated'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                    : level === 'corroborated'
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                    : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                }`}
              >
                {level === 'triangulated' && <ShieldCheck className="w-3.5 h-3.5" />}
                {level === 'corroborated' && <CheckCircle2 className="w-3.5 h-3.5" />}
                {level === 'unverified' && <AlertTriangle className="w-3.5 h-3.5" />}
                <span>
                  {level === 'triangulated'
                    ? 'Multi-Source Triangulated'
                    : level === 'corroborated'
                    ? 'Dual-Source Corroborated'
                    : 'Single-Source Warning'}
                </span>
              </span>
              <span className="text-slate-400">
                {cluster.verification_label}
              </span>
            </div>

            <h2 className="font-display font-bold text-lg sm:text-xl text-white">
              {cluster.headline}
            </h2>
          </div>

          <button
            onClick={onClose}
            aria-label="Close"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6 text-xs font-mono">
          {/* Triangulation Alert Callout */}
          {level === 'unverified' && (
            <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800/50 flex items-start gap-3 text-rose-200">
              <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <h4 className="font-bold text-sm text-rose-300 mb-1">
                  Single-Source Caution Flag
                </h4>
                <p className="font-sans leading-relaxed text-slate-300 text-xs">
                  This story currently traces back to only <strong>1 independent origin</strong> ({sources.join(', ') || 'Unknown'}). Treat it as a claim, not a fact. Before writing script voiceover or claiming military/geopolitical facts, find independent confirmation from official defense releases, counter-party media, or satellite tracking.
                </p>
              </div>
            </div>
          )}

          {level === 'triangulated' && (
            <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-800/50 flex items-start gap-3 text-emerald-200">
              <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <h4 className="font-bold text-sm text-emerald-300 mb-1">
                  Corroborated by {cluster.independent_origin_count || 3} Independent Origins
                </h4>
                <p className="font-sans leading-relaxed text-slate-300 text-xs">
                  Several independent newsrooms report this (wire copies merged). Still attribute specific numbers and quotes to their source, and check primary evidence and the fact-checks below before stating it as fact.
                </p>
              </div>
            </div>
          )}

          {/* 3-Point Pre-Video Verification Audit */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-cyan-400" />
              <span>Pre-Video Scripting Verification Checklist</span>
            </h4>

            <div className="space-y-2">
              {checklist.map((item) => (
                <div
                  key={item.id}
                  className={`p-3.5 rounded-xl border flex items-start gap-3 ${
                    item.passed
                      ? 'bg-slate-900/80 border-emerald-900/60 text-slate-200'
                      : 'bg-slate-900/80 border-slate-800 text-slate-400'
                  }`}
                >
                  {item.passed ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                  )}
                  <div className="flex-1">
                    <span className="font-bold text-slate-200 block text-xs">{item.label}</span>
                    <span className="text-[11px] font-sans text-slate-400 leading-relaxed block mt-0.5">
                      {item.detail}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <FactChecks load={() => api.getFactChecks(cluster.id)} />

          {/* Reporting Sources Breakdown */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Layers className="w-4 h-4 text-purple-400" />
              <span>Contributing Newsrooms ({sourceCount} outlets, {cluster.independent_origin_count || 1} independent)</span>
            </h4>

            <div className="flex flex-wrap gap-2">
              {sources.map((name, i) => (
                <span
                  key={i}
                  className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-200 font-semibold"
                >
                  {name}
                </span>
              ))}
            </div>
          </div>

          {/* Primary Articles */}
          {articles.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-cyan-400" />
                <span>Primary Reporting Wire Links</span>
              </h4>

              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {articles.map((art) => (
                  <a
                    key={art.id}
                    href={art.url}
                    target="_blank"
                    rel="noreferrer"
                    className="block p-3 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition group"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-slate-200 group-hover:text-cyan-300 font-sans text-xs line-clamp-1">
                        {art.title}
                      </span>
                      <ExternalLink className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-slate-500 mt-1">
                      <span>Source: {art.source_id}</span>
                      <span>•</span>
                      <span>{new Date(art.published_at).toLocaleString()}</span>
                    </div>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-slate-800 bg-slate-950 flex items-center justify-between gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs font-mono text-slate-400 hover:text-white transition"
          >
            Close Audit
          </button>

          <button
            onClick={() => {
              onClose();
              onOpenWarRoom(cluster);
            }}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-mono font-semibold bg-orange-600 hover:bg-orange-500 text-white shadow-md transition"
          >
            <span>Proceed to War Room</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
