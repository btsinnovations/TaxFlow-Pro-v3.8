import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import InventoryProjects from "../InventoryProjects";

vi.mock("@/hooks/useAPI", () => ({
  fetchWithAuth: vi.fn().mockResolvedValue({ ok: true, json: async () => [] }),
}));

describe("InventoryProjects", () => {
  it("renders the module shell", () => {
    render(
      <MemoryRouter>
        <InventoryProjects />
      </MemoryRouter>
    );
    expect(screen.getByRole("heading", { name: /Inventory & Project Tags/i })).toBeInTheDocument();
  });
});
