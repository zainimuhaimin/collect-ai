// TASK-P7 — Load test endpoint baca panas backend CollectAI.
//
// Menguji 5 endpoint GET yang paling sering dipanggil UI: dashboard summary,
// customer list (paginasi), customer detail, contract list, contract detail.
// TIDAK ada endpoint ini yang butuh auth (diverifikasi lewat pembacaan kode
// app/backend/api/v1/routers/{dashboard,customers,contracts}.py — tidak satu
// pun memakai Depends(get_current_user)), jadi skrip ini tidak melakukan
// login sama sekali.
//
// Jalankan dari root repo:
//   k6 run perf/k6/read_endpoints.js
//
// Override via env var (WAJIB dicek dulu untuk skala dataset yang sedang aktif
// — cust_id/contract_no berbeda-beda tergantung generator: faker asli pakai
// "CUST-00001"/"CTR-00001-1", bulk_clone pakai prefix "PC000N-"):
//   k6 run -e BASE_URL=http://localhost:8000 \
//          -e SAMPLE_CUST_ID=CUST-00029 \
//          -e SAMPLE_CONTRACT_NO=CTR-00029-1 \
//          -e VUS_PEAK=50 \
//          perf/k6/read_endpoints.js
//
// Cek ID yang valid untuk dataset yang sedang aktif:
//   psql -d collect_ai -c "SELECT cust_id FROM customer_master LIMIT 1;"
//   psql -d collect_ai -c "SELECT contract_no FROM contract_snapshot LIMIT 1;"

import http from 'k6/http';
import { check, group, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API = `${BASE_URL}/api/v1`;
const SAMPLE_CUST_ID = __ENV.SAMPLE_CUST_ID || 'CUST-00029';
const SAMPLE_CONTRACT_NO = __ENV.SAMPLE_CONTRACT_NO || 'CTR-00029-1';
const VUS_PEAK = parseInt(__ENV.VUS_PEAK || '50', 10);

// Metodologi (WAJIB dibaca sebelum menafsirkan hasil — lihat TASK-P7):
// - Jalankan backend dengan BEBERAPA worker (uvicorn --workers N) untuk skala
//   kapasitas nyata; satu worker akan understate kapasitas server sungguhan.
// - Jalankan skenario ini pada dataset KECIL dan BESAR secara terpisah, supaya
//   efek concurrency tidak tercampur dengan efek volume data.
// - Catat spesifikasi mesin & jumlah worker di performance-report.md setiap
//   kali menjalankan ini — angka tanpa konteks hardware tidak bisa dibandingkan.
export const options = {
  stages: [
    { duration: '30s', target: Math.ceil(VUS_PEAK * 0.2) },  // ramp-up pelan
    { duration: '1m', target: VUS_PEAK },                     // ramp ke peak
    { duration: '2m', target: VUS_PEAK },                     // tahan di peak
    { duration: '30s', target: 0 },                            // ramp-down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.01'],
    // Threshold per-endpoint (tag) — supaya satu endpoint lambat tidak
    // tersembunyi di rata-rata gabungan lima endpoint.
    'http_req_duration{endpoint:dashboard_summary}': ['p(95)<500'],
    'http_req_duration{endpoint:customer_list}': ['p(95)<500'],
    'http_req_duration{endpoint:customer_detail}': ['p(95)<500'],
    'http_req_duration{endpoint:contract_list}': ['p(95)<500'],
    'http_req_duration{endpoint:contract_detail}': ['p(95)<500'],
  },
};

function getChecked(url, tagName) {
  const res = http.get(url, { tags: { endpoint: tagName } });
  check(res, {
    [`${tagName}: status 200`]: (r) => r.status === 200,
  });
  return res;
}

export default function () {
  group('dashboard_summary', () => {
    getChecked(`${API}/dashboard/summary`, 'dashboard_summary');
  });

  group('customer_list', () => {
    const page = 1 + Math.floor(Math.random() * 5);
    getChecked(`${API}/customers?page=${page}&page_size=20`, 'customer_list');
  });

  group('customer_detail', () => {
    getChecked(`${API}/customers/${SAMPLE_CUST_ID}`, 'customer_detail');
  });

  group('contract_list', () => {
    const page = 1 + Math.floor(Math.random() * 5);
    getChecked(`${API}/contracts?page=${page}&page_size=20`, 'contract_list');
  });

  group('contract_detail', () => {
    getChecked(`${API}/contracts/${SAMPLE_CONTRACT_NO}`, 'contract_detail');
  });

  sleep(1); // jeda antar-iterasi per VU, mensimulasikan pengguna nyata (bukan hammer murni)
}
