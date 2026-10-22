import type { HealthStatus, ModelStatus, OrganizeResponse, FileOrganizedItem } from '../types';

// In production on Vercel, VITE_API_URL points to Render backend.
// Locally with Vite dev proxy, empty string uses relative /api which Vite proxies to http://127.0.0.1:8000.
const RAW_API_BASE = import.meta.env.VITE_API_URL || '';
const API_BASE = RAW_API_BASE.replace(/\/+$/, '');

export interface SampleFileInfo {
  name: string;
  size: number;
  mime_type: string;
  hint: string;
  download_url: string;
}

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchModelStatus(): Promise<ModelStatus> {
  const res = await fetch(`${API_BASE}/api/model-status`);
  if (!res.ok) {
    throw new Error(`Model status check failed: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchSampleFilesList(): Promise<SampleFileInfo[]> {
  const res = await fetch(`${API_BASE}/api/sample-files`);
  if (!res.ok) {
    throw new Error(`Failed to fetch sample files list: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchSampleFileBlob(filename: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/sample-files/${encodeURIComponent(filename)}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch sample file: ${filename}`);
  }
  return res.blob();
}

export async function uploadAndOrganize(
  files: File[],
  customCategories?: string[],
  descriptions?: Record<string, string>
): Promise<OrganizeResponse> {
  const formData = new FormData();

  files.forEach(file => {
    formData.append('files', file);
  });

  if (customCategories && customCategories.length > 0) {
    formData.append('custom_categories', customCategories.join(','));
  }

  if (descriptions && Object.keys(descriptions).length > 0) {
    formData.append('descriptions', JSON.stringify(descriptions));
  }

  const res = await fetch(`${API_BASE}/api/upload-and-organize`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorData.detail || `Upload failed with status ${res.status}`);
  }

  return res.json();
}

export async function downloadOrganizedZip(
  sessionId: string,
  items: FileOrganizedItem[]
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/download-zip`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: sessionId,
      items: items,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Download failed with status ${res.status}`);
  }

  // Get filename from Content-Disposition header if available
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
    await fetch(`${API_BASE}/api/session/${sessionId}`, { method: 'DELETE' });
  } catch (e) {
    console.warn('Session cleanup failed:', e);
  }
}
