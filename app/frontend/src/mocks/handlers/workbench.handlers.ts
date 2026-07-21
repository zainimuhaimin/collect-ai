import { http, HttpResponse } from 'msw';
import { filterWorkbenchAccounts, workbenchActivityLogFixture } from '../fixtures/workbench.fixtures';
import { workbenchFilterKeySchema } from '../../domains/workbench/workbench.schema';

export const workbenchHandlers = [
  http.get('*/workbench/accounts', ({ request }) => {
    const url = new URL(request.url);
    const rawFilter = url.searchParams.get('filter') ?? 'all';
    const search = url.searchParams.get('search') ?? '';
    const filter = workbenchFilterKeySchema.safeParse(rawFilter).success
      ? workbenchFilterKeySchema.parse(rawFilter)
      : 'all';
    return HttpResponse.json(filterWorkbenchAccounts(filter, search));
  }),

  http.get('*/workbench/activity-log', () => HttpResponse.json(workbenchActivityLogFixture)),
];
