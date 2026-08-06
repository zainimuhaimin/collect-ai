import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getLlmSystemPrompt } from './aiIntelligence.api';

export function useLlmSystemPromptQuery() {
  return useQuery({
    queryKey: queryKeys.aiIntelligence.llmSystemPrompt,
    queryFn: getLlmSystemPrompt,
  });
}
