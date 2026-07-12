# app/machine-learning/config/settings.py
# Semua threshold dan konfigurasi CollectAI ML
# Ubah nilai di sini tanpa perlu menyentuh kode bisnis

import os

# ── DATABASE ──────────────────────────────────────────────────────
DB_URL = os.environ.get(
    "COLLECTAI_DB_URL",
    "postgresql://postgres:postgres@localhost:5432/collect_ai",
)

# ── PATH (relatif terhadap folder machine-learning) ───────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

CHAMPION_MODEL_PATH = os.path.join(MODELS_DIR, "recovery_model_champion.pkl")
CHALLENGER_MODEL_PATH = os.path.join(MODELS_DIR, "recovery_model_challenger.pkl")
REGISTRY_PATH = os.path.join(MODELS_DIR, "registry.json")
ARCHIVE_DIR = os.path.join(MODELS_DIR, "archive")
LOG_PATH = os.path.join(LOGS_DIR, "scoring_log.csv")

# ── FEATURE ENGINEERING ───────────────────────────────────────────
PTP_DAYS_WINDOW = 7
DELAY_TREND_WINDOW_MONTHS = 6
LABEL_WINDOW_DAYS = 30

# INCOME PROXY — key cocok dengan nilai customer_master.cust_income_level
INCOME_PROXY = {
    "< 3 Juta":   3_000_000,
    "3-5 Juta":   4_000_000,
    "5-10 Juta":  8_000_000,
    "10-20 Juta": 15_000_000,
    "> 20 Juta":  25_000_000,
    # fallback nama generik
    "Low":  3_000_000,
    "Mid":  8_000_000,
    "High": 20_000_000,
}

# ── OTS THRESHOLD ─────────────────────────────────────────────────
OTS_TIER_RENDAH = 5_000_000
OTS_TIER_TINGGI = 20_000_000

# ── RISK SEGMENT THRESHOLDS ───────────────────────────────────────
SCORE_THRESHOLD_WONT_PAY = 0.30
SCORE_THRESHOLD_CANNOT_PAY = 0.50
SCORE_THRESHOLD_SELF_CURE = 0.70
REJECTION_COUNT_THRESHOLD = 2
MAX_DPD_FOR_SELFCURE = 7
MIN_PAYMENT_RATE_SELFCURE = 0.80
MAX_INCOME_DEBT_RATIO = 2.0

# ── CBS / BEHAVIORAL GRADE ────────────────────────────────────────
GRADE_A_THRESHOLD = 0.80
GRADE_B_THRESHOLD = 0.60
GRADE_C_THRESHOLD = 0.40

WEIGHT_PAYMENT_RATE = 0.30
WEIGHT_PTP_RELIABILITY = 0.25
WEIGHT_INTERACTION = 0.20
WEIGHT_DELAY_SCORE = 0.25
RECENCY_WEIGHT_DECAY = 0.70

BROKEN_PTP_BLACKLIST = 5
HISTORICAL_DEFAULT_BLACKLIST = 3
PTP_RELIABILITY_BLACKLIST = 0.10
MIN_PTP_MADE_FOR_BLACKLIST = 3

# ── MLOPS & MONITORING ────────────────────────────────────────────
AUC_FLOOR = 0.68
N_CRITICAL_DRIFT_TRIGGER = 2
N_WARNING_DRIFT_TRIGGER = 5
SHADOW_DAYS_MIN = 7
MIN_AUC_IMPROVEMENT = 0.02
RETRAIN_DECAY_RATE = 0.70
MIN_SAMPLES_FOR_EVAL = 200

# ── MODEL TRAINING ────────────────────────────────────────────────
XGB_N_ESTIMATORS = 500
XGB_MAX_DEPTH = 6
XGB_LEARNING_RATE = 0.05
XGB_SUBSAMPLE = 0.80
XGB_COLSAMPLE = 0.80
XGB_MIN_CHILD_WEIGHT = 10
XGB_GAMMA = 1.0
XGB_REG_ALPHA = 0.1
XGB_REG_LAMBDA = 1.0
CV_N_SPLITS = 5
MIN_CV_AUC_TO_DEPLOY = 0.50

# Kolom fitur model — JANGAN ubah tanpa retrain
FEATURE_COLS = [
    "dpd_current", "cycle_encoded", "total_ots",
    "payment_rate", "partial_rate", "avg_delay_days",
    "days_since_last_pay", "ptp_fulfillment_rate",
    "avg_interaction_score", "last_result_code_encoded",
    "treatment_count", "rejection_count", "payment_count",
    "ptp_reliability_index", "delay_trend",
    "historical_default_count", "income_debt_ratio",
    "active_contract_count", "total_active_ots",
    "behavioral_grade_encoded", "b_list_flag",
]
TARGET_COL = "actual_paid"

# ── ENCODING MAPS ─────────────────────────────────────────────────
CYCLE_MAP = {"C0": 0, "C1": 1, "C2": 2, "C3": 3, "C3+": 3}
RESULT_CODE_MAP = {
    "Bayar": 4,
    "PTP": 3,
    "Rumah Kosong": 2,
    "Tidak Bisa": 1,
    "Tidak Bisa Dihubungi": 1,
    "Menolak": 0,
}
BEHAVIORAL_GRADE_MAP = {"A": 3, "B": 2, "C": 1, "D": 0}
