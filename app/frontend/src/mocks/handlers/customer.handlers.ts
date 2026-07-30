import { http, HttpResponse } from 'msw';
import {
  customerRecords,
  findCustomerRecord,
  customerHasBrokenPtp,
  customerHasHighAmbc,
  customerHasDpd30Plus,
} from '../fixtures/customer.fixtures';
import type { CustomerFilter } from '../../domains/customer/customer.schema';

function matchesFilter(record: (typeof customerRecords)[number], filter: string): boolean {
  switch (filter as CustomerFilter) {
    case 'dpd_30_plus':
      return customerHasDpd30Plus(record.seed.custId);
    case 'high_priority':
      return record.listItem.priority === 'High' || record.listItem.priority === 'Critical';
    case 'broken_ptp':
      return customerHasBrokenPtp(record.seed.custId);
    case 'high_ambc':
      return customerHasHighAmbc(record.seed.custId);
    case 'all':
    default:
      return true;
  }
}

function matchesSearch(record: (typeof customerRecords)[number], search: string): boolean {
  if (!search) return true;
  const needle = search.toLowerCase();
  return record.seed.custId.toLowerCase().includes(needle) || record.seed.name.toLowerCase().includes(needle);
}

export const customerHandlers = [
  http.get('*/customers', ({ request }) => {
    const url = new URL(request.url);
    const filter = url.searchParams.get('filter') ?? 'all';
    const search = url.searchParams.get('search') ?? '';
    const page = Number(url.searchParams.get('page') ?? '1');
    const pageSize = Number(url.searchParams.get('page_size') ?? '10');

    const filtered = customerRecords.filter((record) => matchesFilter(record, filter) && matchesSearch(record, search));
    const totalCustomers = filtered.length;
    const totalPages = Math.max(1, Math.ceil(totalCustomers / pageSize));
    const safePage = Math.min(Math.max(page, 1), totalPages);
    const start = (safePage - 1) * pageSize;
    const pageItems = filtered.slice(start, start + pageSize);

    return HttpResponse.json({
      customers: pageItems.map((record) => record.listItem),
      pageInfo: {
        showingFrom: totalCustomers === 0 ? 0 : start + 1,
        showingTo: Math.min(start + pageSize, totalCustomers),
        totalCustomers,
        totalPages,
      },
    });
  }),

  http.get('*/customers/:customerId/contracts', ({ params }) => {
    const record = findCustomerRecord(String(params.customerId));
    return HttpResponse.json(record?.contracts ?? []);
  }),

  http.get('*/customers/:customerId', ({ params }) => {
    const record = findCustomerRecord(String(params.customerId));
    if (!record) {
      return HttpResponse.json({ message: 'Customer not found' }, { status: 404 });
    }
    return HttpResponse.json(record.detail);
  }),
];
