import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import LiabilitiesInvestments from "../LiabilitiesInvestments";

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>{children}</MemoryRouter>
);

describe("LiabilitiesInvestments", () => {
  it("renders the module shell", () => {
    render(<LiabilitiesInvestments />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: /Loans, Credit Lines & Investments/i })).toBeInTheDocument();
  });
});
