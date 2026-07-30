import {
  contractDetailSchema,
  activityLogResponseSchema,
  type ContractDetail,
  type ContractListItem,
  type ActivityLogEntry,
  type PaymentHistoryEntry,
  type ContractRestructuringStatus,
} from '../../domains/contract/contract.schema';
import type { RiskSegment } from '../../domains/shared/riskSegment';

export function formatRupiah(amount: number): string {
  return `Rp ${Math.round(amount).toLocaleString('id-ID')}`;
}

// ── Master contract dataset ─────────────────────────────────────────────
// This is the single source of truth for every contract across the mock backend —
// Contract List/Detail, Customer Detail's "Kontrak Milik Customer Ini" section, and
// the activity-log endpoint all read from this one array so contractNo/custId values
// always line up and cross-navigation never dead-ends.
interface ContractSeed {
  readonly contractNo: string;
  readonly custId: string;
  readonly custName: string;
  readonly productType: string;
  readonly dpdCurrent: number;
  readonly prncOts: number;
  readonly intrOts: number;
  readonly loanAmount: number;
  readonly installmentAmount: number;
  readonly interestRate: number;
  readonly maturityDate: string;
  readonly remainingTenorMonths: number;
  readonly overdueInstallmentCount: number;
  readonly lateFeeAmount: number;
  readonly ambc: number;
  readonly prevCycle: string;
  readonly cycle: string;
  readonly closedViaRestructure: boolean;
  readonly recoveryScore: number;
  readonly riskSegment: RiskSegment;
  readonly selfCureProbability: number;
  readonly rollForwardRisk: number;
  readonly ptpSuccessProbability: number;
  readonly nbaRecommendation: string;
  readonly confidenceLevel: number;
  readonly scoringDate: string;
  readonly lastPtpBroken: boolean;
  readonly restructuringStatus: ContractRestructuringStatus;
}

const contractSeeds: ContractSeed[] = [
  { contractNo: 'CTR-00001-1', custId: 'CUST-00001', custName: 'Budi Pratama Sitorus', productType: 'Personal Loan', dpdCurrent: 62, prncOts: 9_800_000, intrOts: 2_650_000, loanAmount: 18_000_000, installmentAmount: 1_650_000, interestRate: 13.76, maturityDate: '2027-04-10', remainingTenorMonths: 9, overdueInstallmentCount: 3, lateFeeAmount: 185_000, ambc: 12_400_000, prevCycle: 'C1', cycle: 'C2', closedViaRestructure: false, recoveryScore: 41, riskSegment: 'Cannot Pay', selfCureProbability: 11, rollForwardRisk: 68, ptpSuccessProbability: 24, nbaRecommendation: 'Field Visit', confidenceLevel: 82, scoringDate: '2026-07-20', lastPtpBroken: true, restructuringStatus: { restructureGroupId: 'RG-CUST-00001-2026-07-15-1', offerStatus: 'GENERATED', eligibilityTier: 'MANUAL_REVIEW' } },
  { contractNo: 'CTR-00001-2', custId: 'CUST-00001', custName: 'Budi Pratama Sitorus', productType: 'Multiguna', dpdCurrent: 12, prncOts: 5_100_000, intrOts: 640_000, loanAmount: 9_000_000, installmentAmount: 820_000, interestRate: 11.4, maturityDate: '2027-01-05', remainingTenorMonths: 6, overdueInstallmentCount: 1, lateFeeAmount: 42_000, ambc: 3_100_000, prevCycle: 'C0', cycle: 'C0', closedViaRestructure: false, recoveryScore: 77, riskSegment: 'Self-cure', selfCureProbability: 74, rollForwardRisk: 18, ptpSuccessProbability: 81, nbaRecommendation: 'SMS Reminder', confidenceLevel: 90, scoringDate: '2026-07-20', lastPtpBroken: false, restructuringStatus: null },

  { contractNo: 'CTR-00002-1', custId: 'CUST-00002', custName: 'Rina Tiara Wulandari', productType: 'KPR', dpdCurrent: 45, prncOts: 22_400_000, intrOts: 4_300_000, loanAmount: 350_000_000, installmentAmount: 4_200_000, interestRate: 9.5, maturityDate: '2032-02-01', remainingTenorMonths: 68, overdueInstallmentCount: 2, lateFeeAmount: 310_000, ambc: 18_900_000, prevCycle: 'C0', cycle: 'C1', closedViaRestructure: false, recoveryScore: 58, riskSegment: 'Self-cure', selfCureProbability: 62, rollForwardRisk: 35, ptpSuccessProbability: 55, nbaRecommendation: 'WhatsApp Follow-up', confidenceLevel: 85, scoringDate: '2026-07-19', lastPtpBroken: false, restructuringStatus: null },
  { contractNo: 'CTR-00002-2', custId: 'CUST-00002', custName: 'Rina Tiara Wulandari', productType: 'Kartu Kredit', dpdCurrent: 8, prncOts: 2_150_000, intrOts: 310_000, loanAmount: 5_000_000, installmentAmount: 450_000, interestRate: 24.0, maturityDate: '2026-12-15', remainingTenorMonths: 5, overdueInstallmentCount: 0, lateFeeAmount: 0, ambc: 1_200_000, prevCycle: 'C0', cycle: 'C0', closedViaRestructure: false, recoveryScore: 88, riskSegment: 'Self-cure', selfCureProbability: 91, rollForwardRisk: 6, ptpSuccessProbability: 93, nbaRecommendation: 'No Action', confidenceLevel: 94, scoringDate: '2026-07-19', lastPtpBroken: false, restructuringStatus: null },

  { contractNo: 'CTR-00003-1', custId: 'CUST-00003', custName: 'Bambang Pamungkas', productType: 'Personal Loan', dpdCurrent: 95, prncOts: 16_200_000, intrOts: 5_400_000, loanAmount: 25_000_000, installmentAmount: 2_100_000, interestRate: 15.2, maturityDate: '2026-11-20', remainingTenorMonths: 4, overdueInstallmentCount: 5, lateFeeAmount: 620_000, ambc: 21_100_000, prevCycle: 'C2', cycle: 'C3', closedViaRestructure: false, recoveryScore: 22, riskSegment: 'Cannot Pay', selfCureProbability: 4, rollForwardRisk: 88, ptpSuccessProbability: 9, nbaRecommendation: 'Legal Notice (Somasi)', confidenceLevel: 79, scoringDate: '2026-07-18', lastPtpBroken: true, restructuringStatus: { restructureGroupId: 'RG-CUST-00003-2026-07-10-1', offerStatus: 'OFFERED', eligibilityTier: 'AUTO' } },

  { contractNo: 'CTR-00004-1', custId: 'CUST-00004', custName: 'Siti Maesaroh', productType: 'Multiguna', dpdCurrent: 33, prncOts: 4_800_000, intrOts: 900_000, loanAmount: 10_000_000, installmentAmount: 950_000, interestRate: 12.8, maturityDate: '2027-03-01', remainingTenorMonths: 8, overdueInstallmentCount: 2, lateFeeAmount: 95_000, ambc: 5_600_000, prevCycle: 'C0', cycle: 'C1', closedViaRestructure: false, recoveryScore: 64, riskSegment: "Won't Pay", selfCureProbability: 30, rollForwardRisk: 42, ptpSuccessProbability: 21, nbaRecommendation: 'Deskcoll Call', confidenceLevel: 81, scoringDate: '2026-07-21', lastPtpBroken: true, restructuringStatus: null },

  { contractNo: 'CTR-00005-1', custId: 'CUST-00005', custName: 'Dedi Firmansyah', productType: 'Personal Loan', dpdCurrent: 110, prncOts: 14_500_000, intrOts: 4_400_000, loanAmount: 22_000_000, installmentAmount: 1_980_000, interestRate: 14.5, maturityDate: '2026-10-05', remainingTenorMonths: 3, overdueInstallmentCount: 6, lateFeeAmount: 740_000, ambc: 19_800_000, prevCycle: 'C3', cycle: 'C3+', closedViaRestructure: false, recoveryScore: 18, riskSegment: 'Cannot Pay', selfCureProbability: 3, rollForwardRisk: 91, ptpSuccessProbability: 6, nbaRecommendation: 'Legal Notice (Somasi)', confidenceLevel: 76, scoringDate: '2026-07-17', lastPtpBroken: true, restructuringStatus: { restructureGroupId: 'RG-CUST-00005-2026-07-05-1', offerStatus: 'GENERATED', eligibilityTier: 'MANUAL_REVIEW' } },
  { contractNo: 'CTR-00005-2', custId: 'CUST-00005', custName: 'Dedi Firmansyah', productType: 'Kartu Kredit', dpdCurrent: 40, prncOts: 3_200_000, intrOts: 780_000, loanAmount: 6_000_000, installmentAmount: 520_000, interestRate: 26.5, maturityDate: '2026-12-01', remainingTenorMonths: 5, overdueInstallmentCount: 2, lateFeeAmount: 110_000, ambc: 4_400_000, prevCycle: 'C1', cycle: 'C1', closedViaRestructure: false, recoveryScore: 47, riskSegment: 'Cannot Pay', selfCureProbability: 15, rollForwardRisk: 58, ptpSuccessProbability: 19, nbaRecommendation: 'Deskcoll Call', confidenceLevel: 80, scoringDate: '2026-07-17', lastPtpBroken: false, restructuringStatus: null },

  { contractNo: 'CTR-00006-1', custId: 'CUST-00006', custName: 'Andi Saputra', productType: 'Personal Loan', dpdCurrent: 5, prncOts: 6_100_000, intrOts: 820_000, loanAmount: 12_000_000, installmentAmount: 1_050_000, interestRate: 13.0, maturityDate: '2027-06-10', remainingTenorMonths: 11, overdueInstallmentCount: 0, lateFeeAmount: 0, ambc: 900_000, prevCycle: 'C0', cycle: 'C0', closedViaRestructure: false, recoveryScore: 92, riskSegment: 'Self-cure', selfCureProbability: 95, rollForwardRisk: 4, ptpSuccessProbability: 96, nbaRecommendation: 'No Action', confidenceLevel: 96, scoringDate: '2026-07-22', lastPtpBroken: false, restructuringStatus: null },
  { contractNo: 'CTR-00006-2', custId: 'CUST-00006', custName: 'Andi Saputra', productType: 'Multiguna', dpdCurrent: 0, prncOts: 1_200_000, intrOts: 90_000, loanAmount: 3_000_000, installmentAmount: 280_000, interestRate: 10.5, maturityDate: '2026-11-01', remainingTenorMonths: 3, overdueInstallmentCount: 0, lateFeeAmount: 0, ambc: 150_000, prevCycle: 'C0', cycle: 'C0', closedViaRestructure: false, recoveryScore: 97, riskSegment: 'Self-cure', selfCureProbability: 98, rollForwardRisk: 1, ptpSuccessProbability: 99, nbaRecommendation: 'No Action', confidenceLevel: 98, scoringDate: '2026-07-22', lastPtpBroken: false, restructuringStatus: null },
  { contractNo: 'CTR-00006-3', custId: 'CUST-00006', custName: 'Andi Saputra', productType: 'Kartu Kredit', dpdCurrent: 21, prncOts: 2_800_000, intrOts: 410_000, loanAmount: 4_500_000, installmentAmount: 400_000, interestRate: 25.0, maturityDate: '2027-02-15', remainingTenorMonths: 7, overdueInstallmentCount: 1, lateFeeAmount: 55_000, ambc: 1_100_000, prevCycle: 'C0', cycle: 'C0', closedViaRestructure: false, recoveryScore: 80, riskSegment: 'Self-cure', selfCureProbability: 79, rollForwardRisk: 22, ptpSuccessProbability: 74, nbaRecommendation: 'WhatsApp Follow-up', confidenceLevel: 88, scoringDate: '2026-07-22', lastPtpBroken: false, restructuringStatus: null },

  { contractNo: 'CTR-00007-1', custId: 'CUST-00007', custName: 'Rina Kusuma', productType: 'KPR', dpdCurrent: 150, prncOts: 45_000_000, intrOts: 12_000_000, loanAmount: 420_000_000, installmentAmount: 5_100_000, interestRate: 9.9, maturityDate: '2031-08-01', remainingTenorMonths: 60, overdueInstallmentCount: 8, lateFeeAmount: 1_450_000, ambc: 38_500_000, prevCycle: 'C3', cycle: 'C3+', closedViaRestructure: false, recoveryScore: 9, riskSegment: 'Cannot Pay', selfCureProbability: 2, rollForwardRisk: 96, ptpSuccessProbability: 4, nbaRecommendation: 'Legal Notice (Somasi)', confidenceLevel: 74, scoringDate: '2026-07-16', lastPtpBroken: true, restructuringStatus: { restructureGroupId: 'RG-CUST-00007-2026-06-30-1', offerStatus: 'REJECTED', eligibilityTier: 'MANUAL_REVIEW' } },

  { contractNo: 'CTR-00008-1', custId: 'CUST-00008', custName: 'Hendra Gunawan', productType: 'Personal Loan', dpdCurrent: 28, prncOts: 7_400_000, intrOts: 1_100_000, loanAmount: 15_000_000, installmentAmount: 1_320_000, interestRate: 13.5, maturityDate: '2027-05-05', remainingTenorMonths: 10, overdueInstallmentCount: 1, lateFeeAmount: 65_000, ambc: 2_900_000, prevCycle: 'C0', cycle: 'C0', closedViaRestructure: false, recoveryScore: 71, riskSegment: 'Self-cure', selfCureProbability: 68, rollForwardRisk: 29, ptpSuccessProbability: 62, nbaRecommendation: 'SMS Reminder', confidenceLevel: 87, scoringDate: '2026-07-23', lastPtpBroken: false, restructuringStatus: null },

  { contractNo: 'CTR-00009-1', custId: 'CUST-00009', custName: 'Wulan Sari', productType: 'Multiguna', dpdCurrent: 72, prncOts: 9_900_000, intrOts: 2_100_000, loanAmount: 16_000_000, installmentAmount: 1_400_000, interestRate: 12.9, maturityDate: '2026-12-20', remainingTenorMonths: 5, overdueInstallmentCount: 3, lateFeeAmount: 210_000, ambc: 11_200_000, prevCycle: 'C1', cycle: 'C2', closedViaRestructure: false, recoveryScore: 38, riskSegment: "Won't Pay", selfCureProbability: 20, rollForwardRisk: 63, ptpSuccessProbability: 14, nbaRecommendation: 'Deskcoll Call', confidenceLevel: 83, scoringDate: '2026-07-15', lastPtpBroken: true, restructuringStatus: null },

  { contractNo: 'CTR-00010-1', custId: 'CUST-00010', custName: 'Agus Setiawan', productType: 'Kartu Kredit', dpdCurrent: 3, prncOts: 1_800_000, intrOts: 250_000, loanAmount: 4_000_000, installmentAmount: 360_000, interestRate: 24.0, maturityDate: '2026-11-11', remainingTenorMonths: 4, overdueInstallmentCount: 0, lateFeeAmount: 0, ambc: 400_000, prevCycle: 'C0', cycle: 'C0', closedViaRestructure: false, recoveryScore: 94, riskSegment: 'Self-cure', selfCureProbability: 96, rollForwardRisk: 2, ptpSuccessProbability: 97, nbaRecommendation: 'No Action', confidenceLevel: 97, scoringDate: '2026-07-24', lastPtpBroken: false, restructuringStatus: null },

  { contractNo: 'CTR-00011-1', custId: 'CUST-00011', custName: 'Maya Anggraini', productType: 'Personal Loan', dpdCurrent: 55, prncOts: 8_600_000, intrOts: 1_900_000, loanAmount: 14_000_000, installmentAmount: 1_250_000, interestRate: 13.2, maturityDate: '2027-01-15', remainingTenorMonths: 6, overdueInstallmentCount: 2, lateFeeAmount: 150_000, ambc: 9_800_000, prevCycle: 'C0', cycle: 'C1', closedViaRestructure: false, recoveryScore: 52, riskSegment: 'Self-cure', selfCureProbability: 58, rollForwardRisk: 38, ptpSuccessProbability: 49, nbaRecommendation: 'WhatsApp Follow-up', confidenceLevel: 84, scoringDate: '2026-07-14', lastPtpBroken: false, restructuringStatus: null },

  { contractNo: 'CTR-00012-1', custId: 'CUST-00012', custName: 'Fajar Nugroho', productType: 'KPR', dpdCurrent: 180, prncOts: 60_000_000, intrOts: 18_500_000, loanAmount: 500_000_000, installmentAmount: 6_200_000, interestRate: 9.2, maturityDate: '2030-05-01', remainingTenorMonths: 46, overdueInstallmentCount: 9, lateFeeAmount: 2_100_000, ambc: 52_000_000, prevCycle: 'C3+', cycle: 'C3+', closedViaRestructure: false, recoveryScore: 6, riskSegment: 'Cannot Pay', selfCureProbability: 1, rollForwardRisk: 98, ptpSuccessProbability: 3, nbaRecommendation: 'Legal Notice (Somasi)', confidenceLevel: 71, scoringDate: '2026-07-13', lastPtpBroken: true, restructuringStatus: { restructureGroupId: 'RG-CUST-00012-2026-07-22-1', offerStatus: 'GENERATED', eligibilityTier: 'MANUAL_REVIEW' } },

  { contractNo: 'CTR-00013-1', custId: 'CUST-00013', custName: 'Indah Permata', productType: 'Multiguna', dpdCurrent: 0, prncOts: 950_000, intrOts: 60_000, loanAmount: 2_500_000, installmentAmount: 230_000, interestRate: 11.0, maturityDate: '2026-10-10', remainingTenorMonths: 2, overdueInstallmentCount: 0, lateFeeAmount: 0, ambc: 80_000, prevCycle: 'C0', cycle: 'C0', closedViaRestructure: false, recoveryScore: 99, riskSegment: 'Self-cure', selfCureProbability: 99, rollForwardRisk: 0, ptpSuccessProbability: 99, nbaRecommendation: 'No Action', confidenceLevel: 99, scoringDate: '2026-07-25', lastPtpBroken: false, restructuringStatus: null },

  { contractNo: 'CTR-00014-1', custId: 'CUST-00014', custName: 'Yusuf Hidayat', productType: 'Personal Loan', dpdCurrent: 38, prncOts: 6_700_000, intrOts: 1_300_000, loanAmount: 12_500_000, installmentAmount: 1_100_000, interestRate: 13.4, maturityDate: '2027-02-20', remainingTenorMonths: 8, overdueInstallmentCount: 1, lateFeeAmount: 90_000, ambc: 7_200_000, prevCycle: 'C0', cycle: 'C1', closedViaRestructure: false, recoveryScore: 60, riskSegment: 'Self-cure', selfCureProbability: 65, rollForwardRisk: 33, ptpSuccessProbability: 57, nbaRecommendation: 'SMS Reminder', confidenceLevel: 86, scoringDate: '2026-07-12', lastPtpBroken: false, restructuringStatus: null },

  { contractNo: 'CTR-00015-1', custId: 'CUST-00015', custName: 'Nadia Putri', productType: 'Kartu Kredit', dpdCurrent: 65, prncOts: 4_100_000, intrOts: 1_050_000, loanAmount: 7_000_000, installmentAmount: 610_000, interestRate: 25.5, maturityDate: '2026-11-25', remainingTenorMonths: 4, overdueInstallmentCount: 3, lateFeeAmount: 175_000, ambc: 6_300_000, prevCycle: 'C1', cycle: 'C2', closedViaRestructure: false, recoveryScore: 35, riskSegment: "Won't Pay", selfCureProbability: 17, rollForwardRisk: 61, ptpSuccessProbability: 12, nbaRecommendation: 'Deskcoll Call', confidenceLevel: 80, scoringDate: '2026-07-11', lastPtpBroken: true, restructuringStatus: null },

  { contractNo: 'CTR-00016-1', custId: 'CUST-00016', custName: 'Rizky Ramadhan', productType: 'Personal Loan', dpdCurrent: 15, prncOts: 5_500_000, intrOts: 780_000, loanAmount: 11_000_000, installmentAmount: 980_000, interestRate: 12.6, maturityDate: '2027-04-30', remainingTenorMonths: 9, overdueInstallmentCount: 0, lateFeeAmount: 20_000, ambc: 1_600_000, prevCycle: 'C0', cycle: 'C0', closedViaRestructure: false, recoveryScore: 83, riskSegment: 'Self-cure', selfCureProbability: 85, rollForwardRisk: 16, ptpSuccessProbability: 80, nbaRecommendation: 'SMS Reminder', confidenceLevel: 90, scoringDate: '2026-07-26', lastPtpBroken: false, restructuringStatus: null },

  { contractNo: 'CTR-00017-1', custId: 'CUST-00017', custName: 'Lestari Wijaya', productType: 'Multiguna', dpdCurrent: 130, prncOts: 13_800_000, intrOts: 4_100_000, loanAmount: 20_000_000, installmentAmount: 1_780_000, interestRate: 14.0, maturityDate: '2026-10-30', remainingTenorMonths: 3, overdueInstallmentCount: 6, lateFeeAmount: 580_000, ambc: 17_500_000, prevCycle: 'C2', cycle: 'C3', closedViaRestructure: false, recoveryScore: 14, riskSegment: 'Cannot Pay', selfCureProbability: 2, rollForwardRisk: 90, ptpSuccessProbability: 5, nbaRecommendation: 'Legal Notice (Somasi)', confidenceLevel: 77, scoringDate: '2026-07-10', lastPtpBroken: true, restructuringStatus: { restructureGroupId: 'RG-CUST-00017-2026-07-08-1', offerStatus: 'GENERATED', eligibilityTier: 'AUTO' } },

  { contractNo: 'CTR-00018-1', custId: 'CUST-00018', custName: 'Taufik Hidayat', productType: 'KPR', dpdCurrent: 22, prncOts: 18_200_000, intrOts: 3_600_000, loanAmount: 280_000_000, installmentAmount: 3_400_000, interestRate: 9.8, maturityDate: '2029-09-01', remainingTenorMonths: 38, overdueInstallmentCount: 1, lateFeeAmount: 60_000, ambc: 4_900_000, prevCycle: 'C0', cycle: 'C0', closedViaRestructure: true, recoveryScore: 90, riskSegment: 'Self-cure', selfCureProbability: 92, rollForwardRisk: 8, ptpSuccessProbability: 88, nbaRecommendation: 'No Action', confidenceLevel: 95, scoringDate: '2026-07-27', lastPtpBroken: false, restructuringStatus: { restructureGroupId: 'RG-CUST-00018-2026-05-01-1', offerStatus: 'ACCEPTED', eligibilityTier: 'AUTO' } },
];

function buildPaymentHistory(seed: ContractSeed): PaymentHistoryEntry[] {
  const months = ['2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07'];
  const recoverySources = ['WA', 'SMS', 'Deskcoll', 'Visit', 'Somasi'] as const;
  return months.map((month, index) => {
    const isLate = seed.dpdCurrent > 30 ? index % 2 === 0 : index === months.length - 1 && seed.dpdCurrent > 0;
    const dueDate = `${month}-05`;
    if (isLate && index < months.length - (seed.dpdCurrent > 60 ? 1 : 2)) {
      return {
        dueDate,
        actualPayDate: null,
        paymentAmount: 0,
        payStatus: 'UNPAID',
        delayDays: null,
        recoverySource: null,
      };
    }
    const delay = isLate ? 3 + index : 0;
    return {
      dueDate,
      actualPayDate: `${month}-${String(5 + delay).padStart(2, '0')}`,
      paymentAmount: seed.installmentAmount,
      payStatus: delay > 0 ? 'LATE' : 'ON_TIME',
      delayDays: delay > 0 ? delay : 0,
      recoverySource: delay > 0 ? recoverySources[index % recoverySources.length] : null,
    };
  });
}

function buildActivityLog(seed: ContractSeed): ActivityLogEntry[] {
  const base: ActivityLogEntry[] = [
    {
      id: `${seed.contractNo}-log-1`,
      icon: 'sms',
      title: 'Automated SMS Sent',
      timestamp: '20 Jul 2026, 09:15 AM',
      description: `Pengingat jatuh tempo tagihan kontrak ${seed.contractNo} dikirim ke nasabah.`,
      tone: 'default',
      meta: { label: 'Status', value: 'Delivered', tone: 'success' },
    },
    {
      id: `${seed.contractNo}-log-2`,
      icon: 'call',
      title: 'Outbound Call Attempt',
      timestamp: '15 Jul 2026, 02:30 PM',
      description: 'Agen menghubungi nasabah untuk konfirmasi rencana pembayaran.',
      tone: 'default',
    },
  ];
  if (seed.lastPtpBroken) {
    base.unshift({
      id: `${seed.contractNo}-log-broken`,
      icon: 'event_busy',
      title: 'Broken Promise (PTP)',
      timestamp: '12 Jul 2026, 11:59 PM',
      description: 'Janji bayar tidak terdeteksi di sistem pada tanggal jatuh tempo yang dijanjikan.',
      tone: 'danger',
    });
  }
  if (seed.dpdCurrent >= 30) {
    base.push({
      id: `${seed.contractNo}-log-assign`,
      icon: 'person_add',
      title: 'Account Assigned to Internal Team',
      timestamp: '05 Jul 2026, 08:00 AM',
      description: `Kontrak dipindahkan ke tim penagihan internal karena keterlambatan melampaui 30 hari (DPD ${seed.dpdCurrent}).`,
      tone: 'default',
    });
  }
  return base;
}

function toListItem(seed: ContractSeed): ContractListItem {
  return {
    contractNo: seed.contractNo,
    custId: seed.custId,
    custName: seed.custName,
    productType: seed.productType,
    dpdCurrent: seed.dpdCurrent,
    outstanding: formatRupiah(seed.prncOts + seed.intrOts),
    riskSegment: seed.riskSegment,
  };
}

function toDetail(seed: ContractSeed): ContractDetail {
  // Seed values above are authored on a 0-100 scale (matches this fixture file's
  // original convention) — the real backend/schema uses raw 0-1 decimal fractions
  // (see contract.schema.ts), so convert at this single mapping boundary rather
  // than rewriting all 24 seed rows.
  const detail: ContractDetail = {
    contractNo: seed.contractNo,
    custId: seed.custId,
    custName: seed.custName,
    productType: seed.productType,
    cycle: seed.cycle,
    prevCycle: seed.prevCycle,
    closedViaRestructure: seed.closedViaRestructure,
    newContractNo: null,
    loanAmount: seed.loanAmount,
    installmentAmount: seed.installmentAmount,
    interestRate: seed.interestRate / 100,
    maturityDate: seed.maturityDate,
    remainingTenorMonths: seed.remainingTenorMonths,
    dpdCurrent: seed.dpdCurrent,
    overdueInstallmentCount: seed.overdueInstallmentCount,
    lateFeeAmount: seed.lateFeeAmount,
    ambc: seed.ambc,
    outstanding: {
      principal: seed.prncOts,
      interest: seed.intrOts,
      total: seed.prncOts + seed.intrOts,
    },
    aiScoring: {
      recoveryScore: seed.recoveryScore / 100,
      riskSegment: seed.riskSegment,
      selfCureProbability: seed.selfCureProbability / 100,
      rollForwardRisk: seed.rollForwardRisk / 100,
      ptpSuccessProbability: seed.ptpSuccessProbability / 100,
      nbaRecommendation: seed.nbaRecommendation,
      confidenceLevel: seed.confidenceLevel / 100,
      scoringDate: seed.scoringDate,
    },
    paymentHistory: buildPaymentHistory(seed),
    restructuringStatus: seed.restructuringStatus,
  };
  return contractDetailSchema.parse(detail);
}

export const contractRecords = contractSeeds.map((seed) => ({
  seed,
  listItem: toListItem(seed),
  detail: toDetail(seed),
  activityLog: activityLogResponseSchema.parse(buildActivityLog(seed)),
}));

export function findContractRecord(contractNo: string) {
  return contractRecords.find((record) => record.seed.contractNo === contractNo);
}

export function getContractsForCustomer(custId: string) {
  return contractRecords.filter((record) => record.seed.custId === custId);
}
