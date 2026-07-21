import { useState } from 'react';
import { useModelConfigQuery } from '../domains/ai-intelligence/useModelConfigQuery';
import { useSaveWeightingParametersMutation } from '../domains/ai-intelligence/useSaveWeightingParametersMutation';
import type { WeightParameter } from '../domains/ai-intelligence/aiIntelligence.schema';

export function useWeightingParameters() {
  const configQuery = useModelConfigQuery();
  const saveMutation = useSaveWeightingParametersMutation();
  const [draft, setDraft] = useState<WeightParameter[] | null>(null);

  const parameters = draft ?? configQuery.data?.weightingParameters ?? [];
  const isDirty = draft !== null;

  const updateWeight = (label: string, weight: number) => {
    setDraft((current) => (current ?? parameters).map((parameter) => (parameter.label === label ? { ...parameter, weight } : parameter)));
  };

  const resetToDefault = () => setDraft(null);

  const saveChanges = () => {
    if (draft) {
      saveMutation.mutate(draft, { onSuccess: () => setDraft(null) });
    }
  };

  const sumOfWeights = parameters.reduce((total, parameter) => total + parameter.weight, 0);

  return {
    parameters,
    updateWeight,
    resetToDefault,
    saveChanges,
    isDirty,
    sumOfWeights,
    isLoading: configQuery.isLoading,
    isError: configQuery.isError,
    error: configQuery.error,
    refetch: configQuery.refetch,
    isSaving: saveMutation.isPending,
    saveError: saveMutation.error,
  };
}
