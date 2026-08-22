const API_BASE = 'http://localhost:8000/api/v1';

export interface Project {
  id: string;
  owner_id: string;
  name: string;
  description: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ProjectsResponse {
  projects: Project[];
  total: number;
}

export function parseProjectsResponse(data: unknown): Project[] {
  if (data && typeof data === 'object' && Array.isArray((data as ProjectsResponse).projects)) {
    return (data as ProjectsResponse).projects;
  }
  throw new Error('Invalid projects response');
}

export const projectsApi = {
  async list(): Promise<Project[]> {
    const res = await fetch(`${API_BASE}/projects`);
    if (!res.ok) throw new Error(`HTTP ${res.status} — /projects`);
    return parseProjectsResponse(await res.json());
  },

  async create(name: string, description?: string): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.trim(), description }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} — POST /projects`);
    return res.json() as Promise<Project>;
  },
};