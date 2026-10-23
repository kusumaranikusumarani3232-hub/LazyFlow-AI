import type {
  HealthStatus,
  ModelStatus,
  OrganizeResponse,
  FileOrganizedItem,
  FileMetadata,
} from '../types';

// In production on Vercel, VITE_API_URL points to Render backend (e.g. https://lazyflow-ai.onrender.com).
// Locally with Vite dev proxy, empty string uses relative /api which Vite proxies to http://127.0.0.1:8000.
const RAW_API_BASE = (import.meta.env.VITE_API_URL || '').trim();
export const API_BASE = RAW_API_BASE.replace(/\/+$/, '');

export function getApiBaseUrl(): string {
  return API_BASE;
}

export function isApiConfigured(): boolean {
  if (import.meta.env.PROD) {
    return Boolean(API_BASE);
  }
  return true;
}

export interface SampleFileInfo {
  name: string;
  size: number;
  mime_type: string;
  hint: string;
  download_url: string;
}

/**
 * Robust fetch wrapper that distinguishes:
 * 1. Missing frontend configuration (VITE_API_URL absent in production)
 * 2. Network/CORS/Render sleep errors
 * 3. SPA HTML fallbacks where JSON was expected
 * 4. API HTTP error details returned by FastAPI
 */
async function safeFetch(endpoint: string, init?: RequestInit): Promise<Response> {
  const url = `${API_BASE}${endpoint}`;

  if (import.meta.env.PROD && !API_BASE) {
    throw new Error(
      'Frontend configuration missing: VITE_API_URL is not set in this deployment. ' +
      'Please add VITE_API_URL=https://lazyflow-ai.onrender.com in your Vercel Project Settings and redeploy.'
    );
  }

  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (err: any) {
    const isNetworkOrCors =
      err instanceof TypeError ||
      err.name === 'TypeError' ||
      err.message?.includes('fetch') ||
      err.message?.includes('Failed to fetch') ||
      err.message?.includes('NetworkError');

    if (isNetworkOrCors) {
      const target = API_BASE || window.location.origin;
      throw new Error(
        `Unable to connect to backend at ${target}. ` +
        `If the backend is hosted on a Render free instance, it may take up to 50 seconds to wake up from sleep. ` +
        `If the backend is active, verify that CORS allows requests from ${window.location.origin}.`
      );
    }
    throw err;
  }

  if (!res.ok) {
    // Check if received HTML error (e.g. SPA index.html fallback)
    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('text/html')) {
      throw new Error(
        `Backend returned HTML instead of JSON (HTTP ${res.status}). ` +
        `Verify VITE_API_URL points to the live FastAPI backend.`
      );
    }

    let detail = res.statusText || `Request failed with status ${res.status}`;
    try {
      const errJson = await res.json();
      if (errJson) {
        if (typeof errJson.detail === 'string') {
          detail = errJson.detail;
        } else if (Array.isArray(errJson.detail)) {
          detail = errJson.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
        } else if (errJson.message) {
          detail = errJson.message;
        }
      }
    } catch {
      // not json, keep statusText
    }
    throw new Error(detail);
  }

  return res;
}

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await safeFetch('/api/health');
  return res.json();
}

export async function fetchModelStatus(): Promise<ModelStatus> {
  const res = await safeFetch('/api/model-status');
  return res.json();
}

export async function fetchSampleFilesList(): Promise<SampleFileInfo[]> {
  const res = await safeFetch('/api/sample-files');
  return res.json();
}

export async function fetchSampleFileBlob(filename: string): Promise<Blob> {
  const res = await safeFetch(`/api/sample-files/${encodeURIComponent(filename)}`);
  return res.blob();
}

export async function organizeMetadata(
  files: FileMetadata[],
  customCategories?: string[]
): Promise<OrganizeResponse> {
  const res = await safeFetch('/api/organize-metadata', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      files,
      custom_categories: customCategories,
    }),
  });
  return res.json();
}

export async function uploadAndOrganize(
  files: File[],
  customCategories?: string[],
  descriptions?: Record<string, string>
): Promise<OrganizeResponse> {
  const formData = new FormData();

  files.forEach((file) => {
    formData.append('files', file);
  });

  if (customCategories && customCategories.length > 0) {
    formData.append('custom_categories', customCategories.join(','));
  }

  if (descriptions && Object.keys(descriptions).length > 0) {
    formData.append('descriptions', JSON.stringify(descriptions));
  }

  const res = await safeFetch('/api/upload-and-organize', {
    method: 'POST',
    body: formData,
  });

  return res.json();
}

export async function downloadOrganizedZip(
  sessionId: string,
  items: FileOrganizedItem[]
): Promise<void> {
  const res = await safeFetch('/api/download-zip', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: sessionId,
      items: items,
    }),
  });

  let filename = 'lazyflow_organized.zip';
  const disposition = res.headers.get('Content-Disposition');
  if (disposition && disposition.includes('filename=')) {
    const match = disposition.match(/filename="?([^"]+)"?/);
    if (match && match[1]) {
      filename = match[1];
    }
  }

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

export async function cleanupSession(sessionId: string): Promise<void> {
  try {
    await safeFetch(`/api/session/${sessionId}`, { method: 'DELETE' });
  } catch (e) {
    console.warn('Session cleanup failed:', e);
  }
}
