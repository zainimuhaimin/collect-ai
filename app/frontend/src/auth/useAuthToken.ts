import { useEffect, useState } from 'react';
import { clearToken, getToken, setToken } from './tokenStorage';

export function useAuthToken() {
  const [token, setTokenState] = useState<string | null>(() => getToken());

  useEffect(() => {
    const syncFromStorage = () => setTokenState(getToken());
    window.addEventListener('storage', syncFromStorage);
    window.addEventListener('auth:unauthorized', syncFromStorage);
    return () => {
      window.removeEventListener('storage', syncFromStorage);
      window.removeEventListener('auth:unauthorized', syncFromStorage);
    };
  }, []);

  const login = (nextToken: string) => {
    setToken(nextToken);
    setTokenState(nextToken);
  };

  const logout = () => {
    clearToken();
    setTokenState(null);
  };

  return { token, isAuthenticated: token !== null, login, logout };
}
