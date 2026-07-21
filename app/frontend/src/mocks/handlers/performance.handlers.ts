import { http, HttpResponse } from 'msw';
import {
  buildCollectorRankingPage,
  performanceFiltersFixture,
  performanceOperationalLogFixture,
  performanceSummaryFixture,
} from '../fixtures/performance.fixtures';

export const performanceHandlers = [
  http.get('*/performance/filters', () => HttpResponse.json(performanceFiltersFixture)),

  http.get('*/performance/summary', () => HttpResponse.json(performanceSummaryFixture)),

  http.get('*/performance/collectors', ({ request }) => {
    const page = Number(new URL(request.url).searchParams.get('page') ?? '1');
    return HttpResponse.json(buildCollectorRankingPage(page));
  }),

  http.get('*/performance/operational-log', () => HttpResponse.json(performanceOperationalLogFixture)),
];
