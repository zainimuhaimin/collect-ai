import { apiClient, apiRequest } from '../../api/client';
import { snakeToCamelDeep } from '../../api/caseTransform';
import { aiReasoningResponseSchema } from './aiReasoning.schema';

// GET tidak pernah memanggil Gemini, tidak pernah berbiaya — timeout global
// 10s (client.ts) sudah lebih dari cukup.
export function getAiReasoning(custId: string) {
  return apiRequest(
    apiClient.get(`customers/${custId}/ai-reasoning`),
    aiReasoningResponseSchema,
    snakeToCamelDeep,
  );
}

// POST memicu panggilan Gemini sungguhan — override timeout ke ~30s untuk
// route INI SAJA (keputusan #8 ai-reasoning-api-upgrade-tasks.md §7).
// Timeout global 10s (client.ts) TIDAK diubah — melonggarkannya akan
// mempengaruhi seluruh aplikasi demi satu endpoint.
export function generateAiReasoning(custId: string) {
  return apiRequest(
    apiClient.post(`customers/${custId}/ai-reasoning`, { timeout: 30_000 }),
    aiReasoningResponseSchema,
    snakeToCamelDeep,
  );
}
