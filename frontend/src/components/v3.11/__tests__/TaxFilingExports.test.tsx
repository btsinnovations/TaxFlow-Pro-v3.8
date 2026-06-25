import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import TaxFilingExports from "../TaxFilingExports";

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>{children}</MemoryRouter>
);

describe("TaxFilingExports", () => {
  it("renders the module shell", () => {
    render(<TaxFilingExports />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: /Tax Filing Exports/i })).toBeInTheDocument();
  });
});
