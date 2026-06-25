import { render, screen, waitFor } from "@testing-library/react";
import InventoryProjects from "../InventoryProjects";

const mockFetch = vi.fn();

vi.mock("@/hooks/useAPI", () => ({
  fetchWithAuth: (url: string, init?: RequestInit) => mockFetch(url, init),
}));

describe("InventoryProjects", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("renders the module title and loads inventory", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => [
        { id: 1, sku: "WDGT-001", name: "Widget", qty_on_hand: 12, unit_cost: 9.99, valuation_method: "average" },
      ],
    } as Response);
    render(<InventoryProjects />);
    expect(screen.getByText("Inventory & Project Tags")).toBeInTheDocument();
    await waitFor(() => expect(mockFetch).toHaveBeenCalledWith("/api/inventory/", undefined));
    await waitFor(() => expect(screen.getByText("Widget")).toBeInTheDocument());
  });
});
