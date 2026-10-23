import React, { useState } from 'react';
import { Source, SourceCreate } from '../../types';
import { X, Globe2, PlusCircle } from 'lucide-react';

interface AddSourceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (source: SourceCreate) => Promise<void>;
  initial?: Source | null; // set to edit an existing source instead of adding one
}

export const AddSourceModal: React.FC<AddSourceModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  initial,
}) => {
  const [id, setId] = useState(initial?.id ?? '');
  const [name, setName] = useState(initial?.name ?? '');
  const [feedUrl, setFeedUrl] = useState(initial?.feed_url ?? '');
  const [region, setRegion] = useState(initial?.region ?? 'Global');
  const [sourceType, setSourceType] = useState(initial?.source_type ?? 'wire');
  const [reliability, setReliability] = useState(initial?.reliability_score ?? 0.85);
  const [biasCategory, setBiasCategory] = useState(initial?.bias_category ?? '');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id.trim() || !name.trim() || !feedUrl.trim()) {
      setError('ID, Name, and Feed URL are required fields.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        id: id.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_'),
        name: name.trim(),
        feed_url: feedUrl.trim(),
        region: region.trim(),
        source_type: sourceType,
        reliability_score: reliability,
        bias_category: biasCategory || null, // null clears it when editing
        is_active: initial?.is_active ?? true,
      });
      onClose();
    } catch (err: any) {
      setError(err?.message || 'Failed to add source');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg bg-[#0B101B] border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Globe2 className="w-5 h-5 text-emerald-400" />
            <h3 className="font-display font-bold text-base sm:text-lg text-white">
              {initial ? `Edit ${initial.name}` : 'Add Custom Intelligence Feed'}
            </h3>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4 font-mono text-xs">
          {error && (
            <div className="p-3 rounded-xl bg-rose-950/80 border border-rose-800/80 text-rose-300">
              {error}
            </div>
          )}

          <div>
            <label className="text-[11px] uppercase tracking-wider text-slate-400 block mb-1">
              Source ID (unique handle)
            </label>
            <input
              type="text"
              placeholder="e.g. defense_one, isw_reports"
              value={id}
              onChange={(e) => setId(e.target.value)}
              required
              disabled={!!initial}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed"
            />
          </div>

          <div>
            <label className="text-[11px] uppercase tracking-wider text-slate-400 block mb-1">
              Publication / Think Tank Name
            </label>
            <input
              type="text"
              placeholder="e.g. Defense One Global Dispatch"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-cyan-500"
            />
          </div>

          <div>
            <label className="text-[11px] uppercase tracking-wider text-slate-400 block mb-1">
              RSS / Atom Feed URL
            </label>
            <input
              type="url"
              placeholder="https://domain.org/rss.xml"
              value={feedUrl}
              onChange={(e) => setFeedUrl(e.target.value)}
              required
              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-cyan-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] uppercase tracking-wider text-slate-400 block mb-1">
                Geographic Region
              </label>
              <input
                type="text"
                placeholder="e.g. Indo-Pacific, Eastern Europe"
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div>
              <label className="text-[11px] uppercase tracking-wider text-slate-400 block mb-1">
                Source Type
              </label>
              <select
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-cyan-500 cursor-pointer"
              >
                <option value="wire">Wire Syndicate</option>
                <option value="think_tank">Policy Think Tank</option>
                <option value="gov">Official / Gov</option>
                <option value="independent">Independent OSINT</option>
              </select>
            </div>
          </div>

          <div>
            <label className="text-[11px] uppercase tracking-wider text-slate-400 block mb-1">
              Media Ecosystem
            </label>
            {/* Drives the cross-perspective triangulation check: a domestic and an international outlet must both report. */}
            <select
              value={biasCategory}
              onChange={(e) => setBiasCategory(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-cyan-500 cursor-pointer"
            >
              <option value="">Unclassified</option>
              <option value="domestic_mainstream">Domestic Mainstream (domestic lens)</option>
              <option value="business_geoecon">Business / Geoeconomics (domestic lens)</option>
              <option value="western_mainstream">Western Mainstream (international lens)</option>
              <option value="pan_arab_regional">Pan-Arab Regional (international lens)</option>
              <option value="policy_establishment">Policy Establishment (international lens)</option>
              <option value="analytical_independent">Analytical / Independent</option>
            </select>
          </div>

          <div>
            <div className="flex items-center justify-between text-[11px] uppercase tracking-wider text-slate-400 mb-1">
              <span>Reliability Weight</span>
              <span className="text-cyan-400 font-bold">{Math.round(reliability * 100)}%</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="1.0"
              step="0.05"
              value={reliability}
              onChange={(e) => setReliability(Number(e.target.value))}
              className="w-full accent-cyan-400 cursor-pointer"
            />
          </div>

          {/* Actions */}
          <div className="pt-3 border-t border-slate-800 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-slate-400 hover:text-white transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 rounded-xl font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md transition flex items-center gap-1.5"
            >
              <PlusCircle className="w-4 h-4" />
              <span>{submitting ? 'Saving...' : initial ? 'Save Changes' : 'Register Source'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
