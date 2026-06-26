import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import BudgetForecast from "../BudgetForecast";

vi.mock("@/hooks/useAPI", () => ({
  fetchWithAuth: vi.fn().mockResolvedValue({ ok: true, json: async () => [] }),
  getAccounts: vi.fn().mockResolvedValue([]),
}));

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>{children}</MemoryRouter>
);

describe("BudgetForecast", () => {
  it("renders the module shell", () => {
    render(<BudgetForecast />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: /Budget & Cash Flow Forecasting/i })).toBeInTheDocument();
  });
});
