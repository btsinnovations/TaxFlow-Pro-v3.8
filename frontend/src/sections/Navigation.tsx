import { useState, useEffect } from "react";
import { Menu, X, LogIn, LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/hooks/useToast";
import LoginModal from "@/components/LoginModal";

const navLinks = [
  { label: "Upload", href: "/upload" },
  { label: "Dashboard", href: "/" },
  { label: "Reports", href: "/reports" },
  { label: "GL", href: "/gl" },
  { label: "COA", href: "/accounts" },
  { label: "Clients", href: "/clients" },
  { label: "Vendors", href: "/vendors" },
  { label: "Tax", href: "/tax" },
  { label: "Year-End", href: "/year-end" },
  { label: "Health", href: "/health" },
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

          <div className="hidden md:flex items-center gap-8">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="font-sans text-sm text-text-secondary hover:text-gold transition-colors"
              >
                {link.label}
              </a>
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
          <div className="md:hidden bg-canvas border-t border-divider px-4 py-4 space-y-3">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="block font-sans text-sm text-text-secondary hover:text-gold transition-colors"
                onClick={() => setMobileOpen(false)}
              >
                {link.label}
              </a>
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
