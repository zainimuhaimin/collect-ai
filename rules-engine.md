# Rules Engine Mapping - Arsitektur Hybrid AI (CollectAI)

Dokumen ini memuat aturan logika (*business rules*) yang menjadi landasan pembelajaran (*training*) untuk arsitektur Hybrid AI dalam menganalisis probabilitas pembayaran nasabah dan menentukan tindakan penagihan terbaik.

Arsitektur ini dibagi menjadi dua layer:
1. **Layer 1 (XGBoost):** Predictive Engine (Kalkulator Angka Probabilitas)
2. **Layer 2 (Local LLM):** Decision & Reasoning Engine (Pengambil Keputusan & Generator Narasi)

---

## 1. LAYER 1: XGBOOST (PREDICTIVE ENGINE)

Model XGBoost murni bekerja dengan angka. Tugas utamanya adalah membaca rekam jejak nasabah dan mengeluarkan persentase probabilitas keberhasilan penagihan.

**Target Output:** `RECOVERY_SCORE` (Rentang nilai: `0.00` hingga `1.00`)

### Aturan Logika (Feature Weights & Expected Patterns):
Model diharapkan belajar dan menangkap pola korelasi berikut selama proses *training*:

* **Rule 1.1 - Korelasi Keterlambatan Historis:**
    Jika `AVG_DELAY_DAYS` (rata-rata telat bayar 3-4 bulan terakhir) menunjukkan tren yang semakin kecil atau konsisten rendah (misal: 0-3 hari), maka model harus mendorong `RECOVERY_SCORE` mendekati **1.00**.
* **Rule 1.2 - Korelasi Skor Interaksi:**
    Jika `AVG_INTERACTION_SCORE` dari tabel LKP tinggi (Rata-rata 4 atau 5), mengindikasikan nasabah sangat kooperatif, maka `RECOVERY_SCORE` tidak boleh turun drastis meskipun DPD saat ini mulai naik.
* **Rule 1.3 - Penalti DPD (Days Past Due):**
    Semakin tinggi nilai `DPD_CURRENT` dan `CYCLE_NUM` (terutama jika masuk C2 atau C3+), probabilitas harus terkena penalti eksponensial. `RECOVERY_SCORE` akan otomatis ditekan di bawah **0.50** kecuali ada faktor penolong yang sangat kuat dari skor interaksi.
* **Rule 1.4 - Beban Sisa Pokok:**
    Nilai `PRNC_OTS` (Sisa Utang Pokok) berbanding terbalik dengan probabilitas pelunasan. Utang yang terlampau besar dipadukan dengan DPD tinggi akan menghasilkan probabilitas (`RECOVERY_SCORE`) paling rendah (< **0.20**).

---

## 2. LAYER 2: LOCAL LLM (DECISION & REASONING ENGINE)

Local LLM bertugas "membaca" skor dari XGBoost (Layer 1) dan menggabungkannya dengan profil nasabah untuk merumuskan klasifikasi, rekomendasi tindakan, dan narasi.

### A. Aturan Segmentasi Risiko (`RISK_SEGMENT` & `BEHAVIORAL_GRADE`)

LLM harus mengklasifikasikan nasabah ke dalam 4 segmen berikut berdasarkan parameter yang diberikan:

* **Self-cure (Grade A):**
    * *Syarat:* `RECOVERY_SCORE` > **0.80** DAN `DPD_CURRENT` < **15 hari** (Cycle C0/C1).
    * *Logika:* Nasabah ini hanya lupa bayar. Tidak butuh *effort* penagihan fisik (otomatisasi saja).
* **Can Pay (Grade B):**
    * *Syarat:* `RECOVERY_SCORE` **0.50 - 0.79**.
    * *Logika:* Nasabah punya uang dan niat, tapi mungkin sedang terganggu arus kasnya. Masih bisa di- *recovery* dengan sedikit dorongan/pengingat keras.
* **Cannot Pay (Grade C):**
    * *Syarat:* `RECOVERY_SCORE` **0.20 - 0.49** DAN Interaksi terakhir kooperatif (Skor 3 atau 4 / "PTP").
    * *Logika:* Nasabah punya niat baik tapi benar-benar kesulitan dana (misal: *income* lebih rendah dari sisa pokok utang). Butuh solusi restrukturisasi atau penagihan persuasif.
* **Won't Pay (Grade D):**
    * *Syarat:* `RECOVERY_SCORE` < **0.20** DAN/ATAU Interaksi terakhir "Menolak" / "Rumah Kosong".
    * *Logika:* Nasabah tidak kooperatif dan menunjukkan indikasi wanprestasi/kabur. Status masuk ke *Problem Account List*.

### B. Aturan Rekomendasi Tindakan (`NBA_RECOMMENDATION`)

LLM harus mengekstrak pola interaksi historis mana yang paling sering berujung pada pelunasan untuk menentukan `COLLECTION_SENSITIVITY`.

* **WA / SMS (Low Effort):**
    * *Syarat:* Nasabah berada di segmen **Self-cure** atau memiliki riwayat sering membayar H+1 setelah dikirimkan pesan singkat.
* **Call / Deskcoll (Mid Effort):**
    * *Syarat:* Nasabah berada di segmen **Can Pay** dan belum memberikan respons via WA, namun secara historis pernah memberikan janji bayar via telepon.
* **Visit (High Effort):**
    * *Syarat:* Nasabah mengabaikan WA/Call lebih dari 2 kali, ATAU `RECOVERY_SCORE` mulai turun di bawah 0.50, ATAU interaksi sebelumnya "Rumah Kosong". Kunjungan fisik diperlukan untuk konfirmasi keberadaan nasabah/aset.
* **Somasi / Pickup Unit (Critical Effort):**
    * *Syarat:* Nasabah masuk kategori **Won't Pay**, DPD > 60 Hari (Cycle C2/C3+), dan interaksi historis dominan "Menolak".

### C. Aturan Skala Prioritas (`PRIORITY_LEVEL`)

Pemandu bagi *collector* di lapangan untuk menentukan mana yang harus dikerjakan terlebih dahulu pada hari tersebut.

* **Critical:** Utang (`PRNC_OTS`) **SANGAT BESAR** + Segmen **Can Pay** + Rekomendasi **Visit/Somasi**. (Prioritas tertinggi karena *impact* finansial ke perusahaan besar jika lolos).
* **High:** Utang menengah/besar + Segmen **Cannot Pay / Won't Pay** + Butuh **Visit**.
* **Medium:** DPD masih kecil (C1) tapi nominal utang lumayan besar + Butuh pengingat **Call**.
* **Low:** Segmen **Self-cure** dengan utang sisa sedikit. Cukup otomatisasi **WA/SMS** oleh sistem bot.

---

## 3. ALUR EKSEKUSI (*WORKFLOW*)

1. **Daily Batch:** Setiap pagi, sistem menarik data nasabah dari *Database* (Tab 1-4).
2. **Predictive Run:** Sistem mengirim data tersebut ke file `predict_api.py` (XGBoost). Model akan menghitung dan memuntahkan `RECOVERY_SCORE` dalam hitungan milidetik.