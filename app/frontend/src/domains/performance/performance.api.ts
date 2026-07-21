import { apiClient, apiRequest } from '../../api/client';
import {
  collectorRankingResponseSchema,
  performanceFiltersSchema,
  performanceOperationalLogResponseSchema,
  performanceSummarySchema,
} from './performance.schema';

export function getPerformanceFilters() {
  return apiRequest(apiClient.get('performance/filters'), performanceFiltersSchema);
}

export function getPerformanceSummary() {
  return apiRequest(apiClient.get('performance/summary'), performanceSummarySchema);
}

export function getCollectorRanking(page: number) {
  return apiRequest(apiClient.get('performance/collectors', { searchParams: { page } }), collectorRankingResponseSchema);
}

export function getPerformanceOperationalLog() {
  return apiRequest(apiClient.get('performance/operational-log'), performanceOperationalLogResponseSchema);
}
