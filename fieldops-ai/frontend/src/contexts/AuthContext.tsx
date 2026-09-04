import { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';
import type { ReactNode } from 'react';
import type { AuthState, LoginCredentials, User } from '@/types/auth.types';
import { authService } from '@/services/auth.service';
import { clearStoredToken, getStoredToken } from '@/services/api';

interface AuthContextType extends AuthState {
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(getStoredToken());
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } finally {
      clearStoredToken();
      setToken(null);
      setUser(null);
    }
  }, []);

  // Restore active user session on app mount
  useEffect(() => {
    let isMounted = true;

    async function initSession() {
      const storedToken = getStoredToken();
      if (!storedToken) {
        if (isMounted) setIsLoading(false);
        return;
      }

      try {
        const currentUser = await authService.getCurrentUser();
        if (isMounted) {
          setUser(currentUser);
          setToken(storedToken);
        }
      } catch {
        if (isMounted) {
          clearStoredToken();
          setToken(null);
          setUser(null);
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    initSession();

    // Listen for unauthorized 401 response events
    const handleUnauthorized = () => {
      logout();
    };

    window.addEventListener('fieldops:unauthorized', handleUnauthorized);
    return () => {
      isMounted = false;
      window.removeEventListener('fieldops:unauthorized', handleUnauthorized);
    };
  }, [logout]);

  const login = useCallback(async (credentials: LoginCredentials) => {
    setIsLoading(true);
    try {
      const response = await authService.login(credentials);
      
      // Store token based on remember_me option
      if (credentials.remember_me) {
        localStorage.setItem('fieldops_token', response.access_token);
        sessionStorage.removeItem('fieldops_token');
      } else {
        sessionStorage.setItem('fieldops_token', response.access_token);
        localStorage.removeItem('fieldops_token');
      }

      setToken(response.access_token);
      setUser(response.user);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      token,
      isAuthenticated: Boolean(user && token),
      isLoading,
      login,
      logout,
    }),
    [user, token, isLoading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
