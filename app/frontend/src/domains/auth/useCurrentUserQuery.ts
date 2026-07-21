import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { useAuthToken } from '../../auth/useAuthToken';
import { getCurrentUser } from './auth.api';

export function useCurrentUserQuery() {
  const { isAuthenticated } = useAuthToken();
  return useQuery({
    queryKey: queryKeys.auth.currentUser,
    queryFn: getCurrentUser,
    enabled: isAuthenticated,
  });
}
