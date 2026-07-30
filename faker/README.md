# CollectAI — Generator Data Sintetis

Membuat dataset penagihan sintetis yang **realistis dan bebas kebocoran data**
(*leakage*) untuk 4 tabel input CollectAI, lalu memuatnya ke Postgres yang sama
dipakai `app/backend/` dan `app/machine-learning/`.

Dua script yang perlu Anda ketahui:

| Script | Fungsi |
|---|---|
| `generate-faker-realistic.py` | **Generator utama — pakai ini.** |
| `validate_leakage.py` | Audit otomatis: kebocoran data, realisme distribusi, AUC held-out |
| `generate-dataset.py` | Generator lama, **deprecated**. Ditinggalkan karena label-nya bocor (lihat di bawah) |

---

## Kenapa generator ini rumit

Data sintetis untuk model ML mudah dibuat, tapi mudah pula **dibuat salah dengan
cara yang tidak terlihat**. Generator versi pertama menghasilkan AUC model
**0.9595** — angka yang tidak mungkin untuk model collection (realita industri
~0.70–0.80). Penyebabnya bukan modelnya bagus, tapi datanya bocor:

```python
# generate-dataset.py — inti masalahnya
should_pay = dpd_current <= 30     # label ditentukan LANGSUNG oleh sebuah fitur
```

Label pembayaran ditentukan sebagai fungsi tangga dari `dpd_current`, sementara
`dpd_current` adalah fitur nomor 1 di keempat model. Model tidak belajar apa pun
— ia hanya membaca ulang jawabannya. Plus 4 kolom lain yang praktis salinan
`dpd_current` (`overdue_installment_count = int(dpd/30)`,
`late_fee_amount = dpd*10000`, `cycle` tangga dari `dpd`,
`ambc == 0 ⟺ dpd == 0`), dan `recovery_ratio` yang **persis sama** dengan
variabel probabilitas default yang seharusnya tersembunyi.

`generate-faker-realistic.py` dibangun untuk menghilangkan seluruh kanal itu.
Hasilnya: AUC *grouped cross-validation* **0.80 / 0.70 / 0.68 / 0.73** untuk
keempat model — masuk band industri, dan diperoleh dari sinyal yang sah.

---

## Desain: struktur kausal, bukan pengacakan

Kuncinya adalah membalik satu arah panah. Pada versi lama, `dpd_current`
**mengakibatkan** label. Pada versi ini, keduanya adalah **saudara** — punya
orang tua yang sama, tanpa panah langsung di antara mereka:

```
umur, pekerjaan, penghasilan ──► S_orig ──► CUST_SEGMENT = bucket(S_orig + noise)
                                    │
                                    └──► (W, C)   W = kemauan bayar
                                          │       C = kemampuan bayar
                                          │       korelasi 0.35
                                          ▼
                     simulasi bulanan t = 1..m  (AR(1) distress)
                       s_t = 0.75·s_{t-1} + N(0, 0.50)
                       p_t = sigmoid(... W, C, tunggakan, s_t ...)
                       ──► payment_history, lkp_interaction, backlog
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                            ▼
      contract_snapshot pada T_cut                    UNDIAN LABEL
      (dpd, cycle, ambc, late_fee, ...)      logit = μ + 1.30W + 0.85C
      masing-masing + noise independen              − 0.10·tunggakan
                                                    + 0.45·s_baru + N(0,0.50)
```

Konsekuensinya:

- `dpd_current` **tetap prediktif secara sah** — ia akibat dari riwayat
  pembayaran yang sama yang membentuk kemauan/kemampuan bayar.
- Tapi ia **bukan penentu** label. Ada inovasi `s` baru dan noise
  `N(0, 0.50)` yang membatasi *Bayes ceiling* di ~0.83.
- `W` dan `C` **tidak pernah ditulis** ke kolom mana pun, juga tidak sebagai
  transformasi monoton dari kolom mana pun.

Label memuat **dua faktor laten** (kemauan *dan* kemampuan) secara sengaja.
Dengan satu faktor saja, model jenuh di ~0.71 dan fitur tunggal terbaik hampir
menyamai ansambel — artinya tidak ada yang benar-benar dipelajari.

### Semantik point-in-time

`contract_snapshot` **tidak punya kolom `snapshot_date`**, dan pipeline ML tidak
memfilternya berdasarkan tanggal (hanya `payment_history`/`lkp_interaction` yang
dibatasi `<= feature_cutoff`). Kalau generator menulis snapshot "as-of-hari-ini",
kolom `dpd_current`/`cycle`/`ambc` akan mencerminkan keadaan **setelah** jendela
label ditutup — bocor secara struktural.

Karena itu generator membangun `contract_snapshot` pada posisi
`T_cut = AS_OF − 30 hari`, memakai keadaan pra-cutoff saja.

Satu detail halus: kode produksi memakai pembandingan inklusif di kedua sisi,
jadi tanggal `AS_OF − 30` dimiliki oleh jendela fitur **dan** jendela label.
Generator memperlakukannya sebagai **"hari mati"** — tidak ada satu pun event
yang bertanggal di situ.

---

## Cara pakai

```bash
cd faker
pip install -r requirements.txt          # atau pakai .venv root repo

# Generate + muat ke Postgres (2000 customer, ~2900 kontrak)
python generate-faker-realistic.py --reset
```

Kredensial database dibaca dari `.env` di **root repo** (`PGHOST`, `PGPORT`,
`PGUSER`, `PGPASSWORD`, `PGDATABASE`) — sama dengan yang dipakai backend dan ML.

Di akhir run, script mencetak diagnostik yang perlu Anda perhatikan: histogram
DPD, `P(y=1 | bucket DPD)`, hitungan status kontrak, dan **`reference_date` yang
harus diteruskan ke pipeline training**.

### Opsi CLI

| Flag | Default | Fungsi |
|---|---|---|
| `--seed N` | `20260101` | Seed acak. Seed sama + argumen sama ⇒ dataset identik |
| `--customers N` | `2000` | Jumlah customer |
| `--as-of YYYY-MM-DD` | hari ini | Tanggal generasi (menentukan seluruh aljabar timeline) |
| `--snapshot-as-of {cutoff,now}` | `cutoff` | `cutoff` = point-in-time (benar). `now` = mode demo yang **sengaja bocor**, berguna untuk menunjukkan selisih AUC ~0.75 vs ~0.9x |
| `--label-signal F` | `1.0` | Skala sinyal label. **`0.0` menjadikan label koin acak** — dipakai untuk placebo test |
| `--reset` | off | `TRUNCATE ... CASCADE` tabel input **dan** tabel derivatif ML sebelum memuat |
| `--no-db` | off | Jangan tulis ke Postgres |
| `--no-excel` | off | Jangan tulis file Excel |
| `--dump-latents` | off | Simpan `W`/`C`/`S_orig` ke artifact terpisah (untuk `validate_leakage.py`) |

Bisa juga lewat env var: `FAKER_SEED`, `FAKER_CUSTOMERS`, `FAKER_LABEL_SIGNAL`.

### Re-run bersifat aman dan eksplisit

ID bersifat deterministik (`CUST-00001`, `CTR-00001-1`, …) supaya reproducible.
Konsekuensinya, memuat dua kali akan bertabrakan primary key. Generator versi
lama **menelan error itu diam-diam** dan keluar dengan status 0 — sehingga
database termuat separuh tanpa ada yang tahu.

Sekarang:

- Tanpa `--reset`, loader **menolak** menulis kalau tabel target sudah berisi
  data (`RuntimeError`, bukan warning).
- Dengan `--reset`, tabel input **dan** tabel derivatif ML
  (`ai_intelligence_output`, `customer_behavioral_standing`, `scoring_*`,
  `shadow_scores`, `restructuring_*`) di-`TRUNCATE ... CASCADE` lebih dulu —
  membiarkan tabel derivatif akan meninggalkan referensi ke `contract_no` yang
  sudah tidak ada.
- Error koneksi/insert **dilempar ke atas**, tidak ditelan.

---

## Validasi: `validate_leakage.py`

```bash
cd faker && python validate_leakage.py
```

Yang membuat validator ini berguna: ia meng-**import kode konsumen yang
sesungguhnya** (`compute_contract_features`, `compute_customer_features`,
`build_cbs`, `build_target_variable`, `_build_xgb`, `_cross_validate` dari
`app/machine-learning/`), bukan mengimplementasikan ulang logikanya. Jadi yang
diukur benar-benar apa yang dilihat model.

Pemeriksaan yang dijalankan:

| Pemeriksaan | Kriteria |
|---|---|
| Struktural | Tidak ada event di "hari mati"; tidak ada pembayaran bertanggal masa depan; `PAY_STATUS` konsisten dengan nominalnya; `PROMISE_DATE` tidak pernah string kosong; integritas PK/FK |
| Dependensi deterministik | Untuk setiap pasangan fitur, rasio "B konstan di dalam setiap grup A". Menangkap kelas `late_fee = dpd*10000` yang bisa lolos dari korelasi biasa |
| AUC fitur tunggal | Warn ≥0.72, **fail ≥0.80**. Juga memastikan `dpd_current` bukan fitur teratas |
| AUC model penuh | `StratifiedGroupKFold(5, groups=cust_id)`, **fail di luar [0.68, 0.82]** |
| Recoverability laten | Fail kalau `|Spearman(fitur, W atau C)| > 0.75` — tes langsung untuk "laten ditulis apa adanya". Butuh `--dump-latents` |
| **Placebo test** | Regenerasi dengan `--label-signal 0.0` (label jadi koin acak), lalu pastikan AUC CV kolaps ke ~0.50 |

**Grouped CV bukan pilihan kosmetik.** Kontrak dari satu customer berbagi
parameter laten yang sama, jadi split biasa akan membocorkan informasi antar-fold
dan menaikkan estimasi secara palsu.

**Placebo test adalah pemeriksaan paling bernilai** di sini — dan hanya mungkin
karena kita memiliki generatornya. Kalau label dibuat independen dari semua orang
tuanya tapi model masih bisa memprediksinya, ada fitur yang membaca **undian
label**, bukan penyebabnya. Ini menangkap kelas kebocoran yang tidak bisa
dideteksi oleh threshold AUC atau pemeriksaan korelasi, karena ia menghilangkan
kebingungan antara "prediktif secara sah" dan "bocor".

Placebo test terbukti bekerja: ia menemukan bug nyata yang lolos dari semua
pemeriksaan lain — kontrak berstatus `write-off` dulu **selalu** dianggap tidak
membayar, tanpa memandang `--label-signal`. Karena status write-off itu sendiri
fungsi dari jalur tunggakan yang dipakai sebagai fitur, terbentuk kanal korelasi
tersembunyi yang kebal terhadap knob sinyal.

---

## Delapan kanal kebocoran yang ditutup

Didaftar supaya tidak diperkenalkan kembali secara tidak sengaja:

| # | Masalah lama | Perbaikan |
|---|---|---|
| 1 | `should_pay = dpd_current <= 30` — label fungsi tangga dari fitur | Label jadi undian terpisah yang berbagi orang tua laten, tanpa panah langsung |
| 2 | 4 salinan kolinear `dpd`: `overdue = int(dpd/30)`, `late_fee = dpd*10000`, `cycle` tangga `dpd`, `ambc==0 ⟺ dpd==0` | Masing-masing diturunkan dari simulasi + noise independen; AMBC ≠ 0 saat lancar; late fee diakru per angsuran lalu sebagian di-waive |
| 3 | `recovery_ratio` **persis sama** dengan probabilitas default tersembunyi | `LOAN_AMOUNT` = kewajiban kontraktual bruto (`tenor × cicilan`), sehingga rasio berarti "porsi angsuran terselesaikan"; `maturity_date` kontraktual tetap ⇒ `days_to_maturity` independen dari laten |
| 4 | `historic_pay_prob` diundi dari dua rentang **tak bertumpang** (`U(0.10,0.40)` vs `U(0.75,0.97)`) sehingga `payment_rate` hampir memisahkan laten | Keterlambatan lognormal yang bertumpang tebal antar kelas |
| 5 | `ptp_stat = 'KEPT' if not will_default else 'BROKEN'` — pembacaan laten langsung | `PTP_STATUS` diturunkan dari jalur pembayaran, dengan aturan `promise_date > T_cut ⇒ OPEN` |
| 6 | `self_cure = delay <= 7` — fungsi deterministik dari `avg_delay_days` | Diturunkan dari kedekatan interaksi LKP + 10% noise pencatatan |
| 7 | Interaksi hanya dibuat berdasarkan DPD, sehingga kontrak lancar **kehilangan seluruh** interaksi pra-cutoff — guard cutoff berubah menjadi kanal `dpd` | Event stream sepanjang 6–30 bulan riwayat; kontrak lancar pun punya 2–5 interaksi pra-cutoff. Ini juga yang menaikkan populasi training `ptp_success` dari **n=107 ke n=2497** |
| 8 | `CUST_SEGMENT` diskretisasi langsung dari `default_prob` | `bucket(S_orig + noise)` — aman kalau nanti dipromosikan jadi fitur |

Selain itu diperbaiki: pembayaran bertanggal masa depan, `'Overpaid'` yang tidak
terlihat oleh konsumen mana pun, `INTR_OTS` yang bertentangan dengan
`INTEREST_RATE`, DPD yang hanya punya ~35 nilai berbeda (sekarang 253),
`result_code` yang tidak pernah memancarkan level tertentu, dan
`PROMISE_DATE = ''`.

---

## Dua korelasi yang sengaja dibiarkan

Demi kejujuran: `rejection_count`↔`treatment_count` dan
`contact_success_rate`↔`rpc_rate` masih berkorelasi ~0.94–0.95.

Ini **bukan** kebocoran, dan mengejarnya lebih jauh ternyata sia-sia: keempat
fitur itu agregat atas **stream interaksi yang sama**, dan setiap kali satu
pasang ditekan turun, pasangan lain naik menggantikannya sebagai "yang terburuk".
Tidak ada satu pun dari keempatnya yang melewati AUC tunggal 0.73. Jadi
korelasinya didokumentasikan sebagai `KNOWN_STRUCTURAL_PAIRS` di validator, bukan
diperbaiki dengan tuning sampai angkanya "enak dilihat".

---

## Struktur berkas

```text
faker/
├── generate-faker-realistic.py   # generator utama
├── validate_leakage.py           # audit leakage + realisme
├── generate-dataset.py           # generator lama (deprecated — label bocor)
├── helpers/
│   └── database.py               # loader Postgres: reset_tables(), append_dataframes_to_postgres()
├── requirements.txt
└── Dataset_CollectAI_Realistic.xlsx   # output Excel run terakhir (artifact)
```

> `package.json` di folder ini adalah sisa yang tidak terpakai — folder ini
> sepenuhnya Python.

## Tabel yang dihasilkan

| Tabel | Isi |
|---|---|
| `customer_master` | Profil: umur, pekerjaan, penghasilan, wilayah (15 kota tetap), segmen |
| `contract_snapshot` | Keadaan kontrak **pada feature cutoff**: DPD, OTS, cycle, AMBC, late fee, `status` |
| `payment_history` | Baris per pembayaran yang **benar-benar terjadi** — angsuran yang tidak dibayar tidak punya baris |
| `lkp_interaction` | Event stream interaksi penagihan: channel, hasil, PTP |

Ukuran default: 2000 customer, ~2900 kontrak, ~28.000 baris pembayaran,
~61.000 baris interaksi.

---

## Catatan untuk pengembangan lanjutan

- **Jangan lemahkan guard `feature_cutoff`** di
  `app/machine-learning/src/feature_engineering.py`. Kalau suatu fitur kelaparan
  data, tambah massa data pra-cutoff di generator — jangan longgarkan guard-nya.
- **`EMIT_OVERPAID = False`** disengaja: `'Overpaid'` tidak dihitung sebagai
  positif oleh `outcome_labeler.py` maupun oleh `payment_rate` di
  `feature_engineering.py`. Menyalakannya tanpa menambal kedua konsumen itu akan
  melabeli pembayar baik sebagai `y=0`.
- **Setelah mengubah generator, jalankan `validate_leakage.py`** — termasuk
  placebo test. Perubahan yang tampak tidak berbahaya bisa membuka kanal
  korelasi baru.
- `MIN_INSTALLMENT_REDUCTION_PCT` dan aturan bisnis lain **bukan** urusan
  generator; itu ada di `app/machine-learning/config/settings.py`.
