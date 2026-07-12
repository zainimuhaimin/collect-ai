# CollectAI — Scoring Engine
## Panduan Teknis: RECOVERY_SCORE & CONFIDENCE_LEVEL

> Dokumen ini menjelaskan secara detail bagaimana RECOVERY_SCORE dan CONFIDENCE_LEVEL
> dihitung — mulai dari konsep, training model, hingga kode inferensi harian.

---

## DAFTAR ISI

1. [Konsep Dasar — Ini Problem Apa?](#1-konsep-dasar--ini-problem-apa)
2. [Kenapa Gradient Boosting?](#2-kenapa-gradient-boosting)
3. [Mendefinisikan Target Variable](#3-mendefinisikan-target-variable)
4. [Pipeline Training Model](#4-pipeline-training-model)
5. [CONFIDENCE_LEVEL — Formula & Logika](#5-confidence_level--formula--logika)
6. [Business Rules — Segment, NBA, Priority](#6-business-rules--segment-nba-priority)
7. [Daily Runner — Satu File Jalankan Semuanya](#7-daily-runner--satu-file-jalankan-semuanya)
8. [Dependencies](#8-dependencies)

---

## 1. Konsep Dasar — Ini Problem Apa?

RECOVERY_SCORE bukan angka yang dihitung manual dengan rumus aritmatika sederhana.
Ini adalah output dari **model Machine Learning klasifikasi biner**:

```
Pertanyaan yang dijawab model:
"Apakah nasabah ini akan melakukan pembayaran dalam 30 hari ke depan?"

Jawaban model:
Bukan YES/NO, melainkan sebuah PROBABILITAS — misalnya 0.73

Artinya:
Model memperkirakan ada 73% kemungkinan nasabah ini akan bayar dalam 30 hari.
Angka inilah yang menjadi RECOVERY_SCORE.
```

### Kenapa probabilitas, bukan klasifikasi langsung?

Karena di operasional collection, kita butuh **ranking**, bukan hanya label.
Collector punya keterbatasan waktu — mereka harus tahu *seberapa* mendesak
setiap kontrak, bukan sekedar "bayar" atau "tidak bayar."

```
Dua nasabah sama-sama di atas threshold "akan bayar":
  Nasabah A: score 0.92 → hampir pasti bayar sendiri, tidak perlu dicontak
  Nasabah B: score 0.54 → mungkin bayar, tapi perlu didorong

Tanpa score, keduanya terlihat sama. Dengan score, prioritas collector jelas.
```

---

## 2. Kenapa Gradient Boosting?

Gradient Boosting (XGBoost / LightGBM) dipilih karena beberapa alasan praktis:

| Aspek | Penjelasan |
|---|---|
| **Handle missing values** | Data collection sering tidak lengkap (nasabah baru belum punya historis). GBM bisa handle NULL secara native tanpa imputation wajib. |
| **Non-linear relationships** | Hubungan antara DPD dan kemungkinan bayar tidak linear — model tree-based lebih baik menangkap ini. |
| **Feature importance** | Mudah diaudit: kita bisa lihat fitur mana yang paling berpengaruh. Penting untuk compliance dan explainability. |
| **Robust terhadap outlier** | OTS bisa sangat bervariasi (dari jutaan ke ratusan juta). GBM lebih stabil dibanding regresi linear. |
| **Performa empiris** | Di domain credit scoring dan collection, GBM konsisten unggul vs alternatif lain. |

---

## 3. Mendefinisikan Target Variable

Sebelum training, kita harus mendefinisikan apa artinya "berhasil bayar."

```python
def build_target_variable(df_features, df_payment, scoring_date, n_days=30):
    """
    Target: apakah nasabah melakukan pembayaran dalam N hari setelah scoring_date?

    Label:
      1 = melakukan setidaknya 1 pembayaran (Full ATAU Partial) dalam window
      0 = tidak ada pembayaran sama sekali dalam window

    Catatan:
      - Partial dihitung sebagai "bayar" karena menunjukkan itikad baik
      - Window default 30 hari, bisa dikonfigurasi
    """
    import pandas as pd
    from datetime import timedelta

    scoring_date = pd.to_datetime(scoring_date)
    cutoff_date  = scoring_date + timedelta(days=n_days)

    pay = df_payment.copy()
    pay['ACTUAL_PAY_DATE'] = pd.to_datetime(pay['ACTUAL_PAY_DATE'])

    # Filter pembayaran yang terjadi SETELAH scoring date, dalam window
    pay_in_window = pay[
        (pay['ACTUAL_PAY_DATE'] > scoring_date) &
        (pay['ACTUAL_PAY_DATE'] <= cutoff_date) &
        (pay['PAY_STATUS'].isin(['Full', 'Partial']))
    ]

    paid_contracts = set(pay_in_window['CONTRACT_NO'].unique())

    df_features = df_features.copy()
    df_features['paid_within_30d'] = (
        df_features['CONTRACT_NO'].isin(paid_contracts).astype(int)
    )

    # Info distribusi label
    total   = len(df_features)
    n_paid  = df_features['paid_within_30d'].sum()
    n_unpaid = total - n_paid
    print(f"Target distribution:")
    print(f"  Bayar (1) : {n_paid:,}  ({n_paid/total*100:.1f}%)")
    print(f"  Tidak (0) : {n_unpaid:,} ({n_unpaid/total*100:.1f}%)")

    return df_features
```

---

## 4. Pipeline Training Model

### 4.1 Feature Engineering

```python
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────────
# Kolom fitur yang dipakai model — HARUS konsisten antara
# training dan inferensi harian
# ─────────────────────────────────────────────────────────────────
FEATURE_COLS = [
    # Contract-level (13 fitur)
    'DPD_CURRENT',
    'cycle_encoded',
    'total_ots',
    'payment_rate',
    'partial_rate',
    'avg_delay_days',
    'days_since_last_pay',
    'ptp_fulfillment_rate',
    'avg_interaction_score',
    'last_result_code_encoded',
    'treatment_count',
    'rejection_count',
    'payment_count',
    # Customer-level dari CBS (8 fitur enrichment)
    'ptp_reliability_index',
    'delay_trend',
    'historical_default_count',
    'income_debt_ratio',
    'active_contract_count',
    'total_active_ots',
    'behavioral_grade_encoded',
    'b_list_flag',
]

TARGET_COL = 'paid_within_30d'


def compute_contract_features(df_contract, df_payment, df_lkp, reference_date):
    """
    Menghitung semua contract-level features per CONTRACT_NO.
    Sesuai formula di CollectAI_System_Rules.md — Bagian 2.1

    Parameters
    ----------
    df_contract    : DataFrame dari tabel contract_snapshot
    df_payment     : DataFrame dari tabel payment_history
    df_lkp         : DataFrame dari tabel lkp_interaction
    reference_date : str atau date — tanggal "hari ini" saat scoring

    Returns
    -------
    DataFrame dengan satu baris per CONTRACT_NO + semua features
    """
    today = pd.to_datetime(reference_date)
    PTP_DAYS_WINDOW = 7   # ← dari tbl_config

    # ── PAYMENT FEATURES ──────────────────────────────────────────
    pay = df_payment.copy()
    pay['ACTUAL_PAY_DATE'] = pd.to_datetime(pay['ACTUAL_PAY_DATE'])

    pay_agg = pay.groupby('CONTRACT_NO').agg(
        payment_rate       = ('PAY_STATUS', lambda x: (x == 'Full').mean()),
        partial_rate       = ('PAY_STATUS', lambda x: (x == 'Partial').mean()),
        avg_delay_days     = ('DELAY_DAYS', 'mean'),
        last_pay_date      = ('ACTUAL_PAY_DATE', 'max'),
        payment_count      = ('PAYMENT_ID', 'count'),
    ).reset_index()

    pay_agg['days_since_last_pay'] = (
        (today - pay_agg['last_pay_date']).dt.days
    )
    pay_agg = pay_agg.drop(columns=['last_pay_date'])

    # ── LKP FEATURES ──────────────────────────────────────────────
    lkp = df_lkp.copy()
    lkp['ACTION_DATE']  = pd.to_datetime(lkp['ACTION_DATE'])
    lkp['PROMISE_DATE'] = pd.to_datetime(lkp['PROMISE_DATE'])

    # PTP kept: ada pembayaran dalam PTP_DAYS_WINDOW hari setelah PROMISE_DATE
    ptp_rows = lkp[lkp['RESULT_CODE'] == 'PTP'].copy()
    ptp_rows = ptp_rows.merge(
        pay[['CONTRACT_NO', 'ACTUAL_PAY_DATE']],
        on='CONTRACT_NO', how='left'
    )
    ptp_rows['ptp_kept'] = (
        (ptp_rows['ACTUAL_PAY_DATE'] >= ptp_rows['PROMISE_DATE']) &
        (ptp_rows['ACTUAL_PAY_DATE'] <=
         ptp_rows['PROMISE_DATE'] + timedelta(days=PTP_DAYS_WINDOW))
    )
    ptp_agg = (ptp_rows.groupby('CONTRACT_NO')
               .agg(
                   total_ptp_made=('RESULT_CODE', 'count'),
                   total_ptp_kept=('ptp_kept', 'sum'),
               ).reset_index())
    ptp_agg['ptp_fulfillment_rate'] = (
        ptp_agg['total_ptp_kept']
        / ptp_agg['total_ptp_made'].replace(0, np.nan)
    )

    # Result code terakhir per kontrak
    last_lkp = (
        lkp.sort_values('ACTION_DATE')
           .groupby('CONTRACT_NO')
           .tail(1)[['CONTRACT_NO', 'RESULT_CODE']]
           .rename(columns={'RESULT_CODE': 'last_result_code'})
    )

    # Encode RESULT_CODE ke angka ordinal
    # (semakin tinggi = semakin kooperatif / semakin baik)
    RESULT_CODE_MAP = {
        'Bayar'                : 4,
        'PTP'                  : 3,
        'Rumah Kosong'         : 2,
        'Tidak Bisa Dihubungi' : 1,
        'Menolak'              : 0,
    }

    lkp_agg = lkp.groupby('CONTRACT_NO').agg(
        avg_interaction_score = ('INTERACTION_SCORE', 'mean'),
        treatment_count       = ('LKP_ID', 'count'),
        rejection_count       = (
            'RESULT_CODE',
            lambda x: x.isin(['Menolak', 'Tidak Bisa Dihubungi']).sum()
        ),
    ).reset_index()

    lkp_agg = (lkp_agg
               .merge(last_lkp, on='CONTRACT_NO', how='left')
               .merge(ptp_agg[['CONTRACT_NO', 'ptp_fulfillment_rate',
                                'total_ptp_made', 'total_ptp_kept']],
                      on='CONTRACT_NO', how='left'))

    lkp_agg['last_result_code_encoded'] = (
        lkp_agg['last_result_code']
        .map(RESULT_CODE_MAP)
        .fillna(2)   # default: Rumah Kosong jika belum pernah dicontact
    )
    lkp_agg = lkp_agg.drop(columns=['last_result_code'])

    # ── CONTRACT BASE FEATURES ────────────────────────────────────
    cs = df_contract.copy()
    cs['total_ots']     = cs['PRNC_OTS'] + cs['INTR_OTS']
    cs['cycle_encoded'] = (
        cs['CYCLE_AKHIR']
        .map({'C0': 0, 'C1': 1, 'C2': 2, 'C3': 3})
        .fillna(3)
        .astype(int)
    )

    # ── MERGE SEMUA FEATURES ──────────────────────────────────────
    features = (
        cs[['CONTRACT_NO', 'CUST_ID', 'DPD_CURRENT',
            'cycle_encoded', 'total_ots', 'PRODUCT_TYPE']]
        .merge(pay_agg,  on='CONTRACT_NO', how='left')
        .merge(lkp_agg,  on='CONTRACT_NO', how='left')
    )

    return features


def enrich_with_cbs(df_features, df_cbs):
    """
    Gabungkan contract features dengan Customer Behavioral Standing
    sebagai enrichment input untuk model.
    CBS dibuild di Step 3 batch flow (lihat System Rules Bagian 5).
    """
    cbs_cols = [
        'CUST_ID',
        'ptp_reliability_index',
        'delay_trend',
        'historical_default_count',
        'income_debt_ratio',
        'active_contract_count',
        'total_active_ots',
        'BEHAVIORAL_GRADE',
        'B_LIST_STATUS',
    ]
    cbs = df_cbs[cbs_cols].copy()

    # Encode BEHAVIORAL_GRADE: A=3, B=2, C=1, D=0
    cbs['behavioral_grade_encoded'] = (
        cbs['BEHAVIORAL_GRADE'].map({'A': 3, 'B': 2, 'C': 1, 'D': 0})
    )
    # Encode B_LIST_STATUS: Y=1, N=0
    cbs['b_list_flag'] = (cbs['B_LIST_STATUS'] == 'Y').astype(int)
    cbs = cbs.drop(columns=['BEHAVIORAL_GRADE', 'B_LIST_STATUS'])

    enriched = df_features.merge(cbs, on='CUST_ID', how='left')
    return enriched
```

---

### 4.2 Training Model

```python
import xgboost as xgb
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import roc_auc_score, classification_report
import joblib


def train_recovery_model(df_train, save_path='models/recovery_model.pkl'):
    """
    Melatih model XGBoost untuk prediksi RECOVERY_SCORE.

    Best practice:
    - Gunakan data historis minimal 6 bulan ke belakang
    - Pastikan ada mix dari berbagai cycle, segment, dan produk
    - Evaluasi dengan cross-validation sebelum deploy

    Parameters
    ----------
    df_train  : DataFrame hasil build_target_variable()
    save_path : path untuk menyimpan model

    Returns
    -------
    model yang sudah ditraining
    """
    X = df_train[FEATURE_COLS]
    y = df_train[TARGET_COL]

    # ── HANDLE CLASS IMBALANCE ────────────────────────────────────
    # Di dataset collection, biasanya lebih banyak yang "tidak bayar"
    # scale_pos_weight menyeimbangkan bobot kelas
    n_neg = (y == 0).sum()
    n_pos = (y == 1).sum()
    scale_pos_weight = n_neg / n_pos
    print(f"Class ratio (neg/pos): {scale_pos_weight:.2f}")

    # ── MODEL DEFINITION ─────────────────────────────────────────
    model = xgb.XGBClassifier(
        # Arsitektur
        n_estimators     = 500,
        max_depth        = 6,         # cukup dalam untuk capture interaksi fitur
        # Regularisasi (mencegah overfitting)
        learning_rate    = 0.05,      # kecil = lebih stabil, lebih banyak trees
        subsample        = 0.80,      # 80% data per tree
        colsample_bytree = 0.80,      # 80% fitur per tree
        min_child_weight = 10,        # minimum sampel per leaf
        gamma            = 1.0,       # minimum gain untuk split
        reg_alpha        = 0.1,       # L1 regularization
        reg_lambda       = 1.0,       # L2 regularization
        # Imbalance handling
        scale_pos_weight = scale_pos_weight,
        # Output & reproducibility
        eval_metric      = 'auc',
        random_state     = 42,
        n_jobs           = -1,
    )

    # ── CROSS-VALIDATION ─────────────────────────────────────────
    # StratifiedKFold memastikan proporsi label sama di tiap fold
    print("Running 5-fold cross-validation...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X, y, cv=cv, scoring='roc_auc')
    print(f"CV AUC  : {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    # Target AUC minimum untuk deploy: 0.70
    # (artinya model 70% lebih baik dari random guess)
    if cv_scores.mean() < 0.70:
        raise ValueError(
            f"AUC terlalu rendah ({cv_scores.mean():.4f}). "
            "Periksa kualitas data sebelum deploy."
        )

    # ── TRAIN FINAL MODEL ─────────────────────────────────────────
    print("Training final model on full dataset...")
    model.fit(X, y, verbose=False)

    # ── FEATURE IMPORTANCE ────────────────────────────────────────
    # Berguna untuk audit dan explainability
    importance = pd.DataFrame({
        'feature'   : FEATURE_COLS,
        'importance': model.feature_importances_,
    }).sort_values('importance', ascending=False)
    print("\nTop 10 Feature Importances:")
    print(importance.head(10).to_string(index=False))

    # ── EVALUASI PADA TRAINING SET ────────────────────────────────
    y_pred_proba = model.predict_proba(X)[:, 1]
    y_pred_label = (y_pred_proba >= 0.50).astype(int)
    train_auc    = roc_auc_score(y, y_pred_proba)
    print(f"\nTrain AUC : {train_auc:.4f}")
    print("\nClassification Report:")
    print(classification_report(y, y_pred_label,
                                 target_names=['Tidak Bayar', 'Bayar']))

    # ── SIMPAN MODEL ─────────────────────────────────────────────
    model_artifact = {
        'model'        : model,
        'feature_cols' : FEATURE_COLS,
        'target_col'   : TARGET_COL,
        'trained_date' : datetime.today().strftime('%Y-%m-%d'),
        'cv_auc'       : round(cv_scores.mean(), 4),
        'importance'   : importance,
    }
    joblib.dump(model_artifact, save_path)
    print(f"\nModel saved to: {save_path}")

    return model
```

---

### 4.3 Evaluasi & Validasi Model

```python
def evaluate_model(model, df_test):
    """
    Evaluasi model pada data out-of-sample sebelum deploy ke produksi.
    Gunakan data bulan terakhir yang tidak masuk training set.
    """
    from sklearn.metrics import (
        roc_auc_score, precision_recall_curve,
        average_precision_score, confusion_matrix
    )
    import matplotlib.pyplot as plt

    X_test = df_test[FEATURE_COLS]
    y_test = df_test[TARGET_COL]

    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred_label = (y_pred_proba >= 0.50).astype(int)

    auc = roc_auc_score(y_test, y_pred_proba)
    ap  = average_precision_score(y_test, y_pred_proba)
    cm  = confusion_matrix(y_test, y_pred_label)

    print(f"Test AUC             : {auc:.4f}")
    print(f"Average Precision    : {ap:.4f}")
    print(f"Confusion Matrix:")
    print(f"  TN={cm[0,0]:,}  FP={cm[0,1]:,}")
    print(f"  FN={cm[1,0]:,}  TP={cm[1,1]:,}")

    # Kolom praktis untuk operasional:
    # Precision = dari yang diprediksi "bayar", berapa % yang benar-benar bayar?
    # Recall    = dari semua yang benar-benar bayar, berapa % yang berhasil kita tangkap?

    return {'auc': auc, 'ap': ap, 'confusion_matrix': cm}
```

---

## 5. CONFIDENCE_LEVEL — Formula & Logika

CONFIDENCE_LEVEL **bukan** output langsung dari model ML.
Ini adalah nilai terpisah yang mengukur **seberapa yakin kita dengan RECOVERY_SCORE
yang dihasilkan** — terutama berkaitan dengan kelengkapan dan kedalaman data.

### Tiga Komponen CONFIDENCE_LEVEL

```
CONFIDENCE_LEVEL =
    (A) Data Completeness Score  × 0.40
  + (B) History Depth Score      × 0.35
  + (C) Model Certainty Score    × 0.25
```

**Komponen A — Data Completeness (bobot 40%)**
Mengukur berapa persen dari 5 fitur paling kritikal yang tidak null.
Nasabah baru tanpa historis akan rendah di sini.

**Komponen B — History Depth (bobot 35%)**
Mengukur kedalaman data historis yang tersedia.
Semakin banyak transaksi dan interaksi, semakin reliable score-nya.

**Komponen C — Model Certainty (bobot 25%)**
Mengukur seberapa jauh RECOVERY_SCORE dari titik tengah 0.5 (decision boundary).
Score 0.95 atau 0.05 lebih "yakin" daripada score 0.52.

```
Model Certainty = 2 × |RECOVERY_SCORE − 0.5|

Contoh:
  RECOVERY_SCORE = 0.90  → certainty = 2 × |0.90 − 0.5| = 0.80
  RECOVERY_SCORE = 0.50  → certainty = 2 × |0.50 − 0.5| = 0.00
  RECOVERY_SCORE = 0.20  → certainty = 2 × |0.20 − 0.5| = 0.60
```

### Kode Lengkap

```python
def compute_confidence_level(df):
    """
    Menghitung CONFIDENCE_LEVEL untuk setiap kontrak yang di-score.

    Returns DataFrame dengan kolom tambahan:
      - CONFIDENCE_LEVEL      : float 0.00–1.00
      - CONFIDENCE_CATEGORY   : 'HIGH' / 'MEDIUM' / 'LOW'
      - confidence_completeness : sub-komponen A (untuk debugging)
      - confidence_history      : sub-komponen B
      - confidence_certainty    : sub-komponen C
    """

    # ── (A) DATA COMPLETENESS ─────────────────────────────────────
    # 5 fitur paling kritikal untuk scoring yang akurat
    KEY_FEATURES = [
        'avg_delay_days',          # butuh payment history
        'payment_rate',            # butuh payment history
        'ptp_fulfillment_rate',    # butuh LKP history
        'avg_interaction_score',   # butuh LKP history
        'ptp_reliability_index',   # butuh CBS (lintas kontrak)
    ]
    # Hitung persentase fitur kunci yang tidak null per baris
    completeness = df[KEY_FEATURES].notna().mean(axis=1)   # range: 0.0–1.0

    # ── (B) HISTORY DEPTH ─────────────────────────────────────────
    # payment_count: dinormalisasi ke 0-1 dengan cap di 10 transaksi
    # Asumsi: 10+ transaksi sudah cukup untuk reliable
    payment_depth = (
        df['payment_count'].fillna(0).clip(upper=10) / 10
    )

    # treatment_count: dinormalisasi ke 0-1 dengan cap di 5 interaksi
    treatment_depth = (
        df['treatment_count'].fillna(0).clip(upper=5) / 5
    )

    # Kombinasi keduanya (payment lebih berbobot karena lebih informatif)
    history_score = (
        payment_depth   * 0.60 +
        treatment_depth * 0.40
    ).clip(0, 1)

    # ── (C) MODEL CERTAINTY ───────────────────────────────────────
    # Semakin jauh dari 0.5, semakin tinggi certainty
    certainty = (
        2 * (df['RECOVERY_SCORE'] - 0.5).abs()
    ).clip(0, 1)

    # ── WEIGHTED AVERAGE ──────────────────────────────────────────
    confidence = (
        completeness  * 0.40 +
        history_score * 0.35 +
        certainty     * 0.25
    ).round(4)

    # ── KATEGORISASI (sesuai System Rules Bagian 3.2) ─────────────
    conditions = [
        confidence >= 0.75,
        confidence >= 0.50,
    ]
    choices = ['HIGH', 'MEDIUM']
    category = np.select(conditions, choices, default='LOW')

    # ── ASSIGN KE DATAFRAME ───────────────────────────────────────
    df = df.copy()
    df['confidence_completeness'] = completeness.round(4)   # sub-komponen A
    df['confidence_history']      = history_score.round(4)  # sub-komponen B
    df['confidence_certainty']    = certainty.round(4)      # sub-komponen C
    df['CONFIDENCE_LEVEL']        = confidence
    df['CONFIDENCE_CATEGORY']     = category

    return df
```

### Contoh Output per Nasabah

```
┌────────────────┬────────────────┬──────────────────────────────────────────────────────┐
│ Tipe Nasabah   │ Recovery Score │ Breakdown CONFIDENCE                                 │
├────────────────┼────────────────┼──────────────────────────────────────────────────────┤
│ Nasabah lama   │ 0.82           │ A=1.00 B=0.90 C=0.64 → CONFIDENCE=0.86 (HIGH)       │
│ (data lengkap) │                │ 10+ payment, 5+ interaksi, semua fitur ada           │
├────────────────┼────────────────┼──────────────────────────────────────────────────────┤
│ Nasabah baru   │ 0.61           │ A=0.40 B=0.12 C=0.22 → CONFIDENCE=0.27 (LOW)        │
│ (data minim)   │                │ Baru 1 payment, belum ada interaksi LKP              │
├────────────────┼────────────────┼──────────────────────────────────────────────────────┤
│ Score di       │ 0.51           │ A=0.80 B=0.75 C=0.02 → CONFIDENCE=0.58 (MEDIUM)     │
│ boundary 0.5   │                │ Data ada tapi model tidak yakin — perlu human review │
└────────────────┴────────────────┴──────────────────────────────────────────────────────┘
```

---

## 6. Business Rules — Segment, NBA, Priority

```python
def apply_risk_segment(df):
    """
    RISK_SEGMENT — dievaluasi top-down, first-match wins.
    Sesuai System Rules Bagian 3.3.
    """
    # Won't Pay — harus cek duluan karena paling kritis
    cond_wont_pay = (
        (df['RECOVERY_SCORE'] < 0.30) &
        (
            (df['rejection_count'] >= 2) |
            (df['last_result_code_encoded'] <= 1)   # 0=Menolak, 1=Tidak Bisa Dihubungi
        )
    )

    # Cannot Pay
    cond_cannot_pay = (
        (df['RECOVERY_SCORE'] >= 0.30) &
        (df['RECOVERY_SCORE'] <  0.50) &
        (
            (df['total_ptp_made'].fillna(0) - df['total_ptp_kept'].fillna(0) > 0) |
            (df['income_debt_ratio'].fillna(0) > 2.0)
        )
    )

    # Self-cure — kondisi paling ketat (score tinggi + track record bagus)
    cond_self_cure = (
        (df['RECOVERY_SCORE'] >= 0.70) &
        (df['DPD_CURRENT']    <= 7) &
        (df['payment_rate'].fillna(0) >= 0.80)
    )

    df = df.copy()
    df['RISK_SEGMENT'] = np.select(
        [cond_wont_pay, cond_cannot_pay, cond_self_cure],
        ["Won't Pay",   "Cannot Pay",    "Self-cure"],
        default='Can Pay'
    )
    return df


def apply_nba(df, df_cbs):
    """
    NBA_RECOMMENDATION — berdasarkan RISK_SEGMENT + cycle + OTS.
    Dengan override dari COLLECTION_SENSITIVITY di CBS.
    Sesuai System Rules Bagian 3.4.
    """
    # Ambil channel sensitivity dari CBS
    sensitivity_map = (
        df_cbs.set_index('CUST_ID')['COLLECTION_SENSITIVITY'].to_dict()
    )

    CHANNEL_RANK = {'WA': 1, 'Deskcoll': 2, 'Visit': 3, 'Somasi': 4, 'Pickup': 5}
    THRESHOLD_OTS_RENDAH = 5_000_000   # dari tbl_config
    THRESHOLD_OTS_TINGGI = 20_000_000  # dari tbl_config

    def get_nba_row(row):
        seg   = row['RISK_SEGMENT']
        cycle = row['cycle_encoded']
        ots   = row['total_ots']
        hdc   = row.get('historical_default_count', 0) or 0

        # Tentukan NBA default berdasarkan rules
        if seg == 'Self-cure':
            nba = 'WA'

        elif seg == 'Can Pay':
            nba = 'WA' if cycle <= 1 else 'Deskcoll'

        elif seg == 'Cannot Pay':
            nba = 'Deskcoll' if cycle <= 1 else 'Visit'

        else:   # Won't Pay
            if ots >= THRESHOLD_OTS_TINGGI and hdc >= 2:
                nba = 'Pickup'
            elif ots >= THRESHOLD_OTS_RENDAH:
                nba = 'Somasi'
            else:
                nba = 'Visit'

        # Override: gunakan channel yang terbukti efektif untuk nasabah ini
        # Tapi tidak boleh DOWNGRADE (misal dari Somasi ke WA)
        effective_channel = sensitivity_map.get(row['CUST_ID'])
        if effective_channel:
            current_rank  = CHANNEL_RANK.get(nba, 0)
            effective_rank = CHANNEL_RANK.get(effective_channel, 0)
            if effective_rank > current_rank:
                nba = effective_channel

        return nba

    df = df.copy()
    df['NBA_RECOMMENDATION'] = df.apply(get_nba_row, axis=1)
    return df


def apply_priority(df):
    """
    PRIORITY_LEVEL — matriks RISK_SEGMENT × OTS tier.
    Sesuai System Rules Bagian 3.5.
    """
    THRESHOLD_OTS_RENDAH = 5_000_000
    THRESHOLD_OTS_TINGGI = 20_000_000

    PRIORITY_MATRIX = {
        ("Won't Pay",  'rendah')  : 'High',
        ("Won't Pay",  'menengah'): 'Critical',
        ("Won't Pay",  'tinggi')  : 'Critical',
        ('Cannot Pay', 'rendah')  : 'Medium',
        ('Cannot Pay', 'menengah'): 'High',
        ('Cannot Pay', 'tinggi')  : 'Critical',
        ('Can Pay',    'rendah')  : 'Low',
        ('Can Pay',    'menengah'): 'Medium',
        ('Can Pay',    'tinggi')  : 'High',
        ('Self-cure',  'rendah')  : 'Low',
        ('Self-cure',  'menengah'): 'Low',
        ('Self-cure',  'tinggi')  : 'Medium',
    }

    def get_priority_row(row):
        ots = row['total_ots']
        if ots < THRESHOLD_OTS_RENDAH:
            ots_tier = 'rendah'
        elif ots <= THRESHOLD_OTS_TINGGI:
            ots_tier = 'menengah'
        else:
            ots_tier = 'tinggi'
        return PRIORITY_MATRIX.get((row['RISK_SEGMENT'], ots_tier), 'Medium')

    df = df.copy()
    df['PRIORITY_LEVEL'] = df.apply(get_priority_row, axis=1)
    return df
```

---

## 7. Daily Runner — Satu File Jalankan Semuanya

```python
# daily_scoring.py
# Jalankan setiap malam: python daily_scoring.py
# atau via scheduler (cron / Airflow / etc.)

import pandas as pd
import numpy as np
import joblib
from datetime import datetime
from sqlalchemy import create_engine

# ── CONFIG ────────────────────────────────────────────────────────
DB_URL     = "postgresql://user:password@localhost:5432/collectai"
MODEL_PATH = "models/recovery_model.pkl"
LOG_PATH   = "logs/scoring_log.csv"


def load_data(engine, reference_date):
    """Load semua tabel yang dibutuhkan dari database"""
    print(f"  Loading data for {reference_date}...")
    df_contract = pd.read_sql(
        "SELECT * FROM contract_snapshot WHERE status = 'aktif'", engine
    )
    df_payment  = pd.read_sql("SELECT * FROM payment_history",  engine)
    df_lkp      = pd.read_sql("SELECT * FROM lkp_interaction",  engine)
    df_cbs      = pd.read_sql(
        "SELECT * FROM customer_behavioral_standing", engine
    )
    return df_contract, df_payment, df_lkp, df_cbs


def run_quality_check(df_output):
    """
    QC sebelum publish ke tabel final.
    Sesuai System Rules Bagian 6.
    """
    errors = []
    n = len(df_output)

    # Validasi range
    if not df_output['RECOVERY_SCORE'].between(0, 1).all():
        errors.append("RECOVERY_SCORE ada yang di luar range 0–1")
    if not df_output['CONFIDENCE_LEVEL'].between(0, 1).all():
        errors.append("CONFIDENCE_LEVEL ada yang di luar range 0–1")

    # Validasi distribusi RISK_SEGMENT
    dist = df_output['RISK_SEGMENT'].value_counts(normalize=True)
    if dist.get("Won't Pay", 0) > 0.30:
        errors.append(f"Won't Pay terlalu tinggi: {dist.get(\"Won't Pay\",0):.1%}")
    if dist.get('Self-cure', 0) < 0.05:
        errors.append(f"Self-cure terlalu rendah: {dist.get('Self-cure',0):.1%}")

    # Validasi nilai null di kolom wajib
    for col in ['RISK_SEGMENT', 'NBA_RECOMMENDATION', 'PRIORITY_LEVEL']:
        if df_output[col].isna().any():
            errors.append(f"Ada NULL di kolom wajib: {col}")

    if errors:
        for e in errors:
            print(f"  ⚠️  QC ERROR: {e}")
        raise ValueError("Quality check gagal. Output tidak dipublish.")

    print(f"  ✅ Quality check passed ({n:,} records)")
    return True


def publish_output(df_output, engine):
    """UPSERT ke tabel ai_intelligence_output"""
    output_cols = [
        'CONTRACT_NO', 'CUST_ID',
        'RECOVERY_SCORE', 'CONFIDENCE_LEVEL', 'CONFIDENCE_CATEGORY',
        'RISK_SEGMENT', 'NBA_RECOMMENDATION', 'PRIORITY_LEVEL',
        'SCORING_DATE',
    ]
    df_final = df_output[output_cols].copy()

    # Untuk production: gunakan UPSERT (ON CONFLICT DO UPDATE)
    # Di sini menggunakan replace sebagai simplifikasi
    df_final.to_sql(
        'ai_intelligence_output', engine,
        if_exists='replace', index=False
    )
    print(f"  ✅ Published {len(df_final):,} records to ai_intelligence_output")


def log_run(df_output, reference_date, duration_sec, status):
    """Simpan log setiap run untuk monitoring"""
    dist = df_output['RISK_SEGMENT'].value_counts()
    log_entry = {
        'run_date'       : reference_date,
        'run_timestamp'  : datetime.now(),
        'status'         : status,
        'duration_sec'   : round(duration_sec, 1),
        'total_contracts': len(df_output),
        'n_critical'     : (df_output['PRIORITY_LEVEL'] == 'Critical').sum(),
        'n_self_cure'    : dist.get('Self-cure', 0),
        'n_can_pay'      : dist.get('Can Pay', 0),
        'n_cannot_pay'   : dist.get('Cannot Pay', 0),
        'n_wont_pay'     : dist.get("Won't Pay", 0),
        'avg_score'      : round(df_output['RECOVERY_SCORE'].mean(), 4),
        'avg_confidence' : round(df_output['CONFIDENCE_LEVEL'].mean(), 4),
    }
    pd.DataFrame([log_entry]).to_csv(LOG_PATH, mode='a', header=False, index=False)


# ── MAIN ──────────────────────────────────────────────────────────

def run_daily_scoring(reference_date=None):
    start_time = datetime.now()
    if reference_date is None:
        reference_date = datetime.today().strftime('%Y-%m-%d')

    print(f"\n{'='*60}")
    print(f"  CollectAI Daily Scoring — {reference_date}")
    print(f"{'='*60}")

    engine = create_engine(DB_URL)
    status = 'SUCCESS'

    try:
        # STEP 1: Load data
        print("\n[Step 1] Loading data...")
        df_contract, df_payment, df_lkp, df_cbs = load_data(engine, reference_date)
        print(f"  Contracts : {len(df_contract):,}")
        print(f"  Payments  : {len(df_payment):,}")
        print(f"  LKP rows  : {len(df_lkp):,}")
        print(f"  CBS rows  : {len(df_cbs):,}")

        # STEP 2: Contract-level features
        print("\n[Step 2] Computing contract-level features...")
        features = compute_contract_features(df_contract, df_payment, df_lkp, reference_date)

        # STEP 3: Enrich with CBS
        print("\n[Step 3] Enriching with Customer Behavioral Standing...")
        features_enriched = enrich_with_cbs(features, df_cbs)

        # STEP 4: Load model & scoring
        print("\n[Step 4] Scoring...")
        artifact  = joblib.load(MODEL_PATH)
        model     = artifact['model']
        scores    = model.predict_proba(features_enriched[FEATURE_COLS])[:, 1]
        features_enriched = features_enriched.copy()
        features_enriched['RECOVERY_SCORE'] = scores.round(4)

        # STEP 5: CONFIDENCE_LEVEL
        print("\n[Step 5] Computing confidence levels...")
        scored = compute_confidence_level(features_enriched)

        # STEP 6: Business rules
        print("\n[Step 6] Applying business rules...")
        scored = apply_risk_segment(scored)
        scored = apply_nba(scored, df_cbs)
        scored = apply_priority(scored)
        scored['SCORING_DATE'] = reference_date

        # STEP 7: Quality check
        print("\n[Step 7] Running quality check...")
        run_quality_check(scored)

        # STEP 8: Publish
        print("\n[Step 8] Publishing output...")
        publish_output(scored, engine)

        # Summary
        print(f"\n{'─'*60}")
        print(f"  ✅ DONE — {len(scored):,} contracts scored")
        print(f"\n  RISK SEGMENT BREAKDOWN:")
        for seg, cnt in scored['RISK_SEGMENT'].value_counts().items():
            pct = cnt / len(scored) * 100
            print(f"    {seg:<15} : {cnt:>6,}  ({pct:.1f}%)")
        print(f"\n  PRIORITY BREAKDOWN:")
        for lvl, cnt in scored['PRIORITY_LEVEL'].value_counts().items():
            pct = cnt / len(scored) * 100
            print(f"    {lvl:<10} : {cnt:>6,}  ({pct:.1f}%)")
        print(f"\n  AVG RECOVERY SCORE : {scored['RECOVERY_SCORE'].mean():.4f}")
        print(f"  AVG CONFIDENCE     : {scored['CONFIDENCE_LEVEL'].mean():.4f}")

    except Exception as e:
        status = f'ERROR: {str(e)}'
        print(f"\n  ❌ FAILED: {e}")
        raise

    finally:
        duration = (datetime.now() - start_time).total_seconds()
        print(f"\n  Duration: {duration:.1f}s")
        log_run(scored if status == 'SUCCESS' else pd.DataFrame(),
                reference_date, duration, status)

    return scored


if __name__ == '__main__':
    run_daily_scoring()
```

---

## 8. Dependencies

```
# requirements.txt

# Core ML
xgboost>=1.7.0
scikit-learn>=1.2.0
joblib>=1.2.0

# Data processing
pandas>=1.5.0
numpy>=1.23.0

# Database
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0   # untuk PostgreSQL
# pyodbc>=4.0.0           # untuk SQL Server (uncomment jika diperlukan)

# Optional: tracking & monitoring
# mlflow>=2.0.0           # experiment tracking
# evidently>=0.2.0        # model monitoring & drift detection
```

```bash
# Install
pip install -r requirements.txt

# Jalankan training (sekali, atau saat model perlu diretrain)
python train_model.py

# Jalankan scoring harian
python daily_scoring.py

# Atau via cron (setiap malam jam 23:00)
# 0 23 * * * /usr/bin/python3 /app/daily_scoring.py >> /logs/cron.log 2>&1
```

---

> **Kapan model perlu di-retrain?**
> Retrain secara periodik (bulanan atau kuartalan), atau jika:
> - CV AUC turun lebih dari 0.05 dari baseline
> - Distribusi RISK_SEGMENT berubah drastis selama 2 minggu berturut-turut
> - Ada perubahan produk atau kebijakan collection yang signifikan
> - Tool monitoring (Evidently/MLflow) mendeteksi feature drift