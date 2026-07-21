import {
  collectorSchema,
  operationalLogEntrySchema,
  performanceFiltersSchema,
  performanceSummarySchema,
  type Collector,
  type OperationalLogEntry,
  type PerformanceFilters,
  type PerformanceSummary,
} from '../../domains/performance/performance.schema';

export const performanceFiltersFixture: PerformanceFilters = {
  branches: ['All Branches', 'Jakarta Pusat', 'Jakarta Selatan', 'Surabaya'],
  areas: ['Greater Indonesia', 'Java', 'Sumatra'],
  products: ['Personal Loan', 'Credit Card', 'Auto Loan'],
  dateRange: 'Oct 01 - Oct 31, 2023',
};

export const performanceSummaryFixture: PerformanceSummary = {
  totalAchievement: 'Rp 4.280.000.000',
  achievementChange: '+12.4% from last month',
  activeCollectors: 142,
  activeCollectorsProgress: 82,
  avgProductivityIndex: 8.4,
};

// PAGE_SIZE * TOTAL_PAGES intentionally exceeds this fixture list's length (5 real rows);
// pages 2-3 repeat the same rows with re-derived ranks so pagination has something to page
// through in the mock. A real backend would return genuinely distinct rows per page.
const ALL_COLLECTORS: Collector[] = [
  { rank: 1, name: 'Aditya Nugroho', initials: 'AN', employeeId: '#99281', target: '500,000,000', achievement: '485,250,000', collectionRate: 97.05, productivityIndex: 9.8, ratingTone: 'good' },
  { rank: 2, name: 'Siti Rahmawati', initials: 'SR', employeeId: '#99304', target: '450,000,000', achievement: '412,000,000', collectionRate: 91.56, productivityIndex: 9.2, ratingTone: 'good' },
  { rank: 3, name: 'Hendrik Wijaya', initials: 'HW', employeeId: '#99212', target: '600,000,000', achievement: '520,000,000', collectionRate: 86.67, productivityIndex: 8.5, ratingTone: 'fair' },
  { rank: 4, name: 'Indah Permata', initials: 'IP', employeeId: '#99554', target: '400,000,000', achievement: '320,000,000', collectionRate: 80.0, productivityIndex: 7.9, ratingTone: 'fair' },
  { rank: 5, name: 'Reza Pratama', initials: 'RP', employeeId: '#99401', target: '400,000,000', achievement: '210,000,000', collectionRate: 52.5, productivityIndex: 4.2, ratingTone: 'poor' },
];

const PAGE_SIZE = 5;
const TOTAL_COLLECTORS = 142;
const TOTAL_PAGES = 3;

export function buildCollectorRankingPage(page: number) {
  const clampedPage = Math.min(Math.max(page, 1), TOTAL_PAGES);
  const collectors = ALL_COLLECTORS.map((collector, index) => ({
    ...collector,
    rank: (clampedPage - 1) * PAGE_SIZE + index + 1,
  }));
  return {
    collectors,
    pageInfo: {
      showingFrom: (clampedPage - 1) * PAGE_SIZE + 1,
      showingTo: (clampedPage - 1) * PAGE_SIZE + collectors.length,
      totalCollectors: TOTAL_COLLECTORS,
      totalPages: TOTAL_PAGES,
    },
  };
}

export const performanceOperationalLogFixture: OperationalLogEntry[] = [
  { id: 'log-1', message: 'Sistem memperbarui target bulanan untuk cabang Jakarta Pusat.', timestamp: 'Hari ini, 09:12 AM', tone: 'neutral' },
  { id: 'log-2', message: 'Aditya Nugroho mencapai 110% dari target harian produk Personal Loan.', timestamp: 'Hari ini, 08:45 AM', tone: 'success' },
  { id: 'log-3', message: 'Sinkronisasi data otomatis dari server pusat selesai dilakukan.', timestamp: 'Kemarin, 11:30 PM', tone: 'muted' },
];

if (import.meta.env.DEV) {
  performanceFiltersSchema.parse(performanceFiltersFixture);
  performanceSummarySchema.parse(performanceSummaryFixture);
  ALL_COLLECTORS.forEach((collector) => collectorSchema.parse(collector));
  performanceOperationalLogFixture.forEach((entry) => operationalLogEntrySchema.parse(entry));
}
