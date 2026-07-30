import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../../api/queryKeys';
import { submitCustomerResponse } from './restructuring.api';
import type { CustomerResponseValue } from './restructuring.schema';

interface SubmitCustomerResponseVariables {
  readonly custId: string;
  readonly groupId: string;
  readonly response: CustomerResponseValue;
}

export function useSubmitCustomerResponseMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ custId, groupId, response }: SubmitCustomerResponseVariables) =>
      submitCustomerResponse(custId, groupId, response),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.restructuring.options(variables.custId) });
    },
  });
}
