import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import { loginUser, registerUser, logoutUser, getMe, getAuthStatus, bootLocalAdmin } from "@/hooks/useAPI";

interface AuthUser {
  username: string;
  email?: string;
}

interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isFirstBoot: boolean | null;
  boot: (password: string) => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isFirstBoot, setIsFirstBoot] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    getAuthStatus()
      .then((status) => {
        if (cancelled) return;
        const firstBoot = !!status.first_boot;
        setIsFirstBoot(firstBoot);
        const token = localStorage.getItem("token");
        if (token && !firstBoot) {
          return getMe()
            .then((data) => setUser(data))
            .catch(() => {
              localStorage.removeItem("token");
              setUser(null);
            });
        } else {
          setUser(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setIsFirstBoot(false);
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const boot = async (password: string) => {
    const data = await bootLocalAdmin(password);
    localStorage.setItem("token", data.access_token);
    const me = await getMe();
    setUser(me);
    setIsFirstBoot(false);
  };

  const login = async (username: string, password: string) => {
    const data = await loginUser(username, password);
    localStorage.setItem("token", data.access_token);
    const me = await getMe();
    setUser(me);
  };

  const register = async (username: string, email: string, password: string) => {
    await registerUser(username, password, email);  // Creates account
    const data = await loginUser(username, password);  // Auto-login
    localStorage.setItem("token", data.access_token);
    const me = await getMe();
    setUser(me);
  };

  const logout = () => {
    logoutUser();
    localStorage.removeItem("token");
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        isFirstBoot,
        boot,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
