import React, { useState } from 'react';
import { Source, SourceCreate } from '../../types';
import { AddSourceModal } from './AddSourceModal';
import {
  Globe2,
  PlusCircle,
  Sparkles,
  ExternalLink,
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Layers,
  Pause,
  Pencil,
  Play,
  Trash2
} from 'lucide-react';

interface SourcesManagerProps {
  sources: Source[];
  loading: boolean;
  onRefresh: () => void;
  onSeedDefaults: () => Promise<void>;
  isSeeding: boolean;
  onCreateSource: (source: SourceCreate) => Promise<void>;
  onUpdateSource: (sourceId: string, data: SourceCreate) => Promise<void>;
  onToggleSource: (source: Source) => void;
  onDeleteSource: (source: Source) => void;
}

export const SourcesManager: React.FC<SourcesManagerProps> = ({
  sources,
  loading,
  onRefresh,
  onSeedDefaults,
  isSeeding,
  onCreateSource,
  onUpdateSource,
  onToggleSource,
  onDeleteSource,
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editing, setEditing] = useState<Source | null>(null);

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm shadow-xl">
        <div>
          <div className="flex items-center gap-2">
            <Globe2 className="w-5 h-5 text-emerald-400" />
            <h2 className="font-display font-bold text-xl sm:text-2xl text-white">
              Signals & Feed Registry
            </h2>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Authoritative international reporting syndicates, policy think tanks, and geopolitical wire feeds.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onSeedDefaults}
            disabled={isSeeding}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-mono font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
            title="Seed BBC, Al Jazeera, CFR, and CSIS feeds"
          >
            <Sparkles className={`w-3.5 h-3.5 text-amber-400 ${isSeeding ? 'animate-spin' : ''}`} />
            <span>{isSeeding ? 'Seeding...' : 'Seed Defaults'}</span>
          </button>

          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-mono font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg transition active:scale-95"
          >
            <PlusCircle className="w-3.5 h-3.5" />
            <span>Add Feed</span>
          </button>

          <button
            onClick={onRefresh}
            className="p-1.5 rounded-xl bg-slate-800 text-slate-400 hover:text-white transition"
            title="Reload sources"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Sources Table */}
      <div className="overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-900/40">
        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead className="bg-slate-950/80 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Publication / Source</th>
                <th className="py-3 px-4">Region</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-4">Reliability</th>
                <th className="py-3 px-4">Last Ingested</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-500 font-mono">
                    Loading registered feeds...
                  </td>
                </tr>
              ) : sources.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    <p className="mb-3">No intelligence feeds registered yet.</p>
                    <button
                      onClick={onSeedDefaults}
                      disabled={isSeeding}
                      className="px-3 py-1.5 rounded-lg text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition"
                    >
                      Seed Default Feeds Now
                    </button>
                  </td>
                </tr>
              ) : (
                sources.map((src) => (
                  <tr key={src.id} className="hover:bg-slate-800/30 transition">
                    {/* Publication */}
                    <td className="py-3 px-4">
                      <div>
                        <span className="font-semibold text-slate-100 font-sans text-sm">
                          {src.name}
                        </span>
                        <div className="flex items-center gap-2 mt-0.5 text-slate-500 text-[11px]">
                          <span>ID: {src.id}</span>
                          <span>•</span>
                          <a
                            href={src.feed_url}
                            target="_blank"
                            rel="noreferrer"
                            className="hover:text-cyan-400 inline-flex items-center gap-1 max-w-[200px] truncate"
                          >
                            <span>{src.feed_url}</span>
                            <ExternalLink className="w-3 h-3 shrink-0" />
                          </a>
                        </div>
                      </div>
                    </td>

                    {/* Region */}
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700/60 text-[11px]">
                        {src.region}
                      </span>
                    </td>

                    {/* Type */}
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded bg-cyan-950/60 text-cyan-300 border border-cyan-800/40 text-[11px] uppercase">
                        {src.source_type}
                      </span>
                    </td>

                    {/* Reliability */}
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                          <div
                            className="h-full bg-emerald-500 rounded-full"
                            style={{ width: `${src.reliability_score * 100}%` }}
                          />
                        </div>
                        <span className="text-slate-300 font-bold">
                          {Math.round(src.reliability_score * 100)}%
                        </span>
                      </div>
                    </td>

                    {/* Last Ingested */}
                    <td className="py-3 px-4 text-slate-400 text-[11px]">
                      {src.last_fetched_at ? (
                        new Date(src.last_fetched_at).toLocaleString()
                      ) : (
                        <span className="text-slate-600">Pending crawl</span>
                      )}
                    </td>

                    {/* Status */}
                    <td className="py-3 px-4">
                      {src.last_error ? (
                        <span
                          className="inline-flex items-center gap-1 text-rose-400 cursor-help"
                          title={src.last_error}
                        >
                          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                          <span className="truncate max-w-[120px]">Error</span>
                        </span>
                      ) : src.is_active ? (
                        <span className="inline-flex items-center gap-1 text-emerald-400">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Active</span>
                        </span>
                      ) : (
                        <span className="text-slate-500">Disabled</span>
                      )}
                    </td>

                    {/* Actions */}
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => setEditing(src)}
                          className="p-1.5 rounded text-slate-400 hover:text-cyan-400 hover:bg-slate-800 transition"
                          title="Edit source"
                          aria-label={`Edit ${src.name}`}
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => onToggleSource(src)}
                          className="p-1.5 rounded text-slate-400 hover:text-cyan-400 hover:bg-slate-800 transition"
                          title={src.is_active ? 'Pause source' : 'Resume source'}
                          aria-label={src.is_active ? `Pause ${src.name}` : `Resume ${src.name}`}
                        >
                          {src.is_active ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                        </button>
                        <button
                          onClick={() => onDeleteSource(src)}
                          className="p-1.5 rounded text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition"
                          title="Delete source"
                          aria-label={`Delete ${src.name}`}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add / Edit Source Modal (keyed so the form resets per source) */}
      <AddSourceModal
        key={editing?.id ?? 'new'}
        isOpen={isModalOpen || !!editing}
        initial={editing}
        onClose={() => {
          setIsModalOpen(false);
          setEditing(null);
        }}
        onSubmit={editing ? (data) => onUpdateSource(editing.id, data) : onCreateSource}
      />
    </div>
  );
};
