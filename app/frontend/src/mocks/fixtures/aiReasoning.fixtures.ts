import type { AiReasoningResponse } from '../../domains/ai-reasoning/aiReasoning.schema';

// State in-memory per module (bukan per customer) — cukup untuk demo mock:
// sebelum generate -> NONE, setelah generate -> OK dengan hasil yang sama
// untuk siapa pun (fixture, bukan backend sungguhan).
let generated = false;

const NONE_RESULT: AiReasoningResponse = {
  status: 'NONE',
  insufficientReason: null,
  stale: false,
  generatedAt: null,
  promptVersion: null,
  modelUsed: null,
  summary: null,
  customerTreatmentStrategy: null,
  keyFactors: [],
  primaryNbaAction: null,
  primaryNbaRationale: null,
  nbaAgreement: null,
  perContractFocus: [],
  consistencyNote: null,
  analyzedContractNos: [],
};

// Contoh yang sama dengan §6 ai-reasoning-api-upgrade-tasks.md — debitur 3
// kontrak dengan rekomendasi rule-based berbeda-beda (WA/Somasi/Visit) yang
// direkonsiliasi jadi satu strategi.
const OK_RESULT: AiReasoningResponse = {
  status: 'OK',
  insufficientReason: null,
  stale: false,
  generatedAt: new Date().toISOString(),
  promptVersion: 'v1',
  modelUsed: 'gemini-2.0-flash',
  summary:
    'Debitur memiliki 3 kontrak aktif dengan total OTS Rp 45 juta, dan 82% dari eksposur itu sedang menunggak. ' +
    "Kontrak CTR-00029-2 sudah mencapai DPD 95 (C3+) dengan segmen Won't Pay, sementara kontrak terbesarnya " +
    '(CTR-00029-1, Rp 28 juta) masih relatif terkendali di DPD 12.',
  customerTreatmentStrategy:
    'Tangani sebagai satu debitur dengan pendekatan kunjungan langsung, memakai kesempatan itu untuk membahas ' +
    'SELURUH tiga kontraknya sekaligus — bukan tiga upaya terpisah.',
  keyFactors: [
    '82% dari total OTS Rp 45 juta sedang menunggak',
    'CTR-00029-2 sudah DPD 95 (C3+) — segmen Won\'t Pay',
    'Reliabilitas PTP rendah (0.40) — janji bayar sering tidak ditepati',
    '3 kontrak dengan rekomendasi berbeda (WA / Somasi / Visit) — perlu satu pendekatan',
  ],
  primaryNbaAction: 'Visit',
  primaryNbaRationale:
    'Kontrak terburuk sudah C3+ sehingga pengingat WA tidak lagi memadai, tapi kontrak terbesarnya masih bisa ' +
    'diselamatkan — kunjungan memungkinkan negosiasi seluruh portofolio sekaligus.',
  nbaAgreement: 'DIFFER',
  perContractFocus: [
    { contractNo: 'CTR-00029-1', urgency: 'HIGH', note: 'Nilai terbesar dan masih terkendali — fokus utama penyelamatan.' },
    { contractNo: 'CTR-00029-2', urgency: 'CRITICAL', note: 'Sudah C3+. Siapkan opsi restrukturisasi.' },
    { contractNo: 'CTR-00029-3', urgency: 'MEDIUM', note: 'Nilai kecil — jangan jadi alasan kunjungan terpisah.' },
  ],
  consistencyNote:
    'Ketiga kontrak ditangani dengan satu kunjungan, bukan tiga channel berbeda — mengirim WA ramah untuk satu ' +
    'kontrak sementara somasi berjalan untuk kontrak lain akan melemahkan posisi negosiasi.',
  analyzedContractNos: ['CTR-00029-1', 'CTR-00029-2', 'CTR-00029-3'],
};

export function getAiReasoningFixture(): AiReasoningResponse {
  return generated ? OK_RESULT : NONE_RESULT;
}

export function generateAiReasoningFixture(): AiReasoningResponse {
  generated = true;
  return OK_RESULT;
}

// Dipakai test/dev untuk reset state di antara skenario.
export function resetAiReasoningFixture(): void {
  generated = false;
}
