import pandas as pd
# pyrefly: ignore [missing-import]
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
# pyrefly: ignore [missing-import]
import joblib
from core.config import settings
from core.database import get_engine

def train_model():
    """
    Fungsi utama untuk melatih ulang (retrain) model XGBoost berdasarkan data historis dari database.
    """
    engine = get_engine()
    
    # 1. Membaca data historis dari tabel PostgreSQL (bersumber dari Data Dictionary CollectAI)
    # customer_master: Profil dasar nasabah (usia, area, income, dll).
    df_cust = pd.read_sql("SELECT * FROM customer_master", con=engine)
    # contract_snapshot: Informasi beban utang berjalan (DPD, sisa pokok/PRNC_OTS, siklus penagihan).
    df_contr = pd.read_sql("SELECT * FROM contract_snapshot", con=engine)
    # payment_history: Histori riwayat transaksi bayar, digunakan untuk mengekstrak keterlambatan aktual.
    df_pay = pd.read_sql("SELECT * FROM payment_history", con=engine)
    # lkp_interaction: Data Lembar Kerja Penugasan (LKP), mencatat seberapa kooperatif nasabah saat ditagih.
    df_lkp = pd.read_sql("SELECT * FROM lkp_interaction", con=engine)
    # ai_intelligence: Berisi output probabilitas bayar (RECOVERY_SCORE) yang akan dijadikan target/label (Y).
    df_ai = pd.read_sql("SELECT * FROM ai_intelligence", con=engine)

    # 2. Melakukan Feature Engineering
    # Agregasi Payment History: Menghitung rata-rata keterlambatan (DELAY_DAYS) untuk tiap kontrak
    pay_agg = df_pay.groupby('CONTRACT_NO')['DELAY_DAYS'].mean().reset_index()
    pay_agg.rename(columns={'DELAY_DAYS': 'AVG_DELAY_DAYS'}, inplace=True)

    # Agregasi LKP: Menghitung rata-rata kooperatif nasabah (INTERACTION_SCORE) untuk tiap kontrak (1=Kasar, 5=Sangat Kooperatif)
    lkp_agg = df_lkp.groupby('CONTRACT_NO')['INTERACTION_SCORE'].mean().reset_index()
    lkp_agg.rename(columns={'INTERACTION_SCORE': 'AVG_INTERACTION_SCORE'}, inplace=True)

    # 3. Menggabungkan Semua Data (Data Merging)
    # Kita jadikan contract_snapshot sebagai tabel sentral (poros utama)
    df_merged = df_contr.merge(pay_agg, on='CONTRACT_NO', how='left')
    df_merged = df_merged.merge(lkp_agg, on='CONTRACT_NO', how='left')
    # Hubungkan profil nasabah menggunakan CUST_ID
    df_merged = df_merged.merge(df_cust, on='CUST_ID', how='left')
    # Hubungkan dengan kunci jawaban/target (RECOVERY_SCORE) dari tabel AI Intelligence
    df_merged = df_merged.merge(df_ai[['CONTRACT_NO', 'RECOVERY_SCORE']], on='CONTRACT_NO', how='inner')

    # 4. Penanganan Nilai Kosong (Handling Missing Values)
    # Jika tidak ada riwayat bayar, set rata-rata telat ke 0
    df_merged['AVG_DELAY_DAYS'] = df_merged['AVG_DELAY_DAYS'].fillna(0)
    # Jika tidak ada riwayat penagihan, set skor interaksi ke 0
    df_merged['AVG_INTERACTION_SCORE'] = df_merged['AVG_INTERACTION_SCORE'].fillna(0)

    # 5. Konversi Kategori & Persiapan Fitur
    # Model XGBoost membutuhkan data dalam bentuk angka. Cycle penagihan (C0, C1, C2, C3+) diubah ke angka (0-3).
    cycle_mapping = {'C0': 0, 'C1': 1, 'C2': 2, 'C3+': 3}
    df_merged['CYCLE_NUM'] = df_merged['CYCLE_AKHIR'].map(cycle_mapping)

    # Menentukan variabel independen (X) yang mempengaruhi probabilitas
    # - DPD_CURRENT: Hari keterlambatan saat ini
    # - PRNC_OTS: Sisa pokok hutang
    # - CUST_AGE: Usia nasabah
    # - AVG_DELAY_DAYS: Rata-rata telat bayar historis
    # - AVG_INTERACTION_SCORE: Tingkat kooperatif rata-rata
    # - CYCLE_NUM: Tingkat siklus keterlambatan (C0-C3+)
    features = [
        'DPD_CURRENT', 
        'PRNC_OTS', 
        'CUST_AGE', 
        'AVG_DELAY_DAYS', 
        'AVG_INTERACTION_SCORE', 
        'CYCLE_NUM'
    ]

    # Ekstraksi fitur (X) dan target (Y)
    X = df_merged[features]
    y = df_merged['RECOVERY_SCORE'] # Target: rentang nilai desimal 0.00 hingga 1.00

    # 6. Pemisahan Data Latih dan Data Uji (Train-Test Split)
    # 80% data untuk melatih model, 20% data digunakan untuk menguji seberapa akurat model memprediksi soal baru
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 7. Konfigurasi dan Training Model XGBoost
    # Memakai XGBRegressor karena kita memprediksi angka kontinu (probabilitas desimal), bukan klasifikasi kategori.
    model = xgb.XGBRegressor(
        objective='reg:squarederror', # Fungsi perhitungan loss yang akan ditekan sekecil mungkin
        n_estimators=100,             # Jumlah pohon keputusan bertingkat yang dibangun
        learning_rate=0.1,            # Kecepatan penyesuaian bobot pada tiap iterasi
        max_depth=5,                  # Kedalaman logika pohon (dibatasi 5 agar tidak overfitting/menghafal buta)
        random_state=42               # Seed angka acak agar hasil eksperimen konsisten jika diulang
    )

    # Melakukan proses training
    model.fit(X_train, y_train)

    # 8. Evaluasi Kepintaran Model
    # Menyuruh model menjawab soal evaluasi (X_test), lalu dicocokkan dengan kunci asli (y_test)
    y_pred = model.predict(X_test)
    
    # MSE: rata-rata dari kuadrat selisih prediksi dengan kenyataan (Makin kecil makin bagus)
    mse = mean_squared_error(y_test, y_pred)
    # R2: proporsi pergerakan data probabilitas yang mampu dijelaskan oleh logika model (Makin dekat ke 1.0 makin bagus)
    r2 = r2_score(y_test, y_pred)

    # 9. Menyimpan Model ke File
    # Simpan 'otak' kalkulator ML yang sudah dilatih ke format .pkl agar endpoint prediksi (predict_service.py) bisa langsung memakainya
    joblib.dump(model, settings.MODEL_PATH)

    return {
        "status": "success",
        "message": f"Model berhasil ditrain dan disimpan di {settings.MODEL_PATH}",
        "mse": float(mse),
        "r2_score": float(r2)
    }
