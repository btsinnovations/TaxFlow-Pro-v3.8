import { http, HttpResponse } from "msw";

/**
 * MSW handlers for all v3.11 API paths.
 * These mocks are used in dev mode and in Vitest component tests.
 */

// ----- COA -----
const coaAccounts = [
  { id: 1, number: "1000", name: "Cash in Bank", type: "asset", parent_id: null, is_active: true },
  { id: 2, number: "1200", name: "Accounts Receivable", type: "asset", parent_id: null, is_active: true },
  { id: 3, number: "2000", name: "Accounts Payable", type: "liability", parent_id: null, is_active: true },
  { id: 4, number: "3000", name: "Owner's Equity", type: "equity", parent_id: null, is_active: true },
  { id: 5, number: "4000", name: "Sales Revenue", type: "income", parent_id: null, is_active: true },
  { id: 6, number: "5000", name: "Office Supplies", type: "expense", parent_id: null, is_active: true },
];

export const handlers = [
  // ----- COA -----
  http.get("/api/coa", () => HttpResponse.json(coaAccounts)),
  http.post("/api/coa", async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    const newAccount = {
      id: coaAccounts.length + 1,
      ...body,
      is_active: true,
      parent_id: body.parent_id ?? null,
    } as Record<string, unknown>;
    coaAccounts.push(newAccount as typeof coaAccounts[number]);
    return HttpResponse.json(newAccount, { status: 201 });
  }),
  http.put("/api/coa/:id", async ({ params, request }) => {
    const id = Number(params.id);
    const idx = coaAccounts.findIndex((a) => a.id === id);
    if (idx === -1) return HttpResponse.json({ detail: "Not found" }, { status: 404 });
    const body = await request.json() as Record<string, unknown>;
    coaAccounts[idx] = { ...coaAccounts[idx], ...body };
    return HttpResponse.json(coaAccounts[idx]);
  }),
  http.delete("/api/coa/:id", ({ params }) => {
    const id = Number(params.id);
    const idx = coaAccounts.findIndex((a) => a.id === id);
    if (idx === -1) return HttpResponse.json({ detail: "Not found" }, { status: 404 });
    coaAccounts.splice(idx, 1);
    return HttpResponse.json({ deleted: true });
  }),
  http.post("/api/coa/seed", () => HttpResponse.json({ seeded: true, count: coaAccounts.length })),

  // ----- Transactions / Register -----
  http.get("/api/transactions", () => HttpResponse.json([
    { id: 1, date: "2026-01-15", description: "Opening Balance", amount: 5000.0, tx_type: "credit", account_id: 1 },
    { id: 2, date: "2026-01-20", description: "Office Rent", amount: -1500.0, tx_type: "debit", account_id: 1 },
  ])),
  http.post("/api/transactions", async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ id: 3, ...body }, { status: 201 });
  }),
  http.put("/api/transactions/:id", async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ id: Number(params.id), ...body });
  }),
  http.delete("/api/transactions/:id", () => HttpResponse.json({ deleted: true })),
  http.post("/api/transactions/:id/splits", async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ id: 1, ...body }, { status: 201 });
  }),

  // ----- Recurring -----
  http.get("/api/recurring", () => HttpResponse.json([
    { id: 1, name: "Monthly Rent", amount: -1500.0, frequency: "monthly", next_date: "2026-02-01" },
  ])),
  http.post("/api/recurring", async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ id: 2, ...body }, { status: 201 });
  }),
  http.put("/api/recurring/:id", async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ id: Number(params.id), ...body });
  }),
  http.delete("/api/recurring/:id", () => HttpResponse.json({ deleted: true })),

  // ----- Checks -----
  http.get("/api/checks", () => HttpResponse.json([
    { id: 1, check_number: 1001, date: "2026-01-15", payee: "ABC Corp", amount: 500.0, cleared: false },
  ])),
  http.post("/api/checks", async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ id: 2, ...body }, { status: 201 });
  }),

  // ----- Inventory -----
  http.get("/api/inventory", () => HttpResponse.json([
    { id: 1, name: "Widget A", sku: "WID-A", quantity: 100, unit_cost: 5.50, sell_price: 12.00 },
  ])),
  http.post("/api/inventory", async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ id: 2, ...body }, { status: 201 });
  }),

  // ----- FX -----
  http.get("/api/fx", () => HttpResponse.json([
    { id: 1, from_currency: "EUR", to_currency: "USD", rate: 1.08, date: "2026-01-15" },
  ])),
  http.post("/api/fx/convert", async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    const amount = Number(body.amount) || 100;
    const rate = Number(body.rate) || 1.08;
    return HttpResponse.json({ converted: amount * rate, rate, ...body });
  }),

  // ----- Reconciliation -----
  http.get("/api/reconciliation", () => HttpResponse.json([
    { id: 1, import_date: "2026-01-15", status: "matched", account_id: 1, matched_count: 5 },
  ])),
  http.post("/api/reconciliation/import", async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ id: 2, status: "pending", ...body }, { status: 201 });
  }),

  // ----- Reports -----
  http.get("/api/reports", () => HttpResponse.json({ available: ["pnl", "balance_sheet", "cash_flow", "trial_balance"] })),
  http.get("/api/reports/pnl", () => HttpResponse.json({
    revenue: 50000, expenses: 30000, net_income: 20000, period: "2026-01",
  })),
  http.get("/api/reports/balance_sheet", () => HttpResponse.json({
    assets: 120000, liabilities: 45000, equity: 75000, as_of: "2026-01-31",
  })),
  http.get("/api/reports/cash_flow", () => HttpResponse.json({
    operating: 15000, investing: -5000, financing: -2000, net: 8000, period: "2026-01",
  })),
  http.get("/api/reports/trial_balance", () => HttpResponse.json({
    accounts: coaAccounts.map((a) => ({ ...a, balance: 1000.0 })),
  })),

  // ----- Budget -----
  http.get("/api/budget", () => HttpResponse.json([
    { id: 1, category: "Office Supplies", budgeted: 500.0, actual: 320.0, variance: -180.0 },
  ])),
  http.post("/api/budget", async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ id: 2, ...body }, { status: 201 });
  }),

  // ----- Invoicing / A/P / A/R -----
  http.get("/api/invoices", () => HttpResponse.json([
    { id: 1, number: "INV-001", customer: "Acme LLC", amount: 2500.0, status: "sent", date: "2026-01-15" },
  ])),
  http.post("/api/invoices", async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ id: 2, ...body }, { status: 201 });
  }),
  http.get("/api/bills", () => HttpResponse.json([
    { id: 1, number: "BILL-001", vendor: "Supplier Co", amount: 800.0, status: "unpaid", date: "2026-01-10" },
  ])),
  http.post("/api/bills", async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ id: 2, ...body }, { status: 201 });
  }),
  http.get("/api/payments", () => HttpResponse.json([
    { id: 1, invoice_id: 1, amount: 2500.0, date: "2026-01-20", method: "bank_transfer" },
  ])),
  http.post("/api/payments", async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ id: 2, ...body }, { status: 201 });
  }),

  // ----- Liabilities -----
  http.get("/api/liabilities", () => HttpResponse.json([
    { id: 1, name: "Business Loan", principal: 50000.0, rate: 0.075, remaining: 42000.0, monthly_payment: 950.0 },
  ])),
  http.post("/api/liabilities", async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ id: 2, ...body }, { status: 201 });
  }),

  // ----- Investments -----
  http.get("/api/investments", () => HttpResponse.json([
    { id: 1, name: "S&P 500 ETF", symbol: "VOO", shares: 50, cost_basis: 18000.0, current_value: 21500.0 },
  ])),
  http.post("/api/investments", async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ id: 2, ...body }, { status: 201 });
  }),

  // ----- Profiles -----
  http.get("/api/profiles", () => HttpResponse.json([
    { id: 1, name: "Test Client", user_id: 1 },
  ])),
  http.get("/api/profiles/:id", ({ params }) => HttpResponse.json({
    id: Number(params.id), name: "Test Client", user_id: 1,
  })),
  http.get("/api/profiles/:id/members", () => HttpResponse.json([
    { user_id: 1, role: "owner" },
  ])),
  http.post("/api/profiles/:id/members", async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ ...body }, { status: 200 });
  }),

  // ----- Auth -----
  http.post("/api/auth/login", () => HttpResponse.json({
    access_token: "mock-token",
    token_type: "bearer",
  })),
  http.get("/api/health", () => HttpResponse.json({ status: "ok", version: "3.11.6" })),
];