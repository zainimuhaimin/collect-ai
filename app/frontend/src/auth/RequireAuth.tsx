import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthToken } from './useAuthToken';

interface RequireAuthProps {
  readonly children: ReactNode;
}

export default function RequireAuth({ children }: RequireAuthProps) {
  const { isAuthenticated } = useAuthToken();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}
