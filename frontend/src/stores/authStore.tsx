import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import {
  getAuthToken,
  setAuthToken,
  setUnauthorizedHandler,
} from "../api/apiClient";
import { getAuthMe } from "../api/authApi";
import type { AuthRole } from "../types/auth";

type AuthStatus = "loading" | "ready";

export type AuthState = {
  status: AuthStatus;
  authEnabled: boolean;
  authenticated: boolean;
  role: AuthRole | null;
  /** True only when auth is enabled and the user is not yet authenticated. */
  gated: boolean;
  login: (token: string) => Promise<void>;
  logout: () => void;
};

export class InvalidTokenError extends Error {
  constructor(message = "访问令牌无效，请检查后重试") {
    super(message);
    this.name = "InvalidTokenError";
  }
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [authEnabled, setAuthEnabled] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [role, setRole] = useState<AuthRole | null>(null);

  // Called by the api client on any 401: token is already cleared there.
  const handleUnauthorized = useCallback(() => {
    setAuthenticated(false);
    setRole(null);
    // Keep authEnabled as-is so the login gate (not a blank app) is shown.
    setAuthEnabled(true);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(handleUnauthorized);
    return () => setUnauthorizedHandler(null);
  }, [handleUnauthorized]);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const me = await getAuthMe(getAuthToken() ?? undefined);
        if (cancelled) {
          return;
        }
        setAuthEnabled(me.auth_enabled);
        setAuthenticated(me.authenticated);
        setRole(me.role);
        // A stored-but-rejected token (auth on, not authenticated) is stale.
        if (me.auth_enabled && !me.authenticated) {
          setAuthToken(null);
        }
      } catch {
        if (cancelled) {
          return;
        }
        // Could not reach /api/auth/me. Fail open as auth-disabled so the app
        // behaves as today rather than locking the user out of a local tool.
        setAuthEnabled(false);
        setAuthenticated(false);
        setRole(null);
      } finally {
        if (!cancelled) {
          setStatus("ready");
        }
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (token: string) => {
    const trimmed = token.trim();
    if (!trimmed) {
      throw new InvalidTokenError("请输入访问令牌");
    }

    let me;
    try {
      me = await getAuthMe(trimmed);
    } catch {
      throw new InvalidTokenError("无法验证令牌，请确认服务可用后重试");
    }

    if (!me.authenticated) {
      throw new InvalidTokenError();
    }

    setAuthToken(trimmed);
    setAuthEnabled(me.auth_enabled);
    setAuthenticated(true);
    setRole(me.role);
  }, []);

  const logout = useCallback(() => {
    setAuthToken(null);
    setAuthenticated(false);
    setRole(null);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      status,
      authEnabled,
      authenticated,
      role,
      gated: authEnabled && !authenticated,
      login,
      logout,
    }),
    [status, authEnabled, authenticated, role, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
