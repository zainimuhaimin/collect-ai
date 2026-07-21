import { apiClient, apiRequest } from '../../api/client';
import { customerDetailSchema, customerTimelineResponseSchema } from './customer.schema';

export function getCustomerDetail(customerId: string) {
  return apiRequest(apiClient.get(`customer/${customerId}`), customerDetailSchema);
}

export function getCustomerTimeline(customerId: string) {
  return apiRequest(apiClient.get(`customer/${customerId}/timeline`), customerTimelineResponseSchema);
}
