import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import CheckRegister from "../CheckRegister";

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>{children}</MemoryRouter>
);

describe("CheckRegister", () => {
  it("renders the module shell", () => {
    render(<CheckRegister />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: /Check Register/i })).toBeInTheDocument();
  });
});
