import type { ClaimValidation } from '@/features/chat/types';

const API_BASE = 'http://localhost:8000/api/v1';

export interface QualityReport {
  record_id: string;
  session_id: string;
  question: string;
  answer_mode: string;
  citation_valid: boolean;
  cited: number;
  required: number;
  unique_chunks: number;
  total_uses: number;
  warnings: string[];
  reason: string;
  claims_total: number;
  claims_supported: number;
  claims_unsupported: number;
  claims: ClaimValidation['claims'];
  created_at: string;
}

export const qualityApi = {
  async listReports(limit: number = 50): Promise<QualityReport[]> {
    const res = await fetch(`${API_BASE}/quality/reports?limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP ${res.status} — ${API_BASE}/quality/reports`);
    const data = await res.json();
    return data.reports || [];
  },

  async getReport(recordId: string): Promise<QualityReport | null> {
    const res = await fetch(`${API_BASE}/quality/reports/${encodeURIComponent(recordId)}`);
    if (!res.ok) return null;
    return await res.json();
  },
};
