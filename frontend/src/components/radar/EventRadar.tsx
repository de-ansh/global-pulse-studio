import React, { useState } from 'react';
import { EventCluster } from '../../types';
import { ClusterCard } from './ClusterCard';
import { ClusterDetailModal } from './ClusterDetailModal';
import { Search, Filter, ShieldAlert, Sparkles, RefreshCw, Layers } from 'lucide-react';

interface EventRadarProps {
  clusters: EventCluster[];
  loading: boolean;
  onRefresh: () => void;
  hasMore: boolean;
  onLoadMore: () => void;
  onOpenWarRoom: (cluster: EventCluster) => void;
  isCreatingProject: boolean;
  onScanFeeds: () => void;
  isScanning: boolean;
}

export const EventRadar: React.FC<EventRadarProps> = ({
  clusters,
  loading,
  hasMore,
  onLoadMore,
  onRefresh,
  onOpenWarRoom,
  isCreatingProject,
  onScanFeeds,
  isScanning,
}) => {
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [minScoreFilter, setMinScoreFilter] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCluster, setSelectedCluster] = useState<EventCluster | null>(null);

  // Filter logic
  const filteredClusters = clusters.filter((c) => {
    if (severityFilter !== 'all' && c.severity.toLowerCase() !== severityFilter.toLowerCase()) {
      return false;
    }
    if (c.explainer_score < minScoreFilter) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchHeadline = c.headline.toLowerCase().includes(q);
      const matchRegion = c.region.toLowerCase().includes(q);
      const matchActors = (c.key_actors || []).some((a) => a.toLowerCase().includes(q));
      const matchChokepoints = (c.chokepoints || []).some((chk) => chk.toLowerCase().includes(q));
      if (!matchHeadline && !matchRegion && !matchActors && !matchChokepoints) {
        return false;
      }
    }
    return true;
  });

  const crisisCount = clusters.filter((c) => c.severity === 'crisis').length;
  const highPotentialCount = clusters.filter((c) => c.explainer_score >= 60).length;

  return (
    <div className="space-y-6">
      {/* Tactical Radar Command Header & Telemetry Pills */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/40 border border-slate-800/80 backdrop-blur-sm">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
            <h2 className="font-display font-bold text-xl sm:text-2xl text-white">
              Signals & Crisis Radar
            </h2>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Algorithmic event clustering, maritime friction detection, and explainer score ranking.
          </p>
        </div>

        {/* Live Metrics HUD */}
        <div className="flex items-center gap-2.5 font-mono text-xs overflow-x-auto pb-1 md:pb-0">
          <div className="px-3 py-1.5 rounded-xl bg-slate-900/80 border border-slate-800 flex items-center gap-2">
            <Layers className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400">Tracked:</span>
            <span className="font-bold text-white">{clusters.length}</span>
          </div>

          <div className="px-3 py-1.5 rounded-xl bg-rose-950/40 border border-rose-800/40 flex items-center gap-2">
            <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
            <span className="text-rose-300">Crises:</span>
            <span className="font-bold text-rose-200">{crisisCount}</span>
          </div>

          <div className="px-3 py-1.5 rounded-xl bg-cyan-950/40 border border-cyan-800/40 flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-cyan-300">High Viability:</span>
            <span className="font-bold text-cyan-200">{highPotentialCount}</span>
          </div>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3 rounded-xl bg-slate-900/80 border border-slate-800 text-xs font-mono">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Filter by headline, chokepoint (e.g. Hormuz), or key actor..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950/80 border border-slate-800 text-slate-200 pl-9 pr-3 py-1.5 rounded-lg focus:outline-none focus:border-cyan-500 placeholder:text-slate-500"
          />
        </div>

        {/* Severity Filter */}
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-slate-950/80 border border-slate-800 text-slate-200 px-2.5 py-1.5 rounded-lg focus:outline-none focus:border-cyan-500 cursor-pointer"
          >
            <option value="all">Severity: All</option>
            <option value="crisis">Crisis Only</option>
            <option value="escalating">Escalating Only</option>
            <option value="routine">Routine</option>
          </select>

          {/* Min Score Filter */}
          <select
            value={minScoreFilter}
            onChange={(e) => setMinScoreFilter(Number(e.target.value))}
            className="bg-slate-950/80 border border-slate-800 text-slate-200 px-2.5 py-1.5 rounded-lg focus:outline-none focus:border-cyan-500 cursor-pointer"
          >
            <option value="0">Score: Any</option>
            <option value="35">Score: &gt; 35</option>
            <option value="50">Score: &gt; 50</option>
            <option value="70">Score: &gt; 70 (Prime Essay)</option>
          </select>

          {/* Refresh Button */}
          <button
            onClick={onRefresh}
            className="p-1.5 rounded-lg bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700 transition"
            title="Reload cluster registry"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Cluster Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="h-64 rounded-2xl bg-slate-900/40 border border-slate-800/80 animate-pulse p-5"
            />
          ))}
        </div>
      ) : filteredClusters.length === 0 ? (
        <div className="p-12 text-center rounded-2xl bg-slate-900/30 border border-dashed border-slate-800 space-y-4">
          <div className="w-12 h-12 rounded-full bg-slate-800/80 flex items-center justify-center mx-auto text-slate-500">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <h4 className="font-display font-semibold text-base text-slate-300">
              No matching geopolitical events detected
            </h4>
            <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
              Try adjusting your severity or score filters, or crawl international news syndicates to ingest fresh reporting.
            </p>
          </div>
          <button
            onClick={onScanFeeds}
            disabled={isScanning}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-mono font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
            <span>{isScanning ? 'Crawling Feeds...' : 'Crawl Wire Feeds Now'}</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredClusters.map((cluster) => (
            <ClusterCard
              key={cluster.id}
              cluster={cluster}
              onOpenWarRoom={onOpenWarRoom}
              onInspect={(c) => setSelectedCluster(c)}
              isCreatingProject={isCreatingProject}
            />
          ))}
        </div>
      )}

      {!loading && hasMore && (
        <div className="text-center">
          {/* Search and filters only apply to loaded events, so offer to load the rest. */}
          <button
            onClick={onLoadMore}
            className="px-4 py-2 rounded-xl text-xs font-mono font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 transition"
          >
            Load more events
          </button>
        </div>
      )}

      {/* Detail Modal */}
      <ClusterDetailModal
        cluster={selectedCluster}
        onClose={() => setSelectedCluster(null)}
        onOpenWarRoom={onOpenWarRoom}
      />
    </div>
  );
};
