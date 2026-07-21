import { HTTPError, NetworkError, TimeoutError } from 'ky';

export type ApiErrorKind = 'network' | 'http' | 'timeout' | 'validation' | 'unknown';

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly cause?: unknown;

  constructor(message: string, kind: ApiErrorKind, status?: number, cause?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = status;
    this.cause = cause;
  }
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error;
  }
  if (error instanceof HTTPError) {
    return new ApiError(`Request failed with status ${error.response.status}.`, 'http', error.response.status, error);
  }
  if (error instanceof TimeoutError) {
    return new ApiError('The request took too long to respond.', 'timeout', undefined, error);
  }
  if (error instanceof NetworkError || error instanceof TypeError) {
    return new ApiError('Could not reach the server. Check your connection.', 'network', undefined, error);
  }
  return new ApiError('Something unexpected went wrong.', 'unknown', undefined, error);
}

export function toDisplayMessage(error: unknown): string {
  const apiError = toApiError(error);
  switch (apiError.kind) {
    case 'network':
      return 'Could not reach the server. Check your connection and try again.';
    case 'timeout':
      return 'The server took too long to respond. Please try again.';
    case 'validation':
      return 'The server returned data in an unexpected format.';
    case 'http':
      return apiError.status === 401
        ? 'Your session has expired. Please sign in again.'
        : `Something went wrong (status ${apiError.status}). Please try again.`;
    default:
      return 'Something went wrong. Please try again.';
  }
}
