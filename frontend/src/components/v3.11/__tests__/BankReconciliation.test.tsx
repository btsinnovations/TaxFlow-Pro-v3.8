import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import BankReconciliation from "../BankReconciliation";

// MSW server is started in test setup (src/test/setup.ts) and provides
// mock handlers for all /api/* endpoints. We no longer need to mock
// the useAPI hook directly — MSW intercepts the fetch calls.

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>{children}</MemoryRouter>
);

// Provide a token in localStorage so _authHeaders works.
beforeEach(() => {
  localStorage.setItem("token", "mock-token");
});

afterEach(() => {
  localStorage.removeItem("token");
});

describe("BankReconciliation", () => {
  it("renders the module shell", () => {
    render(<BankReconciliation />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: /Bank Reconciliation/i })).toBeInTheDocument();
  });

  it("loads accounts via MSW-mocked API", async () => {
    render(<BankReconciliation />, { wrapper: Wrapper });
    // The component calls getAccounts() on mount which fetches /api/accounts/
    // MSW intercepts this and returns an empty array (default handler).
    // The component should render without crashing.
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Bank Reconciliation/i })).toBeInTheDocument();
    });
  });

  it("shows empty state when no matches are loaded", () => {
    render(<BankReconciliation />, { wrapper: Wrapper });
    expect(screen.getByText(/Import a statement and run auto-match/i)).toBeInTheDocument();
  });

  it("renders the import button", () => {
    render(<BankReconciliation />, { wrapper: Wrapper });
    expect(screen.getByRole("button", { name: /Import/i })).toBeInTheDocument();
  });

  it("renders the account selector", () => {
    render(<BankReconciliation />, { wrapper: Wrapper });
    // The select element should be present even if no accounts are loaded.
    const select = document.querySelector("select");
    expect(select).toBeInTheDocument();
  });
});