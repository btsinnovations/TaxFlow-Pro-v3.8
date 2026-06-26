import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import TaxFilingExports from "../TaxFilingExports";

vi.mock("@/hooks/useAPI", () => ({
  fetchWithAuth: vi.fn().mockResolvedValue({ ok: true, json: async () => [] }),
  getAccounts: vi.fn().mockResolvedValue([]),
}));

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>{children}</MemoryRouter>
);

describe("TaxFilingExports", () => {
  it("renders the module shell", () => {
    render(<TaxFilingExports />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: /Tax Filing Exports/i })).toBeInTheDocument();
  });
});
