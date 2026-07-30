import { apiClient, apiRequest } from '../../api/client';
import { snakeToCamelDeep } from '../../api/caseTransform';
import {
  customerDetailSchema,
  customerListResponseSchema,
  customerContractsResponseSchema,
  type CustomerFilter,
} from './customer.schema';

export function getCustomerDetail(customerId: string) {
  return apiRequest(apiClient.get(`customers/${customerId}`), customerDetailSchema, snakeToCamelDeep);
}

export function getCustomerList(filter: CustomerFilter, search: string, page: number, pageSize: number) {
  // Real backend query param is `page_size` (snake_case), not `pageSize` — verified
  // against a live backend instance's OpenAPI schema.
  const searchParams = new URLSearchParams({
    filter,
    search,
    page: String(page),
    page_size: String(pageSize),
  });
  return apiRequest(apiClient.get(`customers?${searchParams.toString()}`), customerListResponseSchema, snakeToCamelDeep);
}

export function getCustomerContracts(customerId: string) {
  return apiRequest(apiClient.get(`customers/${customerId}/contracts`), customerContractsResponseSchema, snakeToCamelDeep);
}
