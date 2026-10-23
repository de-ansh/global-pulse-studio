import React from 'react';
import { SupportResult } from '../../types';

export const VERDICT_STYLES: Record<string, { label: string; className: string }> = {
  supported: { label: 'Supported', className: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40' },
  partly_supported: { label: 'Partly supported', className: 'bg-amber-500/15 text-amber-300 border-amber-500/40' },
  contradicted: { label: 'Contradicted', className: 'bg-rose-500/15 text-rose-300 border-rose-500/40' },
  not_addressed: { label: 'Not addressed by sources', className: 'bg-slate-800 text-slate-300 border-slate-600' },
  unverifiable: { label: 'Unverifiable (AI quote not found)', className: 'bg-rose-950/60 text-rose-300 border-rose-800/60' },
  not_checked: { label: 'Not checked', className: 'bg-slate-800 text-slate-400 border-slate-700' },
};

interface SourceRef {
  id: string;
  title?: string;
  outlet?: string;
  url?: string;
}

interface SupportVerdictProps {
  result: SupportResult;
  sources: Record<string, SourceRef>;
}

/** AI evidence-check outcome: verdict badge, explanation, and the verbatim (code-verified) quotes it rests on. */
export const SupportVerdict: React.FC<SupportVerdictProps> = ({ result, sources }) => {
  const style = VERDICT_STYLES[result.verdict] || VERDICT_STYLES.not_checked;
  return (
    <div className="space-y-1.5">
      <div className="flex items-start gap-2 text-[11px]">
        <span className={`shrink-0 px-1.5 py-0.5 rounded border font-mono font-bold uppercase text-[9px] ${style.className}`}>
          AI: {style.label}
        </span>
        {result.explanation && <span className="text-slate-400">{result.explanation}</span>}
      </div>
      {result.quotes.map((q, i) => {
        const src = sources[q.source_id];
        return (
          <blockquote key={i} className="pl-3 border-l-2 border-slate-700 text-xs text-slate-300 italic">
            “{q.quote}”{' '}
            <span className="not-italic font-mono text-[10px] text-slate-500">
              {src?.url ? (
                <a href={src.url} target="_blank" rel="noreferrer" className="text-cyan-400 hover:text-cyan-300">
                  [{q.source_id}] {src.outlet}
                </a>
              ) : (
                `[${q.source_id}] ${src?.outlet || ''}`
              )}
            </span>
          </blockquote>
        );
      })}
    </div>
  );
};
