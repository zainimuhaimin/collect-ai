# Mengapa XGBoost, Bukan LLM/Model AI Lain, untuk Mesin Scoring CollectAI

## Ringkasan eksekutif

Perdebatan ini sering dibingkai sebagai "AI lama vs AI baru". Bingkai yang lebih
tepat: **jenis pekerjaan apa yang sedang diselesaikan**. Mesin scoring
CollectAI mengerjakan satu hal spesifik — mengubah ~36 kolom angka per kontrak
menjadi satu probabilitas terkalibrasi, untuk ribuan kontrak setiap hari,
dengan hasil yang harus bisa diaudit dan direproduksi. Itu adalah soal regresi
probabilitas atas data tabular, bukan soal memahami/menghasilkan bahasa — dan
justru di situ XGBoost dan sejenisnya (*gradient-boosted trees*) masih menjadi
standar industri, termasuk di institusi keuangan yang jauh lebih besar dari
kita.

LLM tidak "kalah" secara umum — ia unggul di tugas yang berbeda (bahasa bebas,
narasi, ringkasan). Proyek ini sendiri sudah merencanakan LLM untuk pekerjaan
itu: kartu narasi "AI Reasoning" di halaman Customer Detail
(`ai-reasoning-api-upgrade-tasks.md`) — **melengkapi** XGBoost, bukan
menggantikannya. Dokumen ini menjelaskan kenapa pembagian tugas itu benar,
dengan bukti terukur dari codebase CollectAI sendiri, dan menyiapkan Anda untuk
argumen-argumen yang kemungkinan besar akan muncul.

---

## 1. Apa sebenarnya yang diperdebatkan

| | Tugasnya | Alat yang cocok |
|---|---|---|
| Scoring `recovery_score`, `risk_segment`, dsb | Regresi probabilitas dari kolom numerik terstruktur, dijalankan ribuan kali/hari, harus reproducible | **XGBoost** |
| Narasi "kenapa nasabah ini berisiko" untuk petugas CS | Bahasa bebas, sekali per klik, tidak butuh determinisme ketat | LLM |

Kalau atasan Anda mengusulkan LLM untuk **poin pertama**, itu yang perlu
diluruskan. Kalau untuk poin kedua, Anda sebenarnya sepakat — dan itu memang
sudah ada di roadmap.

---

## 2. Bukti terukur dari proyek ini sendiri

Diukur langsung hari ini di codebase CollectAI, bukan klaim dari brosur:

| Metrik | Nilai | Sumber |
|---|---|---|
| Volume data | 2.000 customer, 2.918 kontrak | `contract_snapshot` |
| Jumlah fitur | 36 (recovery), 12/14/11 (3 model lain) | `config/settings.py` |
| **Waktu training** model `recovery` | **12,3 detik** (termasuk labeling + 5-fold CV) | `train_initial_model.py` |
| **Waktu scoring** 2.817 kontrak | **8,6 detik total** (~3 milidetik/kontrak) | `daily_scoring.py` |
| Ukuran artifact model | ~1,08 MB, satu file | `recovery_model_champion.pkl` |
| AUC (grouped cross-validation) | 0,80 | Di atas floor 0,68 yang di-gate otomatis |
| Explainability | Feature importance keluar otomatis dari training, tanpa kerja tambahan | `cycle_encoded`, `dpd_current`, `overdue_installment_count` sebagai 3 fitur teratas |
| Infra | Jalan di laptop, tanpa GPU, tanpa API key eksternal | — |

Bandingkan dengan skenario LLM untuk pekerjaan yang sama: pada perancangan
fitur "AI Reasoning" di proyek ini — yang hanya memproses **satu** kontrak per
klik, bukan scoring batch — sudah harus direncanakan timeout 20–30 detik dan
arsitektur background job supaya tidak macet di browser. Menskalakan itu ke
2.817 kontrak/hari berarti ribuan pemanggilan API berbayar, dengan urutan waktu
menit-hingga-jam, untuk menggantikan pekerjaan yang XGBoost selesaikan dalam
8,6 detik.

---

## 3. Enam alasan teknis

### 3.1 Data tabular ≠ bahasa

LLM dilatih untuk memprediksi token berikutnya dalam teks. Untuk menyuruhnya
"menghitung" probabilitas dari 36 kolom angka, kolom-kolom itu harus diserialisasi
jadi teks, lalu modelnya menebak angka lewat proses generatif — bukan dioptimalkan
langsung terhadap metrik seperti AUC atau log-loss sebagaimana XGBoost. Ini
seperti memakai penerjemah bahasa untuk mengerjakan spreadsheet: bisa dipaksakan,
tapi bukan untuk itu alat itu dibuat.

### 3.2 Bukan opini — ini temuan riset yang sudah mapan

Grinsztajn dkk. (NeurIPS 2022), *"Why do tree-based models still outperform
deep learning on tabular data?"*, menguji puluhan dataset tabular dan menemukan
model berbasis pohon (XGBoost/GBM) tetap mengungguli deep learning — apalagi
dibanding LLM, yang bahkan bukan didesain untuk regresi tabular. Bukan hanya
literatur: skor kredit resmi seperti FICO, dan mayoritas *credit scoring engine*
di institusi keuangan, memakai model statistik/tree-based yang bisa dijelaskan
— bukan model generatif.

### 3.3 Volume data tidak cukup untuk model besar

Deep learning dan LLM unggul saat data mencapai jutaan baris. Dataset produksi
CollectAI saat ini di kisaran ribuan kontrak. Pada skala ini, model besar
justru rawan *overfitting* atau tidak stabil, sementara gradient boosting
terbukti butuh data jauh lebih sedikit untuk hasil yang baik dan reproducible.

### 3.4 Kecepatan & biaya operasional

Scoring berjalan sebagai batch harian atas seluruh portofolio aktif. XGBoost:
milidetik per kontrak, sekali bayar (waktu training), tanpa biaya marginal per
scoring. LLM API: hitungan detik per panggilan **dan** biaya berjalan tiap kali
dipanggil — mengalikan biaya itu dengan ribuan kontrak per hari, tiap hari,
adalah beban operasional berulang yang tidak dimiliki XGBoost.

### 3.5 Determinisme & auditability

Keputusan yang memengaruhi cara seorang nasabah ditagih atau ditawari
restrukturisasi harus bisa dijelaskan ulang bertahun-tahun kemudian dengan hasil
yang **sama persis** — ini bukan preferensi teknis, ini kebutuhan audit dan
kepatuhan (OJK, internal risk). XGBoost: input + versi model yang sama selalu
menghasilkan output yang sama, dan versinya tercatat di `registry.json`. LLM
generatif tidak punya jaminan formal seperti itu, bahkan dengan pengaturan
"deterministik" sekalipun — provider bisa mengganti versi model kapan saja
tanpa Anda memegang kendali penuh.

### 3.6 Data nasabah tidak perlu keluar dari infrastruktur sendiri

XGBoost berjalan lokal — tidak ada data customer yang perlu dikirim ke server
pihak ketiga untuk keputusan sehari-hari sebanyak ribuan kontrak. Pemakaian LLM
eksternal (yang memang sudah dipertimbangkan proyek ini untuk fitur narasi)
mengharuskan keputusan sadar soal data apa yang boleh dikirim keluar — sesuatu
yang sudah didokumentasikan secara eksplisit sebagai trade-off yang diterima
untuk fitur narasi bervolume rendah, **bukan** untuk scoring bervolume tinggi
setiap kontrak setiap hari.

---

## 4. Supaya argumen ini kredibel: kapan LLM/pendekatan lain memang lebih baik

- **Narasi & penjelasan bahasa bebas** untuk petugas CS — persis fitur "AI
  Reasoning" yang sudah direncanakan di atas XGBoost, bukan menggantikannya.
- **Data tidak terstruktur** (rekaman panggilan, transkrip chat) — kalau nanti
  ditambahkan, itu ranah yang wajar untuk NLP/LLM.
- **Volume data melonjak ke jutaan baris** dengan pola yang jauh lebih kompleks
  — pada titik itu, deep learning tabular (bukan LLM) baru masuk akal
  dievaluasi ulang.

Mengakui ini penting: tunjukkan bahwa keputusan memakai XGBoost bukan
penolakan buta terhadap teknologi baru, tapi pemilihan alat berdasarkan bentuk
pekerjaannya.

---

## 5. Persiapan debat: argumen yang mungkin muncul + jawabannya

**"XGBoost itu 2014, sudah kuno."**
Usia algoritma bukan ukuran kelayakan untuk suatu tugas. Riset 2022 (§3.2) yang
menguji langsung terhadap deep learning modern tetap memenangkan model berbasis
pohon untuk data tabular. "Baru" tidak sama dengan "cocok".

**"LLM sekarang bisa mengerjakan apa saja."**
LLM sangat mumpuni untuk bahasa. Untuk regresi probabilitas terkalibrasi dari
kolom numerik pada skala ribuan baris per hari, itu bukan kekuatan intinya —
mirip memakai mobil balap Formula 1 untuk mengangkut barang harian: cepat di
lintasannya sendiri, tapi bukan alat yang tepat untuk pekerjaan ini.

**"Kompetitor sudah pakai AI generatif, kita ketinggalan."**
Perlu ditanya balik: dipakai untuk apa? Kemungkinan besar untuk chatbot atau
ringkasan — bukan untuk menggantikan mesin scoring inti mereka. Skor kredit di
institusi manapun, termasuk yang paling maju, tetap memakai model yang bisa
diaudit.

**"Biar terlihat lebih canggih di depan klien/manajemen."**
Risiko reputasi dari model yang tidak konsisten atau tidak bisa dijelaskan saat
diaudit jauh lebih mahal daripada persepsi "modern". Yang dijual ke klien
adalah hasil (akurasi, kecepatan, kepatuhan) — bukan nama algoritmanya.

**"LLM bisa terus belajar tanpa perlu retrain."**
Untuk keputusan finansial, ini justru risiko, bukan keunggulan. Keputusan harus
*versioned* dan bisa direproduksi persis — kalau modelnya "berubah sendiri",
audit tahun depan tidak bisa menjelaskan kenapa keputusan hari ini berbeda dari
sebelumnya.

**"Biaya API LLM sekarang murah."**
Hitung skalanya, bukan biaya per panggilan: 2.917 kontrak × scoring harian ×
365 hari adalah beban berulang selamanya. XGBoost re-training mingguan
(`weekly_mlops.py`) berjalan dalam hitungan detik-menit di infrastruktur
sendiri, tanpa biaya marginal.

**"Kalau bukan LLM, kenapa bukan deep learning saja — bukan XGBoost yang
'lama'?"**
Sudah dijawab riset yang sama (§3.2): pada volume data seperti CollectAI saat
ini, deep learning tidak mengungguli gradient boosting, dan butuh jauh lebih
banyak data serta biaya komputasi untuk mencapainya.

**"Ada bukti konkret, bukan cuma teori?"**
Ya — §2 di atas: AUC 0,80 tervalidasi *grouped cross-validation*, training 12,3
detik, scoring 2.817 kontrak dalam 8,6 detik, semuanya terukur langsung dari
sistem yang berjalan hari ini.

**"Coba dulu pakai LLM untuk scoring, biar kelihatan hasilnya."**
Bisa disetujui sebagai **uji coba terbatas** (proof-of-concept pada subset
kecil, dibandingkan head-to-head dengan AUC XGBoost saat ini) — bukan sebagai
penggantian langsung sistem produksi. Ini juga jalan aman untuk menunjukkan
itikad baik tanpa mempertaruhkan keandalan yang sudah terbukti.

---

## 6. Rekomendasi

Pertahankan XGBoost sebagai mesin scoring inti (`recovery`, `self_cure`,
`roll_forward`, `ptp_success`). Lanjutkan rencana LLM sebagai lapisan narasi
pelengkap di atas skor XGBoost (fitur "AI Reasoning") — ini bukti tim tidak
menolak teknologi baru, hanya menempatkannya di pekerjaan yang tepat. Buka
opsi evaluasi ulang kalau kondisi berubah signifikan: volume data melonjak ke
jutaan baris, atau muncul kebutuhan mengolah data tidak terstruktur dalam
skala besar.
