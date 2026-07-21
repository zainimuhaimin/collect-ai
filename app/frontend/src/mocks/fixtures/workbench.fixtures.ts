import {
  workbenchAccountSchema,
  workbenchLogEntrySchema,
  type WorkbenchAccount,
  type WorkbenchFilterKey,
  type WorkbenchLogEntry,
} from '../../domains/workbench/workbench.schema';

// This mock only carries 4 sample accounts, but the UI's "Semua Akun" chip is meant to
// reflect a much larger real book of business. TOTAL_ACCOUNTS_ESTIMATE fakes that larger
// count for the unfiltered view; any real filter/search narrows to the actual matched rows.
const TOTAL_ACCOUNTS_ESTIMATE = 124;

const ALL_WORKBENCH_ACCOUNTS: WorkbenchAccount[] = [
  {
    id: 'ACC-99210',
    accountId: '#ACC-99210',
    name: 'Adi Saputra',
    initials: 'AS',
    dpdDays: 84,
    amount: 'Rp 12.500.000',
    priority: 'Critical',
    location: 'Kabupaten Bekasi, Jawa Barat',
    paymentProbability: 82,
    employmentStatus: 'Karyawan Swasta',
    lastPaymentDate: '14 Jan 2024',
    aiReasoning:
      'Berdasarkan pola transaksi historis, debitur cenderung melakukan pembayaran setelah menerima pengingat via WhatsApp di pagi hari (jam 09:00 - 10:00 WIB). Ada riwayat komunikasi positif sebelumnya namun terhambat karena keterlambatan gaji.',
    aiRecommendations: [
      'Kirim template pesan penagihan persuasif (Restrukturisasi).',
      'Tawarkan perpanjangan tenor 3 bulan jika pembayaran DP dilakukan hari ini.',
      'Kontak via Deskcoll jika WA tidak direspon dalam 4 jam.',
    ],
  },
  {
    id: 'ACC-88412',
    accountId: '#ACC-88412',
    name: 'Maria Monica',
    initials: 'MM',
    dpdDays: 45,
    amount: 'Rp 8.200.000',
    priority: 'Critical',
    location: 'Kota Bandung, Jawa Barat',
    paymentProbability: 58,
    employmentStatus: 'Wiraswasta',
    lastPaymentDate: '02 Des 2023',
    aiReasoning: 'Debitur menunjukkan pola komunikasi responsif pada sore hari namun belum ada komitmen tanggal pembayaran yang pasti pada dua kontak terakhir.',
    aiRecommendations: ['Kirim pengingat sore hari (16:00 - 18:00 WIB).', 'Tawarkan opsi pembayaran sebagian sebagai langkah awal.'],
  },
  {
    id: 'ACC-77103',
    accountId: '#ACC-77103',
    name: 'Rizky Wahyudi',
    initials: 'RW',
    dpdDays: 32,
    amount: 'Rp 25.000.000',
    priority: 'High',
    location: 'Kota Surabaya, Jawa Timur',
    paymentProbability: 65,
    employmentStatus: 'Karyawan Swasta',
    lastPaymentDate: '20 Des 2023',
    aiReasoning: 'Nilai piutang tinggi dengan riwayat pembayaran tepat waktu sebelum keterlambatan terkini. Kemungkinan kendala arus kas sementara.',
    aiRecommendations: ['Prioritaskan kontak personal oleh senior collector.', 'Tawarkan restrukturisasi tenor untuk menjaga nilai piutang.'],
  },
  {
    id: 'ACC-12345',
    accountId: '#ACC-12345',
    name: 'Eka Nuraini',
    initials: 'EN',
    dpdDays: 12,
    amount: 'Rp 4.500.000',
    priority: 'Medium',
    location: 'Kota Semarang, Jawa Tengah',
    paymentProbability: 88,
    employmentStatus: 'Karyawan Swasta',
    lastPaymentDate: '05 Jan 2024',
    aiReasoning: 'Keterlambatan singkat dengan probabilitas self-cure tinggi berdasarkan riwayat pembayaran yang konsisten.',
    aiRecommendations: ['Kirim pengingat otomatis via WhatsApp, tanpa perlu eskalasi manual.'],
  },
];

export const workbenchActivityLogFixture: WorkbenchLogEntry[] = [
  { id: 'wl-1', title: 'WhatsApp terkirim - Automasi System', timestamp: 'Hari ini, 09:12 WIB', tone: 'sent' },
  { id: 'wl-2', title: 'Panggilan tidak terjawab (No Response)', timestamp: 'Kemarin, 16:45 WIB', tone: 'missed' },
];

if (import.meta.env.DEV) {
  ALL_WORKBENCH_ACCOUNTS.forEach((account) => workbenchAccountSchema.parse(account));
  workbenchActivityLogFixture.forEach((entry) => workbenchLogEntrySchema.parse(entry));
}

export function filterWorkbenchAccounts(filter: WorkbenchFilterKey, search: string) {
  let accounts = ALL_WORKBENCH_ACCOUNTS;

  if (filter === 'dpd_30_plus') {
    accounts = accounts.filter((account) => account.dpdDays >= 30);
  } else if (filter === 'high_amount') {
    accounts = accounts.filter((account) => account.priority === 'High' || account.priority === 'Critical');
  }

  const trimmedSearch = search.trim().toLowerCase();
  if (trimmedSearch) {
    accounts = accounts.filter((account) => account.name.toLowerCase().includes(trimmedSearch));
  }

  const totalCount = filter === 'all' && !trimmedSearch ? TOTAL_ACCOUNTS_ESTIMATE : accounts.length;
  return { accounts, totalCount };
}
