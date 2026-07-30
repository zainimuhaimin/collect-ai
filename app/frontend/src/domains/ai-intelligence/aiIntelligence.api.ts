import { apiClient, apiRequest } from '../../api/client';
import { snakeToCamelDeep } from '../../api/caseTransform';
import {
  modelConfigResponseSchema,
  modelOperationalLogResponseSchema,
  saveWeightingParametersResponseSchema,
  syncTriggerResponseSchema,
  syncStatusResponseSchema,
  type WeightParameter,
} from './aiIntelligence.schema';

export function getModelConfig() {
  return apiRequest(apiClient.get('ai-intelligence/model-config'), modelConfigResponseSchema, snakeToCamelDeep);
}

export function getModelOperationalLog() {
  return apiRequest(apiClient.get('ai-intelligence/operational-log'), modelOperationalLogResponseSchema, snakeToCamelDeep);
}

export function saveWeightingParameters(parameters: WeightParameter[]) {
  return apiRequest(
    apiClient.put('ai-intelligence/weighting-parameters', { json: parameters }),
    saveWeightingParametersResponseSchema,
  );
}

// Real backend endpoint (added in parallel — see restructuring-engine-tasks.md /
// backend-architecture-tasks.md) — snake_case wire shape (`job_id`, `started_at`, ...),
// mapped through `snakeToCamelDeep` like Customer/Contract/Dashboard.
export function triggerSync() {
  return apiRequest(apiClient.post('ai-intelligence/sync'), syncTriggerResponseSchema, snakeToCamelDeep);
}

export function getSyncStatus() {
  return apiRequest(apiClient.get('ai-intelligence/sync/status'), syncStatusResponseSchema, snakeToCamelDeep);
}
