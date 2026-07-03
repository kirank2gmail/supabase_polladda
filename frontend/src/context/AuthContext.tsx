import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import * as authApi from "../api/auth";
import { getToken, setToken, setUnauthorizedHandler } from "../api/client";
import type { User } from "../api/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  /** Set after a successful login when the account needs a forced password reset. */
  mustChangePassword: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  completePasswordChange: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [mustChangePassword, setMustChangePassword] = useState(false);

  const clearSession = () => {
    setToken(null);
    setUser(null);
    setMustChangePassword(false);
  };

  useEffect(() => {
    setUnauthorizedHandler(clearSession);

    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then(setUser)
      .catch(() => clearSession())
      .finally(() => setLoading(false));
  }, []);

  const login = async (username: string, password: string) => {
    const resp = await authApi.login(username, password);
    setToken(resp.token);
    setUser(resp.user);
    setMustChangePassword(resp.must_change_password || resp.is_legacy_password);
  };

  const logout = () => {
    authApi.logout().catch(() => {
      /* best-effort — clear local session regardless */
    });
    clearSession();
  };

  const completePasswordChange = () => {
    setMustChangePassword(false);
    setUser((u) => (u ? { ...u, must_change_password: false } : u));
  };

  const refreshUser = async () => {
    const u = await authApi.me();
    setUser(u);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        mustChangePassword,
        login,
        logout,
        completePasswordChange,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
