import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { getAccessToken, setAccessToken, tryRefreshAccessToken } from '@/services/api';
import {
  authService,
  type AuthEnvelope,
  type AuthUser,
  type RegisterPayload,
} from '@/services/authService';
import { Spinner } from '@/components';

interface AuthContextValue {
  currentUser: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (identifier: string, password: string) => Promise<AuthEnvelope>;
  register: (payload: RegisterPayload) => Promise<AuthEnvelope>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Centralized authentication state. On boot it silently refreshes the
 * session from the HttpOnly cookie before rendering, preventing the
 * "login page flash" for already-authenticated users.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const bootstrapped = useRef(false);

  const signOutState = useCallback(() => {
    setAccessToken(null);
    setCurrentUser(null);
  }, []);

  const loadUser = useCallback(async (): Promise<AuthUser | null> => {
    try {
      const user = await authService.me();
      setCurrentUser(user);
      return user;
    } catch {
      signOutState();
      return null;
    }
  }, [signOutState]);

  // Boot: rotate the access token from the refresh cookie, then load /me.
  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    (async () => {
      const token = getAccessToken();
      if (token) {
        await loadUser();
      } else {
        const refreshed = await tryRefreshAccessToken();
        if (refreshed) {
          await loadUser();
        }
      }
      setIsLoading(false);
    })();
  }, [loadUser]);

  // Global session-expiry event from the api client.
  useEffect(() => {
    const onExpired = () => signOutState();
    window.addEventListener('auth:expired', onExpired);
    return () => window.removeEventListener('auth:expired', onExpired);
  }, [signOutState]);

  const login = useCallback(
    async (identifier: string, password: string) => {
      const envelope = await authService.login(identifier, password);
      if (envelope.success && envelope.data?.user) {
        setCurrentUser(envelope.data.user);
      }
      return envelope;
    },
    [],
  );

  const register = useCallback(async (payload: RegisterPayload) => {
    const envelope = await authService.register(payload);
    if (envelope.success && envelope.data?.user) {
      setCurrentUser(envelope.data.user);
    }
    return envelope;
  }, []);

  const logout = useCallback(async () => {
    await authService.logout();
    signOutState();
  }, [signOutState]);

  const refreshUser = useCallback(async () => {
    await loadUser();
  }, [loadUser]);

  const value = useMemo<AuthContextValue>(
    () => ({
      currentUser,
      isAuthenticated: currentUser !== null,
      isLoading,
      login,
      register,
      logout,
      refreshUser,
    }),
    [currentUser, isLoading, login, register, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

/** Full-screen splash used while the auth state is booting. */
export function AuthBootSplash(): ReactNode {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-surface-50">
      <Spinner size="lg" label="Checking your session" />
    </div>
  );
}

/** Blocks rendering of protected children until authenticated. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <AuthBootSplash />;
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

/** Keeps authenticated users away from login/signup screens. */
export function RequireGuest({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <AuthBootSplash />;
  }
  if (isAuthenticated) {
    return <Navigate to="/home" replace />;
  }
  return <>{children}</>;
}
