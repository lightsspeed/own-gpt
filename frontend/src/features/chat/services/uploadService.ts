import type { AttachmentFile } from '../types';

const API_BASE = 'http://localhost:8000/api/v1';

export const uploadService = {
  async uploadFile(file: File, onProgress?: (progress: number) => void): Promise<{ url: string; name: string; size: number; type: string }> {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const xhr = new XMLHttpRequest();
      const promise = new Promise<{ url: string; name: string; size: number; type: string }>((resolve, reject) => {
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable && onProgress) {
            onProgress(Math.round((e.loaded / e.total) * 100));
          }
        });
        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const data = JSON.parse(xhr.responseText);
              resolve({ url: data.url || data.filename || '', name: file.name, size: file.size, type: file.type });
            } catch {
              resolve({ url: '', name: file.name, size: file.size, type: file.type });
            }
          } else {
            reject(new Error(`Upload failed: ${xhr.status}`));
          }
        });
        xhr.addEventListener('error', () => reject(new Error('Network error during upload')));
        xhr.addEventListener('abort', () => reject(new Error('Upload aborted')));
      });

      xhr.open('POST', `${API_BASE}/chat/upload`);
      xhr.send(formData);

      return await promise;
    } catch {
      // Fallback: simulate upload for demo
      return new Promise(resolve => {
        let progress = 0;
        const interval = setInterval(() => {
          progress += Math.random() * 30;
          if (progress >= 100) {
            progress = 100;
            clearInterval(interval);
            onProgress?.(100);
            resolve({ url: '', name: file.name, size: file.size, type: file.type });
          } else {
            onProgress?.(Math.round(progress));
          }
        }, 200);
      });
    }
  },

  canPreview(type: string): boolean {
    return type.startsWith('image/') || type === 'application/pdf' || type.startsWith('text/');
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

  ALLOWED_TYPES: ['.pdf', '.txt', '.md', '.csv', '.json', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.py', '.js', '.ts', '.tsx', '.jsx', '.yaml', '.yml', '.toml', '.env', '.log'],
  MAX_SIZE: 10 * 1024 * 1024, // 10 MB
};
