import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import InventoryProjects from "../InventoryProjects";

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>{children}</MemoryRouter>
);

describe("InventoryProjects", () => {
  it("renders the module shell", () => {
    render(<InventoryProjects />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: /Inventory & Project Tags/i })).toBeInTheDocument();
  });
});
