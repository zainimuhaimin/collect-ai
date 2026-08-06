import { http, HttpResponse } from 'msw';
import {
  applyWeightingParametersUpdate,
  llmSystemPromptFixture,
  modelConfigFixture,
  modelOperationalLogFixture,
  startSyncFixture,
  advanceSyncFixture,
} from '../fixtures/aiIntelligence.fixtures';
import type { WeightParameter } from '../../domains/ai-intelligence/aiIntelligence.schema';

export const aiIntelligenceHandlers = [
  http.get('*/ai-intelligence/model-config', () => HttpResponse.json(modelConfigFixture)),

  http.get('*/ai-intelligence/llm-system-prompt', () => HttpResponse.json(llmSystemPromptFixture)),

  http.get('*/ai-intelligence/operational-log', () => HttpResponse.json(modelOperationalLogFixture)),

  http.put('*/ai-intelligence/weighting-parameters', async ({ request }) => {
    const parameters = (await request.json()) as WeightParameter[];
    return HttpResponse.json(applyWeightingParametersUpdate(parameters));
  }),

  http.post('*/ai-intelligence/sync', () => {
    const result = startSyncFixture();
    if (!result.ok) {
      return HttpResponse.json({ message: 'A sync is already running' }, { status: 409 });
    }
    return HttpResponse.json({ jobId: result.jobId, status: 'running' }, { status: 202 });
  }),

  http.get('*/ai-intelligence/sync/status', () => HttpResponse.json(advanceSyncFixture())),
];
