import { apiClient, apiRequest } from '../../api/client';
import { dashboardSummaryResponseSchema } from './dashboard.schema';

export function getDashboardSummary() {
  return apiRequest(apiClient.get('dashboard/summary'), dashboardSummaryResponseSchema);
}
