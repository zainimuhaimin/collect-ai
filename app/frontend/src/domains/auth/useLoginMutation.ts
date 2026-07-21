import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { useAuthToken } from '../../auth/useAuthToken';
import { login } from './auth.api';
import type { LoginRequest } from './auth.schema';

export function useLoginMutation() {
  const queryClient = useQueryClient();
  const { login: storeToken } = useAuthToken();

  return useMutation({
    mutationFn: (credentials: LoginRequest) => login(credentials),
    onSuccess: (data) => {
      storeToken(data.token);
      queryClient.setQueryData(queryKeys.auth.currentUser, data.user);
    },
  });
}
