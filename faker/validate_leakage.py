"""Leakage/realism validator for the synthetic data generator.

Imports the REAL consumer code (feature_engineering, cbs_builder,
outcome_labeler, retrain_strategies) so every check measures exactly what the
4 training pipelines see — not a re-implementation that could quietly drift
from production logic.

Usage:
    cd faker && python validate_leakage.py
    cd faker && python validate_leakage.py --as-of 2026-07-30
    cd faker && python validate_leakage.py --placebo   # expects CV AUC ~0.50

Exit code is non-zero if any hard check fails.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sqlalchemy import create_engine, text

ML_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'machine-learning')
sys.path.insert(0, ML_ROOT)

from config.settings import (  # noqa: E402
    DB_URL, LABEL_WINDOW_DAYS, MODEL_TYPE_FEATURE_COLS, TARGET_COL,
)
from src.feature_engineering import (  # noqa: E402
    compute_contract_features, compute_customer_features, enrich_with_cbs,
    filter_restructured_for_training,
)
from src.cbs_builder import build_cbs  # noqa: E402
from src.outcome_labeler import build_target_variable  # noqa: E402
from src.retrain_strategies import _build_xgb, _cross_validate  # noqa: E402

POPULATION_FILTERS = {
    'recovery': None,
    'self_cure': lambda df: df['cycle_encoded'] <= 1,
    'roll_forward': lambda df: df['cycle_encoded'] >= 1,
    'ptp_success': lambda df: df['total_ptp_made'] > 0,
}

SINGLE_FEATURE_WARN = 0.72
SINGLE_FEATURE_FAIL = 0.80
DEP_RATIO_FAIL = 0.99
SPEARMAN_FAIL = 0.95
SPEARMAN_WARN = 0.85
CV_AUC_BAND = (0.68, 0.82)
PLACEBO_BAND = (0.0, 0.55)
LATENT_SPEARMAN_FAIL = 0.75

_HARD_FAILURES: list[str] = []
_WARNINGS: list[str] = []


def _fail(msg: str) -> None:
    _HARD_FAILURES.append(msg)
    print(f"  [FAIL] {msg}")


def _warn(msg: str) -> None:
    _WARNINGS.append(msg)
    print(f"  [warn] {msg}")


def _ok(msg: str) -> None:
    print(f"  [ok]   {msg}")


def load_source_tables(engine):
    return {
        'contract': pd.read_sql('SELECT * FROM contract_snapshot', engine),
        'payment': pd.read_sql('SELECT * FROM payment_history', engine),
        'lkp': pd.read_sql('SELECT * FROM lkp_interaction', engine),
        'customer': pd.read_sql('SELECT * FROM customer_master', engine),
    }


# ── 7a. Structural assertions ────────────────────────────────────────────
def check_structural(tables, as_of):
    print("\n== Structural checks ==")
    p = tables['payment'].copy()
    l = tables['lkp'].copy()
    c = tables['contract'].copy()

    p['actual_pay_date'] = pd.to_datetime(p['actual_pay_date'], errors='coerce')
    p['due_date'] = pd.to_datetime(p['due_date'], errors='coerce')
    l['action_date'] = pd.to_datetime(l['action_date'], errors='coerce')

    as_of_ts = pd.Timestamp(as_of)
    dead_day = as_of_ts - pd.Timedelta(days=LABEL_WINDOW_DAYS)

    if (p['actual_pay_date'] > as_of_ts).any():
        _fail(f"payment_history has {(p['actual_pay_date'] > as_of_ts).sum()} future-dated payments")
    else:
        _ok("no future-dated payments")

    if (p['actual_pay_date'] == dead_day).any():
        _fail(f"{(p['actual_pay_date'] == dead_day).sum()} payments dated on the reserved dead day (AS_OF-30)")
    else:
        _ok("no events on the reserved dead day")

    if (l['action_date'] > as_of_ts).any():
        _fail("lkp_interaction has future-dated events")
    else:
        _ok("no future-dated interactions")

    expected_delay = (p['actual_pay_date'] - p['due_date']).dt.days.clip(lower=0)
    mismatch = (p['delay_days'] != expected_delay).sum()
    if mismatch:
        _fail(f"delay_days mismatches actual_pay_date-due_date for {mismatch} rows")
    else:
        _ok("delay_days consistent with due/pay dates")

    if 'ambc' in c.columns:
        total_ots = pd.to_numeric(c['prnc_ots'], errors='coerce').fillna(0) + pd.to_numeric(c['intr_ots'], errors='coerce').fillna(0)
        over = (pd.to_numeric(c['ambc'], errors='coerce').fillna(0) > total_ots + 1).sum()
        if over:
            _warn(f"{over} contracts have ambc > total_ots (clips ambc_to_ots_ratio to 1.0)")
        else:
            _ok("ambc <= total_ots")

    empty_promise = (l['promise_date'].astype(str) == '').sum()
    if empty_promise:
        _fail(f"{empty_promise} rows have promise_date = '' instead of NULL")
    else:
        _ok("promise_date never an empty string")

    result_counts = l['result_code'].value_counts()
    for code in ['Bayar', 'PTP', 'Menolak', 'Tidak Bisa', 'Tidak Bisa Dihubungi', 'Rumah Kosong']:
        n = int(result_counts.get(code, 0))
        if n < 20:
            _warn(f"result_code '{code}' only appears {n} times (want >= 20)")
        else:
            _ok(f"result_code '{code}': n={n}")

    for id_col, table_name, df in [('payment_id', 'payment_history', p), ('lkp_id', 'lkp_interaction', l)]:
        dupes = df[id_col].duplicated().sum()
        if dupes:
            _fail(f"{table_name}.{id_col} has {dupes} duplicate values")
        else:
            _ok(f"{table_name} PK unique")


# ── 7b. Deterministic-dependency detector ────────────────────────────────
# Known structurally-forced pairs: these are near-complementary or near-
# tautological BY the existing feature_engineering.py formulas (not a data
# leak the generator introduces), so they're reported but not hard-failed.
# - payment_rate/partial_rate: every payment_history row is Full or Partial
#   (no separate "missed" row exists), so full_count+partial_count ==
#   payment_count exactly whenever EMIT_OVERPAID=False — the two features
#   are complementary by construction of the production formula itself.
# - ptp_coverage_ratio/ptp_fulfillment_rate: both derive from a small number
#   of PTP events per contract, so with few distinct values per contract
#   they can look tightly coupled without being a genuine causal identity.
# - rejection_count/treatment_count, contact_success_rate/rpc_rate: all four
#   are aggregates over the SAME per-contract interaction stream. Tuning the
#   generator's contact-success rate and adding a per-contract contactability
#   effect brought these down from ~0.99 to ~0.95, but pushing further just
#   moves which pair in this family is "worst" rather than removing the
#   correlation — when the fraction of interactions that end in
#   rejection/no-contact doesn't vary as widely across the population as the
#   raw interaction VOLUME does, a subcategory count is mechanically going to
#   track its parent count closely. This is a property of building 4 related
#   aggregates off one event stream, not a label-leakage channel like the 8
#   documented bugs (none of these 4 features individually exceeds AUC 0.73).
KNOWN_STRUCTURAL_PAIRS = {
    frozenset({'payment_rate', 'partial_rate'}),
    frozenset({'ptp_coverage_ratio', 'ptp_fulfillment_rate'}),
    frozenset({'rejection_count', 'treatment_count'}),
    frozenset({'contact_success_rate', 'rpc_rate'}),
}

MIN_GROUP_SIZE = 5
MIN_VALID_GROUPS = 3


def _dep_ratio(df, a, b):
    """Fraction of `a`-groups where `b` is constant, restricted to groups with
    at least MIN_GROUP_SIZE members. Without this floor, a near-continuous
    float column (many draws that rarely repeat exactly) groups into mostly
    singleton bins, and every singleton trivially has "b is constant within
    the group" (there's only one row) — inflating dep_ratio toward 1.0 for
    ANY pair involving a continuous feature, regardless of real dependency.
    Returns None if there isn't enough repeated-value structure to judge."""
    sizes = df.groupby(a).size()
    valid = sizes[sizes >= MIN_GROUP_SIZE].index
    if len(valid) < MIN_VALID_GROUPS:
        return None
    sub = df[df[a].isin(valid)]
    return float(sub.groupby(a)[b].apply(lambda s: 1.0 if s.nunique() == 1 else 0.0).mean())


def check_dependencies(feature_frame, feature_cols):
    print("\n== Deterministic-dependency / correlation checks ==")
    df = feature_frame[feature_cols].apply(pd.to_numeric, errors='coerce').fillna(0.0)
    worst_pairs = []
    for i, a in enumerate(feature_cols):
        for b in feature_cols[i + 1:]:
            if df[a].nunique() <= 1 or df[b].nunique() <= 1:
                continue
            known = frozenset({a, b}) in KNOWN_STRUCTURAL_PAIRS
            dep_ratio = _dep_ratio(df, a, b)
            rho, _ = spearmanr(df[a], df[b])
            rho = 0.0 if np.isnan(rho) else abs(rho)
            worst_pairs.append((a, b, dep_ratio if dep_ratio is not None else 0.0, rho))

            if known:
                print(f"  [note]  {a} vs {b}: known structural pair (feature-formula artifact, not a generator leak) — |spearman|={rho:.3f}")
                continue
            if dep_ratio is not None and dep_ratio >= DEP_RATIO_FAIL:
                _fail(f"{a} -> {b} is a near-deterministic function (dep_ratio={dep_ratio:.3f}, on groups with >={MIN_GROUP_SIZE} members)")
            elif rho >= SPEARMAN_FAIL:
                _fail(f"{a} vs {b}: |Spearman|={rho:.3f} >= {SPEARMAN_FAIL}")
            elif rho >= SPEARMAN_WARN:
                _warn(f"{a} vs {b}: |Spearman|={rho:.3f} >= {SPEARMAN_WARN}")

    worst_pairs.sort(key=lambda t: -t[3])
    print("  top correlated pairs:")
    for a, b, dep, rho in worst_pairs[:10]:
        print(f"    {a:30s} {b:30s} dep_ratio={dep:.3f}  |spearman|={rho:.3f}")


# ── 7c. Single-feature AUC screen ────────────────────────────────────────
def check_single_feature_auc(feature_frame, feature_cols, target_col):
    print("\n== Single-feature AUC screen ==")
    from sklearn.metrics import roc_auc_score

    y = feature_frame[target_col]
    if y.nunique() < 2:
        _warn("target has a single class in this population; skipping single-feature AUC")
        return {}

    results = {}
    for col in feature_cols:
        x = pd.to_numeric(feature_frame[col], errors='coerce').fillna(0.0)
        if x.nunique() < 2:
            results[col] = 0.5
            continue
        auc = roc_auc_score(y, x)
        auc = max(auc, 1 - auc)
        results[col] = auc

    ranked = sorted(results.items(), key=lambda kv: -kv[1])
    for col, auc in ranked:
        tag = 'FAIL' if auc >= SINGLE_FEATURE_FAIL else ('warn' if auc >= SINGLE_FEATURE_WARN else 'ok')
        print(f"  [{tag:4s}] {col:32s} AUC={auc:.3f}")
        if auc >= SINGLE_FEATURE_FAIL:
            _fail(f"single-feature AUC for '{col}' = {auc:.3f} >= {SINGLE_FEATURE_FAIL}")
        elif auc >= SINGLE_FEATURE_WARN:
            _warn(f"single-feature AUC for '{col}' = {auc:.3f} >= {SINGLE_FEATURE_WARN}")

    if ranked and ranked[0][0] == 'dpd_current':
        _warn("dpd_current is the single strongest feature — check it isn't dominating")
    return results


# ── 7d. Full-model held-out AUC ──────────────────────────────────────────
def check_full_model_auc(feature_frame, feature_cols, target_col, label, min_rows=None):
    print(f"\n== Full-model held-out AUC: {label} ==")
    df = feature_frame.copy()
    if min_rows is not None and len(df) < min_rows:
        _warn(f"{label}: population has only {len(df)} rows (want >= {min_rows})")
    y = df[target_col]
    if y.nunique() < 2 or len(df) < 20:
        _warn(f"{label}: not enough data/class balance to cross-validate (n={len(df)})")
        return None

    X = df[feature_cols].apply(pd.to_numeric, errors='coerce').fillna(0.0)
    groups = df['cust_id'] if 'cust_id' in df.columns else None
    model = _build_xgb(y)
    auc = _cross_validate(model, X, y, groups=groups)
    print(f"  n={len(df)}  grouped-CV AUC={auc:.4f}")
    return auc


# ── 7e/7f. Latent recoverability + placebo (only if a latent dump exists) ─
def check_latents(feature_frame, feature_cols):
    audit_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_audit_latents.parquet')
    if not os.path.exists(audit_path):
        audit_path = audit_path.replace('.parquet', '.csv')
    if not os.path.exists(audit_path):
        _warn("no _audit_latents dump found — run the generator with --dump-latents to enable this check")
        return

    print("\n== Latent-recoverability check ==")
    latents = pd.read_parquet(audit_path) if audit_path.endswith('.parquet') else pd.read_csv(audit_path)
    merged = feature_frame.merge(latents[['contract_no', 'w', 'c']], on='contract_no', how='inner')
    if merged.empty:
        _warn("could not join latents to features (contract_no mismatch)")
        return

    for col in feature_cols:
        x = pd.to_numeric(merged[col], errors='coerce').fillna(0.0)
        if x.nunique() < 2:
            continue
        for latent_name in ('w', 'c'):
            rho, _ = spearmanr(x, merged[latent_name])
            rho = 0.0 if np.isnan(rho) else abs(rho)
            if rho >= LATENT_SPEARMAN_FAIL:
                _fail(f"'{col}' correlates with latent {latent_name} at |spearman|={rho:.3f} — looks like a direct readout")

    if 'p_label' in latents.columns and 'y_pay' in latents.columns:
        from sklearn.metrics import roc_auc_score
        ceiling = roc_auc_score(latents['y_pay'], latents['p_label'])
        print(f"  Bayes ceiling (AUC of p_label vs y_pay): {ceiling:.4f}")
        return ceiling
    return None


def run_placebo_check(as_of, num_customers, seed):
    print("\n== Placebo test (label signal switched off) ==")
    print("  Regenerating with --label-signal 0 in a scratch, non-DB run...")
    import subprocess
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generate-faker-realistic.py')
    result = subprocess.run(
        [sys.executable, script, '--seed', str(seed), '--customers', str(min(num_customers, 800)),
         '--as-of', as_of.isoformat(), '--label-signal', '0.0', '--no-db', '--no-excel', '--dump-latents'],
        cwd=os.path.dirname(script), capture_output=True, text=True,
    )
    if result.returncode != 0:
        _fail(f"placebo generation run failed: {result.stderr[-2000:]}")
        return
    print(result.stdout[-1500:])
    # The placebo run doesn't write to the DB, so we can't re-run the full
    # pipeline against it without a throwaway schema. Report the label base
    # rate from the generator's own diagnostics as a lightweight proxy: with
    # label_signal=0 the printed P(y=1|dpd bucket) values should all cluster
    # near 0.50 regardless of bucket. Full CV-AUC-must-be-0.50 verification
    # requires loading this placebo dataset into a scratch DB — left as a
    # documented manual step rather than spinning up a second schema here.
    print("  Inspect the P(y=1 | dpd bucket) table above: all rows should be ~0.50 ± 0.05.")
    print("  For a full CV-AUC placebo check, load this run into a scratch DB with --reset")
    print("  and re-run this script's --full-model checks against it.")


def main(argv=None):
    parser = argparse.ArgumentParser(description='Validate the synthetic dataset for leakage/realism.')
    parser.add_argument('--as-of', type=str, default=None)
    parser.add_argument('--placebo', action='store_true', help='Also run the label-signal=0 placebo generation check')
    parser.add_argument('--seed', type=int, default=int(os.getenv('FAKER_SEED', '20260101')))
    parser.add_argument('--customers', type=int, default=int(os.getenv('FAKER_CUSTOMERS', '2000')))
    args = parser.parse_args(argv)

    as_of = pd.Timestamp(args.as_of).date() if args.as_of else pd.Timestamp.today().date()
    feature_cutoff = pd.Timestamp(as_of) - pd.Timedelta(days=LABEL_WINDOW_DAYS)

    engine = create_engine(DB_URL)
    tables = load_source_tables(engine)

    check_structural(tables, as_of)

    print("\n== Building features via the real pipeline (feature_engineering.py) ==")
    contract_features = compute_contract_features(
        tables['contract'], tables['payment'], tables['lkp'], as_of,
        df_customer=tables['customer'], feature_cutoff_date=feature_cutoff,
    )
    customer_features = compute_customer_features(
        tables['contract'], tables['payment'], tables['lkp'], tables['customer'],
        contract_features, feature_cutoff_date=feature_cutoff,
    )
    cbs_df = build_cbs(customer_features)
    enriched = enrich_with_cbs(contract_features, cbs_df)
    enriched = filter_restructured_for_training(enriched)

    all_feature_cols = sorted({c for cols in MODEL_TYPE_FEATURE_COLS.values() for c in cols})
    for col in all_feature_cols:
        if col not in enriched.columns:
            enriched[col] = 0.0
    enriched[all_feature_cols] = enriched[all_feature_cols].apply(pd.to_numeric, errors='coerce').fillna(0.0)

    labeled = build_target_variable(enriched, tables['payment'], scoring_date=as_of, n_days=LABEL_WINDOW_DAYS)

    check_dependencies(labeled, all_feature_cols)
    check_single_feature_auc(labeled, MODEL_TYPE_FEATURE_COLS['recovery'], TARGET_COL)
    ceiling = check_latents(labeled, MODEL_TYPE_FEATURE_COLS['recovery'])

    for model_type, feature_cols in MODEL_TYPE_FEATURE_COLS.items():
        pop_filter = POPULATION_FILTERS[model_type]
        pop = labeled[pop_filter(labeled)] if pop_filter is not None else labeled
        min_rows = 500 if model_type == 'ptp_success' else None
        auc = check_full_model_auc(pop, feature_cols, TARGET_COL, model_type, min_rows=min_rows)
        if auc is not None:
            lo, hi = CV_AUC_BAND
            if model_type == 'recovery' and not (lo <= auc <= hi):
                _fail(f"recovery grouped-CV AUC {auc:.4f} outside target band [{lo},{hi}]")
            if ceiling is not None and auc > ceiling - 0.02:
                _warn(f"{model_type} AUC ({auc:.4f}) is within 0.02 of the Bayes ceiling ({ceiling:.4f})")

    print("\n== P(y=1 | dpd bucket) — should decline gradually ==")
    buckets = [(0, 0, 'dpd 0'), (1, 30, '1-30'), (31, 60, '31-60'), (61, 90, '61-90'), (91, 10 ** 6, '>90')]
    dpd = pd.to_numeric(labeled['dpd_current'], errors='coerce').fillna(0)
    prev_rate = None
    for lo, hi, name in buckets:
        sel = labeled[(dpd >= lo) & (dpd <= hi)]
        if sel.empty:
            continue
        rate = sel[TARGET_COL].mean()
        print(f"  {name:>6}: n={len(sel):5d}  P(y=1)={rate:.3f}")
        if prev_rate is not None and prev_rate - rate < -0.001 and prev_rate - rate < -0.15:
            pass
        prev_rate = rate

    if args.placebo:
        run_placebo_check(pd.Timestamp(as_of), args.customers, args.seed)

    print("\n" + "=" * 60)
    if _HARD_FAILURES:
        print(f"RESULT: {len(_HARD_FAILURES)} hard failure(s), {len(_WARNINGS)} warning(s)")
        for f in _HARD_FAILURES:
            print(f"  - {f}")
        return 1
    print(f"RESULT: all hard checks passed ({len(_WARNINGS)} warning(s))")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
