import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import ReportsCenter from "../ReportsCenter";

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>{children}</MemoryRouter>
);

describe("ReportsCenter", () => {
  it("renders the module shell", () => {
    render(<ReportsCenter />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: /Reports Center/i })).toBeInTheDocument();
  });
});
