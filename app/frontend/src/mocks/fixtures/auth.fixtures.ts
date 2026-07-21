import { currentUserSchema, loginResponseSchema, type CurrentUser, type LoginResponse } from '../../domains/auth/auth.schema';

export const MOCK_AUTH_TOKEN = 'mock-dev-token';

export const currentUserFixture: CurrentUser = {
  name: 'Budi Santoso',
  role: 'Regional Manager',
  initials: 'BS',
};

export const loginResponseFixture: LoginResponse = {
  token: MOCK_AUTH_TOKEN,
  user: currentUserFixture,
};

if (import.meta.env.DEV) {
  currentUserSchema.parse(currentUserFixture);
  loginResponseSchema.parse(loginResponseFixture);
}
