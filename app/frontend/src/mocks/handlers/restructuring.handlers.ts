import { http, HttpResponse } from 'msw';
import {
  getAssessmentForCustomer,
  applyCustomerResponse,
  approveGroup,
  rejectGroup,
  listGroups,
  getGroupDetail,
} from '../fixtures/restructuring.fixtures';
import {
  restructuringGroupSchema,
  restructuringGroupActionResultSchema,
} from '../../domains/restructuring/restructuring.schema';

export const restructuringHandlers = [
  http.get('*/customers/:custId/restructuring-options', ({ params }) => {
    return HttpResponse.json(getAssessmentForCustomer(String(params.custId)));
  }),

  http.post('*/customers/:custId/restructuring-options/:groupId/customer-response', async ({ params, request }) => {
    const custId = String(params.custId);
    const groupId = String(params.groupId);
    const body = (await request.json()) as { response: string };
    const response = body.response.toUpperCase() as 'ACCEPTED' | 'REJECTED';

    const result = applyCustomerResponse(custId, groupId, response);
    if (!result.ok) {
      return HttpResponse.json({ message: result.message }, { status: result.status });
    }

    return HttpResponse.json({
      restructureGroupId: groupId,
      custId,
      response,
      message: 'Respons customer tercatat',
    });
  }),

  http.get('*/restructuring-groups', ({ request }) => {
    const url = new URL(request.url);
    // Real backend contract: comma-separated `offer_status` values, e.g.
    // "OFFERED,ACCEPTED,REJECTED,EXPIRED" for the "Riwayat" tab — see
    // restructuring.api.ts's `getRestructuringGroups` for the UI-tab -> query-param
    // mapping this mirrors.
    const statuses = (url.searchParams.get('status') ?? 'GENERATED').split(',').map((value) => value.trim());
    const search = url.searchParams.get('search') ?? '';
    const page = Number(url.searchParams.get('page') ?? '1');
    const pageSize = Number(url.searchParams.get('page_size') ?? '10');
    return HttpResponse.json(listGroups(statuses, search, page, pageSize));
  }),

  http.get('*/restructuring-groups/:groupId', ({ params }) => {
    const detail = getGroupDetail(String(params.groupId));
    if (!detail) {
      return HttpResponse.json({ message: 'restructure_group_id tidak ditemukan' }, { status: 404 });
    }
    return HttpResponse.json(restructuringGroupSchema.parse(detail));
  }),

  http.post('*/restructuring-groups/:groupId/approve', ({ params }) => {
    const record = approveGroup(String(params.groupId));
    if (!record) {
      return HttpResponse.json({ message: 'restructure_group_id tidak ditemukan' }, { status: 404 });
    }
    // Real backend's approve/reject response is a smaller, DIFFERENT shape than the
    // list/detail item (no contract_nos/eligibility_*/npv_*, plus expiry_date) — see
    // restructuring.schema.ts's `restructuringGroupActionResultSchema`.
    return HttpResponse.json(
      restructuringGroupActionResultSchema.parse({
        restructureGroupId: record.restructureGroupId,
        custId: record.custId,
        offerType: record.offerType,
        offerStatus: record.offerStatus,
        generatedDate: record.generatedDate,
        expiryDate: null,
      }),
    );
  }),

  http.post('*/restructuring-groups/:groupId/reject', ({ params }) => {
    const record = rejectGroup(String(params.groupId));
    if (!record) {
      return HttpResponse.json({ message: 'restructure_group_id tidak ditemukan' }, { status: 404 });
    }
    return HttpResponse.json(
      restructuringGroupActionResultSchema.parse({
        restructureGroupId: record.restructureGroupId,
        custId: record.custId,
        offerType: record.offerType,
        offerStatus: record.offerStatus,
        generatedDate: record.generatedDate,
        expiryDate: null,
      }),
    );
  }),
];
