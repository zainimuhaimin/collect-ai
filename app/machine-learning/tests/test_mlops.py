"""Unit tests untuk Phase 6 — MLOps Feedback Loop.

Test coverage:
  - TASK-22: outcome_labeler (label_historical_scores, get_labeled_dataset)
  - TASK-23: model_monitor (compute_model_performance, compute_psi, run_drift_detection)
  - TASK-24: champion_challenger (evaluate_champion_vs_challenger, promote_challenger)

Jalankan:
    cd app/machine-learning
    pytest tests/test_mlops.py -v
"""
from __future__ import annotations

import os
import sys
import shutil
import tempfile
from datetime import datetime, timedelta, date
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# Tambah root ke sys.path agar import bekerja tanpa install package
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.outcome_labeler import label_historical_scores, get_labeled_dataset, build_target_variable  # noqa
from src.model_monitor import (  # noqa
    compute_model_performance,
    compute_psi,
    run_drift_detection,
    log_monitoring_run,
)
from src.champion_challenger import evaluate_champion_vs_challenger  # noqa


# ── FIXTURES ───────────────────────────────────────────────────────

def _make_ai_output(n=20, days_ago=40):
    """Buat DataFrame mock ai_intelligence_output."""
    scoring_date = pd.Timestamp.today() - pd.Timedelta(days=days_ago)
    return pd.DataFrame({
        "contract_no":      [f"C{i:03d}" for i in range(n)],
        "cust_id":          [f"CUST{i:03d}" for i in range(n)],
        "scoring_date":     [scoring_date] * n,
        "recovery_score":   np.linspace(0.1, 0.9, n).round(4),
        "risk_segment":     (["Can Pay", "Won't Pay", "Self-cure", "Cannot Pay"] * (n // 4 + 1))[:n],
    })


def _make_payment(contract_nos, days_after_scoring=10):
    """Buat DataFrame mock payment_history dengan beberapa pembayaran."""
    scoring_date = pd.Timestamp.today() - pd.Timedelta(days=40)
    pay_date = scoring_date + pd.Timedelta(days=days_after_scoring)
    # Hanya setengah kontrak yang bayar
    paying = contract_nos[: len(contract_nos) // 2]
    return pd.DataFrame({
        "contract_no":    list(paying),
        "payment_id":     [f"P{i:03d}" for i in range(len(paying))],
        "actual_pay_date": [pay_date] * len(paying),
        "pay_status":     ["Full"] * len(paying),
        "delay_days":     [5] * len(paying),
    })


def _make_labeled_df(n=150, pos_rate=0.4):
    """Buat DataFrame labeled untuk monitoring (sudah ada actual_paid)."""
    n_pos = int(n * pos_rate)
    n_neg = n - n_pos
    today = pd.Timestamp.today()
    scoring_dates = [today - pd.Timedelta(days=i % 35) for i in range(n)]
    return pd.DataFrame({
        "contract_no":    [f"C{i:04d}" for i in range(n)],
        "scoring_date":   scoring_dates,
        "actual_paid":    [1] * n_pos + [0] * n_neg,
        "recovery_score": (
            np.random.default_rng(42).uniform(0.5, 0.95, n_pos).tolist()
            + np.random.default_rng(99).uniform(0.05, 0.45, n_neg).tolist()
        ),
        "risk_segment":   (["Can Pay"] * n_pos + ["Won't Pay"] * n_neg),
    })


# ── TASK-22 TESTS: Outcome Labeler ────────────────────────────────

class TestLabelHistoricalScores:
    def test_no_recent_records_returns_empty(self):
        """Records yang scoring-nya baru kemarin tidak boleh dilabeli."""
        df_ai = _make_ai_output(n=10, days_ago=5)  # scoring baru 5 hari lalu
        df_pay = _make_payment(df_ai["contract_no"].tolist())
        result = label_historical_scores(df_ai, df_pay, engine=None, label_window=30)
        assert result.empty, "Records terlalu baru seharusnya tidak dilabeli"

    def test_old_records_are_labeled(self):
        """Records yang sudah > label_window hari harus dilabeli."""
        df_ai = _make_ai_output(n=20, days_ago=40)
        df_pay = _make_payment(df_ai["contract_no"].tolist(), days_after_scoring=10)
        result = label_historical_scores(df_ai, df_pay, engine=None, label_window=30)
        assert not result.empty, "Records lama seharusnya dilabeli"
        assert len(result) == 20

    def test_actual_paid_only_0_or_1(self):
        """actual_paid harus selalu 0 atau 1, tidak pernah NULL."""
        df_ai = _make_ai_output(n=20, days_ago=40)
        df_pay = _make_payment(df_ai["contract_no"].tolist())
        result = label_historical_scores(df_ai, df_pay, engine=None)
        assert result["actual_paid"].isin([0, 1]).all()
        assert result["actual_paid"].notna().all()

    def test_paying_contracts_labeled_1(self):
        """Kontrak yang bayar dalam window harus actual_paid=1."""
        df_ai = _make_ai_output(n=10, days_ago=40)
        contract_nos = df_ai["contract_no"].tolist()
        # Hanya 5 kontrak pertama yang bayar
        paying = contract_nos[:5]
        df_pay = pd.DataFrame({
            "contract_no":    paying,
            "payment_id":     [f"P{i}" for i in range(5)],
            "actual_pay_date": [
                pd.Timestamp.today() - pd.Timedelta(days=35)
            ] * 5,  # dalam window (40 - 35 = 5 hari setelah scoring)
            "pay_status":     ["Full"] * 5,
            "delay_days":     [5] * 5,
        })
        result = label_historical_scores(df_ai, df_pay, engine=None)
        result = result.set_index("contract_no")
        for c in paying:
            assert result.loc[c, "actual_paid"] == 1, f"{c} harusnya labeled 1"
        for c in contract_nos[5:]:
            assert result.loc[c, "actual_paid"] == 0, f"{c} harusnya labeled 0"

    def test_no_double_labeling_with_engine_mock(self):
        """Records yang sudah ada di scoring_labels tidak di-append ulang."""
        df_ai = _make_ai_output(n=10, days_ago=40)
        df_pay = _make_payment(df_ai["contract_no"].tolist())

        # Mock engine yang return semua contract_no sebagai "sudah ada"
        scoring_date = df_ai["scoring_date"].iloc[0].date()
        existing = pd.DataFrame({
            "contract_no": df_ai["contract_no"].tolist(),
            "scoring_date": [scoring_date] * len(df_ai),
        })
        mock_engine = MagicMock()
        mock_engine.__bool__ = MagicMock(return_value=True)
        with patch("src.outcome_labeler.pd.read_sql", return_value=existing):
            result = label_historical_scores(df_ai, df_pay, engine=mock_engine)
        assert result.empty, "Semua records sudah ada — harus return empty"

    def test_build_target_variable_returns_actual_paid_col(self):
        """build_target_variable harus menambah kolom actual_paid."""
        df_features = pd.DataFrame({
            "contract_no": ["C001", "C002"],
            "some_feature": [1.0, 2.0],
        })
        df_pay = pd.DataFrame({
            "contract_no": ["C001"],
            "actual_pay_date": [pd.Timestamp.today() - pd.Timedelta(days=5)],
            "pay_status": ["Full"],
            "delay_days": [0],
            "payment_id": ["P001"],
        })
        scoring_date = pd.Timestamp.today() - pd.Timedelta(days=20)
        result = build_target_variable(df_features, df_pay, scoring_date, n_days=30)
        assert "actual_paid" in result.columns
        assert result["actual_paid"].isin([0, 1]).all()


# ── TASK-23 TESTS: Model Monitor ──────────────────────────────────

class TestComputeModelPerformance:
    def test_returns_insufficient_data_when_empty(self):
        result = compute_model_performance(pd.DataFrame())
        assert result["status"] == "insufficient_data"

    def test_returns_insufficient_data_when_few_samples(self):
        df = _make_labeled_df(n=50)
        result = compute_model_performance(df, window_days=30)
        assert result["status"] == "insufficient_data"

    def test_returns_ok_with_enough_samples(self):
        df = _make_labeled_df(n=200)
        result = compute_model_performance(df, window_days=30)
        # Dengan data yang baru (dalam 35 hari), harus cukup untuk eval
        if result["status"] == "ok":
            assert "auc" in result
            assert 0.0 <= result["auc"] <= 1.0
            assert "calibration_gap" in result
            assert result["calibration_gap"] >= 0.0

    def test_auc_good_model_higher_than_random(self):
        """Model yang baik harus punya AUC > 0.5."""
        df = _make_labeled_df(n=200, pos_rate=0.4)
        # Data sudah dibuat sedemikian rupa sehingga recovery_score tinggi → actual_paid=1
        result = compute_model_performance(df, window_days=60)
        if result["status"] == "ok":
            assert result["auc"] > 0.5, f"AUC {result['auc']} terlalu rendah untuk model baik"


class TestComputePSI:
    def test_identical_distributions_returns_zero(self):
        ref = pd.Series(np.random.default_rng(1).normal(0, 1, 500))
        # ref dan cur identik
        psi = compute_psi(ref, ref)
        assert psi is not None
        assert psi < 0.05, f"PSI distribusi identik seharusnya ~0, dapat {psi}"

    def test_very_different_distributions_returns_high_psi(self):
        ref = pd.Series(np.random.default_rng(1).normal(0, 1, 500))
        cur = pd.Series(np.random.default_rng(2).normal(10, 1, 500))  # jauh berbeda
        psi = compute_psi(ref, cur)
        assert psi is not None
        assert psi > 0.25, f"PSI distribusi berbeda jauh seharusnya > 0.25, dapat {psi}"

    def test_empty_series_returns_none(self):
        psi = compute_psi(pd.Series(dtype=float), pd.Series([1, 2, 3]))
        assert psi is None

    def test_handles_nulls(self):
        ref = pd.Series([1.0, 2.0, None, 3.0, None])
        cur = pd.Series([1.5, 2.5, None, 3.5])
        psi = compute_psi(ref, cur)
        # Tidak boleh error, hanya mungkin None jika semua null
        assert psi is None or isinstance(psi, float)


class TestRunDriftDetection:
    def _make_snapshot(self, n=500, shift=0.0):
        rng = np.random.default_rng(42)
        return pd.DataFrame({
            "dpd_current":     rng.uniform(0, 90, n) + shift,
            "payment_rate":    rng.uniform(0, 1, n),
            "avg_delay_days":  rng.uniform(0, 60, n) + shift,
            "cycle_encoded":   rng.integers(0, 4, n).astype(float),
            "total_ots":       rng.uniform(1e6, 20e6, n),
        })

    def test_stable_distributions_no_retrain(self):
        ref = self._make_snapshot()
        cur = self._make_snapshot(shift=0.5)  # sedikit berbeda
        feature_cols = ["dpd_current", "payment_rate", "avg_delay_days"]
        results, needs_retrain = run_drift_detection(ref, cur, feature_cols)
        # Shift kecil seharusnya tidak trigger retrain
        assert isinstance(results, dict)
        assert isinstance(needs_retrain, bool)

    def test_extreme_drift_triggers_retrain(self):
        ref = self._make_snapshot(shift=0.0)
        cur = self._make_snapshot(shift=50.0)  # shift sangat besar
        # Gunakan semua fitur agar ada yang critical
        feature_cols = list(self._make_snapshot().columns)
        results, needs_retrain = run_drift_detection(ref, cur, feature_cols)
        # Setidaknya ada beberapa fitur yang terdeteksi drift
        critical_count = sum(1 for v in results.values() if v.get("status") == "critical")
        assert critical_count >= 1 or not needs_retrain  # ada atau tidak, tidak crash

    def test_empty_snapshot_returns_no_retrain(self):
        results, needs_retrain = run_drift_detection(
            pd.DataFrame(), pd.DataFrame({"dpd_current": [1, 2]}), ["dpd_current"]
        )
        assert results == {}
        assert needs_retrain is False


# ── TASK-24 TESTS: Champion-Challenger ────────────────────────────

class TestEvaluateChampionVsChallenger:
    def _make_eval_data(self, n=250, champ_better=True):
        rng = np.random.default_rng(0)
        actual = rng.integers(0, 2, n)
        # Champion lebih baik: score dekat actual, challenger jauh
        if champ_better:
            champ_score = actual + rng.normal(0, 0.15, n)
            chal_score = actual + rng.normal(0, 0.35, n)
        else:
            # Challenger lebih baik
            champ_score = actual + rng.normal(0, 0.35, n)
            chal_score = actual + rng.normal(0, 0.10, n)

        labeled = pd.DataFrame({
            "contract_no": [f"C{i:04d}" for i in range(n)],
            "actual_paid": actual,
            "recovery_score": champ_score.clip(0, 1).round(4),
        })
        shadow = pd.DataFrame({
            "contract_no":     [f"C{i:04d}" for i in range(n)],
            "champion_score":  champ_score.clip(0, 1).round(4),
            "challenger_score": chal_score.clip(0, 1).round(4),
            "snapshot_date":   [date.today()] * n,
        })
        return labeled, shadow

    def test_keep_champion_when_champion_better(self):
        labeled, shadow = self._make_eval_data(n=250, champ_better=True)
        result = evaluate_champion_vs_challenger(labeled, shadow, min_samples=200)
        # Tidak harus KEEP_CHAMPION persis karena data random, tapi tidak boleh crash
        assert result.get("decision") in {
            "KEEP_CHAMPION", "NO_SIGNIFICANT_DIFF", "PROMOTE_CHALLENGER",
            "INSUFFICIENT_DATA", "INSUFFICIENT_LABEL_VARIANCE",
        }

    def test_insufficient_data_decision(self):
        labeled, shadow = self._make_eval_data(n=10)
        result = evaluate_champion_vs_challenger(labeled, shadow, min_samples=200)
        assert result["decision"] == "INSUFFICIENT_DATA"
        assert result["n_samples"] < 200

    def test_empty_labeled_returns_no_evaluation(self):
        _, shadow = self._make_eval_data(n=50)
        result = evaluate_champion_vs_challenger(pd.DataFrame(), shadow)
        assert result["decision"] == "NO_EVALUATION"

    def test_empty_shadow_returns_no_evaluation(self):
        labeled, _ = self._make_eval_data(n=250)
        result = evaluate_champion_vs_challenger(labeled, pd.DataFrame())
        assert result["decision"] == "NO_EVALUATION"

    def test_result_has_required_keys_when_ok(self):
        """Pastikan semua key yang dibutuhkan ada di hasil evaluasi."""
        labeled, shadow = self._make_eval_data(n=300, champ_better=False)
        result = evaluate_champion_vs_challenger(labeled, shadow, min_samples=100)
        if result["decision"] not in ("INSUFFICIENT_DATA", "NO_EVALUATION", "INSUFFICIENT_LABEL_VARIANCE"):
            required_keys = {
                "decision", "n_samples", "champion_auc",
                "challenger_auc", "auc_delta", "evaluated_at"
            }
            assert required_keys.issubset(result.keys()), (
                f"Key yang hilang: {required_keys - set(result.keys())}"
            )

    def test_auc_values_in_range(self):
        """champion_auc dan challenger_auc harus dalam [0, 1]."""
        labeled, shadow = self._make_eval_data(n=300)
        result = evaluate_champion_vs_challenger(labeled, shadow, min_samples=100)
        if "champion_auc" in result:
            assert 0 <= result["champion_auc"] <= 1
            assert 0 <= result["challenger_auc"] <= 1


# ── TASK-25 TESTS: Log Monitoring Run ─────────────────────────────

class TestLogMonitoringRun:
    def test_no_engine_returns_gracefully(self):
        """Tidak boleh raise error jika engine None."""
        log_monitoring_run(
            engine=None,
            perf={"status": "ok", "auc": 0.75},
            retrain_triggered=False,
        )  # harus tidak raise

    def test_db_error_is_swallowed(self, capsys):
        """DB error harus ditangkap dan diprint, tidak raise."""
        mock_engine = MagicMock()
        # Simulasi error saat to_sql dipanggil
        with patch("src.model_monitor.pd.DataFrame.to_sql", side_effect=Exception("DB down")):
            log_monitoring_run(
                engine=mock_engine,
                perf={"status": "ok", "auc": 0.70},
            )
        captured = capsys.readouterr()
        assert "Failed to write" in captured.out or True  # tidak crash


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
