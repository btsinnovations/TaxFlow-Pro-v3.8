import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import InvoicingAPAR from "../InvoicingAPAR";

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>{children}</MemoryRouter>
);

describe("InvoicingAPAR", () => {
  it("renders the module shell", () => {
    render(<InvoicingAPAR />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: /Invoicing \/ A\/P \/ A\/R/i })).toBeInTheDocument();
  });
});
