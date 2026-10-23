import React, { useState, useEffect } from 'react';
import { EventCluster } from '../../types';
import { api } from '../../api/client';
import { VerificationModal } from './VerificationModal';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  Search,
  Filter,
  RefreshCw,
  Compass,
  Users,
  ArrowRight,
  Layers,
  Sparkles,
  ExternalLink,
  BookOpen
} from 'lucide-react';

interface IndiaDeskProps {
  onOpenWarRoom: (cluster: EventCluster) => void;
  isCreatingProject: boolean;
  onScanFeeds: () => void;
  isScanning: boolean;
}

export const IndiaDesk: React.FC<IndiaDeskProps> = ({
  onOpenWarRoom,
  isCreatingProject,
  onScanFeeds,
  isScanning,
}) => {
  const [clusters, setClusters] = useState<EventCluster[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [triangulationFilter, setTriangulationFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [auditCluster, setAuditCluster] = useState<EventCluster | null>(null);

  const fetchIndiaClusters = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await api.getIndiaClusters();
      setClusters(data);
    } catch (err) {
      console.error('Failed to load India desk clusters:', err);
      setLoadError(`Could not load India Desk events: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIndiaClusters();
  }, []);

  // Filter clusters
  const filtered = clusters.filter((c) => {
    if (triangulationFilter !== 'all' && c.triangulation_level !== triangulationFilter) {
      return false;
    }
    if (severityFilter !== 'all' && c.severity.toLowerCase() !== severityFilter.toLowerCase()) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchHead = c.headline.toLowerCase().includes(q);
      const matchSummary = (c.summary || '').toLowerCase().includes(q);
      const matchActors = (c.key_actors || []).some((a) => a.toLowerCase().includes(q));
      const matchChoke = (c.chokepoints || []).some((chk) => chk.toLowerCase().includes(q));
      const matchSource = (c.source_names || []).some((s) => s.toLowerCase().includes(q));
      if (!matchHead && !matchSummary && !matchActors && !matchChoke && !matchSource) {
        return false;
      }
    }
    return true;
  });

  const triangulatedCount = clusters.filter((c) => c.triangulation_level === 'triangulated').length;
  const corroboratedCount = clusters.filter((c) => c.triangulation_level === 'corroborated').length;
  const unverifiedCount = clusters.filter((c) => c.triangulation_level === 'unverified').length;

  return (
    <div className="space-y-6">
      {loadError && (
        <div role="alert" className="p-3 rounded-xl bg-rose-950/80 border border-rose-800/80 text-rose-300 font-mono text-xs">
          {loadError}
        </div>
      )}

      {/* India Strategic Desk Banner */}
      <div className="p-5 sm:p-6 rounded-2xl bg-gradient-to-r from-orange-950/40 via-slate-900/60 to-emerald-950/40 border border-orange-500/30 backdrop-blur-sm shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-900/90 border border-slate-700 text-[10px] font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                <span className="w-1.5 h-1.5 rounded-full bg-white" />
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <span className="text-slate-300 font-bold ml-1">INDIA STRATEGIC DESK</span>
              </span>
              <span className="text-xs font-mono text-orange-400">Multi-Source Verification Engine</span>
            </div>

            <h2 className="font-display font-extrabold text-2xl sm:text-3xl text-white tracking-tight">
              India & Indo-Pacific Affairs
            </h2>
            <p className="text-xs sm:text-sm text-slate-300 mt-1 max-w-2xl leading-relaxed">
              Cross-verify geopolitical developments across Indian domestic wire reports, international syndicates, and policy think tanks before writing video essays.
            </p>
          </div>

          <div className="flex items-center gap-2 font-mono text-xs shrink-0">
            <button
              onClick={onScanFeeds}
              disabled={isScanning}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg transition active:scale-95"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
              <span>{isScanning ? 'Crawling...' : 'Scan Feeds'}</span>
            </button>
            <button
              onClick={fetchIndiaClusters}
              className="p-2 rounded-xl bg-slate-800 text-slate-300 hover:text-white transition"
              title="Refresh India desk"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Verification Status HUD Banner */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 font-mono text-xs">
          <div className="p-3 rounded-xl bg-emerald-950/50 border border-emerald-800/40 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span className="text-emerald-200">Triangulated (3+ Sources)</span>
            </div>
            <span className="text-base font-bold text-emerald-300">{triangulatedCount}</span>
          </div>

          <div className="p-3 rounded-xl bg-amber-950/50 border border-amber-800/40 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-amber-400" />
              <span className="text-amber-200">Corroborated (2 Sources)</span>
            </div>
            <span className="text-base font-bold text-amber-300">{corroboratedCount}</span>
          </div>

          <div className="p-3 rounded-xl bg-rose-950/50 border border-rose-800/40 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400" />
              <span className="text-rose-200">Single Source Warning</span>
            </div>
            <span className="text-base font-bold text-rose-300">{unverifiedCount}</span>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3 rounded-xl bg-slate-900/80 border border-slate-800 text-xs font-mono">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search LAC, Siliguri Corridor, Andaman, Quad, IMEC, DRDO, ISRO..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950/80 border border-slate-800 text-slate-200 pl-9 pr-3 py-1.5 rounded-lg focus:outline-none focus:border-orange-500 placeholder:text-slate-500"
          />
        </div>

        {/* Verification Filter */}
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <select
            value={triangulationFilter}
            onChange={(e) => setTriangulationFilter(e.target.value)}
            className="bg-slate-950/80 border border-slate-800 text-slate-200 px-2.5 py-1.5 rounded-lg focus:outline-none focus:border-orange-500 cursor-pointer"
          >
            <option value="all">Verification: All</option>
            <option value="triangulated">🛡️ Triangulated Only (3+)</option>
            <option value="corroborated">🟡 Corroborated (2)</option>
            <option value="unverified">⚠️ Unverified (1 source)</option>
          </select>

          {/* Severity Filter */}
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-slate-950/80 border border-slate-800 text-slate-200 px-2.5 py-1.5 rounded-lg focus:outline-none focus:border-orange-500 cursor-pointer"
          >
            <option value="all">Severity: All</option>
            <option value="crisis">Crisis Only</option>
            <option value="escalating">Escalating</option>
            <option value="routine">Routine</option>
          </select>
        </div>
      </div>

      {/* Grid of India Strategic Clusters */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-64 rounded-2xl bg-slate-900/40 border border-slate-800 animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="p-12 text-center rounded-2xl bg-slate-900/30 border border-dashed border-slate-800 space-y-4">
          <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center mx-auto text-slate-400">
            <Compass className="w-6 h-6" />
          </div>
          <div>
            <h4 className="font-display font-semibold text-base text-slate-200">
              No matching India-focused events found
            </h4>
            <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
              Try adjusting your verification filter, or click &quot;Scan Feeds&quot; to fetch the latest dispatches from The Hindu, Indian Express, and international wires.
            </p>
          </div>
          <button
            onClick={onScanFeeds}
            disabled={isScanning}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-mono font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
            <span>Scan News Feeds Now</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filtered.map((cluster) => {
            const level = cluster.triangulation_level || 'unverified';
            const sources = cluster.source_names || [];

            return (
              <div
                key={cluster.id}
                className="group relative flex flex-col justify-between bg-slate-900/60 hover:bg-slate-900/90 border border-slate-800/80 hover:border-orange-500/40 rounded-2xl p-5 transition-all duration-300 shadow-lg"
              >
                <div>
                  {/* Top Bar: Verification Badge & Explainer Score */}
                  <div className="flex items-start justify-between gap-3 mb-3 font-mono text-[11px]">
                    {/* Triangulation Level Badge */}
                    <div
                      className={`flex items-center gap-1 px-2.5 py-0.5 rounded-full font-bold uppercase ${
                        level === 'triangulated'
                          ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30'
                          : level === 'corroborated'
                          ? 'bg-amber-500/10 text-amber-300 border border-amber-500/30'
                          : 'bg-rose-500/10 text-rose-300 border border-rose-500/30'
                      }`}
                    >
                      {level === 'triangulated' && <ShieldCheck className="w-3.5 h-3.5" />}
                      {level === 'corroborated' && <CheckCircle2 className="w-3.5 h-3.5" />}
                      {level === 'unverified' && <AlertTriangle className="w-3.5 h-3.5" />}
                      <span>
                        {level === 'triangulated'
                          ? `Confirmed • ${cluster.independent_origin_count} Origins`
                          : level === 'corroborated'
                          ? `Reported • ${cluster.independent_origin_count} Origins`
                          : 'Unconfirmed Claim'}
                      </span>
                    </div>

                    <div className="px-2 py-0.5 rounded-lg bg-slate-800/80 border border-slate-700 text-cyan-400 font-bold">
                      Score {Math.round(cluster.explainer_score)}
                    </div>
                  </div>

                  {/* Headline */}
                  <h3 className="font-display font-semibold text-base sm:text-lg text-white group-hover:text-orange-300 transition line-clamp-2 leading-snug">
                    {cluster.headline}
                  </h3>

                  {/* Summary */}
                  {cluster.summary && (
                    <p className="mt-2 text-xs text-slate-400 line-clamp-3 leading-relaxed">
                      {cluster.summary}
                    </p>
                  )}

                  {/* Contributing Newsrooms Badges */}
                  <div className="mt-3 pt-3 border-t border-slate-800/80">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500 block mb-1.5">
                      Corroborating Newsrooms:
                    </span>
                    <div className="flex flex-wrap gap-1.5 font-mono text-[10px]">
                      {sources.length > 0 ? (
                        sources.map((s, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700"
                          >
                            {s}
                          </span>
                        ))
                      ) : (
                        <span className="text-slate-500">Source attribution pending</span>
                      )}
                    </div>
                  </div>

                  {/* Chokepoints & Actors */}
                  <div className="mt-3 space-y-1.5">
                    {cluster.chokepoints && cluster.chokepoints.length > 0 && (
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <Compass className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                        {cluster.chokepoints.map((chk, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 rounded bg-cyan-950/60 text-cyan-300 border border-cyan-800/40 text-[10px] font-mono"
                          >
                            {chk}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="mt-5 pt-3.5 border-t border-slate-800/80 flex items-center justify-between gap-2">
                  <button
                    onClick={() => setAuditCluster(cluster)}
                    className="text-xs font-mono text-slate-400 hover:text-white transition flex items-center gap-1"
                  >
                    <BookOpen className="w-3.5 h-3.5 text-orange-400" />
                    <span>Pre-Video Audit</span>
                  </button>

                  <button
                    onClick={() => onOpenWarRoom(cluster)}
                    disabled={isCreatingProject}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-orange-600 hover:bg-orange-500 text-white shadow-sm transition active:scale-95"
                  >
                    <span>War Room</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Pre-Video Verification Modal */}
      <VerificationModal
        cluster={auditCluster}
        onClose={() => setAuditCluster(null)}
        onOpenWarRoom={onOpenWarRoom}
      />
    </div>
  );
};
