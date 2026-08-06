import { http, HttpResponse } from 'msw';
import { getAiReasoningFixture, generateAiReasoningFixture } from '../fixtures/aiReasoning.fixtures';

export const aiReasoningHandlers = [
  http.get('*/customers/:custId/ai-reasoning', () => HttpResponse.json(getAiReasoningFixture())),

  http.post('*/customers/:custId/ai-reasoning', () => HttpResponse.json(generateAiReasoningFixture())),
];
