import { apiClient, apiRequest } from '../../api/client';
import {
  modelConfigResponseSchema,
  modelOperationalLogResponseSchema,
  saveWeightingParametersResponseSchema,
  type WeightParameter,
} from './aiIntelligence.schema';

export function getModelConfig() {
  return apiRequest(apiClient.get('ai-intelligence/model-config'), modelConfigResponseSchema);
}

export function getModelOperationalLog() {
  return apiRequest(apiClient.get('ai-intelligence/operational-log'), modelOperationalLogResponseSchema);
}

export function saveWeightingParameters(parameters: WeightParameter[]) {
  return apiRequest(
    apiClient.put('ai-intelligence/weighting-parameters', { json: parameters }),
    saveWeightingParametersResponseSchema,
  );
}
