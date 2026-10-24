import React, { useEffect, useState } from 'react';
import { NarrationScript, ScriptSource } from '../../types';
import { api } from '../../api/client';
import { FileText, RefreshCw, AlertTriangle, HelpCircle, ExternalLink, ShieldCheck, ListPlus } from 'lucide-react';
import { SupportVerdict, VERDICT_STYLES } from './SupportVerdict';
import { AI_DISABLED_HINT, useFeatures } from '../../features';

interface ScriptPanelProps {
  projectId: string;
}

const KIND_STYLES: Record<string, string> = {
  fact: 'bg-cyan-950/60 text-cyan-300 border-cyan-800/40',
  analysis: 'bg-purple-950/60 text-purple-300 border-purple-800/40',
  transition: 'bg-slate-800 text-slate-400 border-slate-700',
};

const CLAIM_STYLES: Record<string, string> = {
  confirmed: 'text-emerald-300 border-emerald-700/50',
  unverified: 'text-slate-300 border-slate-600',
  disputed: 'text-amber-300 border-amber-700/50',
  false: 'text-rose-300 border-rose-700/50',
};

const CitationChip: React.FC<{ id: string; source?: ScriptSource }> = ({ id, source }) => {
  if (!source) {
    return (
      <span className="px-1.5 py-0.5 rounded border border-rose-700/60 text-rose-300 text-[10px] font-mono line-through" title="This source does not exist">
        {id}
      </span>
    );
  }
  if (source.kind === 'article') {
    return (
      <a
        href={source.url}
        target="_blank"
        rel="noreferrer"
        title={`${source.outlet}: ${source.title} (${source.published_at})`}
        className="px-1.5 py-0.5 rounded border border-cyan-800/60 text-cyan-300 hover:text-cyan-200 text-[10px] font-mono"
      >
        {id}
      </a>
    );
  }
  return (
    <span
      title={`Claim (${source.status}): ${source.text}`}
      className={`px-1.5 py-0.5 rounded border text-[10px] font-mono ${CLAIM_STYLES[source.status || 'unverified']}`}
    >
      {id}
    </span>
  );
};

export const ScriptPanel: React.FC<ScriptPanelProps> = ({ projectId }) => {
  const [script, setScript] = useState<NarrationScript | null>(null);
  const [generating, setGenerating] = useState(false);
  const [checking, setChecking] = useState(false);
  const features = useFeatures();
  const aiTitle = features.ai ? undefined : AI_DISABLED_HINT;
  const [extracting, setExtracting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setScript(null);
    setError(null);
    api
      .getScript(projectId)
      .then(setScript)
      .catch((err) => {
        if (!String(err.message).startsWith('[404]')) setError(err.message);
      });
  }, [projectId]);

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      setScript(await api.generateScript(projectId));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const extractClaims = async () => {
    setExtracting(true);
    setError(null);
    setNotice(null);
    try {
      const added = await api.extractClaims(projectId);
      setNotice(
        added.length
          ? `${added.length} claim(s) added to the Claim Ledger (War Room) as unverified, with the articles each line cites attached.`
          : 'No new checkable claims: everything in the script is already in the Claim Ledger.'
      );
    } catch (err: any) {
      setError(err.message);
    } finally {
      setExtracting(false);
    }
  };

  const checkCitations = async () => {
    setChecking(true);
    setError(null);
    try {
      setScript(await api.checkScript(projectId));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setChecking(false);
    }
  };

  const sourcesById = Object.fromEntries((script?.sources || []).map((s) => [s.id, s]));
  const stats = script?.stats;

  return (
    <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h3 className="font-display font-bold text-lg text-white flex items-center gap-2">
          <FileText className="w-4 h-4 text-emerald-400" />
          <span>Narration Script</span>
        </h3>
        <div className="flex flex-wrap gap-2">
        {script && (
          <button
            onClick={extractClaims}
            disabled={extracting || generating || !features.ai}
            title={aiTitle}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-mono font-semibold bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700 transition disabled:opacity-60"
          >
            <ListPlus className="w-3.5 h-3.5" />
            <span>{extracting ? 'Extracting claims...' : 'Add facts to Claim Ledger'}</span>
          </button>
        )}
        {script && (
          <button
            onClick={checkCitations}
            disabled={checking || generating || !features.ai}
            title={aiTitle}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-mono font-semibold bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700 transition disabled:opacity-60"
          >
            <ShieldCheck className={`w-3.5 h-3.5 ${checking ? 'animate-pulse' : ''}`} />
            <span>{checking ? 'Checking every line...' : 'Check citations with AI'}</span>
          </button>
        )}
        <button
          onClick={generate}
          disabled={generating || checking || !features.ai}
          title={aiTitle}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-mono font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition disabled:opacity-60"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${generating ? 'animate-spin' : ''}`} />
          <span>{generating ? 'Writing script (up to a minute)...' : script ? 'Rewrite Script' : 'Write Script'}</span>
        </button>
        </div>
      </div>
      <p className="text-xs text-slate-400">
        Written by Gemini from this event's reports [S#] and your Claim Ledger [C#] only. Every factual line must cite a source;
        citations are then checked in code, and anything unsupported is flagged below.
      </p>

      {!features.ai && (
        <p className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-400">{AI_DISABLED_HINT}</p>
      )}

      {error && (
        <p role="alert" className="p-3 rounded-xl bg-rose-950/40 border border-rose-800/50 text-xs text-rose-200 font-mono">
          {error}
        </p>
      )}

      {notice && (
        <p role="status" className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-800/50 text-xs text-emerald-200 font-mono">
          {notice}
        </p>
      )}

      {script && stats && (
        <>
          <div className="flex flex-wrap gap-2 text-[11px] font-mono">
            <span className="px-2 py-1 rounded-lg bg-emerald-950/50 border border-emerald-800/40 text-emerald-300">
              {stats.fact_beats_verified} of {stats.fact_beats} factual lines verified
            </span>
            <span className={`px-2 py-1 rounded-lg border ${stats.beats_flagged ? 'bg-amber-950/50 border-amber-800/40 text-amber-300' : 'bg-slate-900 border-slate-800 text-slate-400'}`}>
              {stats.beats_flagged} flagged
            </span>
            <span className="px-2 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-400">
              ~{stats.word_count} words (target {stats.target_words})
            </span>
            <span className="px-2 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-500">
              {script.model} · {new Date(script.created_at).toLocaleString()}
            </span>
          </div>
          {stats.support && (
            <div className="flex flex-wrap gap-1.5 text-[10px] font-mono" aria-label="AI citation check results">
              {Object.entries(stats.support)
                .filter(([, n]) => n > 0)
                .map(([v, n]) => (
                  <span key={v} className={`px-1.5 py-0.5 rounded border ${VERDICT_STYLES[v]?.className}`}>
                    {n} {VERDICT_STYLES[v]?.label.toLowerCase()}
                  </span>
                ))}
            </div>
          )}

          <div>
            <h4 className="font-display font-semibold text-base text-white">{script.content.title}</h4>
            <p className="text-xs text-slate-400 italic">{script.content.logline}</p>
          </div>

          {script.content.acts.map((act, ai) => (
            <div key={ai} className="space-y-2">
              <h5 className="font-mono text-xs font-bold text-purple-300">
                {act.title} <span className="text-slate-500">({act.timecode})</span>
              </h5>
              {act.beats.map((beat, bi) => (
                <div
                  key={bi}
                  className={`p-3 rounded-xl bg-slate-950/70 border ${beat.issues?.length ? 'border-amber-700/50' : 'border-slate-800'} space-y-1.5`}
                >
                  <div className="flex items-start gap-2">
                    <span className={`shrink-0 px-1.5 py-0.5 rounded border text-[9px] font-mono uppercase ${KIND_STYLES[beat.kind] || KIND_STYLES.transition}`}>
                      {beat.kind}
                    </span>
                    <p className="text-sm text-slate-100 leading-relaxed">{beat.narration}</p>
                  </div>
                  {(beat.citations?.length > 0 || beat.broll) && (
                    <div className="flex flex-wrap items-center gap-1.5 pl-1">
                      {beat.citations?.map((c) => <CitationChip key={c} id={c} source={sourcesById[c]} />)}
                      {beat.broll && <span className="text-[11px] text-slate-500 italic">B-roll: {beat.broll}</span>}
                    </div>
                  )}
                  {beat.support && <SupportVerdict result={beat.support} sources={sourcesById} />}
                  {beat.issues?.map((issue, ii) => (
                    <p key={ii} className="flex items-center gap-1.5 text-[11px] font-mono text-amber-300">
                      <AlertTriangle className="w-3 h-3 shrink-0" />
                      <span>{issue}</span>
                    </p>
                  ))}
                </div>
              ))}
            </div>
          ))}

          {script.content.open_questions?.length > 0 && (
            <div className="p-3 rounded-xl bg-amber-950/20 border border-amber-800/40 space-y-1">
              <h5 className="flex items-center gap-1.5 text-xs font-mono font-bold text-amber-300">
                <HelpCircle className="w-3.5 h-3.5" />
                <span>Open questions: source these before recording</span>
              </h5>
              <ul className="list-disc pl-5 text-xs text-slate-300 space-y-0.5">
                {script.content.open_questions.map((q, i) => <li key={i}>{q}</li>)}
              </ul>
            </div>
          )}

          <details className="text-xs">
            <summary className="cursor-pointer font-mono text-slate-400">Sources given to the writer ({script.sources.length})</summary>
            <ul className="mt-2 space-y-1">
              {script.sources.map((s) => (
                <li key={s.id} className="text-slate-300">
                  <span className="font-mono text-slate-500">[{s.id}]</span>{' '}
                  {s.kind === 'article' ? (
                    <a href={s.url} target="_blank" rel="noreferrer" className="text-cyan-300 hover:text-cyan-200 inline-flex items-center gap-1">
                      {s.title} <ExternalLink className="w-3 h-3" />
                    </a>
                  ) : (
                    <span>Claim ({s.status}): {s.text}</span>
                  )}
                  {s.kind === 'article' && <span className="text-slate-500"> · {s.outlet}, {s.published_at}</span>}
                </li>
              ))}
            </ul>
          </details>
        </>
      )}
    </div>
  );
};
