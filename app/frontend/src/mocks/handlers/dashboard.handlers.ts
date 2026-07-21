import { http, HttpResponse } from 'msw';
import { dashboardSummaryFixture } from '../fixtures/dashboard.fixtures';

export const dashboardHandlers = [http.get('*/dashboard/summary', () => HttpResponse.json(dashboardSummaryFixture))];
