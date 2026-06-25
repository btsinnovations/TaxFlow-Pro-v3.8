import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { Lock, Shield } from "lucide-react";

export function BootGate({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, isFirstBoot, boot, login } = useAuth();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleBoot = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    setBusy(true);
    try {
      await boot(password);
    } catch (err: any) {
      setError(err.message || "Setup failed");
    } finally {
      setBusy(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      // v3.10 local mode: server ignores username; only master password matters.
      await login("admin", password);
    } catch (err: any) {
      setError(err.message || "Login failed");
    } finally {
      setBusy(false);
    }
  };

  if (isLoading || (!isAuthenticated && isFirstBoot === null)) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center text-white/70">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-[#C9A96E] border-t-transparent rounded-full animate-spin" />
          Starting TaxFlow Pro…
        </div>
      </div>
    );
  }

  // Authenticated — render the app
  if (isAuthenticated) return <>{children}</>;

  // Not authenticated — show mandatory gate
  return (
    <div className="min-h-screen bg-black text-white flex items-center justify-center px-6">
      <div className="w-full max-w-md border border-white/10 bg-white/[0.02] rounded-xl p-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 rounded-lg bg-[#C9A96E]/10">
            <Shield className="w-6 h-6 text-[#C9A96E]" />
          </div>
          <div>
            <h2 className="text-xl font-semibold">TaxFlow Pro</h2>
            <p className="text-sm text-white/50">
              {isFirstBoot ? "Create master password" : "Enter master password"}
            </p>
          </div>
        </div>

        <form onSubmit={isFirstBoot ? handleBoot : handleLogin} className="space-y-4">
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={isFirstBoot ? "Create password" : "Master password"}
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-3 text-white placeholder-white/40 focus:outline-none focus:border-[#C9A96E]"
              required
              autoFocus
            />
          </div>

          {isFirstBoot && (
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Confirm password"
                className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-3 text-white placeholder-white/40 focus:outline-none focus:border-[#C9A96E]"
                required
              />
            </div>
          )}

          {error && (
            <div className="text-sm text-red-400 bg-red-400/10 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy || !password}
            className="w-full py-3 bg-[#C9A96E] text-black font-medium rounded-lg hover:bg-[#B8975E] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {busy ? (isFirstBoot ? "Creating…" : "Unlocking…") : isFirstBoot ? "Create Password" : "Unlock"}
          </button>
        </form>
      </div>
    </div>
  );
}
