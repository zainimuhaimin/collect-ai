# app/machine-learning/config/settings.py
# Semua threshold dan konfigurasi CollectAI ML
# Ubah nilai di sini tanpa perlu menyentuh kode bisnis

import os

# ── DATABASE ──────────────────────────────────────────────────────
DB_URL = os.environ.get(
    "COLLECTAI_DB_URL",
    "postgresql://postgres:123123@localhost:5432/collect_ai",
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

# ── QC DISTRIBUTION THRESHOLDS (run_quality_check) ────────────────
QC_WONT_PAY_MAX_PCT   = 0.30
QC_SELF_CURE_MIN_PCT  = 0.03   # diturunkan dari 0.05 — segmen Self-cure
                                # sekarang mensyaratkan self_cure_probability
                                # >= SELF_CURE_PROB_THRESHOLD sekaligus, jadi
                                # proporsinya wajar lebih kecil dari sebelumnya
QC_CRITICAL_MAX_PCT  = 0.20

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
    # Contract-level LAMA (13 features)
    "dpd_current", "cycle_encoded", "total_ots",
    "payment_rate", "partial_rate", "avg_delay_days",
    "days_since_last_pay", "ptp_fulfillment_rate",
    "avg_interaction_score", "last_result_code_encoded",
    "treatment_count", "rejection_count", "payment_count",

    # Contract-level BARU (9 features)
    "ambc", "ambc_to_ots_ratio", "prev_cycle_encoded",
    "cycle_direction", "days_to_maturity", "recovery_ratio",
    "installment_to_income_ratio", "overdue_installment_count",
    "late_fee_amount",

    # LKP-level BARU (4 features)
    "rpc_rate", "contact_success_rate",
    "ptp_coverage_ratio", "open_ptp_count",

    # Payment-level BARU (2 features)
    "self_cure_rate", "recovery_source_encoded",

    # Customer-level dari CBS (8 features)
    "ptp_reliability_index", "delay_trend",
    "historical_default_count", "income_debt_ratio",
    "active_contract_count", "total_active_ots",
    "behavioral_grade_encoded", "b_list_flag",
]

SELF_CURE_FEATURE_COLS = [
    "dpd_current", "cycle_encoded", "days_to_maturity",
    "payment_rate", "avg_delay_days", "self_cure_rate",
    "ptp_reliability_index", "behavioral_grade_encoded",
    "recovery_ratio", "installment_to_income_ratio",
    "ambc", "ambc_to_ots_ratio",
]

ROLL_FORWARD_FEATURE_COLS = [
    "dpd_current", "cycle_encoded", "prev_cycle_encoded",
    "cycle_direction", "ambc", "ambc_to_ots_ratio",
    "overdue_installment_count", "payment_rate",
    "avg_delay_days", "days_to_maturity",
    "total_ots", "income_debt_ratio",
    "contact_success_rate", "rpc_rate",
]

PTP_SUCCESS_FEATURE_COLS = [
    "ptp_coverage_ratio", "ptp_reliability_index",
    "avg_interaction_score", "rpc_rate",
    "contact_success_rate", "behavioral_grade_encoded",
    "dpd_current", "cycle_encoded", "ambc",
    "b_list_flag", "broken_ptp_count",
]

SELF_CURE_MODEL_PATH    = os.path.join(MODELS_DIR, "self_cure_model.pkl")
ROLL_FORWARD_MODEL_PATH = os.path.join(MODELS_DIR, "roll_forward_model.pkl")
PTP_SUCCESS_MODEL_PATH  = os.path.join(MODELS_DIR, "ptp_success_model.pkl")

SELF_CURE_CHALLENGER_MODEL_PATH    = os.path.join(MODELS_DIR, "self_cure_model_challenger.pkl")
ROLL_FORWARD_CHALLENGER_MODEL_PATH = os.path.join(MODELS_DIR, "roll_forward_model_challenger.pkl")
PTP_SUCCESS_CHALLENGER_MODEL_PATH  = os.path.join(MODELS_DIR, "ptp_success_model_challenger.pkl")

# ── REGISTRY PER MODEL_TYPE ────────────────────────────────────────
# Dipakai oleh model_registry.py & champion_challenger.py supaya ke-4 model
# (recovery + 3 sub-model) punya versioning, path champion/challenger, dan
# alur promote/rollback yang independen satu sama lain.
MODEL_TYPE_PATHS = {
    "recovery":     {"champion": CHAMPION_MODEL_PATH,     "challenger": CHALLENGER_MODEL_PATH},
    "self_cure":    {"champion": SELF_CURE_MODEL_PATH,    "challenger": SELF_CURE_CHALLENGER_MODEL_PATH},
    "roll_forward": {"champion": ROLL_FORWARD_MODEL_PATH, "challenger": ROLL_FORWARD_CHALLENGER_MODEL_PATH},
    "ptp_success":  {"champion": PTP_SUCCESS_MODEL_PATH,  "challenger": PTP_SUCCESS_CHALLENGER_MODEL_PATH},
}

MODEL_TYPE_FEATURE_COLS = {
    "recovery":     FEATURE_COLS,
    "self_cure":    SELF_CURE_FEATURE_COLS,
    "roll_forward": ROLL_FORWARD_FEATURE_COLS,
    "ptp_success":  PTP_SUCCESS_FEATURE_COLS,
}

# Target label yang dipakai tiap model_type saat retrain/evaluate. roll_forward
# dan ptp_success memakai actual_paid sebagai proxy (lihat catatan di
# pipelines/train_roll_forward.py dan train_ptp_success.py) karena populasi
# trainingnya sudah difilter (cycle>=1 / pernah PTP).
MODEL_TYPE_TARGET_COL = {
    "recovery":     "actual_paid",
    "self_cure":    "actual_self_cure",
    "roll_forward": "actual_paid",
    "ptp_success":  "actual_paid",
}

SELF_CURE_PROB_THRESHOLD    = 0.70
ROLL_FORWARD_HIGH_RISK      = 0.75
PTP_SUCCESS_LOW_THRESHOLD   = 0.30

DAYS_TO_MATURITY_SHORT      = 60
LATE_FEE_WAIVER_THRESHOLD   = 500_000

RPC_RATE_LOW_THRESHOLD      = 0.30
CONTACT_SUCCESS_LOW         = 0.20
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
