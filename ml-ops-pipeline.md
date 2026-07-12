# CollectAI — MLOps Pipeline
## Model Retraining, Monitoring & Champion-Challenger

> Dokumen ini menjelaskan bagaimana model RECOVERY_SCORE diperbarui secara
> berkelanjutan seiring bertambahnya data — tanpa harus menghentikan sistem.

---

## DAFTAR ISI

1. [Masalah: Static Model Blindness](#1-masalah-static-model-blindness)
2. [The Feedback Loop — Kunci Utama](#2-the-feedback-loop--kunci-utama)
3. [Tiga Strategi Retraining](#3-tiga-strategi-retraining)
4. [Outcome Labeler — Membuat Data Label Baru](#4-outcome-labeler--membuat-data-label-baru)
5. [Model Monitor — Deteksi Kapan Harus Retrain](#5-model-monitor--deteksi-kapan-harus-retrain)
6. [Retraining Pipeline — Tiga Strategi](#6-retraining-pipeline--tiga-strategi)
7. [Champion-Challenger — Deploy Aman](#7-champion-challenger--deploy-aman)
8. [Model Registry — Versioning & Rollback](#8-model-registry--versioning--rollback)
9. [Weekly MLOps Orchestrator](#9-weekly-mlops-orchestrator)
10. [Jadwal Lengkap](#10-jadwal-lengkap)

---

## 1. Masalah: Static Model Blindness

Model yang hanya dilatih sekali akan mengalami degradasi performa seiring waktu.
Ada dua penyebab utama:

```
PENYEBAB 1 — CONCEPT DRIFT
  Hubungan antara fitur dan target berubah.

  Contoh nyata:
  Di masa normal    → avg_delay_days = 15 berarti "berisiko sedang"
  Di masa resesi    → avg_delay_days = 15 berarti "relatif aman" (semua orang terlambat)

  Model yang dilatih di masa normal akan SALAH menilai nasabah di masa resesi.


PENYEBAB 2 — DATA DRIFT
  Distribusi input features berubah meski pola hubungannya belum berubah.

  Contoh nyata:
  Tahun lalu → 70% nasabah di cycle C0-C1
  Tahun ini  → 40% nasabah di cycle C0-C1 (portofolio makin tua/berisiko)

  Model tidak salah secara konseptual, tapi tidak pernah "melihat" distribusi baru ini.
```

Tanpa retraining, dalam 3–6 bulan AUC model biasanya turun 0.05–0.15 di domain collection.

---

## 2. The Feedback Loop — Kunci Utama

Inilah insight paling penting: **output sistem kita hari ini secara otomatis menjadi
training data untuk model versi berikutnya**, karena 30 hari kemudian kita tahu
apakah prediksi kita benar atau tidak.

```
─────────────────────────────────────────────────────────────────────────────

  HARI INI (T)                           30 HARI KEMUDIAN (T+30)
  ─────────────────────────────          ──────────────────────────────────────

  Features kontrak C-001:                Cek Payment History untuk C-001:
    dpd_current       = 25                 Ada pembayaran di T+12?  → YES
    avg_delay_days    = 18                 PAY_STATUS = 'Full'?     → YES
    ptp_fulfillment   = 0.60
    ...                                  Label C-001 = 1 (bayar)

  Model prediksi:
    RECOVERY_SCORE = 0.71               ┌──────────────────────────────┐
                                         │  LABELED TRAINING RECORD     │
                                         │  features: {...}             │
                                         │  recovery_score_pred: 0.71  │
                                         │  actual_paid: 1             │  ← BENAR
                                         │  scoring_date: 2025-01-01   │
                                         └──────────────────────────────┘


  Features kontrak C-002:                Cek Payment History untuk C-002:
    dpd_current       = 45                 Ada pembayaran di T+30?  → NO
    avg_delay_days    = 30
    ptp_fulfillment   = 0.20            Label C-002 = 0 (tidak bayar)

  Model prediksi:
    RECOVERY_SCORE = 0.65               ┌──────────────────────────────┐
                                         │  LABELED TRAINING RECORD     │
                                         │  features: {...}             │
                                         │  recovery_score_pred: 0.65  │
                                         │  actual_paid: 0             │  ← SALAH
                                         │  scoring_date: 2025-01-01   │
                                         └──────────────────────────────┘

─────────────────────────────────────────────────────────────────────────────

  Setelah 3 bulan:                       Setelah 6 bulan:
  ~90 hari × kontrak aktif               ~180 hari × kontrak aktif
  = ribuan labeled records baru          = puluhan ribu labeled records baru

  Dataset training awal: 10.000 rows     Dataset sekarang: 50.000+ rows
  Model bisa di-retrain dengan           Lebih kaya, lebih beragam, lebih akurat
  dataset yang jauh lebih kaya.

─────────────────────────────────────────────────────────────────────────────
```

### Dua Sumber Labeled Data

| Sumber | Cara Mendapat Label |
|---|---|
| **Payment History** | Cek apakah ada transaksi dalam 30 hari setelah scoring |
| **CBS Update** | BEHAVIORAL_GRADE yang diperbarui = sinyal perilaku jangka panjang |

### Label Delay Problem

Ada satu hal yang perlu dipahami: **kita tidak bisa langsung melatih model dengan data hari ini**.
Selalu ada jeda 30 hari antara scoring dan tersedianya label aktual.

```
Timeline ketersediaan data:

Jan 01 → Scoring kontrak → RECOVERY_SCORE dihasilkan
Jan 31 → Baru tahu apakah prediksi Jan 01 benar atau salah
Feb 01 → Data Jan 01 baru bisa dimasukkan sebagai training data

Implikasi:
  Data training paling baru yang bisa kita pakai = 30 hari ke belakang.
  Jangan retrain dengan data yang belum ada labelnya.
```

---

## 3. Tiga Strategi Retraining

```
STRATEGY 1: FULL RETRAIN (Paling Sederhana)
  Setiap bulan, latih ulang dari nol dengan SEMUA data historis.

  Kelebihan : Mudah diimplementasi, tidak ada kompleksitas tambahan
  Kekurangan: Tidak responsif terhadap perubahan mendadak
  Cocok untuk: Tim kecil, awal implementasi

  ──────────────────────────────────────────
  Jan 2025: Train → deploy Model v1
  Feb 2025: Train ulang semua data → Model v2
  Mar 2025: Train ulang semua data → Model v3
  ──────────────────────────────────────────


STRATEGY 2: ROLLING WINDOW (Lebih Responsif)
  Hanya gunakan data N bulan terakhir untuk training.

  Kelebihan : Model fokus pada pola terkini, tidak "terkontaminasi" data lama
  Kekurangan: Kehilangan data historis yang mungkin masih relevan
  Cocok untuk: Market yang berubah cepat (contoh: pasca-krisis)

  ──────────────────────────────────────────
  Mar 2025: Train dengan data Sep–Feb (6 bulan)
  Apr 2025: Train dengan data Okt–Mar (6 bulan)
  (data Sep hilang, Maret masuk)
  ──────────────────────────────────────────


STRATEGY 3: RECENCY-WEIGHTED (Rekomendasi) ←── Yang kita pakai
  Gunakan SEMUA data historis, tapi data lebih baru diberi BOBOT lebih tinggi.
  Menggunakan parameter sample_weight di XGBoost.

  Kelebihan : Gunakan semua data (tidak buang informasi), tapi tetap
              lebih sensitif terhadap pola terkini.
              Tidak perlu pilih antara "lama vs baru" — pakai semua.
  Kekurangan: Sedikit lebih kompleks dari Strategy 1

  ──────────────────────────────────────────
  Data Jan 2024  : bobot 0.7^14 ≈ 0.01  (sangat kecil)
  Data Jul 2024  : bobot 0.7^8  ≈ 0.06
  Data Jan 2025  : bobot 0.7^2  ≈ 0.49
  Data Feb 2025  : bobot 0.7^1  ≈ 0.70
  Data Mar 2025  : bobot 1.00         ← paling relevan
  ──────────────────────────────────────────
```

---

## 4. Outcome Labeler — Membuat Data Label Baru

```python
# outcome_labeler.py
# Dijalankan setiap minggu untuk melabeli scoring records yang sudah tua

import pandas as pd
import numpy as np
from datetime import datetime


def label_historical_scores(df_ai_output, df_payment,
                             label_window=30, engine=None):
    """
    Untuk setiap RECOVERY_SCORE yang dihasilkan lebih dari LABEL_WINDOW hari lalu,
    cek apakah nasabah benar-benar membayar dalam window tersebut.

    Ini adalah fungsi PALING PENTING dalam MLOps pipeline — menciptakan
    feedback loop antara prediksi dan kenyataan.

    Parameters
    ----------
    df_ai_output  : DataFrame tabel ai_intelligence_output
    df_payment    : DataFrame tabel payment_history
    label_window  : int, hari untuk cek pembayaran (default: 30)
    engine        : SQLAlchemy engine untuk append ke tabel labeled

    Returns
    -------
    DataFrame dengan kolom tambahan 'actual_paid' (0 atau 1)
    """
    today = pd.Timestamp.today().normalize()

    df_ai_output = df_ai_output.copy()
    df_ai_output['SCORING_DATE'] = pd.to_datetime(df_ai_output['SCORING_DATE'])

    # Hanya label records yang scoring-nya sudah >= label_window hari lalu
    # (kita perlu waktu label_window hari untuk tahu hasilnya)
    cutoff = today - pd.Timedelta(days=label_window)
    to_label = df_ai_output[df_ai_output['SCORING_DATE'] <= cutoff].copy()

    if len(to_label) == 0:
        print("Belum ada records yang cukup tua untuk dilabeli.")
        return pd.DataFrame()

    # Filter pembayaran yang valid (Full atau Partial)
    pay = df_payment.copy()
    pay['ACTUAL_PAY_DATE'] = pd.to_datetime(pay['ACTUAL_PAY_DATE'])
    pay_valid = pay[pay['PAY_STATUS'].isin(['Full', 'Partial'])].copy()

    # JOIN: untuk setiap scoring record, tarik semua pembayaran contractnya
    merged = to_label.merge(
        pay_valid[['CONTRACT_NO', 'ACTUAL_PAY_DATE']],
        on='CONTRACT_NO', how='left'
    )

    # Cek apakah pembayaran jatuh dalam window setelah scoring
    merged['in_window'] = (
        (merged['ACTUAL_PAY_DATE'] > merged['SCORING_DATE']) &
        (merged['ACTUAL_PAY_DATE'] <=
         merged['SCORING_DATE'] + pd.Timedelta(days=label_window))
    )

    # Aggregate: satu baris per scoring record
    # actual_paid = 1 jika ADA minimal 1 pembayaran dalam window
    paid_flag = (
        merged.groupby(['CONTRACT_NO', 'SCORING_DATE'])['in_window']
        .any()
        .reset_index()
        .rename(columns={'in_window': 'actual_paid'})
    )
    paid_flag['actual_paid'] = paid_flag['actual_paid'].astype(int)

    # Merge kembali ke to_label
    labeled = to_label.merge(paid_flag, on=['CONTRACT_NO', 'SCORING_DATE'], how='left')
    labeled['actual_paid'] = labeled['actual_paid'].fillna(0).astype(int)
    labeled['labeled_date'] = today

    # ── RINGKASAN ──────────────────────────────────────────────────
    n = len(labeled)
    n_paid = labeled['actual_paid'].sum()
    print(f"Labeling complete:")
    print(f"  Total records dilabeli : {n:,}")
    print(f"  Actual paid (1)        : {n_paid:,}  ({n_paid/n*100:.1f}%)")
    print(f"  Actual unpaid (0)      : {n-n_paid:,}  ({(n-n_paid)/n*100:.1f}%)")

    # Model accuracy check: berapa yang prediksinya benar?
    labeled['pred_label']   = (labeled['RECOVERY_SCORE'] >= 0.50).astype(int)
    accuracy = (labeled['pred_label'] == labeled['actual_paid']).mean()
    print(f"  Prediction accuracy    : {accuracy*100:.1f}%")

    # Simpan ke database jika engine tersedia
    if engine is not None:
        # Hanya simpan yang belum ada di tabel labeled
        existing_keys = pd.read_sql(
            "SELECT CONTRACT_NO, SCORING_DATE FROM scoring_labels", engine
        )
        new_only = labeled[
            ~labeled.set_index(['CONTRACT_NO', 'SCORING_DATE']).index
            .isin(existing_keys.set_index(['CONTRACT_NO', 'SCORING_DATE']).index)
        ]
        if len(new_only) > 0:
            new_only.to_sql('scoring_labels', engine,
                            if_exists='append', index=False)
            print(f"  Appended {len(new_only):,} new labels to scoring_labels")

    return labeled
```

---

## 5. Model Monitor — Deteksi Kapan Harus Retrain

```python
# model_monitor.py
# Dijalankan setiap minggu, output: apakah model perlu di-retrain?

import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, log_loss


# ── PERFORMA MODEL ─────────────────────────────────────────────────

def compute_model_performance(df_labeled, window_days=30):
    """
    Hitung performa model pada cohort terbaru yang sudah dilabeli.
    Gunakan window_days hari terakhir untuk evaluasi "current performance."

    Metrik:
      AUC          → kemampuan model membedakan "bayar" vs "tidak"
      Log Loss     → seberapa baik probabilitas yang dihasilkan (calibration)
      Calibration  → apakah rata-rata score ≈ actual paid rate?
    """
    df = df_labeled.copy()
    df['SCORING_DATE'] = pd.to_datetime(df['SCORING_DATE'])

    recent_cutoff = df['SCORING_DATE'].max() - pd.Timedelta(days=window_days)
    recent = df[df['SCORING_DATE'] >= recent_cutoff]

    if len(recent) < 100:
        return {
            'status'    : 'insufficient_data',
            'n_samples' : len(recent),
            'message'   : f'Butuh minimal 100 records, hanya ada {len(recent)}'
        }

    y_true  = recent['actual_paid']
    y_score = recent['RECOVERY_SCORE']

    auc        = roc_auc_score(y_true, y_score)
    logloss    = log_loss(y_true, y_score)
    avg_score  = y_score.mean()
    actual_rate = y_true.mean()

    # Calibration gap: idealnya < 0.05
    # Jika jauh → model perlu di-recalibrate atau retrain
    calibration_gap = abs(avg_score - actual_rate)

    # Breakdown per segment (untuk monitoring granular)
    segment_perf = {}
    if 'RISK_SEGMENT' in recent.columns:
        for seg in recent['RISK_SEGMENT'].unique():
            seg_data = recent[recent['RISK_SEGMENT'] == seg]
            if len(seg_data) >= 30:
                seg_actual_rate = seg_data['actual_paid'].mean()
                seg_avg_score   = seg_data['RECOVERY_SCORE'].mean()
                segment_perf[seg] = {
                    'n'              : len(seg_data),
                    'actual_paid_rt' : round(seg_actual_rate, 3),
                    'avg_score'      : round(seg_avg_score, 3),
                    'gap'            : round(abs(seg_avg_score - seg_actual_rate), 3),
                }

    return {
        'status'            : 'ok',
        'n_samples'         : len(recent),
        'auc'               : round(auc, 4),
        'log_loss'          : round(logloss, 4),
        'avg_predicted'     : round(avg_score, 4),
        'actual_paid_rate'  : round(actual_rate, 4),
        'calibration_gap'   : round(calibration_gap, 4),
        'segment_breakdown' : segment_perf,
    }


# ── DRIFT DETECTION (PSI) ──────────────────────────────────────────

def compute_psi(reference_series, current_series, n_bins=10):
    """
    Population Stability Index (PSI) mengukur seberapa banyak
    distribusi sebuah fitur berubah antara training dan sekarang.

    Interpretasi:
      PSI < 0.10  → Stabil, tidak perlu khawatir
      PSI 0.10-0.25 → Perubahan moderat, perlu diperhatikan
      PSI > 0.25  → Perubahan signifikan → pertimbangkan retrain
    """
    ref = reference_series.dropna()
    cur = current_series.dropna()

    if len(ref) == 0 or len(cur) == 0:
        return None

    # Buat bins berdasarkan distribusi data referensi (training)
    _, bin_edges = np.histogram(ref, bins=n_bins)
    bin_edges[0]  = -np.inf
    bin_edges[-1] = np.inf

    # Hitung frekuensi per bin untuk kedua distribusi
    ref_counts, _ = np.histogram(ref, bins=bin_edges)
    cur_counts, _ = np.histogram(cur, bins=bin_edges)

    # Normalisasi ke proporsi, hindari log(0)
    ref_pct = np.where(ref_counts == 0, 0.0001, ref_counts / len(ref))
    cur_pct = np.where(cur_counts == 0, 0.0001, cur_counts / len(cur))

    psi_value = np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct))
    return round(float(psi_value), 4)


def run_drift_detection(df_train_snapshot, df_current_features, feature_cols):
    """
    Hitung PSI untuk setiap fitur input model.
    Bandingkan distribusi saat training vs distribusi hari ini.

    df_train_snapshot: sample fitur yang disimpan saat training terakhir
    df_current_features: fitur dari kontrak aktif hari ini
    """
    results = {}

    for col in feature_cols:
        if col not in df_train_snapshot.columns:
            continue
        if col not in df_current_features.columns:
            continue

        psi = compute_psi(df_train_snapshot[col], df_current_features[col])
        if psi is None:
            continue

        status = (
            'stable'   if psi < 0.10 else
            'warning'  if psi < 0.25 else
            'critical'
        )
        results[col] = {'psi': psi, 'status': status}

    # ── Ringkasan ─────────────────────────────────────────────────
    n_critical = sum(1 for v in results.values() if v['status'] == 'critical')
    n_warning  = sum(1 for v in results.values() if v['status'] == 'warning')
    n_stable   = sum(1 for v in results.values() if v['status'] == 'stable')

    print(f"\nDrift Detection Summary:")
    print(f"  🟢 Stable   (PSI < 0.10) : {n_stable} features")
    print(f"  🟡 Warning  (PSI < 0.25) : {n_warning} features")
    print(f"  🔴 Critical (PSI > 0.25) : {n_critical} features")

    if n_critical > 0:
        print(f"\n  Critical features (perlu segera retrain):")
        for col, v in sorted(results.items(),
                              key=lambda x: x[1]['psi'], reverse=True):
            if v['status'] == 'critical':
                print(f"    {col:<35} PSI = {v['psi']:.4f}")

    # Flag: True = retrain diperlukan
    needs_retrain = n_critical >= 2 or n_warning >= 5
    return results, needs_retrain
```

---

## 6. Retraining Pipeline — Tiga Strategi

```python
# retrain_strategies.py

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import roc_auc_score
import joblib
from datetime import datetime


# ── STRATEGY 1: FULL RETRAIN ───────────────────────────────────────

def strategy_full_retrain(df_labeled, feature_cols, target_col='actual_paid'):
    """
    Latih ulang dari nol menggunakan SEMUA data historis yang tersedia.
    Strategi paling sederhana — cocok sebagai baseline.
    """
    print(f"[Full Retrain] n_samples = {len(df_labeled):,}")

    X = df_labeled[feature_cols]
    y = df_labeled[target_col]

    model = _build_xgb(y)
    cv_auc = _cross_validate(model, X, y)
    model.fit(X, y, verbose=False)

    return model, {
        'strategy'   : 'full_retrain',
        'n_samples'  : len(df_labeled),
        'cv_auc'     : cv_auc,
        'trained_at' : datetime.now().isoformat(),
    }


# ── STRATEGY 2: ROLLING WINDOW ─────────────────────────────────────

def strategy_rolling_window(df_labeled, feature_cols,
                             target_col='actual_paid', months=6):
    """
    Train hanya dengan data N bulan terakhir.
    Model lebih responsif terhadap kondisi terkini.
    """
    df = df_labeled.copy()
    df['SCORING_DATE'] = pd.to_datetime(df['SCORING_DATE'])
    cutoff = pd.Timestamp.today() - pd.DateOffset(months=months)
    df_window = df[df['SCORING_DATE'] >= cutoff]

    print(f"[Rolling Window] months={months}, n_samples={len(df_window):,}")
    if len(df_window) < 500:
        raise ValueError(
            f"Data dalam window {months} bulan terlalu sedikit: {len(df_window):,}. "
            "Pertimbangkan memperlebar window atau menggunakan Full Retrain."
        )

    X = df_window[feature_cols]
    y = df_window[target_col]

    model = _build_xgb(y)
    cv_auc = _cross_validate(model, X, y)
    model.fit(X, y, verbose=False)

    return model, {
        'strategy'       : 'rolling_window',
        'window_months'  : months,
        'n_samples'      : len(df_window),
        'date_from'      : str(df_window['SCORING_DATE'].min().date()),
        'date_to'        : str(df_window['SCORING_DATE'].max().date()),
        'cv_auc'         : cv_auc,
        'trained_at'     : datetime.now().isoformat(),
    }


# ── STRATEGY 3: RECENCY-WEIGHTED (REKOMENDASI) ────────────────────

def strategy_recency_weighted(df_labeled, feature_cols,
                               target_col='actual_paid', decay_rate=0.7):
    """
    [REKOMENDASI] Gunakan SEMUA data historis, tapi beri bobot lebih
    tinggi untuk data yang lebih baru menggunakan sample_weight XGBoost.

    Decay rate 0.7 berarti:
      Data bulan ini  = bobot 1.00
      1 bulan lalu    = bobot 0.70
      2 bulan lalu    = bobot 0.49
      3 bulan lalu    = bobot 0.34
      6 bulan lalu    = bobot 0.12
      12 bulan lalu   = bobot 0.01  (hampir tidak berpengaruh)

    Kelebihan dibanding rolling window:
      - Tidak membuang data lama yang mungkin masih relevan
      - Bobot mengalir secara halus, tidak ada "cliff" di batas bulan
      - Data lama yang langka (nasabah multi-default) tetap terwakili
    """
    df = df_labeled.copy()
    df['SCORING_DATE'] = pd.to_datetime(df['SCORING_DATE'])

    today = pd.Timestamp.today()

    # Hitung umur data dalam bulan (dibulatkan ke bawah)
    df['months_ago'] = (
        (today.year  - df['SCORING_DATE'].dt.year) * 12 +
        (today.month - df['SCORING_DATE'].dt.month)
    ).clip(lower=0)

    # Hitung sample weight: semakin tua, semakin kecil bobotnya
    df['sample_weight'] = decay_rate ** df['months_ago']

    print(f"[Recency-Weighted] n_samples={len(df):,}, decay={decay_rate}")
    print(f"  Bobot rata-rata  : {df['sample_weight'].mean():.3f}")
    print(f"  Rentang bobot    : {df['sample_weight'].min():.4f} – {df['sample_weight'].max():.4f}")

    X = df[feature_cols]
    y = df[target_col]
    w = df['sample_weight']

    model = _build_xgb(y)

    # Train dengan sample_weight
    # Catatan: cross_val_score standar tidak support sample_weight,
    # jadi kita evaluasi pada data 1 bulan terakhir (paling relevan)
    model.fit(X, y, sample_weight=w, verbose=False)

    # Evaluasi pada recent data (tanpa weighting untuk fairness)
    recent = df[df['months_ago'] <= 1]
    recent_auc = None
    if len(recent) >= 100:
        y_pred_recent = model.predict_proba(recent[feature_cols])[:, 1]
        recent_auc    = round(roc_auc_score(recent[target_col], y_pred_recent), 4)
        print(f"  AUC pada data bulan terakhir : {recent_auc}")

    return model, {
        'strategy'      : 'recency_weighted',
        'decay_rate'    : decay_rate,
        'n_samples'     : len(df),
        'recent_auc'    : recent_auc,
        'trained_at'    : datetime.now().isoformat(),
    }


# ── HELPERS ────────────────────────────────────────────────────────

def _build_xgb(y_series):
    """Buat XGBClassifier dengan parameter standar CollectAI"""
    n_neg = (y_series == 0).sum()
    n_pos = (y_series == 1).sum()
    spw   = n_neg / max(n_pos, 1)

    return xgb.XGBClassifier(
        n_estimators     = 500,
        max_depth        = 6,
        learning_rate    = 0.05,
        subsample        = 0.80,
        colsample_bytree = 0.80,
        min_child_weight = 10,
        gamma            = 1.0,
        reg_alpha        = 0.1,
        reg_lambda       = 1.0,
        scale_pos_weight = spw,
        eval_metric      = 'auc',
        random_state     = 42,
        n_jobs           = -1,
    )


def _cross_validate(model, X, y, n_splits=5):
    """5-fold stratified cross-validation"""
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    scores = cross_val_score(model, X, y, cv=cv, scoring='roc_auc')
    print(f"  CV AUC: {scores.mean():.4f} ± {scores.std():.4f}")
    return round(scores.mean(), 4)
```

---

## 7. Champion-Challenger — Deploy Aman

```
KONSEP CHAMPION-CHALLENGER:

  Jangan langsung ganti model lama dengan model baru.
  Jalankan keduanya secara paralel dulu selama 7–14 hari.

  ┌─────────────────────────────────────────────────────────┐
  │                  SCORING HARIAN                         │
  │                                                         │
  │   Semua kontrak → CHAMPION MODEL → Score (production)  │
  │                 ↘ CHALLENGER MODEL → Score (shadow)    │
  │                                                         │
  │   Setelah 14 hari, bandingkan performa keduanya        │
  │   pada actual outcome yang sudah terlabeli.            │
  └─────────────────────────────────────────────────────────┘

  Jika Challenger lebih baik → Promote jadi Champion baru
  Jika tidak → Keep Champion, Retire Challenger
```

```python
# champion_challenger.py

import pandas as pd
import numpy as np
import joblib
import shutil
from datetime import datetime
from sklearn.metrics import roc_auc_score


def run_shadow_scoring(df_features_enriched, feature_cols,
                       champion_path, challenger_path):
    """
    Jalankan kedua model secara paralel.
    Champion score → dipakai untuk operasional
    Challenger score → disimpan di shadow table untuk evaluasi

    Tidak ada risk ke operasional: collector tetap melihat champion score.
    """
    X = df_features_enriched[feature_cols]

    champ_artifact = joblib.load(champion_path)
    chal_artifact  = joblib.load(challenger_path)

    df_result = df_features_enriched[['CONTRACT_NO', 'CUST_ID']].copy()

    # Champion score → yang dipakai operasional
    df_result['champion_score']   = (champ_artifact['model']
                                     .predict_proba(X)[:, 1].round(4))

    # Challenger score → shadow, untuk evaluasi
    df_result['challenger_score'] = (chal_artifact['model']
                                     .predict_proba(X)[:, 1].round(4))

    df_result['score_delta']   = (
        df_result['challenger_score'] - df_result['champion_score']
    ).round(4)
    df_result['snapshot_date'] = datetime.today().date()

    print(f"Shadow scoring: {len(df_result):,} contracts")
    print(f"  Champion avg score   : {df_result['champion_score'].mean():.4f}")
    print(f"  Challenger avg score : {df_result['challenger_score'].mean():.4f}")
    print(f"  Avg delta            : {df_result['score_delta'].mean():+.4f}")

    # Simpan ke shadow table
    # df_result.to_sql('shadow_scores', engine, if_exists='append', index=False)

    return df_result


def evaluate_champion_vs_challenger(df_labeled, df_shadow_scores,
                                    min_samples=200,
                                    min_auc_improvement=0.02):
    """
    Setelah 14 hari shadow mode, bandingkan performa Champion vs Challenger
    menggunakan actual outcomes yang sudah dilabeli.

    Parameters
    ----------
    min_auc_improvement : minimal selisih AUC agar challenger dipromote
                          0.02 = challenger harus lebih baik minimal 2 poin AUC
    """
    # Gabungkan shadow scores dengan actual outcome
    eval_df = df_labeled.merge(
        df_shadow_scores.groupby('CONTRACT_NO').agg(
            champion_score   = ('champion_score',   'mean'),
            challenger_score = ('challenger_score', 'mean'),
        ).reset_index(),
        on='CONTRACT_NO', how='inner'
    )

    n = len(eval_df)
    if n < min_samples:
        return {
            'decision' : 'INSUFFICIENT_DATA',
            'message'  : f'Hanya {n} records, butuh minimal {min_samples}'
        }

    y_true = eval_df['actual_paid']

    champ_auc = roc_auc_score(y_true, eval_df['champion_score'])
    chal_auc  = roc_auc_score(y_true, eval_df['challenger_score'])
    delta     = chal_auc - champ_auc

    # Calibration comparison
    actual_rate   = y_true.mean()
    champ_calib   = abs(eval_df['champion_score'].mean()   - actual_rate)
    chal_calib    = abs(eval_df['challenger_score'].mean() - actual_rate)

    print(f"\nChampion vs Challenger Evaluation")
    print(f"  n_samples          : {n:,}")
    print(f"  Actual paid rate   : {actual_rate:.1%}")
    print(f"  Champion AUC       : {champ_auc:.4f}  (calibration gap: {champ_calib:.4f})")
    print(f"  Challenger AUC     : {chal_auc:.4f}  (calibration gap: {chal_calib:.4f})")
    print(f"  AUC Delta          : {delta:+.4f}")

    # Keputusan
    if delta >= min_auc_improvement:
        decision = 'PROMOTE_CHALLENGER'
        print(f"\n  ✅ DECISION: PROMOTE CHALLENGER")
        print(f"     Challenger menang dengan margin {delta:+.4f} AUC")
    elif delta <= -min_auc_improvement:
        decision = 'KEEP_CHAMPION'
        print(f"\n  ❌ DECISION: KEEP CHAMPION")
        print(f"     Challenger kalah, champion dipertahankan")
    else:
        decision = 'NO_SIGNIFICANT_DIFF'
        print(f"\n  ⚖️  DECISION: NO SIGNIFICANT DIFFERENCE")
        print(f"     Delta {delta:+.4f} di bawah threshold {min_auc_improvement}")
        print(f"     Champion dipertahankan karena tidak ada bukti challenger lebih baik")

    return {
        'decision'         : decision,
        'n_samples'        : n,
        'champion_auc'     : round(champ_auc, 4),
        'challenger_auc'   : round(chal_auc, 4),
        'auc_delta'        : round(delta, 4),
        'champion_calib'   : round(champ_calib, 4),
        'challenger_calib' : round(chal_calib, 4),
        'evaluated_at'     : datetime.now().isoformat(),
    }


def promote_challenger(champion_path, challenger_path, backup_dir='models/archive'):
    """
    Promote challenger menjadi champion baru.
    Champion lama diarsipkan (bukan dihapus) untuk rollback jika diperlukan.
    """
    import os

    os.makedirs(backup_dir, exist_ok=True)

    # Baca metadata champion lama
    old_champ = joblib.load(champion_path)
    trained_date = old_champ.get('trained_at', 'unknown')[:10]

    # Arsipkan champion lama
    backup_name = f"{backup_dir}/recovery_model_champion_{trained_date}.pkl"
    shutil.copy(champion_path, backup_name)
    print(f"  Champion lama diarsipkan: {backup_name}")

    # Promote challenger → champion
    shutil.copy(challenger_path, champion_path)
    print(f"  Challenger dipromote ke: {champion_path}")
    print(f"  ✅ Promotion complete!")

    return backup_name
```

---

## 8. Model Registry — Versioning & Rollback

```python
# model_registry.py
# Manajemen versi model: siapa champion, siapa challenger, history performa

import json
import os
import joblib
from datetime import datetime


REGISTRY_PATH = 'models/registry.json'


def register_model(model_path, metadata, role='challenger'):
    """
    Daftarkan model baru ke registry.

    role: 'champion' atau 'challenger'
    metadata: dict berisi training info (strategy, cv_auc, n_samples, dll)
    """
    registry = _load_registry()

    version = f"v{len(registry['history']) + 1}"
    entry = {
        'version'    : version,
        'role'       : role,
        'path'       : model_path,
        'registered' : datetime.now().isoformat(),
        **metadata
    }

    registry['history'].append(entry)
    if role == 'champion':
        registry['current_champion'] = entry
    elif role == 'challenger':
        registry['current_challenger'] = entry

    _save_registry(registry)
    print(f"Model registered: {version} as {role}")
    return version


def get_champion_path():
    """Ambil path model champion saat ini"""
    registry = _load_registry()
    champ = registry.get('current_champion')
    if champ is None:
        raise FileNotFoundError("Belum ada champion model di registry.")
    return champ['path']


def get_performance_history(last_n=10):
    """Lihat 10 model terakhir dan AUC-nya"""
    registry = _load_registry()
    history  = registry.get('history', [])[-last_n:]

    print(f"\nModel Performance History (last {last_n}):")
    print(f"{'Ver':<6} {'Role':<12} {'Strategy':<22} {'AUC':<8} {'Samples':<10} {'Date'}")
    print("─" * 75)
    for entry in history:
        print(
            f"{entry['version']:<6} "
            f"{entry['role']:<12} "
            f"{entry.get('strategy','?'):<22} "
            f"{entry.get('cv_auc', entry.get('recent_auc', '?')):<8} "
            f"{entry.get('n_samples','?'):<10} "
            f"{entry['registered'][:10]}"
        )

    return history


def rollback_to_previous():
    """
    Rollback ke champion sebelumnya jika ada masalah dengan champion baru.
    """
    registry = _load_registry()
    history  = registry.get('history', [])

    # Cari champion sebelumnya (bukan yang sekarang)
    previous_champions = [
        e for e in history
        if e['role'] == 'champion' and
           e['version'] != registry['current_champion']['version']
    ]

    if not previous_champions:
        raise ValueError("Tidak ada champion sebelumnya untuk rollback.")

    prev = previous_champions[-1]
    print(f"Rolling back to: {prev['version']} (trained {prev['registered'][:10]})")

    import shutil
    shutil.copy(prev['path'], get_champion_path())

    registry['current_champion'] = prev
    _save_registry(registry)
    print(f"✅ Rollback complete to {prev['version']}")


def _load_registry():
    if not os.path.exists(REGISTRY_PATH):
        return {'history': [], 'current_champion': None, 'current_challenger': None}
    with open(REGISTRY_PATH, 'r') as f:
        return json.load(f)


def _save_registry(registry):
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, 'w') as f:
        json.dump(registry, f, indent=2)
```

---

## 9. Weekly MLOps Orchestrator

```python
# mlops_orchestrator.py
# Entry point utama — jalankan setiap minggu via scheduler

import pandas as pd
import joblib
from datetime import datetime
from sqlalchemy import create_engine

# Import semua modul yang sudah dibuat
from outcome_labeler     import label_historical_scores
from model_monitor       import compute_model_performance, run_drift_detection
from retrain_strategies  import strategy_recency_weighted
from champion_challenger import (run_shadow_scoring, evaluate_champion_vs_challenger,
                                  promote_challenger)
from model_registry      import register_model, get_champion_path, get_performance_history
from scoring_engine      import FEATURE_COLS, TARGET_COL, compute_contract_features, enrich_with_cbs

DB_URL = "postgresql://user:password@localhost:5432/collectai"

# ── THRESHOLDS (bisa di-override dari config) ──────────────────────
AUC_FLOOR              = 0.68   # retrain jika AUC turun di bawah ini
N_CRITICAL_DRIFT       = 2      # retrain jika ada fitur ini yg critical drift
SHADOW_DAYS_MIN        = 7      # minimal hari shadow sebelum evaluasi
MIN_AUC_IMPROVEMENT    = 0.02   # challenger harus unggul minimal ini
RETRAIN_STRATEGY       = 'recency_weighted'
DECAY_RATE             = 0.70


def run_weekly_mlops():
    """
    Orchestrator utama MLOps.
    Urutan:
      1. Label outcome dari scoring records yang sudah tua
      2. Monitor performa model saat ini
      3. Deteksi drift pada fitur input
      4. Jika perlu retrain → buat challenger
      5. Jika ada challenger yang siap → evaluasi champion vs challenger
      6. Promote jika challenger lebih baik
    """
    start = datetime.now()
    print(f"\n{'='*65}")
    print(f"  CollectAI MLOps — Weekly Run")
    print(f"  {start.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*65}")

    engine = create_engine(DB_URL)

    # ── LOAD DATA ──────────────────────────────────────────────────
    df_ai_output = pd.read_sql("SELECT * FROM ai_intelligence_output",  engine)
    df_payment   = pd.read_sql("SELECT * FROM payment_history",          engine)
    df_contract  = pd.read_sql("SELECT * FROM contract_snapshot WHERE status='aktif'", engine)
    df_lkp       = pd.read_sql("SELECT * FROM lkp_interaction",          engine)
    df_cbs       = pd.read_sql("SELECT * FROM customer_behavioral_standing", engine)

    try:
        df_labeled_all = pd.read_sql("SELECT * FROM scoring_labels", engine)
    except Exception:
        df_labeled_all = pd.DataFrame()

    # ── STEP 1: LABEL NEW OUTCOMES ─────────────────────────────────
    print(f"\n{'─'*65}")
    print("[Step 1] Labeling historical scoring outcomes...")
    new_labels = label_historical_scores(df_ai_output, df_payment, engine=engine)
    if len(new_labels) > 0:
        df_labeled_all = pd.concat([df_labeled_all, new_labels], ignore_index=True)

    # ── STEP 2: MONITOR MODEL PERFORMANCE ─────────────────────────
    print(f"\n{'─'*65}")
    print("[Step 2] Computing model performance (last 30 days)...")
    perf = compute_model_performance(df_labeled_all, window_days=30)

    if perf['status'] == 'insufficient_data':
        print(f"  ⚠️  {perf['message']}")
        needs_retrain_perf = False
    else:
        print(f"  AUC              : {perf['auc']}")
        print(f"  Calibration gap  : {perf['calibration_gap']}")
        print(f"  n_samples        : {perf['n_samples']:,}")
        needs_retrain_perf = perf['auc'] < AUC_FLOOR

    # ── STEP 3: DRIFT DETECTION ────────────────────────────────────
    print(f"\n{'─'*65}")
    print("[Step 3] Detecting feature drift...")
    champion_artifact  = joblib.load(get_champion_path())
    df_train_snap      = champion_artifact.get('training_features_sample', pd.DataFrame())
    df_current_feats   = compute_contract_features(df_contract, df_payment, df_lkp,
                                                    datetime.today())
    df_current_enrich  = enrich_with_cbs(df_current_feats, df_cbs)

    drift_results, needs_retrain_drift = run_drift_detection(
        df_train_snap, df_current_enrich, FEATURE_COLS
    )

    # ── STEP 4: RETRAIN JIKA DIPERLUKAN ───────────────────────────
    print(f"\n{'─'*65}")
    should_retrain = needs_retrain_perf or needs_retrain_drift

    if should_retrain:
        reason = []
        if needs_retrain_perf:
            reason.append(f"AUC={perf.get('auc','?')} < threshold {AUC_FLOOR}")
        if needs_retrain_drift:
            reason.append("critical feature drift detected")
        print(f"[Step 4] ⚠️  RETRAIN TRIGGERED: {' & '.join(reason)}")

        # Gabungkan semua fitur dengan labeled outcomes
        df_for_retrain = df_current_enrich.merge(
            df_labeled_all[['CONTRACT_NO', 'SCORING_DATE', TARGET_COL]],
            on='CONTRACT_NO', how='inner'
        )

        challenger_model, challenger_meta = strategy_recency_weighted(
            df_for_retrain, FEATURE_COLS, TARGET_COL, decay_rate=DECAY_RATE
        )

        # Simpan challenger + sample fitur training untuk future drift detection
        challenger_path = 'models/recovery_model_challenger.pkl'
        challenger_artifact = {
            'model'                   : challenger_model,
            'feature_cols'            : FEATURE_COLS,
            'training_features_sample': df_current_enrich[FEATURE_COLS].sample(
                                            min(1000, len(df_current_enrich)),
                                            random_state=42),
            **challenger_meta,
        }
        import joblib
        joblib.dump(challenger_artifact, challenger_path)

        version = register_model(challenger_path, challenger_meta, role='challenger')
        print(f"  ✅ Challenger {version} saved and registered")
        print(f"  → Akan di-shadow score selama {SHADOW_DAYS_MIN} hari sebelum dievaluasi")

    else:
        print("[Step 4] ✅ No retrain needed. Model performance is acceptable.")

    # ── STEP 5: EVALUASI CHAMPION VS CHALLENGER ───────────────────
    print(f"\n{'─'*65}")
    challenger_path = 'models/recovery_model_challenger.pkl'

    import os
    if os.path.exists(challenger_path):
        # Load shadow scores yang sudah dikumpulkan
        try:
            df_shadow = pd.read_sql("SELECT * FROM shadow_scores", engine)
            n_shadow_days = df_shadow['snapshot_date'].nunique()

            if n_shadow_days >= SHADOW_DAYS_MIN:
                print(f"[Step 5] Evaluating champion vs challenger ({n_shadow_days} shadow days)...")
                eval_result = evaluate_champion_vs_challenger(
                    df_labeled_all, df_shadow,
                    min_auc_improvement=MIN_AUC_IMPROVEMENT
                )

                if eval_result['decision'] == 'PROMOTE_CHALLENGER':
                    backup_path = promote_challenger(
                        champion_path  = get_champion_path(),
                        challenger_path = challenger_path,
                    )
                    register_model(get_champion_path(), eval_result, role='champion')
                    # Hapus challenger setelah promoted
                    os.remove(challenger_path)
                    print(f"  Old champion backed up to: {backup_path}")

            else:
                print(f"[Step 5] Shadow mode: {n_shadow_days}/{SHADOW_DAYS_MIN} days "
                      f"— belum siap untuk dievaluasi")

        except Exception as e:
            print(f"[Step 5] Tidak ada shadow scores: {e}")

    else:
        print("[Step 5] Tidak ada challenger saat ini — skip evaluation")

    # ── RINGKASAN ──────────────────────────────────────────────────
    duration = (datetime.now() - start).total_seconds()
    print(f"\n{'='*65}")
    print(f"  MLOps run selesai dalam {duration:.1f} detik")
    get_performance_history(last_n=5)
    print(f"{'='*65}\n")


if __name__ == '__main__':
    run_weekly_mlops()
```

---

## 10. Jadwal Lengkap

```
SETIAP MALAM (23:00)
  └── daily_scoring.py           → Score semua kontrak aktif, publish AI Output

SETIAP MINGGU (Senin 06:00)
  └── mlops_orchestrator.py      → Label outcomes + monitor + retrain jika perlu
  └── shadow_scoring.py          → Jika ada challenger, jalankan shadow score

SETIAP BULAN (Tanggal 1, 09:00)
  └── model_registry.py          → Review performance history
  └── get_performance_history()  → Lihat tren AUC 3 bulan terakhir

MANUAL / ON-DEMAND
  └── rollback_to_previous()     → Jika ada masalah setelah promote challenger
  └── force_retrain()            → Jika ada perubahan bisnis mendadak
                                    (contoh: produk baru, perubahan kebijakan)

─────────────────────────────────────────────────────────────────────────────

TIMELINE CONTOH — MODEL MENJADI LEBIH BAIK DARI WAKTU KE WAKTU:

  Bulan 0  : Training awal, 5.000 records, AUC = 0.73 (Model v1, Champion)
  Bulan 1  : +4.000 labeled records. Monitor: AUC masih 0.72. No retrain.
  Bulan 2  : +4.000 labeled records. Monitor: AUC turun ke 0.69. RETRAIN!
             → Challenger v2 dibuat, shadow 14 hari
             → Challenger AUC = 0.75 (+0.03). PROMOTE! v2 jadi Champion.
  Bulan 3  : +4.000 records. AUC stabil 0.74. No retrain.
  Bulan 6  : Dataset = 29.000 records. AUC = 0.78. Retrain rutin bulanan.
             → v3 dibuat dengan 6× lebih banyak data → AUC = 0.80. PROMOTE!
  Bulan 12 : Dataset = 53.000+ records. Model sangat akurat karena
             sudah melihat berbagai siklus ekonomi, jenis nasabah, dan produk.

─────────────────────────────────────────────────────────────────────────────
```

---

> **Catatan Penting:**
> Simpan selalu `training_features_sample` (1.000 baris sample fitur training)
> di dalam artifact model. Ini dibutuhkan untuk `run_drift_detection()` di masa depan —
> tanpa ini, kita tidak tahu distribusi "normal" saat model ditraining.