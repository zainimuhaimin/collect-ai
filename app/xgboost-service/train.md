# Dokumentasi Model Prediktif (XGBoost) - Arsitektur Hybrid AI

Dokumen ini menjelaskan rancangan, metodologi, dan *script* untuk **Layer 1: Predictive Engine** menggunakan algoritma XGBoost. Model ini bertugas sebagai "kalkulator presisi" untuk menebak skor probabilitas bayar nasabah (`RECOVERY_SCORE`), yang nantinya akan disuplai ke **Layer 2 (Local LLM)** untuk penentuan narasi dan *Next Best Action* (NBA).

---

## 1. Metodologi yang Digunakan

Metode yang kita gunakan masuk ke dalam ranah **Supervised Learning** (Pembelajaran Terarah), dengan pendekatan spesifik bernama **Regression** menggunakan teknik **Gradient Boosting**.

* **Supervised Learning:** Kita "mengajari" model dengan memberikan kunci jawaban (`RECOVERY_SCORE`) dari data masa lalu, lalu menyuruh model menebak pola berdasarkan soal yang diberikan (DPD, sisa utang, histori telat bayar, dll).
* **Regression (Regresi):** Karena target yang mau kita tebak adalah **angka desimal/probabilitas** (0.00 sampai 1.00), kita tidak menebak kategori 'Ya/Tidak', melainkan menebak nilai berkelanjutan.
* **Gradient Boosting:** Model menggunakan ratusan "Pohon Keputusan" (*Decision Trees*) kecil secara berurutan. Pohon kedua dibuat khusus untuk **memperbaiki error** dari pohon pertama, pohon ketiga memperbaiki error pohon kedua, dan seterusnya hingga mencapai tingkat presisi maksimal.

---

## 2. Mengapa Memilih XGBoost?

Dalam arsitektur *Hybrid / Agentic AI*, LLM difokuskan pada bahasa dan penalaran logis, sementara XGBoost dikhususkan untuk komputasi matematis. Berikut alasan pemilihan XGBoost:

1. **Raja-nya Data Tabular:** Untuk data berkolom seperti Excel/SQL (berisi angka, uang, hari, kategori), XGBoost memiliki akurasi yang jauh lebih tinggi dibanding *Deep Learning* atau LLM.
2. **Menangkap Pola "Non-Linear":** XGBoost sangat mahir menangkap batasan rumit di dunia nyata (misal: peluang bayar DPD 10 hari = 80%, tapi DPD 120 hari drop drastis menjadi 5%).
3. **Kebal Terhadap Data Bolong & Outlier:** XGBoost otomatis mengerti cara membelokkan logika jika menemukan data nasabah yang kosong (Missing Values) tanpa membuat program menjadi *error*.
4. **Sangat Ringan & Cepat (Low Latency):** Model yang sudah di-*train* (*artifact*) ukurannya hanya beberapa ratus Kilobyte (KB). Saat di-*deploy* di *server*, ia dapat memprediksi skor dalam hitungan milidetik walau hanya menggunakan CPU standar.
5. **Feature Importance (Transparansi):** XGBoost bisa memberikan laporan metrik tentang variabel apa yang paling mempengaruhi kegagalan bayar nasabah (misal: Rata-rata telat bayar berdampak 40%, DPD berdampak 35%).

---

## 3. Script Training XGBoost (`train_xgboost.py`)

*Script* ini berfungsi untuk membaca file `.xlsx`, melakukan *feature engineering*, melatih model, dan mengekspor "otak" model ke dalam file `.pkl`.

```python
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import joblib

print("1. Membaca Dataset dari Excel...")
file_path = "Dataset_CollectAI_Dummy.xlsx"

# Load masing-masing sheet
df_cust = pd.read_excel(file_path, sheet_name="1_Customer_Master")
df_contr = pd.read_excel(file_path, sheet_name="2_Contract_Snapshot")
df_pay = pd.read_excel(file_path, sheet_name="3_Payment_History")
df_lkp = pd.read_excel(file_path, sheet_name="4_LKP_Interaction")
df_ai = pd.read_excel(file_path, sheet_name="5_AI_Intelligence")

print("2. Melakukan Feature Engineering (Sesuai Rules)...")

# Rule 1: Agregasi Tabel Payment History (Cari rata-rata telat bayar)
pay_agg = df_pay.groupby('CONTRACT_NO')['DELAY_DAYS'].mean().reset_index()
pay_agg.rename(columns={'DELAY_DAYS': 'AVG_DELAY_DAYS'}, inplace=True)

# Rule 2: Agregasi Tabel LKP (Cari rata-rata skor interaksi)
lkp_agg = df_lkp.groupby('CONTRACT_NO')['INTERACTION_SCORE'].mean().reset_index()
lkp_agg.rename(columns={'INTERACTION_SCORE': 'AVG_INTERACTION_SCORE'}, inplace=True)

# Gabungkan (Merge) semua data menjadi 1 DataFrame utama
df_merged = df_contr.merge(pay_agg, on='CONTRACT_NO', how='left')
df_merged = df_merged.merge(lkp_agg, on='CONTRACT_NO', how='left')
df_merged = df_merged.merge(df_cust, on='CUST_ID', how='left')
df_merged = df_merged.merge(df_ai[['CONTRACT_NO', 'RECOVERY_SCORE']], on='CONTRACT_NO', how='inner')

# Handling Missing Values
df_merged['AVG_DELAY_DAYS'] = df_merged['AVG_DELAY_DAYS'].fillna(0)
df_merged['AVG_INTERACTION_SCORE'] = df_merged['AVG_INTERACTION_SCORE'].fillna(0)

print("3. Persiapan Fitur & Konversi Data Kategori...")

# Konversi Kategori Cycle ke Numerik
cycle_mapping = {'C0': 0, 'C1': 1, 'C2': 2, 'C3+': 3}
df_merged['CYCLE_NUM'] = df_merged['CYCLE_AKHIR'].map(cycle_mapping)

# Tentukan Features (X) dan Target (y)
features = ['DPD_CURRENT', 'PRNC_OTS', 'CUST_AGE', 'AVG_DELAY_DAYS', 'AVG_INTERACTION_SCORE', 'CYCLE_NUM']
X = df_merged[features]
y = df_merged['RECOVERY_SCORE'] 

# Train-Test Split (80% Train, 20% Test)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print("4. Memulai Training XGBoost...")
model = xgb.XGBRegressor(
    objective='reg:squarederror', 
    n_estimators=100,      
    learning_rate=0.1,     
    max_depth=5,           
    random_state=42
)
model.fit(X_train, y_train)

print("5. Mengevaluasi Model...")
y_pred = model.predict(X_test)
mse = mean_squared_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print(f"-> Mean Squared Error (MSE) : {mse:.4f}")
print(f"-> R2 Score (Akurasi)       : {r2:.4f}")

print("6. Menyimpan Model (Artifact)...")
model_filename = "xgb_recovery_model.pkl"
joblib.dump(model, model_filename)

print(f"Model berhasil diekspor ke: '{model_filename}'")