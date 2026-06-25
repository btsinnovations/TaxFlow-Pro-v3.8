import { render, screen, waitFor } from "@testing-library/react";
import InvoicingAPAR from "../InvoicingAPAR";

const mockFetch = vi.fn();

vi.mock("@/hooks/useAPI", () => ({
  fetchWithAuth: (url: string, init?: RequestInit) => mockFetch(url, init),
}));

describe("InvoicingAPAR", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("renders invoices by default", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => [
        {
          id: 1,
          contact_name: "Acme Corp",
          invoice_number: "INV-001",
          issue_date: "2026-01-01",
          due_date: "2026-02-01",
          total: 500.0,
          amount_paid: 0,
          balance: 500.0,
          status: "open",
          aging_bucket: "current",
        },
      ],
    } as Response);
    render(<InvoicingAPAR />);
    expect(screen.getByText("Invoicing / A/P / A/R")).toBeInTheDocument();
    await waitFor(() => expect(mockFetch).toHaveBeenCalledWith("/api/invoicing/invoices", undefined));
    await waitFor(() => expect(screen.getByText("Acme Corp")).toBeInTheDocument());
  });

  it("switches to bills tab", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => [
        {
          id: 2,
          contact_name: "Supplier Inc",
          invoice_number: "BILL-002",
          issue_date: "2026-01-10",
          due_date: "2026-02-10",
          total: 250.0,
          amount_paid: 0,
          balance: 250.0,
          status: "open",
          aging_bucket: "current",
        },
      ],
    } as Response);
    render(<InvoicingAPAR />);
    const billsTab = await screen.findByRole("tab", { name: /Bills/i });
    billsTab.click();
    await waitFor(() => expect(mockFetch).toHaveBeenLastCalledWith("/api/invoicing/bills", undefined));
    await waitFor(() => expect(screen.getByText("Supplier Inc")).toBeInTheDocument());
  });
});
