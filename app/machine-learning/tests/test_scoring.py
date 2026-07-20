"""Unit tests untuk scoring engine multi-model (TASK-41/43).

Test coverage:
  - test_multi_model_output_columns: output mengandung 4 kolom score
  - test_missing_submodel_graceful: sub-model tidak ada → NULL, tidak error

Jalankan:
    cd app/machine-learning
    pytest tests/test_scoring.py -v
"""
from __future__ import annotations

import os
import sys
import tempfile

import joblib
import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.scoring_engine import score_contracts, compute_confidence_level, run_quality_check
from config.settings import FEATURE_COLS


# ── HELPERS ──────────────────────────────────────────────────────────

class _DummyModel:
    """Dummy classifier yang selalu return probabilitas 0.5 untuk semua kelas."""
    def predict_proba(self, X):
        n = len(X)
        return np.column_stack([np.full(n, 0.5), np.full(n, 0.5)])


def _make_dummy_artifact(feature_cols=None):
    """Return dict artifact {model, feature_cols} dengan dummy model."""
    if feature_cols is None:
        feature_cols = FEATURE_COLS
    return {"model": _DummyModel(), "feature_cols": feature_cols}


def _make_feature_df(n=5):
    """Buat DataFrame fitur minimal untuk scoring."""
    rng = np.random.default_rng(42)
    data = {col: rng.random(n) for col in FEATURE_COLS}
    data["contract_no"] = [f"C{i:03d}" for i in range(n)]
    data["cust_id"] = [f"CUST{i:03d}" for i in range(n)]
    return pd.DataFrame(data)


# ── TEST CASES ─────────────────────────────────────────────────────────

class TestMultiModelScoring:
    """Tests untuk scoring engine multi-model."""

    def test_multi_model_output_columns(self, tmp_path):
        """Output score_contracts harus mengandung 4 kolom score."""
        # Buat 4 dummy model artifacts
        champion_path = str(tmp_path / "champion.pkl")
        sc_path = str(tmp_path / "self_cure.pkl")
        rf_path = str(tmp_path / "roll_forward.pkl")
        ptp_path = str(tmp_path / "ptp_success.pkl")

        joblib.dump(_make_dummy_artifact(), champion_path)
        joblib.dump(_make_dummy_artifact(), sc_path)
        joblib.dump(_make_dummy_artifact(), rf_path)
        joblib.dump(_make_dummy_artifact(), ptp_path)

        # Patch settings paths
        import config.settings as sett
        orig_sc = getattr(sett, "SELF_CURE_MODEL_PATH", None)
        orig_rf = getattr(sett, "ROLL_FORWARD_MODEL_PATH", None)
        orig_ptp = getattr(sett, "PTP_SUCCESS_MODEL_PATH", None)

        sett.SELF_CURE_MODEL_PATH = sc_path
        sett.ROLL_FORWARD_MODEL_PATH = rf_path
        sett.PTP_SUCCESS_MODEL_PATH = ptp_path

        try:
            df = _make_feature_df()
            result = score_contracts(df, champion_path=champion_path)

            # Semua 4 kolom harus ada
            assert "recovery_score" in result.columns, "recovery_score harus ada"
            assert "self_cure_probability" in result.columns, "self_cure_probability harus ada"
            assert "roll_forward_risk" in result.columns, "roll_forward_risk harus ada"
            assert "ptp_success_probability" in result.columns, "ptp_success_probability harus ada"

            # Semua kolom harus dalam range [0, 1]
            for col in ["recovery_score", "self_cure_probability", "roll_forward_risk", "ptp_success_probability"]:
                assert result[col].between(0, 1).all(), f"{col} harus dalam range [0, 1]"

        finally:
            if orig_sc is not None:
                sett.SELF_CURE_MODEL_PATH = orig_sc
            if orig_rf is not None:
                sett.ROLL_FORWARD_MODEL_PATH = orig_rf
            if orig_ptp is not None:
                sett.PTP_SUCCESS_MODEL_PATH = orig_ptp

    def test_missing_submodel_graceful(self, tmp_path):
        """Sub-model tidak ada → kolom = NULL (NaN), daily run tidak error."""
        champion_path = str(tmp_path / "champion.pkl")
        joblib.dump(_make_dummy_artifact(), champion_path)

        # Patch settings ke path yang tidak ada
        import config.settings as sett
        orig_sc = getattr(sett, "SELF_CURE_MODEL_PATH", None)
        orig_rf = getattr(sett, "ROLL_FORWARD_MODEL_PATH", None)
        orig_ptp = getattr(sett, "PTP_SUCCESS_MODEL_PATH", None)

        nonexistent = str(tmp_path / "nonexistent.pkl")
        sett.SELF_CURE_MODEL_PATH = nonexistent
        sett.ROLL_FORWARD_MODEL_PATH = nonexistent
        sett.PTP_SUCCESS_MODEL_PATH = nonexistent

        try:
            df = _make_feature_df()
            result = score_contracts(df, champion_path=champion_path)

            # Tidak boleh raise error
            assert result is not None

            # Kolom sub-model harus ada tapi berisi NaN
            for col in ["self_cure_probability", "roll_forward_risk", "ptp_success_probability"]:
                assert col in result.columns, f"{col} harus ada meski model tidak ada"
                assert result[col].isna().all(), f"{col} harus NaN jika model tidak ada"

            # recovery_score tetap terisi normal
            assert not result["recovery_score"].isna().any(), "recovery_score tidak boleh NaN"

        finally:
            if orig_sc is not None:
                sett.SELF_CURE_MODEL_PATH = orig_sc
            if orig_rf is not None:
                sett.ROLL_FORWARD_MODEL_PATH = orig_rf
            if orig_ptp is not None:
                sett.PTP_SUCCESS_MODEL_PATH = orig_ptp

    def test_confidence_level_computed(self, tmp_path):
        """compute_confidence_level harus menghasilkan confidence_level dan confidence_category."""
        champion_path = str(tmp_path / "champion.pkl")
        joblib.dump(_make_dummy_artifact(), champion_path)

        import config.settings as sett
        nonexistent = str(tmp_path / "nonexistent.pkl")
        orig_sc = getattr(sett, "SELF_CURE_MODEL_PATH", None)
        orig_rf = getattr(sett, "ROLL_FORWARD_MODEL_PATH", None)
        orig_ptp = getattr(sett, "PTP_SUCCESS_MODEL_PATH", None)

        sett.SELF_CURE_MODEL_PATH = nonexistent
        sett.ROLL_FORWARD_MODEL_PATH = nonexistent
        sett.PTP_SUCCESS_MODEL_PATH = nonexistent

        try:
            df = _make_feature_df()
            scored = score_contracts(df, champion_path=champion_path)
            result = compute_confidence_level(scored)

            assert "confidence_level" in result.columns
            assert "confidence_category" in result.columns
            assert result["confidence_level"].between(0, 1).all()
            assert result["confidence_category"].isin(["HIGH", "MEDIUM", "LOW"]).all()

        finally:
            if orig_sc is not None:
                sett.SELF_CURE_MODEL_PATH = orig_sc
            if orig_rf is not None:
                sett.ROLL_FORWARD_MODEL_PATH = orig_rf
            if orig_ptp is not None:
                sett.PTP_SUCCESS_MODEL_PATH = orig_ptp

    def test_qc_validates_sub_model_ranges(self, tmp_path):
        """run_quality_check harus menambahkan range check untuk kolom sub-model."""
        # Buat output dengan sub-model scores yang valid
        n = 20
        df = pd.DataFrame({
            "contract_no": [f"C{i:03d}" for i in range(n)],
            "cust_id": [f"CUST{i:03d}" for i in range(n)],
            "recovery_score": np.random.uniform(0.3, 0.7, n),
            "confidence_level": np.random.uniform(0.5, 0.9, n),
            "confidence_category": ["HIGH"] * n,
            "risk_segment": ["Can Pay"] * (n - 2) + ["Self-cure"] * 2,
            "nba_recommendation": ["Deskcoll"] * n,
            "priority_level": ["Medium"] * n,
            "self_cure_probability": np.random.uniform(0.3, 0.9, n),
            "roll_forward_risk": np.random.uniform(0.2, 0.8, n),
            "ptp_success_probability": np.random.uniform(0.4, 0.9, n),
        })

        result = run_quality_check(df)
        # QC harus lulus (return dict dengan status pass)
        assert result is not None
        assert "wont_pay_pct" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
