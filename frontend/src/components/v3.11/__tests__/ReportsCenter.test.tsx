import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ReportsCenter from "../ReportsCenter";

vi.mock("@/hooks/useAPI", () => ({
  fetchWithAuth: vi.fn().mockResolvedValue({ ok: true, json: async () => [] }),
}));

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>{children}</MemoryRouter>
);

describe("ReportsCenter", () => {
  it("renders the module shell", () => {
    render(<ReportsCenter />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: /Reports Center/i })).toBeInTheDocument();
  });
});
