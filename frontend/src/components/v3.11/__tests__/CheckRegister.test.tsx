import { render, screen, waitFor } from "@testing-library/react";
import CheckRegister from "../CheckRegister";

const mockFetch = vi.fn();
const mockGetAccounts = vi.fn();

vi.mock("@/hooks/useAPI", () => ({
  fetchWithAuth: (url: string, init?: RequestInit) => mockFetch(url, init),
  getAccounts: () => mockGetAccounts(),
}));

describe("CheckRegister", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockGetAccounts.mockReset();
    mockGetAccounts.mockResolvedValue([{ id: 1, name: "Primary Checking", institution: "Test Bank" }]);
  });

  it("renders the module title and account selector", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => [] } as Response);
    render(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      <CheckRegister />
    );
    expect(screen.getByText("Check Register")).toBeInTheDocument();
    await waitFor(() => expect(mockGetAccounts).toHaveBeenCalled());
    await waitFor(() => expect(mockFetch).toHaveBeenCalledWith("/api/checks/1", undefined));
  });

  it("renders check rows after loading", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => [
        {
          id: 101,
          date: "2026-01-15",
          description: "Rent Payment",
          amount: -1200.0,
          tx_type: "check",
          workpaper_ref: "WP-001",
        },
      ],
    } as Response);
    render(<CheckRegister />);
    await waitFor(() => expect(screen.getByText("Rent Payment")).toBeInTheDocument());
    expect(screen.getByText("WP-001")).toBeInTheDocument();
  });
});
