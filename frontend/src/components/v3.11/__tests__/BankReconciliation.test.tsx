import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import BankReconciliation from "../BankReconciliation";

vi.mock("@/hooks/useAPI", () => ({
  fetchWithAuth: vi.fn().mockResolvedValue({ ok: true, json: async () => [] }),
  getAccounts: vi.fn().mockResolvedValue([]),
}));

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>{children}</MemoryRouter>
);

describe("BankReconciliation", () => {
  it("renders the module shell", () => {
    render(<BankReconciliation />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: /Bank Reconciliation/i })).toBeInTheDocument();
  });
});
