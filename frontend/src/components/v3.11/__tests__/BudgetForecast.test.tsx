import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import BudgetForecast from "../BudgetForecast";

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>{children}</MemoryRouter>
);

describe("BudgetForecast", () => {
  it("renders the module shell", () => {
    render(<BudgetForecast />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: /Budget & Cash Flow Forecasting/i })).toBeInTheDocument();
  });
});
