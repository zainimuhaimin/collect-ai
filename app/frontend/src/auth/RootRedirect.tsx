import { Navigate } from 'react-router-dom';
import { useAuthToken } from './useAuthToken';

interface RootRedirectProps {
  readonly className?: string;
}

export default function RootRedirect(_props: RootRedirectProps) {
  const { isAuthenticated } = useAuthToken();
  return <Navigate to={isAuthenticated ? '/dashboard' : '/login'} replace />;
}
