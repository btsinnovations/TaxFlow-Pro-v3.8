import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import CheckRegister from "../CheckRegister";

vi.mock("@/hooks/useAPI", () => ({
  fetchWithAuth: vi.fn().mockResolvedValue({ ok: true, json: async () => [] }),
  getAccounts: vi.fn().mockResolvedValue([]),
}));

describe("CheckRegister", () => {
  it("renders the module shell", () => {
    render(
      <MemoryRouter>
        <CheckRegister />
      </MemoryRouter>
    );
    expect(screen.getByRole("heading", { name: /Check Register/i })).toBeInTheDocument();
  });
});
