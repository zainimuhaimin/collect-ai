import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { generateAiReasoning } from './aiReasoning.api';

export function useGenerateAiReasoningMutation(custId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => generateAiReasoning(custId),
    // onSettled (bukan onSuccess) — 409 (generate lain sedang berjalan) juga
    // harus me-refresh query GET, supaya kartu langsung menampilkan hasil
    // begitu generate yang SEDANG berjalan itu selesai, tanpa perlu klik
    // ulang. Pola sama dengan useTriggerSyncMutation.ts.
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.aiReasoning.detail(custId) });
    },
  });
}
