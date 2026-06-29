// Extended API hooks for backend routers currently without frontend consumers.
// Each function below is a typed placeholder. Jane should implement the fetch
// calls and error handling following the pattern in `useAPI.ts`.

const API_BASE = (() => {
  const envBase = import.meta.env.VITE_API_BASE_URL;
  if (envBase) return envBase;
  return window.location.origin.includes("127.0.0.1:8000") || window.location.origin.includes("localhost:8000")
    ? "/api"
    : "http://localhost:8000/api";
})();

function _authHeaders(contentType: boolean = true): Record<string, string> {
  const headers: Record<string, string> = {};
  const token = localStorage.getItem("token");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (contentType) headers["Content-Type"] = "application/json";
  return headers;
}

async function _fetchJson(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ..._authHeaders(), ...(options.headers || {}) },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// Audit
export async function getAuditLog(limit: number = 50): Promise<any[]> {
  return _fetchJson(`/audit/?limit=${limit}`);
}

// Backup
export async function createBackup(): Promise<any> {
  return _fetchJson("/backup/", { method: "POST" });
}
export async function listBackups(): Promise<any[]> {
  return _fetchJson("/backup/");
}

// COA
export async function getCoaAccounts(): Promise<any[]> {
  return _fetchJson("/coa/");
}
export async function createCoaAccount(data: any): Promise<any> {
  return _fetchJson("/coa/", { method: "POST", body: JSON.stringify(data) });
}

// Dashboard health
export async function getHealth(): Promise<any> {
  return _fetchJson("/health");
}

// Depreciation
export async function getDepreciationAssets(): Promise<any[]> {
  return _fetchJson("/depreciation/");
}
export async function createDepreciationAsset(data: any): Promise<any> {
  return _fetchJson("/depreciation/", { method: "POST", body: JSON.stringify(data) });
}

// Export
export async function getExportFormats(): Promise<any[]> {
  return _fetchJson("/export/formats");
}
export async function requestExport(format: string, payload: any): Promise<any> {
  return _fetchJson("/export/", { method: "POST", body: JSON.stringify({ format, ...payload }) });
}

// Flags
export async function getFlags(): Promise<any[]> {
  return _fetchJson("/flags/");
}
export async function createFlag(data: any): Promise<any> {
  return _fetchJson("/flags/", { method: "POST", body: JSON.stringify(data) });
}

// GL
export async function getGlEntries(): Promise<any[]> {
  return _fetchJson("/gl/");
}
export async function postGlEntry(data: any): Promise<any> {
  return _fetchJson("/gl/", { method: "POST", body: JSON.stringify(data) });
}

// Imports
export async function getImports(): Promise<any[]> {
  return _fetchJson("/imports/");
}
export async function importFile(formData: FormData): Promise<any> {
  const res = await fetch(`${API_BASE}/imports/`, {
    method: "POST",
    headers: _authHeaders(false),
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// Investments
export async function getInvestments(): Promise<any[]> {
  return _fetchJson("/investments/");
}
export async function createInvestment(data: any): Promise<any> {
  return _fetchJson("/investments/", { method: "POST", body: JSON.stringify(data) });
}

// Invoicing
export async function getInvoices(): Promise<any[]> {
  return _fetchJson("/invoicing/");
}
export async function createInvoice(data: any): Promise<any> {
  return _fetchJson("/invoicing/", { method: "POST", body: JSON.stringify(data) });
}

// Liabilities
export async function getLiabilities(): Promise<any[]> {
  return _fetchJson("/liabilities/");
}
export async function createLiability(data: any): Promise<any> {
  return _fetchJson("/liabilities/", { method: "POST", body: JSON.stringify(data) });
}

// Mileage
export async function getMileageEntries(): Promise<any[]> {
  return _fetchJson("/mileage/");
}
export async function createMileageEntry(data: any): Promise<any> {
  return _fetchJson("/mileage/", { method: "POST", body: JSON.stringify(data) });
}

// Periods
export async function getPeriods(): Promise<any[]> {
  return _fetchJson("/periods/");
}
export async function closePeriod(periodId: string): Promise<any> {
  return _fetchJson(`/periods/${periodId}/close`, { method: "POST" });
}

// Rules
export async function getRules(): Promise<any[]> {
  return _fetchJson("/rules/");
}
export async function createRule(data: any): Promise<any> {
  return _fetchJson("/rules/", { method: "POST", body: JSON.stringify(data) });
}

// Sales Tax
export async function getSalesTax(): Promise<any[]> {
  return _fetchJson("/sales_tax/");
}
export async function createSalesTax(data: any): Promise<any> {
  return _fetchJson("/sales_tax/", { method: "POST", body: JSON.stringify(data) });
}

// Tax
export async function getTaxRules(): Promise<any[]> {
  return _fetchJson("/tax/");
}
export async function createTaxRule(data: any): Promise<any> {
  return _fetchJson("/tax/", { method: "POST", body: JSON.stringify(data) });
}

// Upload
export async function uploadFile(file: File, clientId: string = 'default'): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('client_id', clientId);
  const res = await fetch(`${API_BASE}/upload/`, {
    method: "POST",
    headers: _authHeaders(false),
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// Vendors
export async function getVendors(): Promise<any[]> {
  return _fetchJson("/vendors/");
}
export async function createVendor(data: any): Promise<any> {
  return _fetchJson("/vendors/", { method: "POST", body: JSON.stringify(data) });
}

// Year End
export async function getYearEndPackage(): Promise<any> {
  return _fetchJson("/year_end/");
}
export async function runYearEnd(tenantId?: string): Promise<any> {
  return _fetchJson("/year_end/", { method: "POST", body: JSON.stringify({ tenant_id: tenantId }) });
}

// Clients
export async function getClients(): Promise<any[]> {
  return _fetchJson("/clients/");
}
export async function createClient(data: any): Promise<any> {
  return _fetchJson("/clients/", { method: "POST", body: JSON.stringify(data) });
}
