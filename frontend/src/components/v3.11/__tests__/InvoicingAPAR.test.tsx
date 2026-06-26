import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import InvoicingAPAR from "../InvoicingAPAR";

vi.mock("@/hooks/useAPI", () => ({
  fetchWithAuth: vi.fn().mockResolvedValue({ ok: true, json: async () => [] }),
}));

describe("InvoicingAPAR", () => {
  it("renders the module shell", () => {
    render(
      <MemoryRouter>
        <InvoicingAPAR />
      </MemoryRouter>
    );
    expect(screen.getByRole("heading", { name: /Invoicing \/ A\/P \/ A\/R/i })).toBeInTheDocument();
  });
});
