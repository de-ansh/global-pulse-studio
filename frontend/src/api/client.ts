import {
  EventCluster,
  ScanSummary,
  Source,
  SourceCreate,
  Project,
  Dossier,
  ScriptOutline,
  NarrativeAngleOption,
  FactCheck,
  NarrationScript,
  PrimarySourceResults,
  Claim,
  ClaimEvidence,
  ClaimStatus,
  ProjectReadiness,
  ProjectSourceSheet,
} from '../types';

const API_BASE = '/api';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const errorText = await res.text();
    let detail = errorText;
    try {
      const json = JSON.parse(errorText);
      detail = json.detail || json.message || errorText;
    } catch {
      // not JSON
    }
    throw new Error(`[${res.status}] ${detail || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // Radar & Intelligence
  async scanFeeds(): Promise<ScanSummary> {
    const res = await fetch(`${API_BASE}/radar/scan`, { method: 'POST' });
    return handleResponse<ScanSummary>(res);
  },

  async getClusters(params?: {
    region?: string;
    severity?: string;
    minScore?: number;
    focus?: string;
    limit?: number;
    offset?: number;
  }): Promise<EventCluster[]> {
    const query = new URLSearchParams();
    if (params?.region) query.set('region', params.region);
    if (params?.severity) query.set('severity', params.severity);
    if (params?.minScore !== undefined && params.minScore !== null) query.set('min_score', params.minScore.toString());
    if (params?.focus) query.set('focus', params.focus);
    query.set('limit', (params?.limit || 50).toString());
    if (params?.offset) query.set('offset', params.offset.toString());

    const res = await fetch(`${API_BASE}/radar/clusters?${query.toString()}`);
    return handleResponse<EventCluster[]>(res);
  },

  async getIndiaClusters(params?: {
    severity?: string;
    triangulation?: string;
    limit?: number;
  }): Promise<EventCluster[]> {
    const query = new URLSearchParams();
    if (params?.severity) query.set('severity', params.severity);
    if (params?.triangulation) query.set('triangulation', params.triangulation);
    query.set('limit', (params?.limit || 50).toString());

    const res = await fetch(`${API_BASE}/radar/india?${query.toString()}`);
    return handleResponse<EventCluster[]>(res);
  },

  async getClusterDetail(clusterId: string): Promise<EventCluster> {
    const res = await fetch(`${API_BASE}/radar/clusters/${encodeURIComponent(clusterId)}`);
    return handleResponse<EventCluster>(res);
  },

  async getClaimFactChecks(projectId: string, claimId: string): Promise<FactCheck[]> {
    const res = await fetch(
      `${API_BASE}/projects/${encodeURIComponent(projectId)}/claims/${encodeURIComponent(claimId)}/factchecks`
    );
    return handleResponse<FactCheck[]>(res);
  },

  async getFactChecks(clusterId: string): Promise<FactCheck[]> {
    const res = await fetch(`${API_BASE}/radar/clusters/${encodeURIComponent(clusterId)}/factchecks`);
    return handleResponse<FactCheck[]>(res);
  },

  // Sources
  async getSources(): Promise<Source[]> {
    const res = await fetch(`${API_BASE}/radar/sources`);
    return handleResponse<Source[]>(res);
  },

  async seedSources(): Promise<Source[]> {
    const res = await fetch(`${API_BASE}/radar/sources/seed`, { method: 'POST' });
    return handleResponse<Source[]>(res);
  },

  async createSource(source: SourceCreate): Promise<Source> {
    const res = await fetch(`${API_BASE}/radar/sources`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(source),
    });
    return handleResponse<Source>(res);
  },

  async updateSource(sourceId: string, data: Partial<SourceCreate>): Promise<Source> {
    const res = await fetch(`${API_BASE}/radar/sources/${encodeURIComponent(sourceId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse<Source>(res);
  },

  async deleteSource(sourceId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/radar/sources/${encodeURIComponent(sourceId)}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`[${res.status}] ${err}`);
    }
  },

  // Projects
  async getProjects(): Promise<Project[]> {
    const res = await fetch(`${API_BASE}/projects`);
    return handleResponse<Project[]>(res);
  },

  async getProject(projectId: string): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}`);
    return handleResponse<Project>(res);
  },

  async createProject(data: {
    title: string;
    cluster_id?: string;
    target_duration_mins?: number;
    selected_angle?: string;
  }): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse<Project>(res);
  },

  async updateProject(
    projectId: string,
    data: {
      title?: string;
      target_duration_mins?: number;
      status?: string;
      selected_angle?: string;
    }
  ): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse<Project>(res);
  },

  async deleteProject(projectId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`[${res.status}] ${err}`);
    }
  },

  // Claim Ledger
  async getClaims(projectId: string): Promise<Claim[]> {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/claims`);
    return handleResponse<Claim[]>(res);
  },

  async createClaim(projectId: string, data: { text: string; evidence?: ClaimEvidence[] }): Promise<Claim> {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/claims`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse<Claim>(res);
  },

  async updateClaim(
    projectId: string,
    claimId: string,
    data: { text?: string; status?: ClaimStatus; note?: string; evidence?: ClaimEvidence[] }
  ): Promise<Claim> {
    const res = await fetch(
      `${API_BASE}/projects/${encodeURIComponent(projectId)}/claims/${encodeURIComponent(claimId)}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }
    );
    return handleResponse<Claim>(res);
  },

  async deleteClaim(projectId: string, claimId: string): Promise<void> {
    const res = await fetch(
      `${API_BASE}/projects/${encodeURIComponent(projectId)}/claims/${encodeURIComponent(claimId)}`,
      { method: 'DELETE' }
    );
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`[${res.status}] ${err}`);
    }
  },

  // Dossier & Angles & Outline
  async generateDossier(projectId: string): Promise<Dossier> {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/dossier/generate`, {
      method: 'POST',
    });
    return handleResponse<Dossier>(res);
  },

  async findContradictions(projectId: string): Promise<Dossier> {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/dossier/contradictions`, { method: 'POST' });
    return handleResponse<Dossier>(res);
  },

  async getProjectAngles(projectId: string): Promise<NarrativeAngleOption[]> {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/angles`, {
      method: 'POST',
    });
    return handleResponse<NarrativeAngleOption[]>(res);
  },

  async generateOutline(projectId: string): Promise<ScriptOutline> {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/outline/generate`, {
      method: 'POST',
    });
    return handleResponse<ScriptOutline>(res);
  },

  async getScript(projectId: string): Promise<NarrationScript> {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/script`);
    return handleResponse<NarrationScript>(res);
  },

  async generateScript(projectId: string): Promise<NarrationScript> {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/script/generate`, { method: 'POST' });
    return handleResponse<NarrationScript>(res);
  },

  async extractClaims(projectId: string): Promise<Claim[]> {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/claims/extract`, { method: 'POST' });
    return handleResponse<Claim[]>(res);
  },

  async checkScript(projectId: string): Promise<NarrationScript> {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/script/check`, { method: 'POST' });
    return handleResponse<NarrationScript>(res);
  },

  async suggestPrimarySources(projectId: string, claimId: string): Promise<PrimarySourceResults> {
    const res = await fetch(
      `${API_BASE}/projects/${encodeURIComponent(projectId)}/claims/${encodeURIComponent(claimId)}/sources/suggest`,
      { method: 'POST' }
    );
    return handleResponse<PrimarySourceResults>(res);
  },

  async checkClaim(projectId: string, claimId: string): Promise<Claim> {
    const res = await fetch(
      `${API_BASE}/projects/${encodeURIComponent(projectId)}/claims/${encodeURIComponent(claimId)}/check`,
      { method: 'POST' }
    );
    return handleResponse<Claim>(res);
  },

  async exportMarkdown(projectId: string): Promise<string> {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/export`);
    if (!res.ok) {
      throw new Error(`Export failed: [${res.status}] ${res.statusText}`);
    }
    return res.text();
  },

  async getProjectReadiness(projectId: string): Promise<ProjectReadiness> {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/readiness`);
    return handleResponse<ProjectReadiness>(res);
  },

  async getSourceSheet(projectId: string): Promise<ProjectSourceSheet> {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/source-sheet`);
    return handleResponse<ProjectSourceSheet>(res);
  },
};
