import { apiClient, apiRequest } from '../../api/client';
import { snakeToCamelDeep } from '../../api/caseTransform';
import {
  restructuringAssessmentSchema,
  customerResponseResultSchema,
  restructuringGroupsResponseSchema,
  restructuringGroupDetailSchema,
  restructuringGroupActionResultSchema,
  type CustomerResponseValue,
  type RestructuringGroupStatusFilter,
} from './restructuring.schema';

// NOTE: every endpoint in this domain returns a real snake_case backend response
// (`restructure_group_id`, `cust_id`, ...) — all of them run through
// `snakeToCamelDeep` before Zod validation, same as Customer/Contract/Dashboard.
// (Verified live: without this mapper, every one of these calls fails schema
// validation against a real backend, even though it was a no-op difference against
// MSW's already-camelCase fixtures.)

export function getRestructuringOptions(custId: string) {
  return apiRequest(
    apiClient.get(`customers/${custId}/restructuring-options`),
    restructuringAssessmentSchema,
    snakeToCamelDeep,
  );
}

export function submitCustomerResponse(custId: string, groupId: string, response: CustomerResponseValue) {
  return apiRequest(
    apiClient.post(`customers/${custId}/restructuring-options/${groupId}/customer-response`, {
      json: { response },
    }),
    customerResponseResultSchema,
    snakeToCamelDeep,
  );
}

// The backend's `status` query param takes a comma-separated list of real
// `offer_status` values (GENERATED/OFFERED/ACCEPTED/REJECTED/EXPIRED) — it does NOT
// understand a literal "HISTORY" value (verified against a live backend instance,
// which returns an empty list for `status=HISTORY`). This UI-facing "GENERATED" vs
// "HISTORY" tab distinction is mapped to real statuses here, at the API boundary.
const HISTORY_STATUSES = 'OFFERED,ACCEPTED,REJECTED,EXPIRED';

export function getRestructuringGroups(
  status: RestructuringGroupStatusFilter,
  search = '',
  page = 1,
  pageSize = 10,
) {
  const statusParam = status === 'HISTORY' ? HISTORY_STATUSES : 'GENERATED';
  const searchParams = new URLSearchParams({
    status: statusParam,
    page: String(page),
    page_size: String(pageSize),
  });
  if (search) searchParams.set('search', search);
  return apiRequest(
    apiClient.get(`restructuring-groups?${searchParams.toString()}`),
    restructuringGroupsResponseSchema,
    snakeToCamelDeep,
  );
}

export function getRestructuringGroupDetail(groupId: string) {
  return apiRequest(apiClient.get(`restructuring-groups/${groupId}`), restructuringGroupDetailSchema, snakeToCamelDeep);
}

export function approveRestructuringGroup(groupId: string) {
  return apiRequest(
    apiClient.post(`restructuring-groups/${groupId}/approve`),
    restructuringGroupActionResultSchema,
    snakeToCamelDeep,
  );
}

export function rejectRestructuringGroup(groupId: string) {
  return apiRequest(
    apiClient.post(`restructuring-groups/${groupId}/reject`),
    restructuringGroupActionResultSchema,
    snakeToCamelDeep,
  );
}
