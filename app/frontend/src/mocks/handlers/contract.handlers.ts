import { http, HttpResponse } from 'msw';
import { contractRecords, findContractRecord, getContractsForCustomer } from '../fixtures/contract.fixtures';
import type { ContractFilter } from '../../domains/contract/contract.schema';

const HIGH_AMOUNT_THRESHOLD = 10_000_000;
const HIGH_AMBC_THRESHOLD = 10_000_000;

function matchesFilter(record: (typeof contractRecords)[number], filter: string): boolean {
  const seed = record.seed;
  switch (filter as ContractFilter) {
    case 'dpd_30_plus':
      return seed.dpdCurrent >= 30;
    case 'high_priority':
      return seed.prncOts + seed.intrOts >= HIGH_AMOUNT_THRESHOLD;
    case 'broken_ptp':
      return seed.lastPtpBroken;
    case 'high_ambc':
      return seed.ambc >= HIGH_AMBC_THRESHOLD;
    case 'all':
    default:
      return true;
  }
}

function matchesSearch(record: (typeof contractRecords)[number], search: string): boolean {
  if (!search) return true;
  const needle = search.toLowerCase();
  return (
    record.seed.contractNo.toLowerCase().includes(needle) ||
    record.seed.custId.toLowerCase().includes(needle) ||
    record.seed.custName.toLowerCase().includes(needle)
  );
}

export const contractHandlers = [
  http.get('*/contracts', ({ request }) => {
    const url = new URL(request.url);
    const filter = url.searchParams.get('filter') ?? 'all';
    const search = url.searchParams.get('search') ?? '';
    const page = Number(url.searchParams.get('page') ?? '1');
    const pageSize = Number(url.searchParams.get('page_size') ?? '10');

    const filtered = contractRecords.filter((record) => matchesFilter(record, filter) && matchesSearch(record, search));
    const totalContracts = filtered.length;
    const totalPages = Math.max(1, Math.ceil(totalContracts / pageSize));
    const safePage = Math.min(Math.max(page, 1), totalPages);
    const start = (safePage - 1) * pageSize;
    const pageItems = filtered.slice(start, start + pageSize);

    return HttpResponse.json({
      contracts: pageItems.map((record) => record.listItem),
      pageInfo: {
        showingFrom: totalContracts === 0 ? 0 : start + 1,
        showingTo: Math.min(start + pageSize, totalContracts),
        totalContracts,
        totalPages,
      },
    });
  }),

  http.get('*/contracts/:contractNo/activity-log', ({ params }) => {
    const record = findContractRecord(String(params.contractNo));
    if (!record) {
      return HttpResponse.json([], { status: 404 });
    }
    return HttpResponse.json(record.activityLog);
  }),

  http.get('*/contracts/:contractNo', ({ params }) => {
    const record = findContractRecord(String(params.contractNo));
    if (!record) {
      return HttpResponse.json({ message: 'Contract not found' }, { status: 404 });
    }
    return HttpResponse.json(record.detail);
  }),
];

// Re-exported so customer.handlers.ts can build `GET /customers/:custId/contracts`
// from the exact same underlying dataset.
export { getContractsForCustomer };
