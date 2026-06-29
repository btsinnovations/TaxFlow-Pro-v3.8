import { useState, useEffect } from "react";
import { Menu, X, LogIn, LogOut, ChevronDown } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/hooks/useToast";
import LoginModal from "@/components/LoginModal";

const navGroups = [
  {
    label: "Overview",
    links: [
      { label: "Dashboard", href: "/" },
      { label: "Health", href: "/health" },
    ],
  },
  {
    label: "Transactions",
    links: [
      { label: "Upload", href: "/upload" },
      { label: "Imports", href: "/imports" },
      { label: "Reconciliation", href: "/reconciliation" },
      { label: "Checks", href: "/check-register" },
      { label: "Recurring", href: "/recurring" },
      { label: "Flags", href: "/flags" },
    ],
  },
  {
    label: "Accounting",
    links: [
      { label: "GL", href: "/gl" },
      { label: "COA", href: "/accounts" },
      { label: "Reports", href: "/reports" },
      { label: "Budget", href: "/budget-forecast" },
      { label: "Periods", href: "/periods" },
      { label: "Year-End", href: "/year-end" },
    ],
  },
  {
    label: "Entities",
    links: [
      { label: "Clients", href: "/clients" },
      { label: "Vendors", href: "/vendors" },
      { label: "Invoicing", href: "/invoicing" },
    ],
  },
  {
    label: "Tax",
    links: [
      { label: "Tax Rules", href: "/tax" },
      { label: "Tax Exports", href: "/tax-exports" },
      { label: "Sales Tax", href: "/sales-tax" },
    ],
  },
  {
    label: "Assets",
    links: [
      { label: "Depreciation", href: "/depreciation" },
      { label: "Investments", href: "/investments" },
      { label: "Inventory", href: "/" },
      { label: "Liabilities", href: "/liabilities" },
      { label: "Mileage", href: "/mileage" },
    ],
  },
  {
    label: "System",
    links: [
      { label: "Audit", href: "/audit" },
      { label: "Backup", href: "/backup" },
      { label: "Export", href: "/export" },
      { label: "Rules", href: "/rules" },
      { label: "Multi-Currency", href: "/multi-currency" },
      { label: "Register", href: "/register" },
    ],
  },
];

export default function Navigation() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);
  const { user, isAuthenticated, logout } = useAuth();
  const { addToast } = useToast();

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const handleLogout = () => {
    logout();
    addToast("Logged out successfully", "info");
  };

  return (
    <>
      <nav
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          scrolled ? "bg-canvas/95 backdrop-blur-md border-b border-divider" : "bg-transparent"
        }`}
      >
        <div className="max-w-[1440px] mx-auto px-4 md:px-8 h-16 flex items-center justify-between">
          <a href="/" className="font-serif text-xl text-gold tracking-tight">
            TaxFlow Pro
          </a>

          <div className="hidden md:flex items-center gap-1">
            {navGroups.map((group) => (
              <div key={group.label} className="relative group">
                <button className="font-sans text-sm text-text-secondary hover:text-gold transition-colors flex items-center gap-0.5 px-2 py-1">
                  {group.label}
                  <ChevronDown className="w-3 h-3" />
                </button>
                <div className="absolute top-full left-0 hidden group-hover:block bg-canvas border border-divider rounded-md shadow-lg min-w-[160px] z-50">
                  {group.links.map((link) => (
                    <a
                      key={link.href}
                      href={link.href}
                      className="block px-3 py-1.5 font-sans text-sm text-text-secondary hover:text-gold hover:bg-gold/5 transition-colors"
                    >
                      {link.label}
                    </a>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-3">
            {isAuthenticated && user ? (
              <>
                <span className="font-sans text-sm text-text-secondary">{user.username}</span>
                <div className="w-8 h-8 rounded-full bg-gold flex items-center justify-center text-canvas text-xs font-semibold">
                  {user.username.slice(0, 2).toUpperCase()}
                </div>
                <button
                  onClick={handleLogout}
                  className="p-1.5 rounded hover:bg-white/5 transition-colors text-text-secondary"
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

          <button
            className="md:hidden p-2 text-text-secondary"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label="Toggle menu"
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {mobileOpen && (
          <div className="md:hidden bg-canvas border-t border-divider px-4 py-4 space-y-4">
            {navGroups.map((group) => (
              <div key={group.label}>
                <p className="font-sans text-xs text-gold/70 uppercase tracking-wide mb-2">{group.label}</p>
                <div className="space-y-1 pl-2">
                  {group.links.map((link) => (
                    <a
                      key={link.href}
                      href={link.href}
                      className="block font-sans text-sm text-text-secondary hover:text-gold transition-colors"
                      onClick={() => setMobileOpen(false)}
                    >
                      {link.label}
                    </a>
                  ))}
                </div>
              </div>
            ))}
            <div className="border-t border-divider pt-3">
              {isAuthenticated && user ? (
                <div className="flex items-center justify-between">
                  <span className="font-sans text-sm text-text-secondary">{user.username}</span>
                  <button onClick={handleLogout} className="text-gold text-sm">Logout</button>
                </div>
              ) : (
                <button onClick={() => setLoginOpen(true)} className="text-gold text-sm">Sign In</button>
              )}
            </div>
          </div>
        )}
      </nav>
      <LoginModal isOpen={loginOpen} onClose={() => setLoginOpen(false)} />
    </>
  );
}
