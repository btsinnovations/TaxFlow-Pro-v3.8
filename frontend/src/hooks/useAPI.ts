const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

// ---------------------------------------------------------------------------
// Auth helper: attach the JWT Bearer token to protected requests
// ---------------------------------------------------------------------------
function authHeaders(contentType: boolean = false): Record<string, string> {
  const token = localStorage.getItem('token');
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  if (contentType) {
    headers['Content-Type'] = 'application/json';
  }
  return headers;
}

async function handleResponse(res: Response, fallbackError: string) {
  if (!res.ok) {
    const text = await res.text().catch(() => fallbackError);
    throw new Error(text || fallbackError);
  }
  // Some endpoints (e.g. logout) may return an empty body.
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return res.json();
  }
  return res.text();
}

export async function uploadFile(file: File, clientId: string = 'default'): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);

  // Pass the selected client as a query parameter so the backend can resolve
  // or create a default account for that client.
  const query = clientId && clientId !== 'default' ? `?client_id=${clientId}` : '';

  const res = await fetch(`${API_BASE}/upload/${query}`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  });
  return handleResponse(res, 'Upload failed');
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
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_id: fileId,
      client_id: options.client_id || 'default',
      profile: options.profile || 'personal',
      output_format: options.output_format || 'qif',
      use_fast: options.use_fast || false,
      use_ml: options.use_ml !== false,
    }),
  });
  return handleResponse(res, 'Processing failed');
}

export async function downloadResult(fileId: string, format: string = 'qif'): Promise<Blob> {
  const res = await fetch(`${API_BASE}/upload/download/${fileId}?format=${format}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error('Download failed');
  return res.blob();
}

export async function exportStatement(statementId: string | number, format: string = 'csv'): Promise<Blob> {
  const res = await fetch(`${API_BASE}/export/statement/${statementId}?format=${format}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error('Export failed');
  return res.blob();
}

export async function getClients(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/clients/`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch clients');
}

export async function createClient(data: { name: string; email?: string; tax_id?: string }): Promise<any> {
  const payload: any = { name: data.name, tax_id: data.tax_id };
  if (data.email) payload.email = data.email;

  const res = await fetch(`${API_BASE}/clients/`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleResponse(res, 'Failed to create client');
}

export async function getAuditLog(limit: number = 50): Promise<any[]> {
  const res = await fetch(`${API_BASE}/audit/logs?limit=${limit}`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch audit log');
}

export async function getTaxRules(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/tax/`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch tax rules');
}

export async function updateTaxRule(ruleId: string, data: any): Promise<any> {
  const res = await fetch(`${API_BASE}/tax/${ruleId}`, {
    method: 'PATCH',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse(res, 'Failed to update tax rule');
}

export async function getDashboardStats(): Promise<any> {
  const res = await fetch(`${API_BASE}/dashboard/`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch stats');
}

export async function getTests(): Promise<any> {
  const res = await fetch(`${API_BASE}/tests/`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch tests');
}

export async function runTests(): Promise<any> {
  const res = await fetch(`${API_BASE}/tests/run`, {
    method: 'POST',
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to run tests');
}

export async function getMLStatus(): Promise<any> {
  const res = await fetch(`${API_BASE}/ml/status`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch ML status');
}

export async function toggleML(): Promise<any> {
  const res = await fetch(`${API_BASE}/ml/toggle`, {
    method: 'POST',
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to toggle ML');
}

export async function categorizeStatement(statementId: number | string): Promise<any> {
  const res = await fetch(`${API_BASE}/ml/categorize/${statementId}`, {
    method: 'POST',
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to categorize statement');
}

export async function getCategories(schedule?: string): Promise<any[]> {
  const url = schedule ? `${API_BASE}/categories?schedule=${schedule}` : `${API_BASE}/categories`;
  const res = await fetch(url, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch categories');
}

export async function getExportFormats(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/export/formats`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch export formats');
}

export async function updateClient(clientId: string, data: { name: string; email?: string; tax_id?: string }): Promise<any> {
  const payload: any = { name: data.name, tax_id: data.tax_id };
  if (data.email) payload.email = data.email;

  const res = await fetch(`${API_BASE}/clients/${clientId}`, {
    method: 'PATCH',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleResponse(res, 'Failed to update client');
}

export async function deleteClient(clientId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/clients/${clientId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to delete client');
}

export async function getProcessedFiles(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/audit/logs`, {
    headers: authHeaders(),
  });
  const events = await handleResponse(res, 'Failed to fetch processed files');
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
  const res = await fetch(url, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch accounts');
}

export async function createAccount(data: { client_id: string; name: string; institution: string; type?: string; account_number_masked?: string; notes?: string }): Promise<any> {
  const res = await fetch(`${API_BASE}/accounts/`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_id: data.client_id,
      name: data.name,
      institution: data.institution,
      type: data.type || 'checking',
      account_number_masked: data.account_number_masked,
    }),
  });
  return handleResponse(res, 'Failed to create account');
}

export async function deleteAccount(accountId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/accounts/${accountId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to delete account');
}

export async function syncAccount(accountId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/accounts/${accountId}/sync`, {
    method: 'POST',
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to sync account');
}

// Auth API functions
export async function loginUser(username: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("Login failed");
  return res.json();
}

export async function registerUser(username: string, email: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, email, password }),
  });
  if (!res.ok) throw new Error("Registration failed");
  return res.json();
}

export async function logoutUser() {
  const token = localStorage.getItem("token");
  if (token) {
    await fetch(`${API_BASE}/auth/logout`, {
      method: "POST",
      headers: authHeaders(),
    });
  }
}

export async function getMe() {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Not authenticated");
  return res.json();
}

// ===================================================================
// Tax Summary API
// ===================================================================

export async function getTaxSummary(year: number): Promise<any> {
  const res = await fetch(`${API_BASE}/tax/summary/${year}`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch tax summary');
}

// ===================================================================
// Transactions API
// ===================================================================

export async function getTransactions(params: {
  client_id: number;
  year?: string;
  category?: string;
  confirmed?: boolean;
  archived?: boolean;
  search?: string;
  tx_type?: string;
  is_manual?: boolean;
  is_journal?: boolean;
  skip?: number;
  limit?: number;
  order_by?: string;
  order_dir?: string;
}): Promise<any[]> {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') qs.set(k, String(v));
  });
  const res = await fetch(`${API_BASE}/transactions?${qs.toString()}`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch transactions');
}

export async function getTransactionsSummary(params: {
  client_id: number;
  year?: string;
  category?: string;
}): Promise<any> {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') qs.set(k, String(v));
  });
  const res = await fetch(`${API_BASE}/transactions/summary?${qs.toString()}`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch transactions summary');
}

export async function updateTransaction(txId: number, data: {
  date?: string;
  description?: string;
  amount?: number;
  tx_type?: string;
  category?: string;
  confirmed?: boolean;
  tax_line?: string;
  running_balance?: number;
}): Promise<any> {
  const res = await fetch(`${API_BASE}/transactions/${txId}`, {
    method: 'PATCH',
    headers: { ...authHeaders(true), 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse(res, 'Failed to update transaction');
}

export async function archiveTransaction(txId: number): Promise<any> {
  const res = await fetch(`${API_BASE}/transactions/${txId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to archive transaction');
}

// ===================================================================
// Budgets API
// ===================================================================

export async function getBudgets(client_id: number, year?: number): Promise<any[]> {
  const qs = new URLSearchParams();
  qs.set('client_id', String(client_id));
  if (year !== undefined) qs.set('year', String(year));
  const res = await fetch(`${API_BASE}/budgets?${qs.toString()}`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch budgets');
}

export async function getBudget(budgetId: number): Promise<any> {
  const res = await fetch(`${API_BASE}/budgets/${budgetId}`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch budget');
}

export async function createBudget(client_id: number, data: {
  name: string;
  period_start: string;
  period_end: string;
  is_active: boolean;
  entries: { category: string; amount: number }[];
}): Promise<any> {
  const qs = `?client_id=${client_id}`;
  const res = await fetch(`${API_BASE}/budgets${qs}`, {
    method: 'POST',
    headers: { ...authHeaders(true), 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse(res, 'Failed to create budget');
}

export async function updateBudget(budgetId: number, data: {
  name: string;
  period_start: string;
  period_end: string;
  is_active: boolean;
  entries: { category: string; amount: number }[];
}): Promise<any> {
  const res = await fetch(`${API_BASE}/budgets/${budgetId}`, {
    method: 'PUT',
    headers: { ...authHeaders(true), 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse(res, 'Failed to update budget');
}

export async function deleteBudget(budgetId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/budgets/${budgetId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error('Failed to delete budget');
}

export async function getBudgetVsActual(budgetId: number): Promise<any> {
  const res = await fetch(`${API_BASE}/budgets/${budgetId}/vs-actual`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch budget vs actual');
}

// ===================================================================
// Forecast API
// ===================================================================

export async function getForecast(client_id: number, months_ahead: number = 12): Promise<any> {
  const qs = `?client_id=${client_id}&months_ahead=${months_ahead}`;
  const res = await fetch(`${API_BASE}/forecast${qs}`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch forecast');
}

// ===================================================================
// Depreciation API
// ===================================================================

export async function getDepreciationMethods(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/depreciation/methods`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch depreciation methods');
}

export async function getMacrsTables(): Promise<any> {
  const res = await fetch(`${API_BASE}/depreciation/macrs-tables`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch MACRS tables');
}

export async function calculateDepreciation(data: {
  asset_name: string;
  asset_class: string;
  cost_basis: number;
  placed_in_service_date: string;
  recovery_period: number;
  method: string;
  section_179_expense?: number;
  bonus_depreciation_pct?: number;
  salvage_value?: number;
  business_use_pct?: number;
}): Promise<any> {
  const res = await fetch(`${API_BASE}/depreciation/calculate`, {
    method: 'POST',
    headers: { ...authHeaders(true), 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse(res, 'Failed to calculate depreciation');
}

// ===================================================================
// Reports API
// ===================================================================

export async function getSignedReports(client_id: number, skip: number = 0, limit: number = 100): Promise<any[]> {
  const qs = `?client_id=${client_id}&skip=${skip}&limit=${limit}`;
  const res = await fetch(`${API_BASE}/reports/signed${qs}`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch signed reports');
}

export async function getSignedReport(reportId: number): Promise<any> {
  const res = await fetch(`${API_BASE}/reports/signed/${reportId}`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Failed to fetch signed report');
}

export async function signReport(reportType: string, data: {
  client_id: number;
  year?: string;
  title: string;
  report_data: object;
  master_password: string;
}): Promise<any> {
  const res = await fetch(`${API_BASE}/reports/${reportType}/sign`, {
    method: 'POST',
    headers: { ...authHeaders(true), 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse(res, 'Failed to sign report');
}
