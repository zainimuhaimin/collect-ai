"""Generate realistic synthetic data for CollectAI.

Design principle: features must be *noisy consequences* of a latent
creditworthiness, never deterministic readouts of it. See the causal DAG below.

The previous version of this script leaked the label badly: it drew DPD_CURRENT
first and then decided the label-window payment with `should_pay = dpd <= 30`,
which made the training label ~a step function of the single strongest feature
(recovery AUC read 0.96). This version inverts that arrow — DPD_CURRENT is a
*child* of the simulated pre-cutoff payment path, and the label-window outcome
is an independent noisy draw from the same latents. dpd stays legitimately
predictive without determining the answer.

Causal DAG
----------
  age, occupation, income ─► S_orig ─► CUST_SEGMENT = bucket(S_orig + noise)
                                └─► (W, C)   W = willingness, C = capacity
                                       │
   product ─► INTEREST_RATE ─┐         │
   income  ─► principal ─────┼─► tenor, INSTALLMENT_AMOUNT, LOAN_AMOUNT,
   months_on_book ──────────-┘         │   MATURITY_DATE   (independent of W,C)
                                       ▼
   monthly process t=1..m: s_t = PHI*s_{t-1} + N(0,SIGMA_S)   (AR(1) distress)
                           p_t = f(W, C, arrears, paid_prev, s_t)
                           ─► payment_history rows, lkp_interaction events,
                              arrears path a_t
                                       │
              ┌────────────────────────┴───────────────────────┐
              ▼                                                ▼
   contract_snapshot as of T_CUT            LABEL DRAW (one more month, same
   (each column + independent noise)        process, fresh shock + noise)

The label draw is a SIBLING of DPD_CURRENT, not a descendant: they share
parents (W, C, s, arrears) but there is no edge between them. The fresh AR(1)
innovation plus an irreducible noise term cap the Bayes-optimal AUC around
0.83, so a well-specified model should land near 0.75.

Point-in-time semantics
-----------------------
contract_snapshot has no snapshot_date column (dropped by design, see
collect-ai-upgrade.md) and the training pipeline does NOT filter it — only
payment_history/lkp_interaction get the `<= feature_cutoff` guard. So this
script must decide what "as of" means, and it generates contract_snapshot as
of T_CUT (= AS_OF - 30d), i.e. from pre-cutoff state only. SNAPSHOT_AS_OF='now'
is kept as a demonstration mode: running the validator in both modes shows the
AUC gap that justifies adding a real point-in-time store upstream.
"""
from __future__ import annotations

import argparse
import math
import os
import random
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from faker import Faker

from helpers.database import append_dataframes_to_postgres, reset_tables

fake = Faker('id_ID')

# ==========================================
# CONFIG
# ==========================================
SEED = int(os.getenv('FAKER_SEED', '20260101'))
NUM_CUSTOMERS = int(os.getenv('FAKER_CUSTOMERS', '2000'))

# Kept in sync with app/machine-learning/config/settings.py LABEL_WINDOW_DAYS.
LABEL_WINDOW_DAYS = 30

# Emit 'Overpaid'? Default False on purpose: outcome_labeler.py only counts
# {'Full','Partial'} as a paid label and feature_engineering.py's payment_rate
# only counts =='Full', so an 'Overpaid' row is invisible to BOTH — it would
# mislabel a good payer as y=0 and depress their payment_rate. Multi-installment
# payments are emitted as one 'Full' row per installment settled instead.
EMIT_OVERPAID = False

# Needs contract_snapshot.status (schema_v5.sql). helpers/database.py drops
# unknown columns with a warning, so leaving this True before the migration
# degrades gracefully rather than failing the load.
EMIT_STATUS = True

# Single knob for label signal strength. 0.0 makes the label a coin flip
# independent of every latent — the placebo test in validate_leakage.py relies
# on this to prove no feature reads the label mechanism itself.
LABEL_SIGNAL_SCALE = float(os.getenv('FAKER_LABEL_SIGNAL', '1.0'))

MAX_MONTHS_ON_BOOK = 30
MIN_MONTHS_ON_BOOK = 6
# Arrears is tracked as a continuous shortfall in installment-equivalents (see
# _simulate_one), capped here before it forces a write-off decision.
ARREARS_CAP = 8.0
WRITE_OFF_PROB = 0.10

# AR(1) distress process
PHI = 0.75
SIGMA_S = 0.50

# Monthly payment propensity. Calibrated (see the numeric checks that produced
# these numbers) so an average-latent customer's backlog stays low across a
# 6-30 month history — the earlier constants left a chronic partial-payer's
# shortfall growing almost every month even though they "paid" every month,
# which skewed the whole portfolio toward >90 DPD.
P_FLOOR, P_CEIL = 0.10, 0.98
B_INTERCEPT = 1.05
B_W, B_C = 0.75, 0.25
B_ARREARS = -0.14
B_PAID_PREV = 0.30

# Label draw. Coefficients calibrated by end-to-end simulation to land at
# ~0.75 grouped-CV AUC with a ~0.83 Bayes ceiling and no single feature > 0.72.
L_W, L_C = 1.30, 0.85
L_ARREARS = -0.10
L_SHOCK = 0.45
L_NOISE_SD = 0.50
TARGET_BASE_RATE = 0.50

LATE_FEE_DAILY_RATE = 0.0005
LATE_FEE_CAP_RATIO = 0.05
GRACE_DAYS_MAX = 4
SELF_CURE_LOOKBACK_DAYS = 15

PRODUCT_INTEREST_RATE_RANGE = {
    # Rate tahunan ilustratif per PRODUCT_TYPE (dipakai restructuring engine
    # untuk hitung amortisasi/haircut — BUKAN fitur model scoring, lihat
    # collect-ai-upgrade.md). Perlu di-review tim finance sebelum production.
    'Motor': (0.18, 0.30),
    'Elektronik & Furnitur': (0.20, 0.36),
    'Haji & Umrah': (0.12, 0.20),
    'Dana Tunai': (0.24, 0.40),
    'Modal Usaha': (0.15, 0.24),
}

PRODUCT_TENOR_RANGE = {
    'Motor': (12, 36),
    'Elektronik & Furnitur': (6, 24),
    'Haji & Umrah': (12, 36),
    'Dana Tunai': (6, 24),
    'Modal Usaha': (12, 36),
}

PRODUCT_TYPES = list(PRODUCT_INTEREST_RATE_RANGE.keys())

# Keys must match app/machine-learning/config/settings.py INCOME_PROXY exactly
# (including the space after '<' / '>') — there is no normalisation upstream, so
# any drift silently falls back to a default income.
INCOME_LEVELS = ['< 3 Juta', '3-5 Juta', '5-10 Juta', '10-20 Juta', '> 20 Juta']
INCOME_WEIGHTS = [0.22, 0.30, 0.28, 0.14, 0.06]
INCOME_PROXY = {
    '< 3 Juta': 3_000_000,
    '3-5 Juta': 4_000_000,
    '5-10 Juta': 8_000_000,
    '10-20 Juta': 15_000_000,
    '> 20 Juta': 25_000_000,
}

OCCUPATIONS = ['Karyawan Swasta', 'PNS/TNI/Polri', 'Wiraswasta', 'Buruh', 'Profesional', 'Lainnya']

# Occupation depends on income band (as in reality), so the latent's observable
# parents are correlated rather than independent.
OCCUPATION_WEIGHTS_BY_INCOME = {
    '< 3 Juta':   [0.20, 0.03, 0.20, 0.42, 0.02, 0.13],
    '3-5 Juta':   [0.33, 0.10, 0.22, 0.22, 0.05, 0.08],
    '5-10 Juta':  [0.38, 0.18, 0.22, 0.06, 0.11, 0.05],
    '10-20 Juta': [0.31, 0.22, 0.24, 0.01, 0.19, 0.03],
    '> 20 Juta':  [0.22, 0.18, 0.30, 0.00, 0.28, 0.02],
}

# Fixed list instead of fake.city_name(): no consumer reads cust_region today,
# but at 2000 customers a free-form city generates ~400 distinct values, which
# would be a landmine for anyone who later one-hot encodes it.
REGIONS = [
    'Jakarta Selatan', 'Jakarta Timur', 'Jakarta Barat', 'Bekasi', 'Depok',
    'Tangerang', 'Bogor', 'Bandung', 'Semarang', 'Surabaya',
    'Yogyakarta', 'Medan', 'Makassar', 'Palembang', 'Denpasar',
]

Z_INCOME = {'< 3 Juta': -0.90, '3-5 Juta': -0.35, '5-10 Juta': 0.15, '10-20 Juta': 0.70, '> 20 Juta': 1.10}
Z_OCC = {
    'PNS/TNI/Polri': 0.55, 'Profesional': 0.35, 'Karyawan Swasta': 0.10,
    'Lainnya': -0.15, 'Wiraswasta': -0.25, 'Buruh': -0.50,
}

CYCLE_DECODE = {0: 'C0', 1: 'C1', 2: 'C2', 3: 'C3+'}

RESULT_NO_CONTACT_FIELD = 'Rumah Kosong'
RESULT_NO_CONTACT_REMOTE = 'Tidak Bisa Dihubungi'
FIELD_CHANNELS = {'Visit', 'Pickup'}
ESCALATED_CHANNELS = {'Visit', 'Somasi', 'Pickup'}

RNG = np.random.default_rng(SEED)


def set_seeds(seed: int) -> None:
    global RNG
    random.seed(seed)
    np.random.seed(seed)
    Faker.seed(seed)
    fake.seed_instance(seed)
    RNG = np.random.default_rng(seed)


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def _round_to(value: float, step: int) -> float:
    if step <= 0:
        return round(float(value), 2)
    return float(int(round(float(value) / step)) * step)


def assign_interest_rate(product_type):
    """Rate tahunan (decimal) untuk satu kontrak, acak dalam rentang wajar
    per PRODUCT_TYPE. Independen dari latent — rate ditentukan saat
    origination oleh kebijakan produk, bukan oleh perilaku bayar nasabah."""
    low, high = PRODUCT_INTEREST_RATE_RANGE.get(product_type, (0.18, 0.30))
    return round(random.uniform(low, high), 4)


# ==========================================
# LATENTS  (never written to any table)
# ==========================================
def draw_customer_latents(income_level, age, occupation):
    """Origination scorecard S_orig plus the two behavioural latents.

    W = willingness (payment discipline, drives timing/delay).
    C = capacity (ability to pay in full, drives partial-vs-full and amounts).

    R^2(S_orig -> W) is only ~0.17: socio-economics is weakly informative, which
    is both realistic and what keeps CUST_SEGMENT (a noisy bucket of S_orig)
    from being a monotone transform of W or C.
    """
    z_age = -0.45 if age < 25 else (0.25 if 30 <= age <= 50 else (-0.20 if age > 60 else 0.0))
    s_orig = (
        0.55 * Z_INCOME[income_level]
        + 0.40 * Z_OCC[occupation]
        + 0.25 * z_age
        + RNG.normal(0.0, 0.55)
    )
    # Correlated willingness/capacity residuals (corr 0.35).
    e_w, e_c = RNG.multivariate_normal([0.0, 0.0], [[1.0, 0.35], [0.35, 1.0]]) * 0.95
    return s_orig, 0.45 * s_orig + e_w, 0.35 * s_orig + e_c


def draw_contract_latents(w_cust, c_cust):
    """Per-contract latents: mostly inherited, partly contract-specific."""
    rho_w, rho_c = 0.80, 0.75
    w = rho_w * w_cust + math.sqrt(1 - rho_w ** 2) * RNG.normal()
    c = rho_c * c_cust + math.sqrt(1 - rho_c ** 2) * RNG.normal()
    return w, c


def _standardise(values):
    arr = np.asarray(values, dtype=float)
    sd = arr.std()
    return (arr - arr.mean()) / (sd if sd > 1e-9 else 1.0)


# ==========================================
# 1. CUSTOMER MASTER
# ==========================================
def generate_customer_master(n):
    rows = []
    raw = []
    for i in range(1, n + 1):
        cust_id = f'CUST-{i:05d}'
        age = int(np.clip(round(RNG.normal(37, 9)), 21, 65))
        income_level = random.choices(INCOME_LEVELS, weights=INCOME_WEIGHTS)[0]
        occupation = random.choices(OCCUPATIONS, weights=OCCUPATION_WEIGHTS_BY_INCOME[income_level])[0]
        s_orig, w_raw, c_raw = draw_customer_latents(income_level, age, occupation)
        raw.append((cust_id, age, income_level, occupation, s_orig, w_raw, c_raw))

    # Standardise across the population so the process coefficients mean the
    # same thing regardless of the sampled socio-economic mix.
    w_std = _standardise([r[5] for r in raw])
    c_std = _standardise([r[6] for r in raw])
    s_std = _standardise([r[4] for r in raw])

    # CUST_SEGMENT is a coarse, NOISY bucket of the origination score — not of
    # W/C, and not of any "will default" flag. The old version discretised the
    # hidden default probability directly, which made it a latent readout.
    noisy = s_std + RNG.normal(0.0, 0.60, size=len(raw))
    lo, hi = np.quantile(noisy, [0.30, 0.75])

    latents = {}
    for idx, (cust_id, age, income_level, occupation, _s, _w, _c) in enumerate(raw):
        score = noisy[idx]
        segment = 'Low Risk' if score >= hi else ('Medium Risk' if score >= lo else 'High Risk')
        rows.append({
            'CUST_ID': cust_id,
            'CUST_NAME': fake.name(),
            'CUST_AGE': age,
            'CUST_OCCUPATION': occupation,
            'CUST_INCOME_LEVEL': income_level,
            'CUST_REGION': random.choice(REGIONS),
            'CUST_PHONE': fake.phone_number(),
            'CUST_SEGMENT': segment,
        })
        latents[cust_id] = {
            's_orig': float(s_std[idx]),
            'w': float(w_std[idx]),
            'c': float(c_std[idx]),
            'income_level': income_level,
        }

    return pd.DataFrame(rows), latents


# ==========================================
# 2. CONTRACT TERMS  (origination only — no DPD/cycle/AMBC here)
# ==========================================
def build_contract_terms(df_cust, latents, as_of):
    """Origination terms, all independent of the behavioural latents.

    This independence is the point: a contract's size, rate, tenor and maturity
    are set by product policy at origination, so features derived from them
    (days_to_maturity, installment_to_income_ratio) should be near-noise. The
    old version derived loan_amount and maturity_date from a latent-driven
    `progress` variable, which turned recovery_ratio into a direct readout of
    the default probability.
    """
    t_cut = as_of - timedelta(days=LABEL_WINDOW_DAYS)
    terms = []

    for _, row in df_cust.iterrows():
        cust_id = row['CUST_ID']
        lat = latents[cust_id]
        income_proxy = INCOME_PROXY[lat['income_level']]
        num_contracts = random.choices([1, 2, 3], weights=[0.65, 0.25, 0.10])[0]

        for j in range(num_contracts):
            contract_no = f"CTR-{cust_id.split('-')[1]}-{j + 1}"
            product_type = random.choice(PRODUCT_TYPES)
            rate = assign_interest_rate(product_type)
            tenor_lo, tenor_hi = PRODUCT_TENOR_RANGE[product_type]
            tenor = random.randint(tenor_lo, tenor_hi)

            principal = _round_to(income_proxy * random.uniform(1.2, 4.5), 100_000)
            monthly_rate = rate / 12.0
            if monthly_rate > 0:
                installment = principal * monthly_rate / (1 - (1 + monthly_rate) ** -tenor)
            else:
                installment = principal / tenor
            installment = _round_to(installment, 1_000)

            months_on_book = random.randint(MIN_MONTHS_ON_BOOK, min(tenor, MAX_MONTHS_ON_BOOK))
            # Schedule phase: spreads due dates across the month so DPD comes out
            # continuous instead of clustering on a handful of values.
            phase = random.randint(1, 29)

            w_ctr, c_ctr = draw_contract_latents(lat['w'], lat['c'])

            # LOAN_AMOUNT is the GROSS contractual obligation (tenor x installment),
            # not the financed principal. feature_engineering.py computes
            # recovery_ratio = (loan_amount - total_ots)/loan_amount; with the
            # principal it goes negative early in the contract and gets clipped to
            # 0, piling up an artificial spike. As gross obligation it is exactly
            # "fraction of the obligation settled" and never clips.
            loan_amount = _round_to(tenor * installment, 1)

            first_due = t_cut - timedelta(days=phase + 30 * (months_on_book - 1))
            maturity = first_due - timedelta(days=30) + timedelta(days=30 * tenor)

            terms.append({
                'contract_no': contract_no,
                'cust_id': cust_id,
                'product_type': product_type,
                'interest_rate': rate,
                'monthly_rate': monthly_rate,
                'tenor': tenor,
                'principal': principal,
                'installment': installment,
                'loan_amount': loan_amount,
                'months_on_book': months_on_book,
                'phase': phase,
                'maturity_date': maturity,
                'w': w_ctr,
                'c': c_ctr,
            })

    return pd.DataFrame(terms)


# ==========================================
# 3. BEHAVIOURAL PATH SIMULATION  (the core)
# ==========================================
def _due_date(t_cut, phase, months_on_book, j):
    """Installment j of m sits at t_cut - phase - 30*(m-j); installment m+1
    lands inside the label window. Every open contract therefore has exactly one
    scheduled installment in the window, so the label never depends on whether a
    due date happened to fall there.

    AS_OF - 30 is deliberately never produced: the feature window (<= AS_OF-30)
    and label window ([AS_OF-30, AS_OF]) share that single day, so it is left
    empty to keep the two strictly disjoint.
    """
    if j <= months_on_book:
        return t_cut - timedelta(days=phase + 30 * (months_on_book - j))
    return t_cut - timedelta(days=phase) + timedelta(days=30)


def _draw_payment_details(w, c, arrears, installment):
    """Given that a payment happens, how much and how late.

    delay is lognormal with a wide sigma so late-payers and on-time payers
    overlap heavily. The old version drew from two non-overlapping ranges
    (0.10-0.40 vs 0.75-0.97), which let payment_rate almost perfectly separate
    the classes.
    """
    p_partial = _sigmoid(-0.85 - 0.75 * c + 0.10 * min(arrears, ARREARS_CAP))
    is_partial = RNG.random() < p_partial
    if is_partial:
        ratio = float(np.clip(0.55 + 0.18 * c + RNG.normal(0, 0.15), 0.10, 0.97))
    else:
        ratio = 1.0
    delay = int(np.clip(math.exp(math.log(9) - 0.50 * w + 0.10 * arrears + RNG.normal(0, 0.80)) - 6, 0, 89))
    amount = _round_to(ratio * installment, 1_000)
    return ratio, delay, amount


def _monthly_pay_prob(w, c, arrears, paid_prev, shock):
    logit = (
        B_INTERCEPT + B_W * w + B_C * c
        + B_ARREARS * arrears + B_PAID_PREV * (1.0 if paid_prev else 0.0)
        + shock
    )
    # The floor/ceiling are load-bearing, not cosmetic: without them deep
    # arrears becomes an absorbing "never pays" state and arrears alone reaches
    # single-feature AUC 0.93. With them, P(y|dpd bucket) declines gradually.
    return P_FLOOR + (P_CEIL - P_FLOOR) * _sigmoid(logit)


def _simulate_path(term, t_cut, as_of):
    """Simulate one contract's monthly payment path THROUGH T_CUT — everything
    that feeds contract_snapshot/payment_history/lkp_interaction, but stops
    short of the label-window draw (see `_draw_label` below). Split out so
    `_solve_mu_label` can freeze this stochastic part once per contract and
    bisect the label intercept as a deterministic function of `mu` alone —
    otherwise re-simulating the whole path fresh for every bisection candidate
    makes the "rate" being optimized pure noise, not a monotone function of
    `mu`, and the bisection converges to whatever it happens to land on.

    `backlog` is a SINGLE continuous shortfall tracker, in installment-
    equivalent units (e.g. backlog=2.3 means "2.3 installments behind"). An
    earlier version tracked two separate things — a bounded arrears counter
    (incremented only on a complete miss) and an unbounded FIFO queue of
    unpaid due dates (for DPD) — and they diverged badly: a customer who pays
    SOMETHING every month (e.g. consistently 40% of the installment) never
    incremented the arrears counter at all, since that only fired on a full
    miss, while the FIFO queue kept growing almost every month anyway. That
    skewed the whole population toward extreme DPD. `backlog` fixes this by
    accruing the actual shortfall (1 - ratio) every month regardless of
    whether some payment was made, which is what "days past due" mechanically
    means for an amortizing loan.
    """
    w, c = term['w'], term['c']
    installment = term['installment']
    m = int(term['months_on_book'])
    phase = int(term['phase'])
    tenor = int(term['tenor'])

    shock = RNG.normal(0.0, SIGMA_S / math.sqrt(1 - PHI ** 2))
    backlog = 0.0
    paid_prev = True
    k_paid = 0
    status = 'aktif'
    schedule = []
    backlog_by_month = []

    for j in range(1, m + 1):
        shock = PHI * shock + RNG.normal(0.0, SIGMA_S)
        due = _due_date(t_cut, phase, m, j)

        pays = RNG.random() < _monthly_pay_prob(w, c, min(backlog, ARREARS_CAP), paid_prev, shock)
        entry = {'j': j, 'due_date': due, 'settled': False}

        if pays:
            ratio, delay, amount = _draw_payment_details(w, c, backlog, installment)
            pay_date = due + timedelta(days=delay)
            if pay_date == t_cut:
                # t_cut is the shared boundary of the feature window (<= t_cut)
                # and the label window (>= t_cut) in the real pipeline
                # (feature_engineering.py / outcome_labeler.py both use
                # inclusive comparisons at this exact date) — nudge strictly
                # before it so a pre-cutoff schedule payment never straddles
                # both windows at once.
                pay_date -= timedelta(days=1)
            # Right-censoring: a payment that would land after AS_OF simply has
            # not happened yet. The old version emitted it anyway, producing
            # actual_pay_date up to ~70 days in the future.
            if pay_date > as_of:
                pays = False
            else:
                entry.update({'settled': True, 'pay_date': pay_date, 'amount': amount,
                              'ratio': ratio, 'delay': delay})
                if ratio >= 0.98:
                    k_paid += 1
                    if backlog > 1.0:
                        # Full payment clears the current installment PLUS a
                        # catch-up on the backlog — what lets a customer
                        # genuinely recover instead of the backlog only ever
                        # growing.
                        catchup = 1 + int(RNG.poisson(max(0.0, 1.10 + 0.70 * c)))
                        backlog = max(0.0, backlog - catchup)
                    else:
                        backlog = max(0.0, backlog - 1.0)
                else:
                    backlog = max(0.0, backlog + (1.0 - ratio))

        if not pays:
            backlog += 1.0

        paid_prev = entry['settled']
        schedule.append(entry)
        backlog_by_month.append(backlog)

        if backlog > ARREARS_CAP:
            if RNG.random() < WRITE_OFF_PROB:
                status = 'write-off'
                break
            backlog = ARREARS_CAP
            backlog_by_month[-1] = backlog

    a_cut = backlog
    a_prev = backlog_by_month[-2] if len(backlog_by_month) >= 2 else backlog
    if k_paid >= tenor:
        status = 'lunas'

    # DPD derives directly from the bounded backlog: each whole installment of
    # shortfall corresponds to roughly one due-date cycle (~30 days), with
    # `phase` giving within-cycle granularity so DPD comes out continuous
    # rather than clustering at multiples of 30.
    dpd_cut = 0
    whole_behind = int(a_cut)
    if status != 'lunas' and whole_behind >= 1:
        grace = random.randint(0, GRACE_DAYS_MAX)
        dpd_cut = max(0, phase + 30 * (whole_behind - 1) - grace)
        dpd_cut = min(dpd_cut, 260)

    return {
        'contract_no': term['contract_no'],
        'schedule': schedule,
        'backlog_by_month': backlog_by_month,
        'a_cut': a_cut,
        'a_prev': a_prev,
        'whole_behind': whole_behind,
        'dpd_cut': dpd_cut,
        'k_paid': min(k_paid, tenor),
        'shock_cut': shock,
        'status': status,
    }


def _draw_label(term, pre, t_cut, as_of, mu_label):
    """Label-window draw — shares parents with dpd_cut (w, c, backlog, shock)
    but there is NO edge from dpd_cut to here. The fresh shock innovation plus
    L_NOISE_SD are what keep the Bayes ceiling around 0.83."""
    w, c = term['w'], term['c']
    installment = term['installment']
    m = int(term['months_on_book'])
    phase = int(term['phase'])
    a_cut = pre['a_cut']
    whole_behind = pre['whole_behind']
    k_paid = pre['k_paid']

    label_events = []
    y_pay = False
    p_label = 0.0
    if pre['status'] == 'aktif':
        shock_label = PHI * pre['shock_cut'] + RNG.normal(0.0, SIGMA_S)
        signal = LABEL_SIGNAL_SCALE * (
            L_W * w + L_C * c + L_ARREARS * a_cut + L_SHOCK * shock_label
        )
        p_label = _sigmoid(mu_label + signal + RNG.normal(0.0, L_NOISE_SD))
        y_pay = RNG.random() < p_label
        if y_pay:
            target_due = (
                _due_date(t_cut, phase, m, m - whole_behind + 1)
                if whole_behind >= 1
                else _due_date(t_cut, phase, m, m + 1)
            )
            ratio, _delay, amount = _draw_payment_details(w, c, a_cut, installment)
            # Bias toward the middle of the window so ±5 days of drift between
            # generation date and training reference_date keeps most labels.
            offset = random.randint(6, 24)
            pay_date = as_of - timedelta(days=offset)
            label_events.append({
                'due_date': target_due, 'pay_date': pay_date, 'amount': amount, 'ratio': ratio,
                'delay': max(0, (pay_date - target_due).days),
            })
            if ratio >= 0.98:
                k_paid += 1
    elif pre['status'] == 'lunas':
        # Half of the payoffs land inside the window so 'lunas' is not a
        # deterministic negative class (which would be a brand-new leak).
        if RNG.random() < 0.50:
            ratio, _d, amount = _draw_payment_details(w, c, 0, installment)
            pay_date = as_of - timedelta(days=random.randint(6, 24))
            due = _due_date(t_cut, phase, m, m + 1)
            label_events.append({'due_date': due, 'pay_date': pay_date, 'amount': amount,
                                 'ratio': 1.0, 'delay': max(0, (pay_date - due).days)})
            y_pay = True
    elif pre['status'] == 'write-off':
        # A small, FIXED (not LABEL_SIGNAL_SCALE-scaled) chance of an
        # out-of-band recovery — legal action, a late settlement — so
        # write-off isn't a deterministic non-payer. Making this unconditional
        # (y_pay=False always) would mean "backlog high enough to write off"
        # acts as an extra, LABEL_SIGNAL_SCALE-independent channel linking
        # dpd/backlog to the label — confirmed by the placebo test
        # (label_signal=0 should give ~0.50 CV AUC; a hard-coded non-payment
        # for the whole write-off tail pulled it well above that).
        if RNG.random() < 0.06:
            ratio, _d, amount = _draw_payment_details(w, c, 0, installment)
            pay_date = as_of - timedelta(days=random.randint(6, 24))
            due = _due_date(t_cut, phase, m, m + 1)
            label_events.append({'due_date': due, 'pay_date': pay_date, 'amount': amount,
                                 'ratio': ratio, 'delay': max(0, (pay_date - due).days)})
            y_pay = True

    return label_events, y_pay, p_label, k_paid


def _simulate_one(term, t_cut, as_of, mu_label):
    pre = _simulate_path(term, t_cut, as_of)
    label_events, y_pay, p_label, k_paid = _draw_label(term, pre, t_cut, as_of, mu_label)
    result = dict(pre)
    result['k_paid'] = min(k_paid, int(term['tenor']))
    result['label_events'] = label_events
    result['y_pay'] = y_pay
    result['p_label'] = p_label
    return result


def _solve_mu_label(df_terms, t_cut, as_of, sample_size=800):
    """Bisect the label intercept so the realised base rate lands near 0.50.

    The pre-label path (and its randomness) is frozen ONCE per sampled
    contract via `_simulate_path`; only the label OFFSET's noise and the
    Bernoulli threshold draw are frozen per contract too (`offsets`/`uniforms`
    below), so `rate(mu)` inside the loop is a pure, monotonically
    non-decreasing function of `mu` — no RNG calls happen inside the bisection
    itself. Re-simulating a fresh stochastic path per candidate `mu` (the
    earlier approach) made `rate` noisy rather than monotone, so bisection
    could converge anywhere.
    """
    if LABEL_SIGNAL_SCALE == 0.0:
        return 0.0

    sample = df_terms.sample(n=min(sample_size, len(df_terms)), random_state=SEED)
    offsets = []
    uniforms = []
    for _, term in sample.iterrows():
        pre = _simulate_path(term, t_cut, as_of)
        if pre['status'] != 'aktif':
            continue
        shock_label = PHI * pre['shock_cut'] + RNG.normal(0.0, SIGMA_S)
        signal = LABEL_SIGNAL_SCALE * (
            L_W * term['w'] + L_C * term['c'] + L_ARREARS * pre['a_cut'] + L_SHOCK * shock_label
        )
        offsets.append(signal + RNG.normal(0.0, L_NOISE_SD))
        uniforms.append(RNG.random())

    if not offsets:
        return 0.0
    offsets = np.array(offsets)
    uniforms = np.array(uniforms)

    lo, hi = -8.0, 8.0
    for _ in range(40):
        mid = (lo + hi) / 2
        rate = float(np.mean(uniforms < _sigmoid_vec(mid + offsets)))
        if rate < TARGET_BASE_RATE:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _sigmoid_vec(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def simulate_contract_paths(df_terms, t_cut, as_of):
    mu_label = _solve_mu_label(df_terms, t_cut, as_of)
    paths = {}
    for _, term in df_terms.iterrows():
        paths[term['contract_no']] = _simulate_one(term, t_cut, as_of, mu_label)
    return paths, mu_label


# ==========================================
# 4. LKP INTERACTION
# ==========================================
INTENSITY_BY_ARREARS = {0: 0.30, 1: 1.5, 2: 2.5}
INTENSITY_DEEP = 3.5

CHANNEL_MIX = [
    # (max_dpd, channels, weights)
    # SMS merged into WA (decision #7, ai-reasoning-api-upgrade-tasks.md P0-1):
    # its share is reallocated onto WA rather than dropped, so bucket C0/C1
    # interaction volume doesn't shrink and the distribution stays realistic.
    (0, ['WA', 'Deskcoll'], [0.90, 0.10]),
    (30, ['WA', 'Deskcoll', 'Visit'], [0.55, 0.40, 0.05]),
    (60, ['Deskcoll', 'Visit', 'WA', 'Somasi'], [0.40, 0.40, 0.15, 0.05]),
    (90, ['Visit', 'Somasi', 'Deskcoll', 'Pickup'], [0.45, 0.30, 0.15, 0.10]),
]
CHANNEL_MIX_DEEP = (['Pickup', 'Somasi', 'Visit', 'Deskcoll'], [0.35, 0.35, 0.25, 0.05])

CHANNEL_CONTACT_EFFECT = {'WA': 0.35, 'Deskcoll': 0.30, 'Visit': 0.10, 'Somasi': -0.10, 'Pickup': -0.25}

RESULT_SCORE_BASE = {
    'Bayar': (4, 5), 'PTP': (3, 4), 'Tidak Bisa': (2, 3),
    'Menolak': (1, 2), RESULT_NO_CONTACT_FIELD: (1, 1), RESULT_NO_CONTACT_REMOTE: (1, 1),
}


def _pick_channel(dpd_at_time, escalated):
    for max_dpd, channels, weights in CHANNEL_MIX:
        if dpd_at_time <= max_dpd:
            picked = random.choices(channels, weights=weights)[0]
            break
    else:
        picked = random.choices(*CHANNEL_MIX_DEEP)[0]
    # Somasi ratchet: once a formal demand letter has gone out, collections does
    # not drop back to a WhatsApp reminder.
    if escalated and picked not in ESCALATED_CHANNELS:
        picked = random.choices(['Visit', 'Somasi', 'Pickup'], weights=[0.45, 0.35, 0.20])[0]
    return picked


def _draw_result(w, c, arrears, channel, has_payment_soon, contactability=0.0):
    # `contactability` is a per-contract random effect independent of arrears
    # (e.g. a wrong/updated phone number, works from home vs. a hard-to-reach
    # job) — without it, event VOLUME and contact FAILURE RATE are driven by
    # the exact same "how delinquent is this account" signal, so the two
    # counts move together almost mechanically even though they're measuring
    # different things.
    p_contact = _sigmoid(1.00 + 0.50 * w - 0.25 * arrears + contactability + CHANNEL_CONTACT_EFFECT.get(channel, 0.0))
    if RNG.random() > p_contact:
        if channel in FIELD_CHANNELS:
            return RESULT_NO_CONTACT_FIELD, False, False
        return RESULT_NO_CONTACT_REMOTE, False, False

    logits = {
        'Bayar': 0.7 * w + 0.6 * c,
        'PTP': 0.5 * w - 0.2 * c + 0.3,
        'Menolak': -0.9 * w,
        'Tidak Bisa': -0.9 * c + 0.3 * w,
    }
    if not has_payment_soon:
        # 'Bayar' must correspond to money actually arriving, otherwise the code
        # becomes a readout of the latent rather than a record of an event.
        logits.pop('Bayar')
    keys = list(logits)
    exp = np.exp(np.array([logits[k] for k in keys], dtype=float))
    result = str(RNG.choice(keys, p=exp / exp.sum()))
    rpc = RNG.random() < (0.90 if channel in {'WA', 'Deskcoll'} else 0.80)
    return result, True, rpc


def generate_lkp_history(df_terms, paths, t_cut, as_of):
    rows = []
    lkp_counter = 1
    terms_by_no = {t['contract_no']: t for _, t in df_terms.iterrows()}

    for contract_no, path in paths.items():
        term = terms_by_no[contract_no]
        w, c = term['w'], term['c']
        installment = term['installment']
        schedule = path['schedule']
        backlog_by_month = path['backlog_by_month']
        escalated = False
        collector_pool = [f"COLL-{random.randint(1, 50):03d}" for _ in range(2)]
        collector_effect = {cid: RNG.normal(0, 0.5) for cid in collector_pool}
        contactability = float(RNG.normal(0.0, 1.1))

        for idx, entry in enumerate(schedule):
            due = entry['due_date']
            arrears_at = backlog_by_month[idx]
            next_due = schedule[idx + 1]['due_date'] if idx + 1 < len(schedule) else due + timedelta(days=30)

            events = []
            # Pre-due courtesy reminder — this is what gives even a perfectly
            # current contract some pre-cutoff interaction history. Without it,
            # the feature cutoff strips every interaction from low-DPD contracts
            # and treatment_count/rpc_rate collapse to 0 exactly for the payers.
            if RNG.random() < 0.30:
                events.append(due - timedelta(days=3))

            base = INTENSITY_BY_ARREARS.get(min(int(round(arrears_at)), 3), INTENSITY_DEEP)
            n_events = min(5, int(RNG.poisson(base * random.uniform(0.7, 1.3))))
            span_lo = due + timedelta(days=1)
            span_hi = min(next_due, as_of)
            if span_hi > span_lo:
                span = (span_hi - span_lo).days
                for _ in range(n_events):
                    events.append(span_lo + timedelta(days=random.randint(0, max(0, span))))

            for action_date in sorted(events):
                if action_date > as_of or action_date == as_of - timedelta(days=LABEL_WINDOW_DAYS):
                    continue
                dpd_at_time = max(0, (action_date - due).days) if arrears_at > 0 else 0
                channel = _pick_channel(dpd_at_time, escalated)
                if channel in {'Somasi', 'Pickup'}:
                    escalated = True

                has_payment_soon = entry.get('settled') and entry.get('pay_date') is not None and (
                    0 <= (entry['pay_date'] - action_date).days <= 3
                )
                result, contact_success, rpc = _draw_result(w, c, arrears_at, channel, has_payment_soon, contactability)

                lo, hi = RESULT_SCORE_BASE[result]
                cid = random.choice(collector_pool)
                score = int(np.clip(random.randint(lo, hi) + round(collector_effect[cid]), 1, 5))

                promise_date = None
                ptp_amount = None
                ptp_status = None
                if result == 'PTP':
                    promise_date = action_date + timedelta(days=random.randint(3, 14))
                    ambc_at_time = max(installment, arrears_at * installment)
                    coverage = float(np.clip(RNG.beta(3, 4) + 0.35 * _sigmoid(c) - 0.10, 0.10, 1.30))
                    ptp_amount = _round_to(max(100_000.0, ambc_at_time * coverage), 50_000)
                    # Point-in-time: a promise still in the future as of the
                    # snapshot is OPEN, so PTP_STATUS can never encode a
                    # label-window payment. The old version set it directly from
                    # the hidden will_default flag.
                    if promise_date > t_cut:
                        ptp_status = 'OPEN'
                    else:
                        window_lo = promise_date - timedelta(days=2)
                        window_hi = promise_date + timedelta(days=7)
                        kept = any(
                            e.get('settled') and e.get('pay_date') is not None
                            and window_lo <= e['pay_date'] <= window_hi
                            for e in schedule
                        )
                        ptp_status = 'KEPT' if kept else 'BROKEN'

                rows.append({
                    'LKP_ID': f"LKP-{lkp_counter:06d}",
                    'CONTRACT_NO': contract_no,
                    'ACTION_DATE': action_date.strftime('%Y-%m-%d'),
                    'TREATMENT_TYPE': channel,
                    'RESULT_CODE': result,
                    'PROMISE_DATE': promise_date.strftime('%Y-%m-%d') if promise_date else None,
                    'COLLECTOR_ID': cid,
                    'INTERACTION_SCORE': score,
                    'PTP_AMOUNT': ptp_amount,
                    'PTP_STATUS': ptp_status,
                    'RPC_FLAG': bool(rpc),
                    'CONTACT_SUCCESS_FLAG': bool(contact_success),
                })
                lkp_counter += 1

    return pd.DataFrame(rows)


# ==========================================
# 5. PAYMENT HISTORY
# ==========================================
TREATMENT_TO_SOURCE = {
    'WA': 'WA', 'Deskcoll': 'Deskcoll',
    'Visit': 'Visit', 'Somasi': 'Somasi', 'Pickup': 'Somasi',
}
PAY_METHODS = ['Autodebet', 'VA', 'Kasir', 'Transfer Bank', 'COD']


def _pick_recovery_source(lkp_lookup, contract_no, pay_date):
    """Channel yang benar-benar berinteraksi sebelum nasabah bayar."""
    history = lkp_lookup.get(contract_no)
    if not history:
        return None
    prior = [t for d, t in history if d <= pay_date]
    if prior:
        return TREATMENT_TO_SOURCE.get(prior[-1], 'Deskcoll')
    return TREATMENT_TO_SOURCE.get(history[0][1], 'Deskcoll')


def _status_from_ratio(amount, installment):
    r = amount / installment if installment else 1.0
    if r > 1.02:
        return 'Overpaid' if EMIT_OVERPAID else 'Full'
    return 'Full' if r >= 0.98 else 'Partial'


def generate_payment_history(df_terms, paths, lkp_lookup, interactions_by_contract):
    rows = []
    counter = 1
    terms_by_no = {t['contract_no']: t for _, t in df_terms.iterrows()}

    for contract_no, path in paths.items():
        installment = terms_by_no[contract_no]['installment']
        method_pref = random.choice(PAY_METHODS)
        events = [e for e in path['schedule'] if e.get('settled')] + path['label_events']

        for entry in events:
            due = entry['due_date']
            pay_date = entry['pay_date']
            amount = entry['amount']
            delay = max(0, (pay_date - due).days)

            # Derived, not drawn: a payment is "self-cured" when it arrived
            # without a collector touching the account recently. The old version
            # used `delay <= 7`, which made self_cure_rate a deterministic
            # function of avg_delay_days — two model features, one variable.
            recent = interactions_by_contract.get(contract_no, [])
            touched = any(
                (pay_date - timedelta(days=SELF_CURE_LOOKBACK_DAYS)) <= d <= pay_date for d in recent
            )
            self_cure = not touched
            if RNG.random() < 0.10:
                self_cure = not self_cure

            rows.append({
                'PAYMENT_ID': f"PAY-{counter:07d}",
                'CONTRACT_NO': contract_no,
                'DUE_DATE': due.strftime('%Y-%m-%d'),
                'ACTUAL_PAY_DATE': pay_date.strftime('%Y-%m-%d'),
                'PAYMENT_AMOUNT': amount,
                'PAY_STATUS': _status_from_ratio(amount, installment),
                'PAY_METHOD': method_pref if RNG.random() < 0.80 else random.choice(PAY_METHODS),
                'DELAY_DAYS': delay,
                'SELF_CURE_FLAG': bool(self_cure),
                'RECOVERY_SOURCE': None if self_cure else _pick_recovery_source(lkp_lookup, contract_no, pay_date),
            })
            counter += 1

    return pd.DataFrame(rows)


# ==========================================
# 6. CONTRACT SNAPSHOT  (assembled from the path, as of T_CUT)
# ==========================================
def _cycle_from_arrears(arrears):
    bucket = min(int(round(arrears)), 3)
    label = CYCLE_DECODE.get(bucket, 'C3+')
    # Month-end cutoff and data-entry noise: cycle is NOT a pure step function
    # of dpd, so cycle_encoded stops being a clean copy of dpd_current.
    if RNG.random() < 0.07:
        shifted = int(np.clip(bucket + random.choice([-1, 1]), 0, 3))
        label = CYCLE_DECODE[shifted]
    return label


def assemble_contract_snapshot(df_terms, paths, snapshot_as_of):
    rows = []
    for _, term in df_terms.iterrows():
        contract_no = term['contract_no']
        path = paths[contract_no]
        installment = term['installment']
        principal = term['principal']
        tenor = int(term['tenor'])
        monthly_rate = term['monthly_rate']

        a_cut = path['a_cut']
        dpd = path['dpd_cut']
        k_paid = path['k_paid']

        if snapshot_as_of == 'now':
            # Demo mode only: folds the label-window outcome into the snapshot,
            # which is exactly the leakage the 'cutoff' default avoids.
            if path['y_pay']:
                a_cut = max(0, a_cut - 1)
                dpd = max(0, dpd - 30)

        # True amortisation residual rather than a flat 10% of principal.
        if monthly_rate > 0 and k_paid < tenor:
            prnc_ots = principal * (
                ((1 + monthly_rate) ** tenor - (1 + monthly_rate) ** k_paid)
                / ((1 + monthly_rate) ** tenor - 1)
            )
        else:
            prnc_ots = max(0.0, principal * (1 - k_paid / tenor))
        prnc_ots = max(0.0, _round_to(prnc_ots, 1_000))
        intr_ots = max(0.0, _round_to((tenor - k_paid) * installment - prnc_ots, 1_000))
        total_ots = prnc_ots + intr_ots

        # Late fees accrue per overdue installment with waivers, so the value is
        # no longer a bijection with dpd (it used to be exactly dpd * 10000).
        # Installments behind are staggered in age (oldest = dpd, newest ~ a
        # few days), so the average overdue-days across all of them is
        # approximated as a fraction of the oldest installment's age rather
        # than assuming every unpaid installment is exactly `dpd` days late.
        whole_behind = int(a_cut)
        avg_days_overdue = dpd * 0.6
        gross_fee = min(
            whole_behind * installment * LATE_FEE_DAILY_RATE * avg_days_overdue,
            LATE_FEE_CAP_RATIO * principal,
        )
        roll = RNG.random()
        if roll < 0.25:
            late_fee = 0.0
        elif roll < 0.40:
            late_fee = _round_to(gross_fee * random.uniform(0.3, 0.7), 1_000)
        else:
            late_fee = _round_to(gross_fee, 1_000)

        # AMBC has a floor at the current installment when the account is
        # current, except for accounts already collected by autodebet. This
        # breaks the old `ambc == 0 <=> dpd == 0` biconditional. `a_cut` is
        # already the full continuous backlog (whole + fractional installments).
        if whole_behind == 0:
            ambc = 0.0 if RNG.random() < 0.15 else installment
        else:
            # Wide multiplier (not a narrow +/-5%) so AMBC carries real
            # independent variation instead of being a near-exact linear
            # rescaling of the same backlog that drives DPD_CURRENT — a
            # negotiated adjustment, a fee reassessment, a partial not yet
            # netted, etc.
            ambc = _round_to((a_cut * installment + late_fee) * random.uniform(0.75, 1.35), 1_000)
        ambc = min(ambc, total_ots) if total_ots > 0 else 0.0

        # Independent reporting-lag noise: the count of overdue installments
        # doesn't always move in perfect lockstep with the backlog that
        # drives DPD_CURRENT (a payment can settle mid-cycle before the count
        # is refreshed, or a grace-period installment isn't counted yet).
        overdue_count = whole_behind
        if RNG.random() < 0.30:
            overdue_count = max(0, overdue_count + random.choice([-1, 1]))
        if whole_behind >= 3 and RNG.random() < 0.15:
            overdue_count = max(0, overdue_count + random.choice([-2, 2]))

        row = {
            'CONTRACT_NO': contract_no,
            'CUST_ID': term['cust_id'],
            'DPD_CURRENT': int(dpd),
            'PRNC_OTS': prnc_ots,
            'INTR_OTS': intr_ots,
            'CYCLE': _cycle_from_arrears(a_cut),
            'PRODUCT_TYPE': term['product_type'],
            'INTEREST_RATE': term['interest_rate'],
            'AMBC': ambc,
            'PREV_CYCLE': _cycle_from_arrears(path['a_prev']),
            'LOAN_AMOUNT': term['loan_amount'],
            'INSTALLMENT_AMOUNT': installment,
            'MATURITY_DATE': term['maturity_date'].strftime('%Y-%m-%d'),
            'OVERDUE_INSTALLMENT_COUNT': overdue_count,
            'LATE_FEE_AMOUNT': late_fee,
        }
        if EMIT_STATUS:
            row['STATUS'] = path['status']
        rows.append(row)

    return pd.DataFrame(rows)


# ==========================================
# DIAGNOSTICS
# ==========================================
def print_diagnostics(df_contract, paths, as_of, mu_label):
    dpd = df_contract['DPD_CURRENT']
    labels = {cn: p['y_pay'] for cn, p in paths.items()}
    base_rate = float(np.mean(list(labels.values())))

    print(f"\n  reference_date untuk training : {as_of.isoformat()}")
    print(f"  feature_cutoff               : {(as_of - timedelta(days=LABEL_WINDOW_DAYS)).isoformat()}")
    print(f"  mu_label (solved)            : {mu_label:.4f}")
    print(f"  base label rate              : {base_rate:.4f}")
    print(f"  distinct DPD values          : {dpd.nunique()}")

    buckets = [(0, 0, 'dpd 0'), (1, 30, '1-30'), (31, 60, '31-60'), (61, 90, '61-90'), (91, 10**6, '>90')]
    print("\n  P(y=1 | dpd bucket)  — should decline gradually, no cliff:")
    for lo, hi, name in buckets:
        sel = df_contract[(dpd >= lo) & (dpd <= hi)]['CONTRACT_NO']
        if len(sel) == 0:
            continue
        vals = [labels[c] for c in sel if c in labels]
        share = 100.0 * len(sel) / len(df_contract)
        if vals:
            print(f"    {name:>6}: n={len(vals):5d} ({share:4.1f}%)  P(y=1)={np.mean(vals):.3f}")

    if EMIT_STATUS and 'STATUS' in df_contract.columns:
        print(f"\n  status: {df_contract['STATUS'].value_counts().to_dict()}")


# ==========================================
# MAIN
# ==========================================
def main(argv=None):
    global NUM_CUSTOMERS, SEED, EMIT_STATUS, LABEL_SIGNAL_SCALE

    parser = argparse.ArgumentParser(description='Generate realistic synthetic data for CollectAI.')
    parser.add_argument('--seed', type=int, default=SEED)
    parser.add_argument('--customers', type=int, default=NUM_CUSTOMERS)
    parser.add_argument('--as-of', type=str, default=None, help='YYYY-MM-DD (default: today)')
    parser.add_argument('--snapshot-as-of', choices=['cutoff', 'now'], default='cutoff')
    parser.add_argument('--label-signal', type=float, default=LABEL_SIGNAL_SCALE,
                        help='0.0 = placebo (label independent of all latents)')
    parser.add_argument('--reset', action='store_true', help='TRUNCATE target tables before loading')
    parser.add_argument('--no-db', action='store_true')
    parser.add_argument('--no-excel', action='store_true')
    parser.add_argument('--dump-latents', action='store_true',
                        help='Write _audit_latents.parquet for the leakage validator')
    parser.add_argument('--dump-schedule', action='store_true',
                        help='Write _installment_schedule.parquet (atau tabel '
                        '{prefix}installment_schedule kalau --no-db tidak dipakai): '
                        'due_date penuh per angsuran (termasuk yang belum dibayar) — '
                        'dipakai TASK-S2 (scripts/simulate_days.py) untuk menghitung '
                        'overdue/DPD dari payment_history yang disuap bertahap.')
    parser.add_argument('--table-prefix', type=str, default='',
                        help='Prefiks nama tabel tujuan DB, mis. "stg_" untuk menulis '
                        'ke stg_customer_master dkk alih-alih tabel live (TASK-S2). '
                        'Tabel ML derivatif TIDAK ikut di-reset saat prefix dipakai.')
    args = parser.parse_args(argv)

    SEED = args.seed
    NUM_CUSTOMERS = args.customers
    LABEL_SIGNAL_SCALE = args.label_signal
    set_seeds(SEED)

    as_of = datetime.strptime(args.as_of, '%Y-%m-%d').date() if args.as_of else date.today()
    t_cut = as_of - timedelta(days=LABEL_WINDOW_DAYS)

    print('=' * 60)
    print('Generating REALISTIC data for CollectAI...')
    print(f'  seed={SEED}  customers={NUM_CUSTOMERS}  as_of={as_of}')
    print(f'  snapshot_as_of={args.snapshot_as_of}  label_signal={LABEL_SIGNAL_SCALE}')
    print('=' * 60)

    df_customer, latents = generate_customer_master(NUM_CUSTOMERS)
    df_terms = build_contract_terms(df_customer, latents, as_of)
    print(f'  simulating {len(df_terms)} contract paths...')
    paths, mu_label = simulate_contract_paths(df_terms, t_cut, as_of)

    df_lkp = generate_lkp_history(df_terms, paths, t_cut, as_of)

    lkp_lookup = {}
    interactions_by_contract = {}
    if not df_lkp.empty:
        lkp_sorted = df_lkp.sort_values('ACTION_DATE')
        for contract_no, grp in lkp_sorted.groupby('CONTRACT_NO'):
            dates = [d.date() for d in pd.to_datetime(grp['ACTION_DATE'])]
            lkp_lookup[contract_no] = list(zip(dates, grp['TREATMENT_TYPE']))
            interactions_by_contract[contract_no] = dates

    df_payment = generate_payment_history(df_terms, paths, lkp_lookup, interactions_by_contract)
    df_contract = assemble_contract_snapshot(df_terms, paths, args.snapshot_as_of)

    paid = len(df_payment[df_payment['PAY_STATUS'].isin(['Full', 'Overpaid'])])
    partial = len(df_payment[df_payment['PAY_STATUS'] == 'Partial'])
    print(f"\n✓ Customers: {len(df_customer)}")
    print(f"✓ Contracts: {len(df_contract)}")
    print(f"✓ Payment records: {len(df_payment)}")
    if len(df_payment):
        print(f"  - Full/Overpaid: {paid} ({100 * paid / len(df_payment):.1f}%)")
        print(f"  - Partial: {partial} ({100 * partial / len(df_payment):.1f}%)")
    print(f"✓ LKP interactions: {len(df_lkp)}")
    print_diagnostics(df_contract, paths, as_of, mu_label)

    if args.dump_latents:
        audit = pd.DataFrame([
            {
                'contract_no': t['contract_no'], 'cust_id': t['cust_id'],
                'w': t['w'], 'c': t['c'],
                'a_cut': paths[t['contract_no']]['a_cut'],
                'shock_cut': paths[t['contract_no']]['shock_cut'],
                'p_label': paths[t['contract_no']]['p_label'],
                'y_pay': paths[t['contract_no']]['y_pay'],
            }
            for _, t in df_terms.iterrows()
        ])
        audit_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_audit_latents.parquet')
        try:
            audit.to_parquet(audit_path, index=False)
        except Exception:
            audit_path = audit_path.replace('.parquet', '.csv')
            audit.to_csv(audit_path, index=False)
        print(f"\n✓ Latents (audit only, never loaded to DB): {audit_path}")

    if args.dump_schedule:
        # Jadwal cicilan PENUH per kontrak, termasuk angsuran yang belum
        # dibayar — faker biasanya TIDAK menyimpan ini kemana pun (hanya
        # payment yang benar-benar terjadi jadi baris payment_history).
        # due_date murni fungsi deterministik (t_cut, phase, months_on_book,
        # j) lewat _due_date() — TIDAK menyentuh latents (w, c) atau hasil
        # stokastik apa pun, jadi aman dipakai TASK-S2 tanpa membocorkan
        # ground truth. j berjalan 1..m (historis, <= t_cut) PLUS SATU
        # angsuran tambahan (m+1) yang jatuh di jendela label ([t_cut,
        # as_of]) — persis satu-satunya angsuran "masa depan" yang memang
        # disimulasikan generator ini (lihat docstring _due_date()), jadi
        # ini batas horizon yang jujur: simulasi hari-per-hari (S2) hanya
        # valid sampai `as_of` run ini, tidak lebih.
        schedule_rows = []
        for _, term in df_terms.iterrows():
            m = int(term['months_on_book'])
            phase = int(term['phase'])
            installment_amount = term['installment']
            for j in range(1, m + 2):
                schedule_rows.append({
                    'contract_no': term['contract_no'],
                    'installment_no': j,
                    'due_date': _due_date(t_cut, phase, m, j).strftime('%Y-%m-%d'),
                    'installment_amount': installment_amount,
                })
        schedule_df = pd.DataFrame(schedule_rows)
        if args.no_db:
            schedule_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_installment_schedule.parquet')
            try:
                schedule_df.to_parquet(schedule_path, index=False)
            except Exception:
                schedule_path = schedule_path.replace('.parquet', '.csv')
                schedule_df.to_csv(schedule_path, index=False)
            print(f"✓ Installment schedule ({len(schedule_df):,} baris, horizon s/d {as_of.isoformat()}): {schedule_path}")
    else:
        schedule_df = None

    if not args.no_excel:
        print('\nSaving to Excel...')
        excel_filename = 'Dataset_CollectAI_Realistic.xlsx'
        with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
            df_customer.to_excel(writer, sheet_name='1_Customer_Master', index=False)
            df_contract.to_excel(writer, sheet_name='2_Contract_Snapshot', index=False)
            df_payment.to_excel(writer, sheet_name='3_Payment_History', index=False)
            df_lkp.to_excel(writer, sheet_name='4_LKP_Interaction', index=False)
        print(f'✓ Saved to {excel_filename}')

    if not args.no_db:
        db_tables = {
            'customer_master': df_customer,
            'contract_snapshot': df_contract,
            'payment_history': df_payment,
            'lkp_interaction': df_lkp,
        }
        if args.dump_schedule and schedule_df is not None:
            db_tables['installment_schedule'] = schedule_df
        prefix = args.table_prefix
        is_staging = bool(prefix)
        if args.reset:
            print(f'\nResetting target tables (prefix={prefix!r})...')
            reset_tables(list(db_tables.keys()), include_derived=not is_staging, table_prefix=prefix)
        print(f'\nSaving to PostgreSQL (prefix={prefix!r})...')
        append_dataframes_to_postgres(
            db_tables, if_exists='append', require_empty=not args.reset, table_prefix=prefix,
        )
        print('✓ Data loaded to PostgreSQL\n')

    print(f"NEXT: run training with reference_date='{as_of.isoformat()}'\n")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
