const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

export async function uploadFile(file: File, clientId: string = 'default', forceOcr: boolean = false): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('client_id', clientId);
  formData.append('force_ocr', String(forceOcr));

  const res = await fetch(`${API_BASE}/upload/`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function processFile(fileId: string, options: {
  client_id?: string;
  profile?: string;
  output_format?: 'qif' | 'csv' | 'json';
  use_fast?: boolean;
  use_ml?: boolean;
} = {}): Promise<any> {
  const res = await fetch(`${API_BASE}/upload/process`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_id: fileId,
      client_id: options.client_id || 'default',
      profile: options.profile || 'personal',
      output_format: options.output_format || 'qif',
      use_fast: options.use_fast || false,
      use_ml: options.use_ml !== false,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function downloadResult(fileId: string, format: string = 'qif'): Promise<Blob> {
  const res = await fetch(`${API_BASE}/upload/download/${fileId}?format=${format}`);
  if (!res.ok) throw new Error('Download failed');
  return res.blob();
}

export async function getClients(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/clients/`);
  if (!res.ok) throw new Error('Failed to fetch clients');
  return res.json();
}

export async function createClient(data: { name: string; entity_type?: string; tax_id?: string; notes?: string }): Promise<any> {
  const res = await fetch(`${API_BASE}/clients/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create client');
  return res.json();
}

export async function getAuditLog(limit: number = 50): Promise<any[]> {
  const res = await fetch(`${API_BASE}/audit/?limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch audit log');
  return res.json();
}

export async function getTaxRules(tenantId?: string | number): Promise<any[]> {
  const q = tenantId != null ? `?tenant_id=${tenantId}` : "?tenant_id=default";
  const res = await fetch(`${API_BASE}/tax/${q}`);
  if (!res.ok) throw new Error('Failed to fetch tax rules');
  return res.json();
}

export async function updateTaxRule(ruleId: string, data: any, tenantId?: string | number): Promise<any> {
  const q = tenantId != null ? `?tenant_id=${tenantId}` : "?tenant_id=default";
  const res = await fetch(`${API_BASE}/tax/${ruleId}${q}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update tax rule');
  return res.json();
}

export async function getDashboardStats(): Promise<any> {
  const res = await fetch(`${API_BASE}/dashboard/stats`);
  if (!res.ok) throw new Error('Failed to fetch stats');
  return res.json();
}

export async function getTests(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/tests/`);
  if (!res.ok) throw new Error('Failed to fetch tests');
  return res.json();
}

export async function runTests(): Promise<any> {
  const res = await fetch(`${API_BASE}/tests/run`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to run tests');
  return res.json();
}

export async function getMLStatus(): Promise<any> {
  const res = await fetch(`${API_BASE}/ml/status`);
  if (!res.ok) throw new Error('Failed to fetch ML status');
  return res.json();
}

export async function toggleML(): Promise<any> {
  const res = await fetch(`${API_BASE}/ml/toggle`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to toggle ML');
  return res.json();
}

export async function getExportFormats(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/export/formats`);
  if (!res.ok) throw new Error('Failed to fetch export formats');
  return res.json();
}

export async function updateClient(clientId: string, data: { name: string; entity_type?: string; tax_id?: string; notes?: string }): Promise<any> {
  const res = await fetch(`${API_BASE}/clients/${clientId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update client');
  return res.json();
}

export async function deleteClient(clientId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/clients/${clientId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete client');
  return res.json();
}

export async function getProcessedFiles(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/audit/`);
  if (!res.ok) throw new Error('Failed to fetch processed files');
  const events = await res.json();
  // Filter to processing complete events and extract file info
  return events
    .filter((e: any) => e.event_type === 'PROCESSING_COMPLETE' || e.event_type === 'FILE_UPLOAD')
    .map((e: any) => ({
      file_id: e.details?.file_id,
      filename: e.details?.filename || e.description?.match(/from (\S+)/)?.[1] || 'Unknown',
      institution: e.details?.institution,
      transaction_count: e.details?.transaction_count,
      processed_at: e.timestamp,
      status: e.event_type === 'PROCESSING_COMPLETE' ? 'completed' : 'uploaded',
    }))
    .filter((f: any) => f.file_id);
}

export async function getAccounts(clientId?: string): Promise<any[]> {
  const url = clientId ? `${API_BASE}/accounts/?client_id=${clientId}` : `${API_BASE}/accounts/`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch accounts');
  return res.json();
}

export async function createAccount(data: { client_id: string; nickname: string; institution: string; account_type?: string; account_number_last4?: string; notes?: string }): Promise<any> {
  const res = await fetch(`${API_BASE}/accounts/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create account');
  return res.json();
}

export async function deleteAccount(accountId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/accounts/${accountId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete account');
  return res.json();
}

export async function syncAccount(accountId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/accounts/${accountId}/sync`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to sync account');
  return res.json();
}

// Auth API functions
export async function bootLocalAdmin(password: string) {
  const res = await fetch(`${API_BASE}/auth/boot`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) throw new Error("Boot failed");
  return res.json();
}

export async function getAuthStatus() {
  const res = await fetch(`${API_BASE}/auth/status`);
  if (!res.ok) throw new Error("Failed to fetch auth status");
  return res.json();
}

export async function loginUser(username: string, password: string) {
  // v3.9 hybrid auth: try JSON login first; server ignores username for local admin.
  const res = await fetch(`${API_BASE}/auth/login-json`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("Login failed");
  return res.json();
}

export async function registerUser(username: string, password: string, email: string = "") {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, email }),
  });
  if (!res.ok) throw new Error("Registration failed");
  return res.json();
}

export async function logoutUser() {
  const token = localStorage.getItem("token");
  if (token) {
    await fetch(`${API_BASE}/auth/logout`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${token}` },
    });
  }
}

export async function getMe() {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: { "Authorization": `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Not authenticated");
  return res.json();
}

export async function fetchWithAuth(url: string, options: RequestInit = {}) {
  const token = localStorage.getItem("token");
  return fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });
}


