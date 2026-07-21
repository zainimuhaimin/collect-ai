import { http, HttpResponse } from 'msw';
import { customerDetailFixture, customerTimelineFixture } from '../fixtures/customer.fixtures';

export const customerHandlers = [
  http.get('*/customer/:customerId', ({ params }) => {
    return HttpResponse.json({ ...customerDetailFixture, id: String(params.customerId) });
  }),

  http.get('*/customer/:customerId/timeline', () => {
    return HttpResponse.json(customerTimelineFixture);
  }),
];
