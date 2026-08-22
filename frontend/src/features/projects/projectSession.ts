export const GENERAL_PROJECT_KEY = '__general__';

export const PROJECT_STORAGE_KEY = 'owngpt:active_project';

export interface SessionRegistry {
  [projectKey: string]: string;
}

export function projectSessionKey(projectId: string | null | undefined): string {
  return projectId || GENERAL_PROJECT_KEY;
}

export function ensureProjectSession(
  registry: SessionRegistry,
  projectId: string | null | undefined,
  createId: () => string,
): { registry: SessionRegistry; sessionId: string } {
  const key = projectSessionKey(projectId);
  const existing = registry[key];
  if (existing) return { registry, sessionId: existing };
  const id = createId();
  return { registry: { ...registry, [key]: id }, sessionId: id };
}

export function removeSessionFromRegistry(registry: SessionRegistry, sessionId: string): SessionRegistry {
  let changed = false;
  const next: SessionRegistry = {};
  for (const [key, id] of Object.entries(registry)) {
    if (id === sessionId) {
      changed = true;
      continue;
    }
    next[key] = id;
  }
  return changed ? next : registry;
}

export function persistActiveProject(projectId: string | null | undefined): void {
  if (typeof localStorage === 'undefined') return;
  if (projectId) {
    localStorage.setItem(PROJECT_STORAGE_KEY, projectId);
  } else {
    localStorage.removeItem(PROJECT_STORAGE_KEY);
  }
}

export function readActiveProject(): string | null {
  if (typeof localStorage === 'undefined') return null;
  return localStorage.getItem(PROJECT_STORAGE_KEY);
}