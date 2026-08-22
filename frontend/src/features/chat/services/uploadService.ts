const API_BASE = 'http://localhost:8000/api/v1';

const JOB_POLL_INTERVAL_MS = 1500;
const JOB_POLL_MAX_ATTEMPTS = 160;

interface UploadResponse {
  filename: string;
  status: string;
  chunks: number;
  job_id?: string;
  message?: string;
  file_type?: string;
}

async function waitForIngestion(jobId: string, onProgress?: (progress: number) => void): Promise<UploadResponse> {
  let attempts = 0;
  for (;;) {
    const res = await fetch(`${API_BASE}/ingestion/jobs/${jobId}`);
    if (!res.ok) throw new Error(`Ingestion check failed (HTTP ${res.status})`);
    const job = await res.json();
    if (job.status === 'failed') throw new Error(job.error || 'Document ingestion failed');
    if (job.status === 'completed' || job.status === 'duplicate') return job;
    onProgress?.(99);
    if (++attempts >= JOB_POLL_MAX_ATTEMPTS) throw new Error('Document ingestion timed out');
    await new Promise(r => setTimeout(r, JOB_POLL_INTERVAL_MS));
  }
}

export const uploadService = {
  async uploadFile(
    file: File,
    onProgress?: (progress: number) => void,
    projectId?: string | null,
  ): Promise<{ url: string; name: string; size: number; type: string }> {
    const formData = new FormData();
    formData.append('file', file);
    if (projectId) formData.append('project_id', projectId);

    const xhr = new XMLHttpRequest();
    const uploaded = await new Promise<UploadResponse>((resolve, reject) => {
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress(Math.min(Math.round((e.loaded / e.total) * 95), 95));
        }
      });
      xhr.addEventListener('load', () => {
        let data: UploadResponse;
        try {
          data = JSON.parse(xhr.responseText);
        } catch {
          reject(new Error('Invalid upload response'));
          return;
        }
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(data);
        } else {
          const msg = typeof data.message === 'string' ? data.message : (data as any).detail
          reject(new Error(typeof msg === 'string' ? msg : `Upload failed: ${xhr.status}`));
        }
      });
      xhr.addEventListener('error', () => reject(new Error('Network error during upload')));
      xhr.addEventListener('abort', () => reject(new Error('Upload aborted')));
      xhr.open('POST', `${API_BASE}/documents/upload`);
      xhr.send(formData);
    });

    if (uploaded.status !== 'duplicate') {
      if (!uploaded.job_id) throw new Error('Upload did not return an ingestion job id');
      await waitForIngestion(uploaded.job_id, onProgress);
    }
    onProgress?.(100);
    return { url: '', name: file.name, size: file.size, type: file.type };
  },

  canPreview(type: string): boolean {
    return type === 'application/pdf' || type.startsWith('text/');
  },

  readAsDataURL(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  },

  formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  },

  ALLOWED_TYPES: ['.pdf', '.txt', '.md'],
  MAX_SIZE: 10 * 1024 * 1024, // 10 MB
};