export interface Source {
  id: string;
  name: string;
  feed_url: string;
  homepage_url?: string | null;
  source_type: string;
  region: string;
  bias_category?: string | null;
  reliability_score: number;
  is_active: boolean;
  last_fetched_at?: string | null;
  last_error?: string | null;
  created_at: string;
}

export interface SourceCreate {
  id: string;
  name: string;
  feed_url: string;
  homepage_url?: string;
  source_type?: string;
  region?: string;
  bias_category?: string | null;
  reliability_score?: number;
  is_active?: boolean;
}

export interface Article {
  id: string;
  source_id: string;
  cluster_id?: string | null;
  title: string;
  url: string;
  author?: string | null;
  summary?: string | null;
  published_at: string;
  ingested_at: string;
  topics?: string[];
}

export interface VerificationChecklistItem {
  id: string;
  label: string;
  passed: boolean;
  detail: string;
}

export interface EventCluster {
  id: string;
  headline: string;
  summary?: string | null;
  region: string;
  severity: 'routine' | 'escalating' | 'crisis' | string;
  status: string;
  first_seen: string;
  last_updated: string;
  article_count: number;
  explainer_score: number;
  key_actors: string[];
  chokepoints: string[];
  strategic_keywords: string[];
  articles?: Article[];

  // Multi-source triangulation metrics
  source_count?: number;
  source_names?: string[];
  triangulation_level?: 'triangulated' | 'corroborated' | 'unverified' | string;
  confidence_score?: number;
  independent_origin_count?: number;
  verification_label?: string;
  is_india_relevant?: boolean;
  has_domestic_source?: boolean;
  has_international_source?: boolean;
  verification_checklist?: VerificationChecklistItem[];
}

export interface FactCheck {
  claim: string;
  claimant?: string | null;
  claim_date?: string | null;
  publisher: string;
  rating: string;
  title?: string | null;
  url: string;
  review_date?: string | null;
  relevance?: 'same_claim' | 'related_topic' | 'unclassified' | null; // AI triage against the searched statement
  relevance_reason?: string | null;
}

export type ClaimStatus = 'unverified' | 'confirmed' | 'disputed' | 'false';

export interface ClaimEvidence {
  url: string;
  label: string;
  archive_url?: string | null;
}

export interface Claim {
  id: string;
  project_id: string;
  text: string;
  status: ClaimStatus;
  note?: string | null;
  evidence: ClaimEvidence[];
  created_at: string;
  status_changed_at?: string | null;
  ai_check?: ClaimCheck | null;
}

export interface PrimarySourceSuggestion {
  title: string;
  url: string;
  domain: string;
  snippet: string;
  official: boolean; // .gov / .mil / .int / UN / EU domain
  resolved: boolean; // false if the Google redirect couldn't be resolved (link may expire)
}

export interface PrimarySourceResults {
  summary: string; // AI-written summary of the search results
  sources: PrimarySourceSuggestion[]; // taken from Google Search grounding, not written by the model
  model: string;
}

export type SupportVerdictType = 'supported' | 'partly_supported' | 'contradicted' | 'not_addressed' | 'unverifiable' | 'not_checked';

export interface SupportResult {
  verdict: SupportVerdictType;
  explanation: string;
  quotes: { source_id: string; quote: string }[]; // verified verbatim against the source by the backend
}

export interface ClaimCheck extends SupportResult {
  sources: { id: string; title?: string; outlet?: string; url?: string }[];
  claim_text: string; // wording that was checked; differs from the claim if it was edited since
  model: string;
  created_at: string;
}


export interface ScanSummary {
  sources_scanned: number;
  new_articles_ingested: number;
  duplicate_articles_skipped: number;
  clusters_created_or_updated: number;
  errors: Array<{ source_id: string; error: string }>;
}

export interface DossierTimelineEvent {
  date: string;
  event: string;
  source: string;
  url: string;
}

export interface DossierStakeholder {
  actor: string;
  role: string;
  example_headline?: string | null;
}

export interface DossierGeography {
  chokepoints: string[];
  region: string;
  key_corridors: string[];
}

export interface ContradictionSide {
  source_id: string;
  quote: string;
  outlet?: string;
  title?: string;
  url?: string;
}

export interface DossierContradiction {
  issue: string;
  side_a: string;
  side_b: string;
  method?: 'ai_verified'; // absent for auto-paired headlines
  explanation?: string;
  a?: ContradictionSide;
  b?: ContradictionSide;
}

export interface DossierCitation {
  title: string;
  url: string;
  published_at: string;
  source_id: string;
}

export interface Dossier {
  id: string;
  project_id: string;
  timeline_events: DossierTimelineEvent[];
  stakeholders: DossierStakeholder[];
  geography: DossierGeography;
  contradictions: DossierContradiction[];
  citations: DossierCitation[];
  updated_at: string;
}

export interface ScriptAct {
  act_number: number;
  title: string;
  target_timestamp: string;
  narration_lead: string;
  key_questions: string[];
  visual_cues: string[];
}

export interface HookVariant {
  label: string;
  narration: string;
  visual_cue: string;
}

export interface ScriptOutline {
  id: string;
  project_id: string;
  acts: ScriptAct[];
  hook_variants: HookVariant[];
  visual_prompts: string[];
  updated_at: string;
}

export interface Project {
  id: string;
  title: string;
  working_slug: string;
  target_duration_mins: number;
  status: 'concept' | 'researching' | 'scripting' | 'storyboarding' | 'ready' | string;
  selected_angle?: string | null;
  cluster_id?: string | null;
  created_at: string;
  updated_at: string;
  dossier?: Dossier | null;
  script_outline?: ScriptOutline | null;
}

export interface NarrativeAngleOption {
  id: string;
  title: string;
  premise: string;
  hook: string;
  tone: string;
  key_tension: string;
}

export interface ScriptSource {
  id: string; // S# for articles, C# for Claim Ledger entries
  kind: 'article' | 'claim';
  title?: string;
  outlet?: string;
  url?: string;
  published_at?: string;
  text?: string;
  status?: ClaimStatus;
}

export interface ScriptBeat {
  kind: 'fact' | 'analysis' | 'transition';
  narration: string;
  citations: string[];
  broll?: string;
  issues?: string[]; // set by the backend's citation check
  support?: SupportResult; // set by the AI citation check
}

export interface NarrationScript {
  id: string;
  project_id: string;
  content: {
    title: string;
    logline: string;
    acts: { title: string; timecode: string; beats: ScriptBeat[] }[];
    open_questions: string[];
  };
  sources: ScriptSource[];
  stats: {
    beats: number;
    fact_beats: number;
    fact_beats_verified: number;
    beats_flagged: number;
    needs_source: number;
    word_count: number;
    target_words: number;
    support?: Record<SupportVerdictType, number>;
  };
  model: string;
  created_at: string;
}

export interface ReadinessChecklistItem {
  id: string;
  label: string;
  passed: boolean;
  detail: string;
}

export interface ProjectReadiness {
  project_id: string;
  score: number;
  status: 'ready' | 'needs_review' | 'unverified' | string;
  total_claims: number;
  confirmed_claims: number;
  unverified_claims: number;
  disputed_claims: number;
  false_claims: number;
  total_sources: number;
  independent_origins: number;
  script_support_checked: boolean;
  script_verdict_summary: Record<string, number>;
  checklist: ReadinessChecklistItem[];
  warnings: string[];
}

export interface SourceSheetCitation {
  type: string;
  id: string;
  text: string;
  status: string;
  evidence_urls: string[];
  archive_urls: string[];
  verbatim_quotes: string[];
  outlet?: string | null;
}

export interface ProjectSourceSheet {
  project_id: string;
  title: string;
  generated_at: string;
  readiness_score: number;
  citations: SourceSheetCitation[];
  sources: any[];
  markdown: string;
}

