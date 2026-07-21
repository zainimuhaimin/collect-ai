import {
  customerDetailSchema,
  customerTimelineResponseSchema,
  type CustomerDetail,
  type TimelineEntry,
} from '../../domains/customer/customer.schema';

export const customerDetailFixture: CustomerDetail = {
  id: 'C-90218341',
  name: 'Budi Pratama Sitorus',
  initials: 'BP',
  verified: true,
  outstandingBalance: 'Rp 12.450.000',
  balanceChange: '-12% since last month',
  ptpHistory: { success: 4, broken: 2, rate: '66%' },
  ptpMonths: [
    { month: 'May', result: 'success' },
    { month: 'Jun', result: 'success' },
    { month: 'Jul', result: 'broken' },
    { month: 'Aug', result: 'success' },
    { month: 'Sep', result: 'success' },
    { month: 'Oct', result: 'broken' },
  ],
  riskTier: 'HIGH RISK',
  riskTierLevel: 'Tier 3',
  riskScore: 82,
  recoveryScore: 74,
  recoveryLabel: 'Moderate Recovery',
  selfCureProbability: '12.5%',
  ptpSuccessProbability: '68.2%',
  targetNbaAction: 'Personalized SMS Hook',
  aiJustification:
    'Nasabah menunjukkan pola pembayaran yang reaktif terhadap pengingat digital pada akhir pekan. Skor pemulihan 74 didorong oleh sejarah 4 janji bayar yang ditepati dalam 6 bulan terakhir. Rekomendasi tindakan utama adalah mengirimkan pesan SMS yang dipersonalisasi pada hari Jumat pukul 17:00, dengan penekanan pada opsi restrukturisasi ringan untuk menghindari eskalasi ke agen lapangan. Probabilitas keberhasilan janji bayar (PTP) mencapai 68.2% jika dilakukan pendekatan non-konfrontatif.',
};

export const customerTimelineFixture: TimelineEntry[] = [
  {
    id: 'tl-1',
    icon: 'sms',
    title: 'Automated SMS Sent',
    timestamp: '12 Oct 2023, 10:45 AM',
    description: '"Halo Budi, mohon segera melakukan pelunasan tagihan Anda..."',
    tone: 'default',
    meta: { label: 'Status', value: 'Delivered', tone: 'success' },
  },
  {
    id: 'tl-2',
    icon: 'call',
    title: 'Inbound Call Received',
    timestamp: '10 Oct 2023, 02:15 PM',
    description: 'Nasabah menanyakan perihal denda keterlambatan. Agent: Santi Wijaya. Status: Resolved',
    tone: 'default',
  },
  {
    id: 'tl-3',
    icon: 'event_busy',
    title: 'Broken Promise (PTP)',
    timestamp: '05 Oct 2023, 11:59 PM',
    description: 'Janji bayar sebesar Rp 1.500.000 tidak terdeteksi di sistem pada tanggal jatuh tempo yang dijanjikan.',
    tone: 'danger',
  },
  {
    id: 'tl-4',
    icon: 'person_add',
    title: 'Account Assigned to Internal Team',
    timestamp: '01 Oct 2023, 08:00 AM',
    description: 'Akun dipindahkan dari sistem otomatis ke tim penagihan internal karena keterlambatan melampaui 30 hari (DPD 30+).',
    tone: 'default',
  },
];

if (import.meta.env.DEV) {
  customerDetailSchema.parse(customerDetailFixture);
  customerTimelineResponseSchema.parse(customerTimelineFixture);
}
