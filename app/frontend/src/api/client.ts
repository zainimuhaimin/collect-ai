import ky from 'ky';
import { type ZodType } from 'zod';
import { clearToken, getToken } from '../auth/tokenStorage';
import { ApiError, toApiError } from './apiError';

export const apiClient = ky.create({
  prefix: import.meta.env.VITE_API_BASE_URL ?? '/api',
  timeout: 10_000,
  retry: {
    limit: 2,
    methods: ['get'],
    statusCodes: [408, 429, 500, 502, 503, 504],
  },
  hooks: {
    beforeRequest: [
      ({ request }) => {
        const token = getToken();
        if (token) {
          request.headers.set('Authorization', `Bearer ${token}`);
        }
      },
    ],
    afterResponse: [
      ({ response }) => {
        if (response.status === 401) {
          clearToken();
          window.dispatchEvent(new Event('auth:unauthorized'));
        }
        return response;
      },
    ],
  },
});

export async function apiRequest<T>(promise: Promise<Response>, schema: ZodType<T>): Promise<T> {
  let response: Response;
  try {
    response = await promise;
  } catch (error) {
    throw toApiError(error);
  }

  const json = await response.json();
  const parsed = schema.safeParse(json);
  if (!parsed.success) {
    throw new ApiError('Received unexpected data shape from the server.', 'validation', response.status, parsed.error);
  }
  return parsed.data;
}
