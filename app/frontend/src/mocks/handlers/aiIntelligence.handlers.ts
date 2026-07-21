import { http, HttpResponse } from 'msw';
import {
  applyWeightingParametersUpdate,
  modelConfigFixture,
  modelOperationalLogFixture,
} from '../fixtures/aiIntelligence.fixtures';
import type { WeightParameter } from '../../domains/ai-intelligence/aiIntelligence.schema';

export const aiIntelligenceHandlers = [
  http.get('*/ai-intelligence/model-config', () => HttpResponse.json(modelConfigFixture)),

  http.get('*/ai-intelligence/operational-log', () => HttpResponse.json(modelOperationalLogFixture)),

  http.put('*/ai-intelligence/weighting-parameters', async ({ request }) => {
    const parameters = (await request.json()) as WeightParameter[];
    return HttpResponse.json(applyWeightingParametersUpdate(parameters));
  }),
];
