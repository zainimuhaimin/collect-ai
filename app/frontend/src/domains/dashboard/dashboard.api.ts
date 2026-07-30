import { apiClient, apiRequest } from '../../api/client';
import { snakeToCamelDeep } from '../../api/caseTransform';
import { dashboardSummaryResponseSchema } from './dashboard.schema';

export function getDashboardSummary() {
  return apiRequest(apiClient.get('dashboard/summary'), dashboardSummaryResponseSchema, snakeToCamelDeep);
}
