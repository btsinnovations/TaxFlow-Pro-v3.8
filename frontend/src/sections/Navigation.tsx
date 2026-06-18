import { useState, useEffect } from "react";
import { Menu, X, LogIn, LogOut, ChevronRight } from "lucide-react";
import { NavLink, Link, useLocation } from "react-router";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/hooks/useToast";
import LoginModal from "@/components/LoginModal";
import ClientSelector from "@/components/ClientSelector";

interface NavGroup {
  label: string;
  links: { label: string; to: string }[];
}

const navGroups: NavGroup[] = [
  {
    label: "Core",
    links: [
      { label: "Dashboard", to: "/" },
      { label: "Upload", to: "/upload" },
      { label: "Processed Files", to: "/processed-files" },
      { label: "Transactions", to: "/transactions" },
      { label: "Tax Summary", to: "/tax-summary" },
    ],
  },
  {
    label: "Accounting",
    links: [
      { label: "Budgets", to: "/budgets" },
      { label: "Receipts", to: "/receipts" },
      { label: "Journal Entries", to: "/journal-entries" },
      { label: "Periods", to: "/periods" },
      { label: "Reports", to: "/reports" },
    ],
  },
  {
    label: "Tools",
    links: [
      { label: "Forecast", to: "/forecast" },
      { label: "Depreciation", to: "/depreciation" },
      { label: "Bank Connections", to: "/bank-connections" },
      { label: "Batch Import", to: "/batch-import" },
      { label: "Archive & Restore", to: "/archive" },
      { label: "Exchange Rates", to: "/exchange-rates" },
      { label: "Engagements", to: "/engagements" },
    ],
  },
  {
    label: "System",
    links: [
      { label: "Settings", to: "/settings" },
    ],
  },
];

export default function Navigation() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);
  const { user, isAuthenticated, logout } = useAuth();
  const { addToast } = useToast();
  const location = useLocation();

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    logout();
    addToast("Logged out successfully", "info");
  };

  return (
    <>
      <nav
        className={`fixed top-0 left-0 right-0 z-40 transition-all duration-300 ${
          scrolled ? "bg-canvas/95 backdrop-blur-md border-b border-divider" : "bg-transparent"
        }`}
      >
        <div className="max-w-[1440px] mx-auto px-4 md:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              className="p-2 text-text-secondary hover:text-gold transition-colors"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={20} />
            </button>
            <Link to="/" className="font-serif text-xl text-gold tracking-tight">
              TaxFlow Pro
            </Link>
          </div>

          <div className="hidden md:flex items-center gap-6">
            {isAuthenticated && <ClientSelector />}
          </div>

          <div className="flex items-center gap-3">
            {isAuthenticated && user ? (
              <>
                <span className="hidden md:inline font-sans text-sm text-text-secondary">{user.username}</span>
                <div className="w-8 h-8 rounded-full bg-gold flex items-center justify-center text-canvas text-xs font-semibold">
                  {user.username.slice(0, 2).toUpperCase()}
                </div>
                <button
                  onClick={handleLogout}
                  className="hidden md:flex p-1.5 rounded hover:bg-white/5 transition-colors text-text-secondary"
                  title="Logout"
                >
                  <LogOut size={16} />
                </button>
              </>
            ) : (
              <button
                onClick={() => setLoginOpen(true)}
                className="flex items-center gap-1.5 font-sans text-sm text-gold border border-gold/30 px-3 py-1.5 rounded hover:bg-gold/10 transition-colors"
              >
                <LogIn size={14} />
                Sign In
              </button>
            )}
          </div>
        </div>
      </nav>

      {/* Sidebar overlay */}
      <div
        className={`fixed inset-0 z-50 transition-opacity duration-300 ${
          mobileOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
      >
        <div
          className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          onClick={() => setMobileOpen(false)}
        />
        <aside
          className={`absolute top-0 left-0 bottom-0 w-[280px] bg-surface border-r border-divider transform transition-transform duration-300 ${
            mobileOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="h-16 flex items-center justify-between px-4 border-b border-divider">
            <Link to="/" className="font-serif text-xl text-gold tracking-tight">
              TaxFlow Pro
            </Link>
            <button
              onClick={() => setMobileOpen(false)}
              className="p-2 text-text-secondary hover:text-gold transition-colors"
              aria-label="Close navigation"
            >
              <X size={20} />
            </button>
          </div>

          <div className="p-4 border-b border-divider md:hidden">
            {isAuthenticated && <ClientSelector />}
          </div>

          <div className="p-4 overflow-y-auto h-[calc(100%-64px-73px)]">
            {navGroups.map((group) => (
              <div key={group.label} className="mb-6">
                <h3 className="font-mono text-[10px] uppercase tracking-wide text-text-secondary mb-2 px-3">
                  {group.label}
                </h3>
                <div className="space-y-1">
                  {group.links.map((link) => {
                    const isActive =
                      link.to === "/"
                        ? location.pathname === "/"
                        : location.pathname === link.to || location.pathname.startsWith(`${link.to}/`);
                    return (
                      <NavLink
                        key={link.to}
                        to={link.to}
                        className={`flex items-center justify-between px-3 py-2 rounded-md text-sm transition-colors ${
                          isActive
                            ? "bg-gold/10 text-gold border-l-2 border-gold"
                            : "text-text-secondary hover:bg-surface-hover hover:text-text-primary"
                        }`}
                      >
                        {link.label}
                        {isActive && <ChevronRight size={14} />}
                      </NavLink>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {isAuthenticated && (
            <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-divider md:hidden">
              <button
                onClick={handleLogout}
                className="flex items-center gap-2 text-text-secondary hover:text-gold transition-colors text-sm"
              >
                <LogOut size={14} />
                Logout
              </button>
            </div>
          )}
        </aside>
      </div>

      <LoginModal isOpen={loginOpen} onClose={() => setLoginOpen(false)} />
    </>
  );
}
