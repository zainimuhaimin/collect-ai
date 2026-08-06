import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { getAiReasoning } from './aiReasoning.api';

// Tidak ada polling (`refetchInterval`) — beda dari pola Sync AI Intelligence.
// Keputusan #8 dokumen adalah timeout override ~30s per-request, bukan
// 202+poll, jadi cukup query biasa yang dibaca ulang saat halaman dibuka
// atau setelah mutation generate selesai (lihat useGenerateAiReasoningMutation).
export function useAiReasoningQuery(custId: string) {
  return useQuery({
    queryKey: queryKeys.aiReasoning.detail(custId),
    queryFn: () => getAiReasoning(custId),
    enabled: Boolean(custId),
  });
}
