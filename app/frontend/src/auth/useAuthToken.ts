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
    // Each `useAuthToken()` call holds its own independent React state — without this,
    // other already-mounted instances (e.g. the one inside `RequireAuth`, which is a
    // SEPARATE hook call from whichever component called `logout()`, such as TopBar)
    // never learn the token was cleared, so `RequireAuth` wouldn't redirect to /login
    // until some other unrelated re-render happened. Reuses the same
    // 'auth:unauthorized' event/listener this hook already wires up for the 401 case
    // in api/client.ts, so every mounted instance re-syncs immediately. Verified live:
    // without this, clicking Logout left the user sitting on the same authenticated
    // page.
    window.dispatchEvent(new Event('auth:unauthorized'));
  };

  return { token, isAuthenticated: token !== null, login, logout };
}
