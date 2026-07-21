import { dashboardSummaryResponseSchema, type DashboardSummary } from '../../domains/dashboard/dashboard.schema';

export const dashboardSummaryFixture: DashboardSummary = {
  kpis: [
    { icon: 'account_balance_wallet', label: 'Total Outstanding', value: 'Rp 4.280.000.000', change: '+4.2%', trend: 'up', tone: 'positive' },
    { icon: 'person_off', label: 'Active Delinquent Accounts', value: '12,482', change: '-1.5%', trend: 'down', tone: 'negative' },
    { icon: 'task_alt', label: 'PTP Success Rate (%)', value: '74.2%', change: '+12%', trend: 'up', tone: 'positive' },
    { icon: 'insights', label: 'Avg AI Confidence (%)', value: '89.5%', change: 'Stable', trend: 'flat', tone: 'neutral' },
  ],
  dpdBuckets: [
    { label: 'C0 (1-30)', settled: 70, activePtp: 20, broken: 10 },
    { label: 'C1 (31-60)', settled: 55, activePtp: 15, broken: 20 },
    { label: 'C2 (61-90)', settled: 35, activePtp: 12, broken: 18 },
    { label: 'C3+ (90+)', settled: 15, activePtp: 8, broken: 22 },
  ],
  contactabilityFunnel: [
    { label: 'Attempts (100k)', value: '100k', percentage: '100%' },
    { label: 'Contacted (65k)', value: '65k', percentage: '65%' },
    { label: 'Engaged (32k)', value: '32k', percentage: '32%' },
    { label: 'Commitment (18k)', value: '18k', percentage: '18%' },
  ],
  channelEfficiency: { channel: 'WhatsApp', rate: '82%' },
  brokenPtpPriorities: [
    { customerId: '#CA-88901', name: 'Andi Saputra', initials: 'AS', amount: 'Rp 12.500.000', ambcValue: '0.94', ambcTier: 'High', lastAction: 'Broken Promise', lastActionDate: 'Oct 24, 2023' },
    { customerId: '#CA-88942', name: 'Rina Tiara', initials: 'RT', amount: 'Rp 8.240.000', ambcValue: '0.89', ambcTier: 'High', lastAction: 'Partial Payment Failed', lastActionDate: 'Oct 23, 2023' },
    { customerId: '#CA-89012', name: 'Bambang Pamungkas', initials: 'BP', amount: 'Rp 25.100.000', ambcValue: '0.92', ambcTier: 'High', lastAction: 'WA Unread > 48h', lastActionDate: 'Oct 22, 2023' },
    { customerId: '#CA-89211', name: 'Siti Maesaroh', initials: 'SM', amount: 'Rp 4.700.000', ambcValue: '0.81', ambcTier: 'High', lastAction: 'Direct Refusal', lastActionDate: 'Oct 22, 2023' },
    { customerId: '#CA-89304', name: 'Dedi Firmansyah', initials: 'DF', amount: 'Rp 18.900.000', ambcValue: '0.97', ambcTier: 'High', lastAction: 'Skiptrace Required', lastActionDate: 'Oct 21, 2023' },
  ],
  syncNote: 'Data last synchronized: 2 minutes ago',
};

if (import.meta.env.DEV) {
  dashboardSummaryResponseSchema.parse(dashboardSummaryFixture);
}
