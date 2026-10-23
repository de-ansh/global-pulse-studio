import React, { useState } from 'react';
import { FactCheck } from '../../types';
import { SearchCheck, ExternalLink, Plus, Check } from 'lucide-react';

interface FactChecksProps {
  load: () => Promise<FactCheck[]>; // event headline or a single claim
  subject?: string; // what the empty-state message refers to
  onAdd?: (fc: FactCheck) => Promise<void>; // shows "Add as evidence" on each result
  addedUrls?: string[];
}

export const FactChecks: React.FC<FactChecksProps> = ({ load, subject = 'this story', onAdd, addedUrls = [] }) => {
  const [results, setResults] = useState<FactCheck[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const search = async () => {
    setLoading(true);
    setError(null);
    try {
      setResults(await load());
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const add = async (fc: FactCheck) => {
    if (!onAdd) return;
    setAdding(fc.url);
    setError(null);
    try {
      await onAdd(fc);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setAdding(null);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
          <SearchCheck className="w-4 h-4 text-amber-400" />
          <span>Published Fact-Checks</span>
        </h4>
        <button
          onClick={search}
          disabled={loading}
          className="px-3 py-1.5 rounded-lg text-xs font-mono bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition disabled:opacity-50"
        >
          {loading ? 'Searching...' : results ? 'Search Again' : 'Search Fact-Checkers'}
        </button>
      </div>

      {error && (
        <p role="alert" className="p-3 rounded-xl bg-rose-950/40 border border-rose-800/50 text-xs text-rose-200 font-mono">
          {error}
        </p>
      )}

      {results && results.length === 0 && (
        <p className="p-3 rounded-xl bg-slate-900/40 border border-dashed border-slate-800 text-xs text-slate-400 font-sans">
          No published fact-checks match {subject}. That is not a confirmation, only that no fact-checker has reviewed it yet.
        </p>
      )}

      {results && results.length > 0 && (
        <div className="space-y-2">
          {results.map((fc, i) => {
            const added = addedUrls.includes(fc.url);
            return (
              <div key={i} className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition">
                <a href={fc.url} target="_blank" rel="noreferrer" className="block">
                  <div className="flex items-center gap-2 font-mono text-[10px] mb-1">
                    <span className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 font-bold uppercase">
                      {fc.rating}
                    </span>
                    <span className="text-slate-400">{fc.publisher}</span>
                    {fc.review_date && <span className="text-slate-500">{new Date(fc.review_date).toLocaleDateString()}</span>}
                    <ExternalLink className="w-3 h-3 text-slate-500 ml-auto shrink-0" />
                  </div>
                  <p className="text-xs text-slate-200 font-sans leading-relaxed">
                    {fc.claimant && <span className="text-slate-400">{fc.claimant}: </span>}
                    {fc.claim}
                  </p>
                </a>
                {onAdd && (
                  <button
                    onClick={() => add(fc)}
                    disabled={added || adding !== null}
                    className="mt-2 inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-mono bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition disabled:opacity-50"
                  >
                    {added ? <Check className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
                    <span>{added ? 'Attached as evidence' : adding === fc.url ? 'Attaching...' : 'Add as evidence'}</span>
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
