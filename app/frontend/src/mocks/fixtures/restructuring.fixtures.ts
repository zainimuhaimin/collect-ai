import {
  restructuringAssessmentSchema,
  type RestructuringAssessment,
  type OfferType,
  type EligibilityTier,
  type OfferStatus,
  type CustomerResponseValue,
  type RestructureOffer,
} from '../../domains/restructuring/restructuring.schema';

// Single source of truth for every restructuring group in the mock — both
// `GET /customers/:custId/restructuring-options` (Customer Detail's "Opsi
// Restrukturisasi" card) and `GET /restructuring-groups` (Restructuring Approval
// queue, TASK-E) are derived from this same mutable array, so approving/rejecting a
// group in one place is reflected in the other.
interface RestructuringRecord {
  restructureGroupId: string;
  custId: string;
  contractNos: string[];
  offerType: OfferType;
  eligibilityTier: EligibilityTier;
  eligibilityReasons: string[];
  offerStatus: OfferStatus;
  customerResponse: CustomerResponseValue | null;
  generatedDate: string;
  offer: Omit<RestructureOffer, 'contractNos' | 'offerType'>;
}

export const restructuringRecords: RestructuringRecord[] = [
  {
    restructureGroupId: 'RG-CUST-00001-2026-07-15-1',
    custId: 'CUST-00001',
    contractNos: ['CTR-00001-1'],
    offerType: 'REFINANCE',
    eligibilityTier: 'MANUAL_REVIEW',
    eligibilityReasons: ['DPD 62 di luar window standar (30-180) untuk offer_type ini'],
    offerStatus: 'GENERATED',
    customerResponse: null,
    generatedDate: '2026-07-15',
    offer: {
      recommendedNewTenorMonths: 18,
      recommendedNewRate: 0.145,
      recommendedNewInstallment: 780_000,
      recoveryFromAsset: 0,
      npvBaseline: 3_200_000,
      npvRestructured: 9_800_000,
      npvRestructuredRiskAdjusted: 7_840_000,
      totalRemainingCurrent: 33_320_000,
      totalNewSchedule: 25_480_000,
      isGuardrailPassed: true,
    },
  },
  {
    restructureGroupId: 'RG-CUST-00003-2026-07-10-1',
    custId: 'CUST-00003',
    contractNos: ['CTR-00003-1'],
    offerType: 'REFINANCE',
    eligibilityTier: 'AUTO',
    eligibilityReasons: [],
    offerStatus: 'OFFERED',
    customerResponse: null,
    generatedDate: '2026-07-10',
    offer: {
      recommendedNewTenorMonths: 15,
      recommendedNewRate: 0.152,
      recommendedNewInstallment: 1_650_000,
      recoveryFromAsset: 0,
      npvBaseline: 4_100_000,
      npvRestructured: 12_900_000,
      npvRestructuredRiskAdjusted: 10_320_000,
      totalRemainingCurrent: 43_860_000,
      totalNewSchedule: 33_540_000,
      isGuardrailPassed: true,
    },
  },
  {
    restructureGroupId: 'RG-CUST-00005-2026-07-05-1',
    custId: 'CUST-00005',
    contractNos: ['CTR-00005-1', 'CTR-00005-2'],
    offerType: 'CONSOLIDATE',
    eligibilityTier: 'MANUAL_REVIEW',
    eligibilityReasons: ['Menggabungkan >1 kontrak (CONSOLIDATE) selalu butuh review supervisor'],
    offerStatus: 'GENERATED',
    customerResponse: null,
    generatedDate: '2026-07-05',
    offer: {
      recommendedNewTenorMonths: 24,
      recommendedNewRate: 0.138,
      recommendedNewInstallment: 980_000,
      recoveryFromAsset: 0,
      npvBaseline: 5_600_000,
      npvRestructured: 15_200_000,
      npvRestructuredRiskAdjusted: 12_160_000,
      totalRemainingCurrent: 51_680_000,
      totalNewSchedule: 39_520_000,
      isGuardrailPassed: true,
    },
  },
  {
    restructureGroupId: 'RG-CUST-00007-2026-06-30-1',
    custId: 'CUST-00007',
    contractNos: ['CTR-00007-1'],
    offerType: 'REFINANCE',
    eligibilityTier: 'MANUAL_REVIEW',
    eligibilityReasons: ['DPD 150 sangat tinggi — ditolak supervisor, tidak ditawarkan ke customer'],
    offerStatus: 'REJECTED',
    customerResponse: null,
    generatedDate: '2026-06-30',
    offer: {
      recommendedNewTenorMonths: 36,
      recommendedNewRate: 0.099,
      recommendedNewInstallment: 4_850_000,
      recoveryFromAsset: 0,
      npvBaseline: 8_900_000,
      npvRestructured: 21_400_000,
      npvRestructuredRiskAdjusted: 17_120_000,
      totalRemainingCurrent: 72_760_000,
      totalNewSchedule: 55_640_000,
      isGuardrailPassed: true,
    },
  },
  {
    restructureGroupId: 'RG-CUST-00012-2026-07-22-1',
    custId: 'CUST-00012',
    contractNos: ['CTR-00012-1'],
    offerType: 'REFINANCE',
    eligibilityTier: 'MANUAL_REVIEW',
    eligibilityReasons: ['Total OTS combined di atas ambang otomatis — butuh persetujuan supervisor'],
    offerStatus: 'GENERATED',
    customerResponse: null,
    generatedDate: '2026-07-22',
    offer: {
      recommendedNewTenorMonths: 48,
      recommendedNewRate: 0.092,
      recommendedNewInstallment: 5_900_000,
      recoveryFromAsset: 0,
      npvBaseline: 12_000_000,
      npvRestructured: 34_500_000,
      npvRestructuredRiskAdjusted: 27_600_000,
      totalRemainingCurrent: 117_300_000,
      totalNewSchedule: 89_700_000,
      isGuardrailPassed: true,
    },
  },
  {
    restructureGroupId: 'RG-CUST-00017-2026-07-08-1',
    custId: 'CUST-00017',
    contractNos: ['CTR-00017-1'],
    offerType: 'REFINANCE',
    eligibilityTier: 'AUTO',
    eligibilityReasons: [],
    offerStatus: 'OFFERED',
    customerResponse: null,
    generatedDate: '2026-07-08',
    offer: {
      recommendedNewTenorMonths: 12,
      recommendedNewRate: 0.14,
      recommendedNewInstallment: 1_700_000,
      recoveryFromAsset: 0,
      npvBaseline: 3_900_000,
      npvRestructured: 11_200_000,
      npvRestructuredRiskAdjusted: 8_960_000,
      totalRemainingCurrent: 38_080_000,
      totalNewSchedule: 29_120_000,
      isGuardrailPassed: true,
    },
  },
  {
    restructureGroupId: 'RG-CUST-00018-2026-05-01-1',
    custId: 'CUST-00018',
    contractNos: ['CTR-00018-1'],
    offerType: 'REFINANCE',
    eligibilityTier: 'AUTO',
    eligibilityReasons: [],
    offerStatus: 'ACCEPTED',
    customerResponse: 'ACCEPTED',
    generatedDate: '2026-05-01',
    offer: {
      recommendedNewTenorMonths: 30,
      recommendedNewRate: 0.098,
      recommendedNewInstallment: 3_300_000,
      recoveryFromAsset: 0,
      npvBaseline: 6_200_000,
      npvRestructured: 18_900_000,
      npvRestructuredRiskAdjusted: 15_120_000,
      totalRemainingCurrent: 64_260_000,
      totalNewSchedule: 49_140_000,
      isGuardrailPassed: true,
    },
  },
];

function toAssessment(record: RestructuringRecord): RestructuringAssessment {
  return restructuringAssessmentSchema.parse({
    custId: record.custId,
    contractNo: record.contractNos[0],
    restructureGroupId: record.restructureGroupId,
    eligibilityTier: record.eligibilityTier,
    eligibilityReasons: record.eligibilityReasons,
    offers: [
      {
        offerType: record.offerType,
        contractNos: record.contractNos,
        ...record.offer,
      },
    ],
    canRespond: record.offerStatus === 'OFFERED',
    customerResponse: record.customerResponse,
    source: 'ON_DEMAND',
  } satisfies RestructuringAssessment);
}

export function findRestructuringRecordForCustomer(custId: string) {
  return restructuringRecords.find((record) => record.custId === custId);
}

export function findRestructuringRecordByGroupId(groupId: string) {
  return restructuringRecords.find((record) => record.restructureGroupId === groupId);
}

// A customer with no persisted group at all is a BLOCKED assessment — mirrors the
// real endpoint's "data kontrak tidak valid untuk dihitung" case (here: simply no
// restructuring candidate was generated for this customer yet).
export function getAssessmentForCustomer(custId: string): RestructuringAssessment {
  const record = findRestructuringRecordForCustomer(custId);
  if (!record) {
    return restructuringAssessmentSchema.parse({
      custId,
      contractNo: '',
      restructureGroupId: '',
      eligibilityTier: 'BLOCKED',
      eligibilityReasons: ['Belum ada kontrak yang memenuhi kriteria dasar restrukturisasi untuk customer ini'],
      offers: [],
      canRespond: false,
      customerResponse: null,
      source: 'ON_DEMAND',
    } satisfies RestructuringAssessment);
  }
  return toAssessment(record);
}

export function applyCustomerResponse(
  custId: string,
  groupId: string,
  response: CustomerResponseValue,
): { ok: true } | { ok: false; status: number; message: string } {
  const record = findRestructuringRecordByGroupId(groupId);
  if (!record || record.custId !== custId) {
    return { ok: false, status: 404, message: 'restructure_group_id tidak ditemukan untuk cust_id ini' };
  }
  if (record.offerStatus !== 'OFFERED') {
    return { ok: false, status: 409, message: 'Tawaran belum OFFERED (masih GENERATED) atau sudah direspons sebelumnya' };
  }
  record.offerStatus = response;
  record.customerResponse = response;
  return { ok: true };
}

export function approveGroup(groupId: string): RestructuringRecord | undefined {
  const record = findRestructuringRecordByGroupId(groupId);
  if (record && record.offerStatus === 'GENERATED') {
    record.offerStatus = 'OFFERED';
  }
  return record;
}

export function rejectGroup(groupId: string): RestructuringRecord | undefined {
  const record = findRestructuringRecordByGroupId(groupId);
  if (record && record.offerStatus === 'GENERATED') {
    record.offerStatus = 'REJECTED';
  }
  return record;
}

// Wire shape joins multiple reasons with "; " (single string, not an array) — matches
// the real backend's `eligibility_reasons` field (see restructuring.schema.ts).
function toGroupListItem(record: RestructuringRecord) {
  return {
    restructureGroupId: record.restructureGroupId,
    custId: record.custId,
    contractNos: record.contractNos,
    offerType: record.offerType,
    eligibilityTier: record.eligibilityTier,
    eligibilityReasons: record.eligibilityReasons.join('; '),
    npvBaseline: record.offer.npvBaseline,
    npvRestructured: record.offer.npvRestructured,
    npvRestructuredRiskAdjusted: record.offer.npvRestructuredRiskAdjusted,
    totalRemainingCurrent: record.offer.totalRemainingCurrent,
    totalNewSchedule: record.offer.totalNewSchedule,
    offerStatus: record.offerStatus,
    generatedDate: record.generatedDate,
  };
}

export function listGroups(statuses: string[], search = '', page = 1, pageSize = 10) {
  const needle = search.trim().toLowerCase();
  const filtered = restructuringRecords
    .filter((record) => (statuses as OfferStatus[]).includes(record.offerStatus))
    .filter(
      (record) =>
        !needle ||
        record.restructureGroupId.toLowerCase().includes(needle) ||
        record.custId.toLowerCase().includes(needle),
    )
    .map(toGroupListItem);

  const total = filtered.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = (page - 1) * pageSize;
  const groups = filtered.slice(start, start + pageSize);

  return {
    groups,
    pageInfo: {
      showingFrom: total === 0 ? 0 : start + 1,
      showingTo: Math.min(start + pageSize, total),
      totalGroups: total,
      totalPages,
    },
  };
}

export function getGroupDetail(groupId: string) {
  const record = findRestructuringRecordByGroupId(groupId);
  return record ? toGroupListItem(record) : undefined;
}
