import { apiClient, apiRequest } from '../../api/client';
import { workbenchAccountsResponseSchema, workbenchActivityLogResponseSchema, type WorkbenchFilterKey } from './workbench.schema';

export interface WorkbenchAccountsParams {
  readonly filter: WorkbenchFilterKey;
  readonly search: string;
}

export function getWorkbenchAccounts({ filter, search }: WorkbenchAccountsParams) {
  return apiRequest(
    apiClient.get('workbench/accounts', { searchParams: { filter, search } }),
    workbenchAccountsResponseSchema,
  );
}

export function getWorkbenchActivityLog() {
  return apiRequest(apiClient.get('workbench/activity-log'), workbenchActivityLogResponseSchema);
}
