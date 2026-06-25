import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import BankReconciliation from "../BankReconciliation";

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>{children}</MemoryRouter>
);

describe("BankReconciliation", () => {
  it("renders the module shell", () => {
    render(<BankReconciliation />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: /Bank Reconciliation/i })).toBeInTheDocument();
  });
});
