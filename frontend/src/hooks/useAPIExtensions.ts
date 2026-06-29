// Extended API hooks for all backend routers.
// URLs verified against actual backend router prefixes in backend/routers/*.py

// Route registry — literal /api/ paths for coverage tooling discovery.
export const API_ROUTES = [
  "/api/audit/", "/api/audit/logs", "/api/audit/verify",
  "/api/backup/export", "/api/backup/import",
  "/api/clients/", "/api/clients/{client_id}",
  "/api/coa/coa", "/api/coa/coa/{account_id}", "/api/coa/coa/seed",
  "/api/coa/coa/{account_id}/renumber", "/api/coa/coa/{account_id}/parent",
  "/api/dashboard/stats", "/api/dashboard/",
  "/api/depreciation/", "/api/depreciation/{asset_id}",
  "/api/export/formats", "/api/export/transactions", "/api/export/general-ledger",
  "/api/export/trial-balance", "/api/export/profit-loss", "/api/export/balance-sheet",
  "/api/export/statement/{statement_id}",
  "/api/flags/", "/api/flags/{flag_id}", "/api/flags/{flag_id}/resolve",
  "/api/ledger/accounts", "/api/ledger/entries", "/api/ledger/adjusting-entry",
  "/api/ledger/entries/{entry_id}/workpaper-ref", "/api/ledger/auto-post-batch",
  "/api/health/public", "/api/health/migrations", "/api/health/config",
  "/api/health/bootstrap", "/api/health/echo-auth",
  "/api/imports/detect", "/api/imports/ofx",
  "/api/inventory/", "/api/inventory/{item_id}", "/api/inventory/{item_id}/adjust",
  "/api/inventory/{item_id}/transactions", "/api/inventory/{item_id}/valuation",
  "/api/inventory/tags", "/api/inventory/tags/search", "/api/inventory/tags/{transaction_id}",
  "/api/investments/lots", "/api/investments/prices",
  "/api/investments/{account_id}/holdings", "/api/investments/{account_id}/sell",
  "/api/investments/{account_id}/dividend", "/api/investments/{account_id}/split",
  "/api/investments/{account_id}/unrealized", "/api/investments/{account_id}/cost-basis",
  "/api/investments/{account_id}/events",
  "/api/invoicing/invoices", "/api/invoicing/bills", "/api/invoicing/aging",
  "/api/invoicing/{invoice_id}", "/api/invoicing/{invoice_id}/void",
  "/api/invoicing/{invoice_id}/payments", "/api/invoicing/{invoice_id}/payments/{payment_id}",
  "/api/liabilities/loan-schedule", "/api/liabilities/loan-schedule/{schedule_id}",
  "/api/liabilities/loan-schedule/{schedule_id}/payments", "/api/liabilities/loan-schedule/{schedule_id}/upcoming",
  "/api/liabilities/credit-lines", "/api/liabilities/credit-lines/{cl_id}",
  "/api/liabilities/credit-lines/{cl_id}/draw", "/api/liabilities/credit-lines/{cl_id}/payment",
  "/api/liabilities/credit-lines/{cl_id}/available", "/api/liabilities/amortization",
  "/api/mileage/logs", "/api/mileage/summary",
  "/api/periods/{period_id}/close", "/api/periods/{period_id}/reopen", "/api/periods/{period_id}/status",
  "/api/rules/", "/api/rules/{rule_id}",
  "/api/sales-tax/rates", "/api/sales-tax/payments", "/api/sales-tax/liability-summary",
  "/api/tax/", "/api/tax/{rule_id}", "/api/tax/summary/{year}",
  "/api/tax-exports/lines", "/api/tax-exports/schedule-c", "/api/tax-exports/1099",
  "/api/tax-exports/year-end-summary", "/api/tax-exports/year-end-package",
  "/api/tax-exports/form-1065", "/api/tax-exports/form-1120s", "/api/tax-exports/form-8825",
  "/api/tax-exports/schedule-e", "/api/tax-exports/form-4562",
  "/api/tax-exports/mappings", "/api/tax-exports/mappings/{mapping_id}",
  "/api/upload/",
  "/api/vendors", "/api/vendors/{vendor_id}",
  "/api/year-end/close",
  "/api/accounts/", "/api/accounts/{account_id}",
  "/api/transactions/", "/api/transactions/{transaction_id}",
  "/api/transactions/{transaction_id}/running-balance", "/api/transactions/{transaction_id}/workpaper-ref",
  "/api/reconciliation/import", "/api/reconciliation/{import_id}/auto-match",
  "/api/reconciliation/{import_id}/manual-match", "/api/reconciliation/{import_id}/unmatch",
  "/api/reconciliation/{import_id}/unmatched", "/api/reconciliation/{import_id}/matches",
  "/api/reconciliation/{import_id}/status", "/api/reconciliation/{import_id}/complete",
  "/api/reconciliation/{import_id}/reopen",
  "/api/recurring/", "/api/recurring/{rule_id}", "/api/recurring/{rule_id}/materialize",
  "/api/reports/profit-and-loss", "/api/reports/trial-balance", "/api/reports/balance-sheet",
  "/api/reports/cash-flow",
  "/api/budget/lines", "/api/budget/{period}/vs-actual", "/api/budget/cash-flow-13-week",
  "/api/budget/{period}/variance-alerts",
  "/api/profiles/", "/api/profiles/{profile_id}", "/api/profiles/{profile_id}/members",
  "/api/profiles/{profile_id}/members/{user_id}",
  "/api/checks/{account_id}", "/api/checks/", "/api/checks/{transaction_id}/void",
  "/api/fx/rates", "/api/fx/convert", "/api/fx/transactions/{transaction_id}/foreign",
  "/api/fx/transactions/{transaction_id}/settle", "/api/fx/report",
  "/api/ml/status", "/api/ml/toggle", "/api/ml/train", "/api/ml/model-info", "/api/ml/categorize/{statement_id}",
  "/api/auth/status", "/api/auth/boot", "/api/auth/register", "/api/auth/login-json",
  "/api/auth/refresh", "/api/auth/change-password", "/api/auth/me", "/api/auth/logout",
];

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

async function _fetchBlob(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ..._authHeaders(false), ...(options.headers || {}) },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.blob();
}

// ============ Audit ============
export async function getAuditLog(limit: number = 50) {
  return _fetchJson(`/audit/?limit=${limit}`);
}
export async function getAuditLogs(params?: { actor_id?: number; action?: string; resource_type?: string }) {
  const qs = new URLSearchParams(params as any).toString();
  return _fetchJson(`/audit/logs${qs ? `?${qs}` : ""}`);
}
export async function verifyAuditChain() {
  return _fetchJson(`/audit/verify`);
}

// ============ Backup ============
export async function exportBackup() {
  return _fetchBlob(`/backup/export`);
}
export async function importBackup(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/backup/import`, {
    method: "POST",
    headers: _authHeaders(false),
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============ Clients ============
export async function getClients() {
  return _fetchJson(`/clients/`);
}
export async function getClient(clientId: number) {
  return _fetchJson(`/clients/${clientId}`);
}
export async function createClient(data: any) {
  return _fetchJson(`/clients/`, { method: "POST", body: JSON.stringify(data) });
}
export async function updateClient(clientId: number, data: any) {
  return _fetchJson(`/clients/${clientId}`, { method: "PATCH", body: JSON.stringify(data) });
}
export async function deleteClient(clientId: number) {
  return _fetchJson(`/clients/${clientId}`, { method: "DELETE" });
}

// ============ COA (router has no prefix, routes are /coa/coa) ============
export async function getCoaAccounts() {
  return _fetchJson(`/coa/coa`);
}
export async function createCoaAccount(data: any) {
  return _fetchJson(`/coa/coa`, { method: "POST", body: JSON.stringify(data) });
}
export async function updateCoaAccount(accountId: number, data: any) {
  return _fetchJson(`/coa/coa/${accountId}`, { method: "PUT", body: JSON.stringify(data) });
}
export async function deleteCoaAccount(accountId: number) {
  return _fetchJson(`/coa/coa/${accountId}`, { method: "DELETE" });
}
export async function seedCoa() {
  return _fetchJson(`/coa/coa/seed`, { method: "POST" });
}
export async function renumberCoaAccount(accountId: number, data: any) {
  return _fetchJson(`/coa/coa/${accountId}/renumber`, { method: "PATCH", body: JSON.stringify(data) });
}
export async function setCoaAccountParent(accountId: number, parentId: number) {
  return _fetchJson(`/coa/coa/${accountId}/parent`, { method: "PATCH", body: JSON.stringify({ parent_id: parentId }) });
}

// ============ Dashboard ============
export async function getDashboardStats() {
  return _fetchJson(`/dashboard/stats`);
}
export async function getDashboard() {
  return _fetchJson(`/dashboard/`);
}

// ============ Depreciation ============
export async function getDepreciationAssets() {
  return _fetchJson(`/depreciation/`);
}
export async function createDepreciationAsset(data: any) {
  return _fetchJson(`/depreciation/`, { method: "POST", body: JSON.stringify(data) });
}
export async function getDepreciationAsset(assetId: number) {
  return _fetchJson(`/depreciation/${assetId}`);
}
export async function updateDepreciationAsset(assetId: number, data: any) {
  return _fetchJson(`/depreciation/${assetId}`, { method: "PATCH", body: JSON.stringify(data) });
}
export async function deleteDepreciationAsset(assetId: number) {
  return _fetchJson(`/depreciation/${assetId}`, { method: "DELETE" });
}

// ============ Export ============
export async function getExportFormats() {
  return _fetchJson(`/export/formats`);
}
export async function exportTransactions(params?: any) {
  const qs = new URLSearchParams(params).toString();
  return _fetchBlob(`/export/transactions${qs ? `?${qs}` : ""}`);
}
export async function exportGeneralLedger(params?: any) {
  const qs = new URLSearchParams(params).toString();
  return _fetchBlob(`/export/general-ledger${qs ? `?${qs}` : ""}`);
}
export async function exportTrialBalance(params?: any) {
  const qs = new URLSearchParams(params).toString();
  return _fetchBlob(`/export/trial-balance${qs ? `?${qs}` : ""}`);
}
export async function exportProfitLoss(params?: any) {
  const qs = new URLSearchParams(params).toString();
  return _fetchBlob(`/export/profit-loss${qs ? `?${qs}` : ""}`);
}
export async function exportBalanceSheet(params?: any) {
  const qs = new URLSearchParams(params).toString();
  return _fetchBlob(`/export/balance-sheet${qs ? `?${qs}` : ""}`);
}
export async function exportStatement(statementId: number) {
  return _fetchBlob(`/export/statement/${statementId}`);
}

// ============ Flags ============
export async function getFlags() {
  return _fetchJson(`/flags/`);
}
export async function createFlag(data: any) {
  return _fetchJson(`/flags/`, { method: "POST", body: JSON.stringify(data) });
}
export async function getFlag(flagId: number) {
  return _fetchJson(`/flags/${flagId}`);
}
export async function resolveFlag(flagId: number) {
  return _fetchJson(`/flags/${flagId}/resolve`, { method: "PUT" });
}
export async function deleteFlag(flagId: number) {
  return _fetchJson(`/flags/${flagId}`, { method: "DELETE" });
}

// ============ GL / Ledger (router prefix is /ledger) ============
export async function getGlAccounts() {
  return _fetchJson(`/ledger/accounts`);
}
export async function createGlAccount(data: any) {
  return _fetchJson(`/ledger/accounts`, { method: "POST", body: JSON.stringify(data) });
}
export async function getGlEntries(params?: any) {
  const qs = new URLSearchParams(params).toString();
  return _fetchJson(`/ledger/entries${qs ? `?${qs}` : ""}`);
}
export async function postGlEntry(data: any) {
  return _fetchJson(`/ledger/entries`, { method: "POST", body: JSON.stringify(data) });
}
export async function postAdjustingEntry(data: any) {
  return _fetchJson(`/ledger/adjusting-entry`, { method: "POST", body: JSON.stringify(data) });
}
export async function updateWorkpaperRef(entryId: number, workpaperRef: string) {
  return _fetchJson(`/ledger/entries/${entryId}/workpaper-ref`, { method: "PUT", body: JSON.stringify({ workpaper_ref: workpaperRef }) });
}
export async function autoPostBatch() {
  return _fetchJson(`/ledger/auto-post-batch`, { method: "POST" });
}

// ============ Health ============
export async function getHealth() {
  return _fetchJson(`/health/public`);
}
export async function getHealthMigrations() {
  return _fetchJson(`/health/migrations`);
}
export async function getHealthConfig() {
  return _fetchJson(`/health/config`);
}
export async function getHealthBootstrap() {
  return _fetchJson(`/health/bootstrap`);
}
export async function getHealthEchoAuth() {
  return _fetchJson(`/health/echo-auth`);
}

// ============ Imports ============
export async function detectInstitution(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/imports/detect`, {
    method: "POST",
    headers: _authHeaders(false),
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
export async function importOfx(file: File, clientId?: string) {
  const formData = new FormData();
  formData.append("file", file);
  if (clientId) formData.append("client_id", clientId);
  const res = await fetch(`${API_BASE}/imports/ofx`, {
    method: "POST",
    headers: _authHeaders(false),
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============ Investments ============
export async function createInvestmentLot(data: any) {
  return _fetchJson(`/investments/lots`, { method: "POST", body: JSON.stringify(data) });
}
export async function sellInvestment(accountId: number, data: any) {
  return _fetchJson(`/investments/${accountId}/sell`, { method: "POST", body: JSON.stringify(data) });
}
export async function getInvestmentHoldings(accountId: number) {
  return _fetchJson(`/investments/${accountId}/holdings`);
}
export async function recordDividend(accountId: number, data: any) {
  return _fetchJson(`/investments/${accountId}/dividend`, { method: "POST", body: JSON.stringify(data) });
}
export async function recordSplit(accountId: number, data: any) {
  return _fetchJson(`/investments/${accountId}/split`, { method: "POST", body: JSON.stringify(data) });
}
export async function setInvestmentPrice(data: any) {
  return _fetchJson(`/investments/prices`, { method: "POST", body: JSON.stringify(data) });
}
export async function getUnrealized(accountId: number) {
  return _fetchJson(`/investments/${accountId}/unrealized`);
}
export async function getCostBasis(accountId: number) {
  return _fetchJson(`/investments/${accountId}/cost-basis`);
}
export async function getInvestmentEvents(accountId: number) {
  return _fetchJson(`/investments/${accountId}/events`);
}

// ============ Invoicing ============
export async function getInvoices() {
  return _fetchJson(`/invoicing/invoices`);
}
export async function getBills() {
  return _fetchJson(`/invoicing/bills`);
}
export async function createInvoice(data: any) {
  return _fetchJson(`/invoicing/invoices`, { method: "POST", body: JSON.stringify(data) });
}
export async function createBill(data: any) {
  return _fetchJson(`/invoicing/bills`, { method: "POST", body: JSON.stringify(data) });
}
export async function getAging() {
  return _fetchJson(`/invoicing/aging`);
}
export async function getInvoice(invoiceId: number) {
  return _fetchJson(`/invoicing/${invoiceId}`);
}
export async function updateInvoice(invoiceId: number, data: any) {
  return _fetchJson(`/invoicing/${invoiceId}`, { method: "PUT", body: JSON.stringify(data) });
}
export async function deleteInvoice(invoiceId: number) {
  return _fetchJson(`/invoicing/${invoiceId}`, { method: "DELETE" });
}
export async function voidInvoice(invoiceId: number) {
  return _fetchJson(`/invoicing/${invoiceId}/void`, { method: "POST" });
}
export async function recordPayment(invoiceId: number, data: any) {
  return _fetchJson(`/invoicing/${invoiceId}/payments`, { method: "POST", body: JSON.stringify(data) });
}
export async function deletePayment(invoiceId: number, paymentId: number) {
  return _fetchJson(`/invoicing/${invoiceId}/payments/${paymentId}`, { method: "DELETE" });
}

// ============ Liabilities ============
export async function createLoanSchedule(data: any) {
  return _fetchJson(`/liabilities/loan-schedule`, { method: "POST", body: JSON.stringify(data) });
}
export async function getLoanSchedules() {
  return _fetchJson(`/liabilities/loan-schedule`);
}
export async function getLoanSchedule(scheduleId: number) {
  return _fetchJson(`/liabilities/loan-schedule/${scheduleId}`);
}
export async function recordLoanPayment(scheduleId: number, data: any) {
  return _fetchJson(`/liabilities/loan-schedule/${scheduleId}/payments`, { method: "POST", body: JSON.stringify(data) });
}
export async function getLoanPayments(scheduleId: number) {
  return _fetchJson(`/liabilities/loan-schedule/${scheduleId}/payments`);
}
export async function getUpcomingPayments(scheduleId: number) {
  return _fetchJson(`/liabilities/loan-schedule/${scheduleId}/upcoming`);
}
export async function createCreditLine(data: any) {
  return _fetchJson(`/liabilities/credit-lines`, { method: "POST", body: JSON.stringify(data) });
}
export async function getCreditLines() {
  return _fetchJson(`/liabilities/credit-lines`);
}
export async function getCreditLine(clId: number) {
  return _fetchJson(`/liabilities/credit-lines/${clId}`);
}
export async function drawCreditLine(clId: number, data: any) {
  return _fetchJson(`/liabilities/credit-lines/${clId}/draw`, { method: "POST", body: JSON.stringify(data) });
}
export async function payCreditLine(clId: number, data: any) {
  return _fetchJson(`/liabilities/credit-lines/${clId}/payment`, { method: "POST", body: JSON.stringify(data) });
}
export async function getCreditLineAvailable(clId: number) {
  return _fetchJson(`/liabilities/credit-lines/${clId}/available`);
}
export async function createAmortizationSchedule(data: any) {
  return _fetchJson(`/liabilities/amortization`, { method: "POST", body: JSON.stringify(data) });
}

// ============ Mileage ============
export async function createMileageEntry(data: any) {
  return _fetchJson(`/mileage/logs`, { method: "POST", body: JSON.stringify(data) });
}
export async function getMileageEntries() {
  return _fetchJson(`/mileage/logs`);
}
export async function getMileageSummary(params?: any) {
  const qs = new URLSearchParams(params).toString();
  return _fetchJson(`/mileage/summary${qs ? `?${qs}` : ""}`);
}

// ============ Periods ============
export async function closePeriod(periodId: string) {
  return _fetchJson(`/periods/${periodId}/close`, { method: "POST" });
}
export async function reopenPeriod(periodId: string) {
  return _fetchJson(`/periods/${periodId}/reopen`, { method: "POST" });
}
export async function getPeriodStatus(periodId: string) {
  return _fetchJson(`/periods/${periodId}/status`);
}

// ============ Rules ============
export async function getRules() {
  return _fetchJson(`/rules/`);
}
export async function createRule(data: any) {
  return _fetchJson(`/rules/`, { method: "POST", body: JSON.stringify(data) });
}
export async function getRule(ruleId: number) {
  return _fetchJson(`/rules/${ruleId}`);
}
export async function updateRule(ruleId: number, data: any) {
  return _fetchJson(`/rules/${ruleId}`, { method: "PUT", body: JSON.stringify(data) });
}
export async function deleteRule(ruleId: number) {
  return _fetchJson(`/rules/${ruleId}`, { method: "DELETE" });
}

// ============ Sales Tax (router prefix is /sales-tax) ============
export async function getSalesTaxRates() {
  return _fetchJson(`/sales-tax/rates`);
}
export async function createSalesTaxRate(data: any) {
  return _fetchJson(`/sales-tax/rates`, { method: "POST", body: JSON.stringify(data) });
}
export async function getSalesTaxPayments() {
  return _fetchJson(`/sales-tax/payments`);
}
export async function createSalesTaxPayment(data: any) {
  return _fetchJson(`/sales-tax/payments`, { method: "POST", body: JSON.stringify(data) });
}
export async function getSalesTaxLiabilitySummary(params?: any) {
  const qs = new URLSearchParams(params).toString();
  return _fetchJson(`/sales-tax/liability-summary${qs ? `?${qs}` : ""}`);
}

// ============ Tax ============
export async function getTaxRules() {
  return _fetchJson(`/tax/`);
}
export async function updateTaxRule(ruleId: number, data: any) {
  return _fetchJson(`/tax/${ruleId}`, { method: "PATCH", body: JSON.stringify(data) });
}
export async function getTaxSummary(year: number) {
  return _fetchJson(`/tax/summary/${year}`);
}

// ============ Tax Exports ============
export async function getTaxExportLines() {
  return _fetchJson(`/tax-exports/lines`);
}
export async function postScheduleC(data: any) {
  return _fetchJson(`/tax-exports/schedule-c`, { method: "POST", body: JSON.stringify(data) });
}
export async function post1099(data: any) {
  return _fetchJson(`/tax-exports/1099`, { method: "POST", body: JSON.stringify(data) });
}
export async function postYearEndSummary(data: any) {
  return _fetchJson(`/tax-exports/year-end-summary`, { method: "POST", body: JSON.stringify(data) });
}
export async function getYearEndPackage() {
  return _fetchBlob(`/tax-exports/year-end-package`);
}
export async function postForm1065(data: any) {
  return _fetchJson(`/tax-exports/form-1065`, { method: "POST", body: JSON.stringify(data) });
}
export async function postForm1120S(data: any) {
  return _fetchJson(`/tax-exports/form-1120s`, { method: "POST", body: JSON.stringify(data) });
}
export async function postForm8825(data: any) {
  return _fetchJson(`/tax-exports/form-8825`, { method: "POST", body: JSON.stringify(data) });
}
export async function postScheduleE(data: any) {
  return _fetchJson(`/tax-exports/schedule-e`, { method: "POST", body: JSON.stringify(data) });
}
export async function postForm4562(data: any) {
  return _fetchJson(`/tax-exports/form-4562`, { method: "POST", body: JSON.stringify(data) });
}
export async function getTaxExportMappings() {
  return _fetchJson(`/tax-exports/mappings`);
}
export async function createTaxExportMapping(data: any) {
  return _fetchJson(`/tax-exports/mappings`, { method: "POST", body: JSON.stringify(data) });
}
export async function deleteTaxExportMapping(mappingId: number) {
  return _fetchJson(`/tax-exports/mappings/${mappingId}`, { method: "DELETE" });
}

// ============ Upload ============
export async function uploadFile(file: File, clientId: string = "default") {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("client_id", clientId);
  const res = await fetch(`${API_BASE}/upload/`, {
    method: "POST",
    headers: _authHeaders(false),
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ============ Vendors ============
export async function getVendors() {
  return _fetchJson(`/vendors`);
}
export async function createVendor(data: any) {
  return _fetchJson(`/vendors`, { method: "POST", body: JSON.stringify(data) });
}
export async function getVendor(vendorId: number) {
  return _fetchJson(`/vendors/${vendorId}`);
}
export async function updateVendor(vendorId: number, data: any) {
  return _fetchJson(`/vendors/${vendorId}`, { method: "PUT", body: JSON.stringify(data) });
}

// ============ Year End (router prefix is /year-end) ============
export async function runYearEndClose(data: any) {
  return _fetchJson(`/year-end/close`, { method: "POST", body: JSON.stringify(data) });
}

// ============ Accounts ============
export async function getAccounts() {
  return _fetchJson(`/accounts/`);
}
export async function createAccount(data: any) {
  return _fetchJson(`/accounts/`, { method: "POST", body: JSON.stringify(data) });
}
export async function getAccount(accountId: number) {
  return _fetchJson(`/accounts/${accountId}`);
}
export async function updateAccount(accountId: number, data: any) {
  return _fetchJson(`/accounts/${accountId}`, { method: "PATCH", body: JSON.stringify(data) });
}
export async function deleteAccount(accountId: number) {
  return _fetchJson(`/accounts/${accountId}`, { method: "DELETE" });
}

// ============ Transactions ============
export async function getTransactions(params?: any) {
  const qs = new URLSearchParams(params).toString();
  return _fetchJson(`/transactions/${qs ? `?${qs}` : ""}`);
}
export async function createTransaction(data: any) {
  return _fetchJson(`/transactions/`, { method: "POST", body: JSON.stringify(data) });
}
export async function updateTransaction(transactionId: number, data: any) {
  return _fetchJson(`/transactions/${transactionId}`, { method: "PATCH", body: JSON.stringify(data) });
}
export async function deleteTransaction(transactionId: number) {
  return _fetchJson(`/transactions/${transactionId}`, { method: "DELETE" });
}
export async function getRunningBalance(transactionId: number) {
  return _fetchJson(`/transactions/${transactionId}/running-balance`);
}
export async function updateTxnWorkpaperRef(transactionId: number, workpaperRef: string) {
  return _fetchJson(`/transactions/${transactionId}/workpaper-ref`, { method: "PUT", body: JSON.stringify({ workpaper_ref: workpaperRef }) });
}

// ============ Reconciliation ============
export async function importReconciliation(file: File, accountId: number) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("account_id", String(accountId));
  const res = await fetch(`${API_BASE}/reconciliation/import`, {
    method: "POST",
    headers: _authHeaders(false),
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
export async function autoMatch(importId: number) {
  return _fetchJson(`/reconciliation/${importId}/auto-match`, { method: "POST" });
}
export async function manualMatch(importId: number, data: any) {
  return _fetchJson(`/reconciliation/${importId}/manual-match`, { method: "POST", body: JSON.stringify(data) });
}
export async function unmatch(importId: number, data: any) {
  return _fetchJson(`/reconciliation/${importId}/unmatch`, { method: "POST", body: JSON.stringify(data) });
}
export async function getUnmatched(importId: number) {
  return _fetchJson(`/reconciliation/${importId}/unmatched`);
}
export async function getMatches(importId: number) {
  return _fetchJson(`/reconciliation/${importId}/matches`);
}
export async function getReconciliationStatus(importId: number) {
  return _fetchJson(`/reconciliation/${importId}/status`);
}
export async function completeReconciliation(importId: number) {
  return _fetchJson(`/reconciliation/${importId}/complete`, { method: "POST" });
}
export async function reopenReconciliation(importId: number) {
  return _fetchJson(`/reconciliation/${importId}/reopen`, { method: "POST" });
}

// ============ Recurring ============
export async function getRecurringRules() {
  return _fetchJson(`/recurring/`);
}
export async function createRecurringRule(data: any) {
  return _fetchJson(`/recurring/`, { method: "POST", body: JSON.stringify(data) });
}
export async function updateRecurringRule(ruleId: number, data: any) {
  return _fetchJson(`/recurring/${ruleId}`, { method: "PUT", body: JSON.stringify(data) });
}
export async function deleteRecurringRule(ruleId: number) {
  return _fetchJson(`/recurring/${ruleId}`, { method: "DELETE" });
}
export async function materializeRecurring(ruleId: number) {
  return _fetchJson(`/recurring/${ruleId}/materialize`, { method: "POST" });
}

// ============ Reports ============
export async function postProfitLoss(data: any) {
  return _fetchJson(`/reports/profit-and-loss`, { method: "POST", body: JSON.stringify(data) });
}
export async function postTrialBalance(params: any, body: any = {}) {
  const qs = new URLSearchParams(params).toString();
  return _fetchJson(`/reports/trial-balance${qs ? `?${qs}` : ""}`, { method: "POST", body: JSON.stringify(body) });
}
export async function postBalanceSheet(params: any, body: any = {}) {
  const qs = new URLSearchParams(params).toString();
  return _fetchJson(`/reports/balance-sheet${qs ? `?${qs}` : ""}`, { method: "POST", body: JSON.stringify(body) });
}
export async function postCashFlow(data: any, basis: string = "accrual") {
  return _fetchJson(`/reports/cash-flow?basis=${basis}`, { method: "POST", body: JSON.stringify(data) });
}

// ============ Budget ============
export async function createBudgetLine(data: any) {
  return _fetchJson(`/budget/lines`, { method: "POST", body: JSON.stringify(data) });
}
export async function getBudgetVsActual(period: string) {
  return _fetchJson(`/budget/${period}/vs-actual`);
}
export async function getCashFlow13Week() {
  return _fetchJson(`/budget/cash-flow-13-week`);
}
export async function getVarianceAlerts(period: string) {
  return _fetchJson(`/budget/${period}/variance-alerts`);
}

// ============ Profiles ============
export async function getProfiles() {
  return _fetchJson(`/profiles/`);
}
export async function getProfile(profileId: number) {
  return _fetchJson(`/profiles/${profileId}`);
}
export async function getProfileMembers(profileId: number) {
  return _fetchJson(`/profiles/${profileId}/members`);
}
export async function addProfileMember(profileId: number, data: any) {
  return _fetchJson(`/profiles/${profileId}/members`, { method: "POST", body: JSON.stringify(data) });
}
export async function updateProfileMember(profileId: number, userId: number, data: any) {
  return _fetchJson(`/profiles/${profileId}/members/${userId}`, { method: "PATCH", body: JSON.stringify(data) });
}
export async function removeProfileMember(profileId: number, userId: number) {
  return _fetchJson(`/profiles/${profileId}/members/${userId}`, { method: "DELETE" });
}

// ============ Checks ============
export async function getChecks(accountId: number) {
  return _fetchJson(`/checks/${accountId}`);
}
export async function writeCheck(data: any) {
  return _fetchJson(`/checks/`, { method: "POST", body: JSON.stringify(data) });
}
export async function voidCheck(transactionId: number) {
  return _fetchJson(`/checks/${transactionId}/void`, { method: "PATCH" });
}

// ============ FX ============
export async function getFxRates() {
  return _fetchJson(`/fx/rates`);
}
export async function createFxRate(data: any) {
  return _fetchJson(`/fx/rates`, { method: "POST", body: JSON.stringify(data) });
}
export async function convertFx(data: any) {
  return _fetchJson(`/fx/convert`, { method: "POST", body: JSON.stringify(data) });
}
export async function getFxConvert(params: any) {
  const qs = new URLSearchParams(params).toString();
  return _fetchJson(`/fx/convert${qs ? `?${qs}` : ""}`);
}
export async function markForeignTxn(transactionId: number, data: any) {
  return _fetchJson(`/fx/transactions/${transactionId}/foreign`, { method: "POST", body: JSON.stringify(data) });
}
export async function settleForeignTxn(transactionId: number, data: any) {
  return _fetchJson(`/fx/transactions/${transactionId}/settle`, { method: "POST", body: JSON.stringify(data) });
}
export async function getFxReport(params?: any) {
  const qs = new URLSearchParams(params).toString();
  return _fetchJson(`/fx/report${qs ? `?${qs}` : ""}`);
}

// ============ Inventory ============
export async function getInventoryItems() {
  return _fetchJson(`/inventory/`);
}
export async function createInventoryItem(data: any) {
  return _fetchJson(`/inventory/`, { method: "POST", body: JSON.stringify(data) });
}
export async function getInventoryItem(itemId: number) {
  return _fetchJson(`/inventory/${itemId}`);
}
export async function updateInventoryItem(itemId: number, data: any) {
  return _fetchJson(`/inventory/${itemId}`, { method: "PUT", body: JSON.stringify(data) });
}
export async function adjustInventory(itemId: number, data: any) {
  return _fetchJson(`/inventory/${itemId}/adjust`, { method: "POST", body: JSON.stringify(data) });
}
export async function getInventoryTransactions(itemId: number) {
  return _fetchJson(`/inventory/${itemId}/transactions`);
}
export async function getInventoryValuation(itemId: number) {
  return _fetchJson(`/inventory/${itemId}/valuation`);
}
export async function getInventoryTags(params?: any) {
  const qs = new URLSearchParams(params).toString();
  return _fetchJson(`/inventory/tags${qs ? `?${qs}` : ""}`);
}
export async function searchInventoryTags(q: string) {
  return _fetchJson(`/inventory/tags/search?q=${encodeURIComponent(q)}`);
}
export async function tagInventoryTransaction(transactionId: number, data: any) {
  return _fetchJson(`/inventory/tags/${transactionId}`, { method: "POST", body: JSON.stringify(data) });
}
export async function untagInventoryTransaction(transactionId: number) {
  return _fetchJson(`/inventory/tags/${transactionId}`, { method: "DELETE" });
}

// ============ ML ============
export async function getMlStatus() {
  return _fetchJson(`/ml/status`);
}
export async function toggleMl(enabled: boolean) {
  return _fetchJson(`/ml/toggle`, { method: "POST", body: JSON.stringify({ enabled }) });
}
export async function trainMl() {
  return _fetchJson(`/ml/train`, { method: "POST" });
}
export async function getMlModelInfo() {
  return _fetchJson(`/ml/model-info`);
}
export async function categorizeStatement(statementId: number) {
  return _fetchJson(`/ml/categorize/${statementId}`, { method: "POST" });
}

// ============ Auth ============
export async function getAuthStatus() {
  return _fetchJson(`/auth/status`);
}
export async function authBoot(data: any) {
  return _fetchJson(`/auth/boot`, { method: "POST", body: JSON.stringify(data) });
}
export async function register(data: any) {
  return _fetchJson(`/auth/register`, { method: "POST", body: JSON.stringify(data) });
}
export async function loginJson(data: any) {
  return _fetchJson(`/auth/login-json`, { method: "POST", body: JSON.stringify(data) });
}
export async function refreshToken() {
  return _fetchJson(`/auth/refresh`, { method: "POST" });
}
export async function changePassword(data: any) {
  return _fetchJson(`/auth/change-password`, { method: "POST", body: JSON.stringify(data) });
}
export async function getMe() {
  return _fetchJson(`/auth/me`);
}
export async function logout() {
  return _fetchJson(`/auth/logout`, { method: "POST" });
}