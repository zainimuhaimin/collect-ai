import { apiClient, apiRequest } from '../../api/client';
import { snakeToCamelDeep } from '../../api/caseTransform';
import {
  contractListResponseSchema,
  contractDetailSchema,
  activityLogResponseSchema,
  type ContractFilter,
} from './contract.schema';

export function getContractList(filter: ContractFilter, search: string, page: number, pageSize: number) {
  // Real backend query param is `page_size` (snake_case), not `pageSize` — verified
  // against a live backend instance's OpenAPI schema.
  const searchParams = new URLSearchParams({
    filter,
    search,
    page: String(page),
    page_size: String(pageSize),
  });
  return apiRequest(apiClient.get(`contracts?${searchParams.toString()}`), contractListResponseSchema, snakeToCamelDeep);
}

export function getContractDetail(contractNo: string) {
  return apiRequest(apiClient.get(`contracts/${contractNo}`), contractDetailSchema, snakeToCamelDeep);
}

export function getContractActivityLog(contractNo: string) {
  return apiRequest(apiClient.get(`contracts/${contractNo}/activity-log`), activityLogResponseSchema, snakeToCamelDeep);
}
