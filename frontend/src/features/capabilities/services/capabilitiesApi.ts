const API_BASE = 'http://localhost:8000/api/v1';

export interface Capability {
  name: string;
  owner: string;
  dependencies: string[];
  lifecycle_stage: string;
  maturity: string;
  artifacts: string[];
  api_prefix: string;
}

export interface CapabilitiesResponse {
  count: number;
  capabilities: Record<string, Capability>;
}

export const capabilitiesApi = {
  async list(): Promise<CapabilitiesResponse> {
    const res = await fetch(`${API_BASE}/capabilities`);
    if (!res.ok) throw new Error(`HTTP ${res.status} — /capabilities`);
    return await res.json();
  },

  async get(id: string): Promise<Capability | null> {
    const res = await fetch(`${API_BASE}/capabilities/${encodeURIComponent(id)}`);
    if (!res.ok) return null;
    return await res.json();
  },
};
