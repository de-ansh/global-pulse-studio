import React, { useEffect, useState } from 'react';
import { Claim, ClaimStatus, FactCheck, PrimarySourceResults } from '../../types';
import { api } from '../../api/client';
import { FactChecks } from '../radar/FactChecks';
import { SupportVerdict } from '../studio/SupportVerdict';
import { ListChecks, Trash2, ExternalLink, Plus, SearchCheck, ShieldCheck, Landmark, Check, ChevronDown } from 'lucide-react';
import { AI_DISABLED_HINT, useFeatures } from '../../features';

// One-click verdicts are offered only where the AI's verified quotes point clearly one way.
const SUGGESTED_STATUS: Partial<Record<string, ClaimStatus>> = { supported: 'confirmed', contradicted: 'false' };

interface ClaimLedgerProps {
  projectId: string;
}

const STATUS_STYLES: Record<ClaimStatus, string> = {
  unverified: 'bg-slate-800 text-slate-300 border-slate-700',
  confirmed: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
  disputed: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
  false: 'bg-rose-500/15 text-rose-300 border-rose-500/40',
};

export const ClaimLedger: React.FC<ClaimLedgerProps> = ({ projectId }) => {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [newText, setNewText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [factCheckOpen, setFactCheckOpen] = useState<string | null>(null);
  const [aiChecking, setAiChecking] = useState<string | null>(null);
  const [finding, setFinding] = useState<string | null>(null);
  const [moreOpen, setMoreOpen] = useState<string | null>(null);
  const features = useFeatures();
  const [primary, setPrimary] = useState<Record<string, PrimarySourceResults>>({});

  const findPrimarySources = (claim: Claim) => {
    setFinding(claim.id);
    run(async () => {
      const found = await api.suggestPrimarySources(projectId, claim.id);
      setPrimary((prev) => ({ ...prev, [claim.id]: found }));
    }).finally(() => setFinding(null));
  };

  const attachPrimary = (claim: Claim, url: string, label: string) =>
    run(async () => {
      replace(await api.updateClaim(projectId, claim.id, { evidence: [...claim.evidence, { url, label: label.slice(0, 200) }] }));
    });

  const runAiCheck = (claim: Claim) => {
    setAiChecking(claim.id);
    run(async () => replace(await api.checkClaim(projectId, claim.id))).finally(() => setAiChecking(null));
  };

  useEffect(() => {
    setError(null);
    api.getClaims(projectId).then(setClaims).catch((err) => setError(err.message));
  }, [projectId]);

  const run = async (action: () => Promise<void>) => {
    setError(null);
    try {
      await action();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const replace = (updated: Claim) => setClaims((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));

  const addClaim = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newText.trim()) return;
    run(async () => {
      const created = await api.createClaim(projectId, { text: newText.trim() });
      setClaims((prev) => [...prev, created]);
      setNewText('');
    });
  };

  const addEvidence = (claim: Claim, form: HTMLFormElement) => {
    const data = new FormData(form);
    const url = String(data.get('url') || '').trim();
    if (!url) return;
    run(async () => {
      const evidence = [...claim.evidence, { url, label: String(data.get('label') || '').trim() }];
      replace(await api.updateClaim(projectId, claim.id, { evidence }));
      form.reset();
    });
  };

  // A fact-check becomes evidence labelled with its verdict; the claim's own verdict stays the creator's call.
  const addFactCheckEvidence = async (claim: Claim, fc: FactCheck) => {
    const label = `Fact-check: ${fc.rating} (${fc.publisher})`.slice(0, 200);
    replace(await api.updateClaim(projectId, claim.id, { evidence: [...claim.evidence, { url: fc.url, label }] }));
  };

  const removeEvidence = (claim: Claim, index: number) =>
    run(async () => {
      replace(await api.updateClaim(projectId, claim.id, { evidence: claim.evidence.filter((_, i) => i !== index) }));
    });

  const confirmedCount = claims.filter((c) => c.status === 'confirmed').length;

  return (
    <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-4">
      <h3 className="font-display font-bold text-base text-white flex items-center gap-2">
        <ListChecks className="w-4 h-4 text-emerald-400" />
        <span>Claim Ledger</span>
        <span className="text-xs font-mono font-normal text-slate-400 ml-auto">
          {confirmedCount} of {claims.length} confirmed
        </span>
      </h3>
      <p className="text-xs text-slate-400">
        List each fact your script depends on, attach primary evidence, and record your verdict. Unconfirmed claims are flagged in the export.
      </p>

      {error && (
        <p role="alert" className="p-3 rounded-xl bg-rose-950/40 border border-rose-800/50 text-xs text-rose-200 font-mono">
          {error}
        </p>
      )}

      <form onSubmit={addClaim} className="flex gap-2">
        <label htmlFor="new-claim" className="sr-only">New claim</label>
        <input
          id="new-claim"
          value={newText}
          onChange={(e) => setNewText(e.target.value)}
          maxLength={1000}
          placeholder='e.g. "Tanker seized in Strait of Hormuz on 20 Oct"'
          className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500"
        />
        <button
          type="submit"
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-mono bg-cyan-600 hover:bg-cyan-500 text-white transition"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Add Claim</span>
        </button>
      </form>

      <div className="space-y-3">
        {claims.map((claim) => (
          <div key={claim.id} className="p-4 rounded-xl bg-slate-950/80 border border-slate-800/80 space-y-3">
            <div className="flex items-start gap-3">
              <div className="flex-1 space-y-1">
                <p className="text-sm text-slate-100">{claim.text}</p>
                {/* Epistemic Stance Indicator */}
                {claim.epistemic_level === 'official_attribution' ? (
                  <div className="flex items-center gap-1.5 text-[11px] font-mono text-purple-300">
                    <span className="px-2 py-0.5 rounded bg-purple-950/60 border border-purple-800/50 font-semibold uppercase">
                      Attributed Speech
                    </span>
                    <span className="text-slate-400">
                      {claim.attributed_to ? `Claimed by: ${claim.attributed_to}` : 'Official statement (maintain attribution in script)'}
                    </span>
                  </div>
                ) : claim.epistemic_level === 'unattributed_rumor' ? (
                  <div className="flex items-center gap-1.5 text-[11px] font-mono text-amber-300">
                    <span className="px-2 py-0.5 rounded bg-amber-950/60 border border-amber-800/50 font-semibold uppercase">
                      Unconfirmed Rumor
                    </span>
                    <span className="text-amber-400/80">
                      Anonymous or social media source; secondary corroboration required before script lock.
                    </span>
                  </div>
                ) : claim.epistemic_level === 'analysis_or_opinion' ? (
                  <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400">
                    <span className="px-2 py-0.5 rounded bg-slate-800/80 border border-slate-700/60 font-semibold uppercase">
                      Assessment
                    </span>
                    <span className="text-slate-500">
                      Analytical projection or opinion; narrate as viewpoint.
                    </span>
                  </div>
                ) : null}
              </div>
              <label className="sr-only" htmlFor={`status-${claim.id}`}>Verdict</label>
              <select
                id={`status-${claim.id}`}
                value={claim.status}
                onChange={(e) =>
                  run(async () => replace(await api.updateClaim(projectId, claim.id, { status: e.target.value as ClaimStatus })))
                }
                className={`text-xs font-mono font-bold uppercase rounded-lg border px-2 py-1 focus:outline-none ${STATUS_STYLES[claim.status]}`}
              >
                <option value="unverified">Unverified</option>
                <option value="confirmed">Confirmed</option>
                <option value="disputed">Disputed</option>
                <option value="false">False</option>
              </select>
              <button
                onClick={() => {
                  if (window.confirm('Delete this claim?')) {
                    run(async () => {
                      await api.deleteClaim(projectId, claim.id);
                      setClaims((prev) => prev.filter((c) => c.id !== claim.id));
                    });
                  }
                }}
                className="p-1 text-slate-500 hover:text-rose-400 transition"
                aria-label="Delete claim"
                title="Delete claim"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>

            {claim.status_changed_at && (
              <p className="text-[10px] font-mono text-slate-500">
                Verdict set {new Date(claim.status_changed_at).toLocaleString()}
              </p>
            )}

            {claim.evidence.length > 0 && (
              <ul className="space-y-1">
                {claim.evidence.map((ev, i) => (
                  <li key={i} className="flex min-w-0 items-center gap-2 text-xs">
                    <a href={ev.url} target="_blank" rel="noreferrer" title={ev.label || ev.url} className="flex min-w-0 items-center gap-1 text-cyan-300 hover:text-cyan-200">
                      <ExternalLink className="w-3 h-3 shrink-0" />
                      <span className="truncate min-w-0">{ev.label || ev.url}</span>
                    </a>
                    {ev.archive_url && (
                      <a
                        href={ev.archive_url}
                        target="_blank"
                        rel="noreferrer"
                        title="Open Wayback Machine archive permalink"
                        className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] font-mono text-slate-400 hover:text-cyan-300 border border-slate-700/60 shrink-0"
                      >
                        archive
                      </a>
                    )}
                    <button
                      onClick={() => removeEvidence(claim, i)}
                      className="text-slate-500 hover:text-rose-400"
                      aria-label={`Remove evidence ${ev.label || ev.url}`}
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </li>
                ))}
              </ul>
            )}

              {claim.ai_check && (
                <div className="p-3 rounded-lg bg-slate-900/70 border border-slate-800 space-y-2">
                  <SupportVerdict
                    result={claim.ai_check}
                    sources={Object.fromEntries(claim.ai_check.sources.map((s) => [s.id, s]))}
                  />
                  <p className="text-[10px] font-mono text-slate-500">
                    Checked against {claim.ai_check.sources.length} source(s) · {claim.ai_check.model} ·{' '}
                    {new Date(claim.ai_check.created_at).toLocaleString()}
                    {claim.ai_check.claim_text !== claim.text && (
                      <span className="text-amber-300"> · claim edited since this check; re-run it</span>
                    )}
                  </p>
                  {SUGGESTED_STATUS[claim.ai_check.verdict] && claim.status !== SUGGESTED_STATUS[claim.ai_check.verdict] && (
                    <button
                      onClick={() =>
                        run(async () =>
                          replace(await api.updateClaim(projectId, claim.id, { status: SUGGESTED_STATUS[claim.ai_check!.verdict] }))
                        )
                      }
                      className="px-2 py-1 rounded-lg text-[11px] font-mono bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
                    >
                      Mark as {SUGGESTED_STATUS[claim.ai_check.verdict]} (you have read the quotes)
                    </button>
                  )}
                </div>
              )}

            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => runAiCheck(claim)}
                disabled={aiChecking !== null || !features.ai}
                title={features.ai ? 'Compare this claim with the story\'s reports and your evidence' : AI_DISABLED_HINT}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-700 hover:bg-emerald-600 text-white transition disabled:opacity-50"
              >
                <ShieldCheck className={`w-3.5 h-3.5 ${aiChecking === claim.id ? 'animate-pulse' : ''}`} />
                <span>{aiChecking === claim.id ? 'Checking...' : claim.ai_check ? 'Verify again' : 'Verify with AI'}</span>
              </button>
              <button
                onClick={() => setMoreOpen(moreOpen === claim.id ? null : claim.id)}
                aria-expanded={moreOpen === claim.id}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
              >
                <span>More</span>
                <ChevronDown className={`w-3.5 h-3.5 transition ${moreOpen === claim.id ? 'rotate-180' : ''}`} />
              </button>
              {claim.note && moreOpen !== claim.id && <span className="text-[11px] text-slate-500 truncate">Note: {claim.note}</span>}
            </div>

            {moreOpen === claim.id && (
              <div className="space-y-3 pt-1 border-t border-slate-800/80">
                <div className="flex flex-wrap gap-2 pt-3">
                  <button
                    onClick={() => findPrimarySources(claim)}
                    disabled={finding !== null || !features.ai}
                    title={features.ai ? undefined : AI_DISABLED_HINT}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-sky-300 border border-slate-700 transition disabled:opacity-50"
                  >
                    <Landmark className={`w-3.5 h-3.5 ${finding === claim.id ? 'animate-pulse' : ''}`} />
                    <span>{finding === claim.id ? 'Searching the web...' : 'Find primary sources'}</span>
                  </button>
                  <button
                    onClick={() => setFactCheckOpen(factCheckOpen === claim.id ? null : claim.id)}
                    aria-expanded={factCheckOpen === claim.id}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-amber-300 border border-slate-700 transition"
                  >
                    <SearchCheck className="w-3.5 h-3.5" />
                    <span>{factCheckOpen === claim.id ? 'Hide fact-checks' : 'Search published fact-checks'}</span>
                  </button>
                </div>
              {primary[claim.id] && (
                <div className="p-3 rounded-lg bg-slate-900/70 border border-slate-800 space-y-2">
                  <p className="text-[10px] font-mono uppercase tracking-wider text-slate-500">AI summary of what the search found (verify in the sources)</p>
                  <p className="text-xs text-slate-300 whitespace-pre-line">{primary[claim.id].summary}</p>
                  {primary[claim.id].sources.length === 0 && (
                    <p className="text-xs text-slate-500">The search returned no linkable sources.</p>
                  )}
                  {primary[claim.id].sources.map((src) => {
                    const added = claim.evidence.some((e) => e.url === src.url);
                    return (
                      <div key={src.url} className="p-2 rounded-lg bg-slate-950/70 border border-slate-800 space-y-1">
                        <div className="flex items-center gap-2 text-[11px] font-mono">
                          {src.official && (
                            <span className="px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-300 border border-sky-500/30 text-[9px] font-bold uppercase">
                              Official
                            </span>
                          )}
                          <a href={src.url} target="_blank" rel="noreferrer" className="text-cyan-300 hover:text-cyan-200 flex min-w-0 items-center gap-1 truncate">
                            {src.domain} <ExternalLink className="w-3 h-3 shrink-0" />
                          </a>
                          {!src.resolved && <span className="text-amber-300 text-[10px]">temporary link</span>}
                          <button
                            onClick={() => attachPrimary(claim, src.url, `${src.official ? 'Official source' : 'Source'}: ${src.domain}`)}
                            disabled={added}
                            className="ml-auto inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 disabled:opacity-50"
                          >
                            {added ? <Check className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
                            <span>{added ? 'Attached' : 'Add as evidence'}</span>
                          </button>
                        </div>
                        {src.snippet && <p className="text-[11px] text-slate-400">{src.snippet}</p>}
                      </div>
                    );
                  })}
                </div>
              )}
                {factCheckOpen === claim.id && (
                  <FactChecks
                    load={() => api.getClaimFactChecks(projectId, claim.id)}
                    subject="this claim"
                    onAdd={(fc) => addFactCheckEvidence(claim, fc)}
                    addedUrls={claim.evidence.map((e) => e.url)}
                  />
                )}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                addEvidence(claim, e.currentTarget);
              }}
              className="flex flex-col sm:flex-row gap-2"
            >
              <input
                name="url"
                type="url"
                required
                placeholder="Add evidence: paste a link"
                aria-label="Evidence URL"
                className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
              />
              <input
                name="label"
                maxLength={200}
                placeholder="Label"
                aria-label="Evidence label"
                className="sm:w-40 bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
              />
              <button type="submit" className="px-2.5 py-1.5 rounded-lg text-xs font-mono bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition">
                Attach
              </button>
            </form>
            <textarea
              defaultValue={claim.note || ''}
              onBlur={(e) => {
                if (e.target.value !== (claim.note || '')) {
                  const note = e.target.value;
                  run(async () => replace(await api.updateClaim(projectId, claim.id, { note })));
                }
              }}
              maxLength={4000}
              rows={2}
              placeholder="Why this verdict? (saved when you click away)"
              aria-label="Verdict note"
              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-cyan-500"
            />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
