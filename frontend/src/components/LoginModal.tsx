import { useState } from "react";
import { X } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/hooks/useToast";

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function LoginModal({ isOpen, onClose }: LoginModalProps) {
  const { isFirstBoot, boot, login, isLoading } = useAuth();
  const [mode, setMode] = useState<"login" | "boot">("boot");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { addToast } = useToast();

  // Default to boot mode on first boot if not already chosen
  if (isFirstBoot && mode !== "boot") {
    setMode("boot");
  }

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (mode === "boot" && password !== confirmPassword) {
      setError("Passwords do not match");
      addToast("Passwords do not match", "error");
      return;
    }

    setSubmitting(true);
    try {
      if (mode === "boot") {
        await boot(password);
        addToast("TaxFlow initialized successfully", "success");
      } else {
        await login("local", password);
        addToast("Signed in successfully", "success");
      }
      setPassword("");
      setConfirmPassword("");
      setError("");
      onClose();
    } catch (err: any) {
      const msg = err.message || "Authentication failed";
      setError(msg);
      addToast(msg, "error");
    } finally {
      setSubmitting(false);
    }
  };

  const title = mode === "boot" ? "Initialize TaxFlow" : "Sign In";
  const submitLabel = mode === "boot" ? "Set Master Password" : "Sign In";

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-surface border border-divider rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="font-serif text-xl text-text-primary">{title}</h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-white/5 text-text-secondary">
            <X size={20} />
          </button>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded px-3 py-2 mb-4 text-sm text-red-400">
            {error}
          </div>
        )}

        {isFirstBoot && mode === "boot" && (
          <div className="mb-4 text-sm text-text-secondary">
            Welcome to TaxFlow Pro. Choose a master password to secure your local installation.
            This password is used for all future logins and is never sent to the cloud.
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-text-secondary mb-1">{mode === "boot" ? "Master Password" : "Password"}</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-canvas border border-divider rounded px-3 py-2 text-text-primary focus:outline-none focus:border-gold"
              required
            />
          </div>

          {mode === "boot" && (
            <div>
              <label className="block text-sm text-text-secondary mb-1">Confirm Password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full bg-canvas border border-divider rounded px-3 py-2 text-text-primary focus:outline-none focus:border-gold"
                required
              />
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || isLoading}
            className="w-full bg-gold text-canvas font-semibold py-2 rounded hover:bg-gold/90 transition-colors disabled:opacity-50"
          >
            {submitting ? "Please wait..." : submitLabel}
          </button>
        </form>

        {!isFirstBoot && mode !== "login" && (
          <div className="mt-4 flex justify-center text-sm text-text-secondary">
            Already initialized?{" "}
            <button
              onClick={() => setMode("login")}
              className="ml-1 text-gold hover:underline"
            >
              Sign In
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
