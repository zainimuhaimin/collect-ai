import {
  customerDetailSchema,
  customerListItemSchema,
  customerContractSummarySchema,
  type CustomerDetail,
  type CustomerListItem,
  type CustomerPriority,
  type CustomerContractSummary,
} from '../../domains/customer/customer.schema';
import { contractRecords, formatRupiah, getContractsForCustomer } from './contract.fixtures';

// Customer Behavioral Standing (CBS) fields have no per-contract source — they live on
// `customer_behavioral_standing`, keyed by cust_id only. Everything else about a
// customer (outstanding balance, risk segment, AI scoring, priority) is derived below
// from the SAME contract dataset `contract.fixtures.ts` owns, so Customer Detail /
// Customer List / "Kontrak Milik Customer Ini" never disagree with Contract List/Detail.
interface CustomerSeed {
  readonly custId: string;
  readonly name: string;
  readonly initials: string;
  readonly behavioralGrade: string;
  readonly bListStatus: 'Y' | 'N';
  readonly restructureCount: number;
  readonly priority: CustomerPriority;
}

const customerSeeds: CustomerSeed[] = [
  { custId: 'CUST-00001', name: 'Budi Pratama Sitorus', initials: 'BP', behavioralGrade: 'D', bListStatus: 'Y', restructureCount: 0, priority: 'Critical' },
  { custId: 'CUST-00002', name: 'Rina Tiara Wulandari', initials: 'RT', behavioralGrade: 'C', bListStatus: 'N', restructureCount: 0, priority: 'High' },
  { custId: 'CUST-00003', name: 'Bambang Pamungkas', initials: 'BP', behavioralGrade: 'E', bListStatus: 'Y', restructureCount: 1, priority: 'Critical' },
  { custId: 'CUST-00004', name: 'Siti Maesaroh', initials: 'SM', behavioralGrade: 'C', bListStatus: 'N', restructureCount: 0, priority: 'Medium' },
  { custId: 'CUST-00005', name: 'Dedi Firmansyah', initials: 'DF', behavioralGrade: 'E', bListStatus: 'Y', restructureCount: 0, priority: 'Critical' },
  { custId: 'CUST-00006', name: 'Andi Saputra', initials: 'AS', behavioralGrade: 'A', bListStatus: 'N', restructureCount: 0, priority: 'Medium' },
  { custId: 'CUST-00007', name: 'Rina Kusuma', initials: 'RK', behavioralGrade: 'E', bListStatus: 'Y', restructureCount: 1, priority: 'Critical' },
  { custId: 'CUST-00008', name: 'Hendra Gunawan', initials: 'HG', behavioralGrade: 'B', bListStatus: 'N', restructureCount: 0, priority: 'Medium' },
  { custId: 'CUST-00009', name: 'Wulan Sari', initials: 'WS', behavioralGrade: 'D', bListStatus: 'N', restructureCount: 0, priority: 'High' },
  { custId: 'CUST-00010', name: 'Agus Setiawan', initials: 'AS', behavioralGrade: 'A', bListStatus: 'N', restructureCount: 0, priority: 'Medium' },
  { custId: 'CUST-00011', name: 'Maya Anggraini', initials: 'MA', behavioralGrade: 'B', bListStatus: 'N', restructureCount: 0, priority: 'Medium' },
  { custId: 'CUST-00012', name: 'Fajar Nugroho', initials: 'FN', behavioralGrade: 'E', bListStatus: 'Y', restructureCount: 0, priority: 'Critical' },
  { custId: 'CUST-00013', name: 'Indah Permata', initials: 'IP', behavioralGrade: 'A', bListStatus: 'N', restructureCount: 0, priority: 'Medium' },
  { custId: 'CUST-00014', name: 'Yusuf Hidayat', initials: 'YH', behavioralGrade: 'B', bListStatus: 'N', restructureCount: 0, priority: 'Medium' },
  { custId: 'CUST-00015', name: 'Nadia Putri', initials: 'NP', behavioralGrade: 'D', bListStatus: 'N', restructureCount: 0, priority: 'High' },
  { custId: 'CUST-00016', name: 'Rizky Ramadhan', initials: 'RR', behavioralGrade: 'B', bListStatus: 'N', restructureCount: 0, priority: 'Medium' },
  { custId: 'CUST-00017', name: 'Lestari Wijaya', initials: 'LW', behavioralGrade: 'E', bListStatus: 'Y', restructureCount: 0, priority: 'Critical' },
  { custId: 'CUST-00018', name: 'Taufik Hidayat', initials: 'TH', behavioralGrade: 'A', bListStatus: 'N', restructureCount: 1, priority: 'Medium' },
];

function primaryContractFor(custId: string) {
  const contracts = getContractsForCustomer(custId);
  return contracts.reduce((highestDpd, current) =>
    current.seed.dpdCurrent > highestDpd.seed.dpdCurrent ? current : highestDpd,
  );
}

function toCustomerDetail(seed: CustomerSeed): CustomerDetail {
  const contracts = getContractsForCustomer(seed.custId);
  const primary = primaryContractFor(seed.custId);
  const totalOutstanding = contracts.reduce((sum, record) => sum + record.seed.prncOts + record.seed.intrOts, 0);

  return customerDetailSchema.parse({
    custId: seed.custId,
    name: seed.name,
    initials: seed.initials,
    outstandingBalance: formatRupiah(totalOutstanding),
    riskSegment: primary.seed.riskSegment,
    riskScore: Math.max(0, Math.min(100, 100 - primary.seed.recoveryScore)),
    recoveryScore: primary.seed.recoveryScore,
    selfCureProbability: primary.seed.selfCureProbability,
    rollForwardRisk: primary.seed.rollForwardRisk,
    ptpSuccessProbability: primary.seed.ptpSuccessProbability,
    nbaRecommendation: primary.seed.nbaRecommendation,
    behavioralGrade: seed.behavioralGrade,
    bListStatus: seed.bListStatus,
    restructureCount: seed.restructureCount,
    activeContractCount: contracts.length,
  } satisfies CustomerDetail);
}

function toCustomerListItem(seed: CustomerSeed): CustomerListItem {
  const contracts = getContractsForCustomer(seed.custId);

  return customerListItemSchema.parse({
    custId: seed.custId,
    name: seed.name,
    activeContractCount: contracts.length,
    behavioralGrade: seed.behavioralGrade,
    bListStatus: seed.bListStatus,
    priority: seed.priority,
  } satisfies CustomerListItem);
}

function toCustomerContractSummary(record: (typeof contractRecords)[number]): CustomerContractSummary {
  return customerContractSummarySchema.parse({
    contractNo: record.seed.contractNo,
    productType: record.seed.productType,
    dpdCurrent: record.seed.dpdCurrent,
    outstanding: formatRupiah(record.seed.prncOts + record.seed.intrOts),
    riskSegment: record.seed.riskSegment,
  } satisfies CustomerContractSummary);
}

export const customerRecords = customerSeeds.map((seed) => ({
  seed,
  detail: toCustomerDetail(seed),
  listItem: toCustomerListItem(seed),
  contracts: getContractsForCustomer(seed.custId).map(toCustomerContractSummary),
}));

export function findCustomerRecord(custId: string) {
  return customerRecords.find((record) => record.seed.custId === custId);
}

// Any contract belonging to this customer with a broken PTP / high-AMBC flag counts
// for the customer-level `broken_ptp`/`high_ambc` filters (per design doc: those
// attributes are really per-contract, so at the Customer level it means "has a
// contract that...").
export function customerHasBrokenPtp(custId: string): boolean {
  return getContractsForCustomer(custId).some((record) => record.seed.lastPtpBroken);
}

const HIGH_AMBC_THRESHOLD = 10_000_000;
export function customerHasHighAmbc(custId: string): boolean {
  return getContractsForCustomer(custId).some((record) => record.seed.ambc >= HIGH_AMBC_THRESHOLD);
}

// `dpd_30_plus` filter no longer has a `dpdDays` field on the list item to read (see
// customer.schema.ts's TASK-5 rework) — derived straight from the underlying contracts.
const DPD_30_PLUS_THRESHOLD = 30;
export function customerHasDpd30Plus(custId: string): boolean {
  return getContractsForCustomer(custId).some((record) => record.seed.dpdCurrent >= DPD_30_PLUS_THRESHOLD);
}
