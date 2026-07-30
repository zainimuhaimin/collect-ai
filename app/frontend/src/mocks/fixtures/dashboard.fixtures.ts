import { dashboardSummaryResponseSchema, type DashboardSummary } from '../../domains/dashboard/dashboard.schema';

// Matches the REAL `GET /dashboard/summary` contract (see dashboard.schema.ts) —
// camelCase here on purpose: `snakeToCamelDeep` is a no-op on already-camelCase keys,
// so this fixture round-trips through the same mapper `dashboard.api.ts` applies to a
// real snake_case backend response.
export const dashboardSummaryFixture: DashboardSummary = {
  kpis: {
    totalOutstanding: 4_280_000_000,
    activeDelinquentAccounts: 12_482,
    ptpKeepRate: 0.35,
    manualReviewPending: 7,
  },
  dpdBuckets: [
    { bucket: 'C0', settled: 70, activePtp: 20, broken: 10, total: 100 },
    { bucket: 'C1', settled: 55, activePtp: 15, broken: 20, total: 90 },
    { bucket: 'C2', settled: 35, activePtp: 12, broken: 18, total: 65 },
    { bucket: 'C3+', settled: 15, activePtp: 8, broken: 22, total: 45 },
  ],
  channelEfficiency: [
    { treatmentType: 'WA', contactSuccessRate: 0.62 },
    { treatmentType: 'Deskcoll', contactSuccessRate: 0.45 },
    { treatmentType: 'Visit', contactSuccessRate: 0.3 },
  ],
  riskSegmentDistribution: {
    'Cannot Pay': 3184,
    'Self-cure': 6920,
    "Won't Pay": 2378,
    'Can Pay': 4210,
  },
  syncNote: 'Data terakhir disinkronkan: 21 Jul 2026 17:07',
};

if (import.meta.env.DEV) {
  dashboardSummaryResponseSchema.parse(dashboardSummaryFixture);
}
