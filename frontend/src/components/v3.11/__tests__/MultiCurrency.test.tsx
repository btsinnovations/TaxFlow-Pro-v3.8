import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import MultiCurrency from "../MultiCurrency";

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>{children}</MemoryRouter>
);

describe("MultiCurrency", () => {
  it("renders the module shell", () => {
    render(<MultiCurrency />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: /Multi-Currency/i })).toBeInTheDocument();
  });
});
