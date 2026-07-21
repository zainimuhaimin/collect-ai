import { apiClient, apiRequest } from '../../api/client';
import { currentUserSchema, loginResponseSchema, type LoginRequest } from './auth.schema';

export function login(credentials: LoginRequest) {
  return apiRequest(apiClient.post('auth/login', { json: credentials }), loginResponseSchema);
}

export function getCurrentUser() {
  return apiRequest(apiClient.get('auth/me'), currentUserSchema);
}
