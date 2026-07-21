import { http, HttpResponse } from 'msw';
import { currentUserFixture, loginResponseFixture, MOCK_AUTH_TOKEN } from '../fixtures/auth.fixtures';

export const authHandlers = [
  http.post('*/auth/login', async ({ request }) => {
    const body = (await request.json()) as { username?: string; password?: string };
    if (!body.username || !body.password) {
      return HttpResponse.json({ message: 'Username and password are required.' }, { status: 401 });
    }
    return HttpResponse.json(loginResponseFixture);
  }),

  http.get('*/auth/me', ({ request }) => {
    const authHeader = request.headers.get('Authorization');
    if (authHeader !== `Bearer ${MOCK_AUTH_TOKEN}`) {
      return HttpResponse.json({ message: 'Unauthorized' }, { status: 401 });
    }
    return HttpResponse.json(currentUserFixture);
  }),
];
