"""Service Sync AI Intelligence (training-if-missing + scoring) — dipicu tombol
di halaman AI Intelligence frontend (belum digarap, dipersiapkan di sini).

Alurnya untuk tiap model_type (recovery/self_cure/roll_forward/ptp_success):
kalau belum punya champion sama sekali (dicek langsung dari
app/machine-learning/models/registry.json, TANPA import modul ml/ ke proses
backend — cukup baca file JSON-nya), latih dulu (subprocess ke
pipelines/train_*.py) SEBELUM scoring. `recovery` WAJIB ada championnya
(pipelines/daily_scoring.py raise FileNotFoundError kalau tidak ada — lihat
src/scoring_engine.py::score_contracts, recovery_score tidak boleh NULL); 3
model_type lain (self_cure/roll_forward/ptp_success) tetap dilatih kalau belum
ada supaya scoring-nya lengkap — kalau dilewati, scoring_engine tetap jalan
tapi kolom itu jadi NULL (soft-degrade, bukan hard-fail), jadi lebih baik
dilatih dulu di sini. Baru setelah SEMUA model_type siap, jalankan
pipelines/daily_scoring.py SEKALI (menghasilkan ke-4 skor sekaligus lewat
score_contracts(), BUKAN dipanggil per model_type — 1 langkah "daily_scoring"
gabungan di akhir, bukan 4 langkah scoring terpisah).

pipelines/weekly_mlops.py dijalankan SELALU sebagai langkah terakhir setelah
daily_scoring.py sukses. Script itu satu-satunya penulis model_monitoring_log
(sumber kartu "Scoring Model Health" + hitungan drift di halaman AI
Intelligence). Sebelumnya langkah ini hanya jalan kalau job melatih model dari
nol, yang berarti begitu ke-4 champion ada, SEMUA sync berikutnya tidak
memperbarui monitoring sama sekali — kartu health-nya beku di angka run
pertama, dan di environment yang model-nya sudah disalin masuk (champion ada
tanpa pernah training) barisnya tidak pernah dibuat sehingga kartunya
placeholder selamanya. Drift dihitung ulang tiap scoring baru, jadi run-nya
memang harus mengikuti tiap scoring, bukan hanya training pertama.

Tiap job yang selesai/gagal juga dicatat 1 baris ke model_governance_audit_log
(lewat repository), supaya tabel "Operational Log" di halaman AI Intelligence
benar-benar merekam aktivitas model. Sebelumnya satu-satunya penulis tabel itu
di seluruh repo adalah penyimpanan bobot CBS, jadi sync — aktivitas model yang
paling utama — tidak pernah muncul di log operasional sama sekali. State
in-memory tidak cukup untuk ini karena hilang setiap backend restart.

Job berjalan di background thread (`threading.Thread(daemon=True)`, BUKAN
asyncio/BackgroundTasks) karena ini genuinely CPU/subprocess-bound dan bisa
makan waktu lama (training 4 model + scoring) — event loop FastAPI tidak
boleh ikut nge-block selama itu. Hanya 1 job boleh jalan sekaligus (guarded
`_lock` module-level); panggilan POST /ai-intelligence/sync saat masih ada
job `running` -> ditolak (409 di router), TIDAK di-queue/antre.

State job (`_state`) MURNI in-memory, SENGAJA module-level singleton (bukan
atribut instance) — service ini bisa dibuat ulang per-request (tidak
di-`lru_cache` seperti service lain di core/dependencies.py) tapi job Sync
harus tetap 1 untuk SELURUH proses backend. Ephemeral, hilang kalau proses
backend restart — cukup untuk kebutuhan tombol Sync, tidak perlu tabel DB.

`last_scored_at` (di GET status) TIDAK lewat state ini — itu baca real-time
dari DB lewat IAiIntelligenceSyncRepository tiap kali GET dipanggil, independen
dari job yang sedang/sudah berjalan (lihat get_status())."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Optional, Tuple

from core.config import settings
from domain.models import SyncJobState, SyncStep
from repositories.interfaces import IAiIntelligenceSyncRepository

# services/ai_intelligence_sync_service.py -> services -> backend -> app -> repo_root
# (pola dirname yang sama dipakai core/config.py::_REPO_ROOT — file ini juga
# langsung anak dari app/backend/, jadi jumlah dirname()-nya sama persis)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_ML_ROOT = os.path.join(_REPO_ROOT, "app", "machine-learning")
_REGISTRY_PATH = os.path.join(_ML_ROOT, "models", "registry.json")

MODEL_TYPES = ("recovery", "self_cure", "roll_forward", "ptp_success")

_TRAIN_SCRIPT_BY_TYPE = {
    "recovery": "pipelines/train_initial_model.py",
    "self_cure": "pipelines/train_self_cure.py",
    "roll_forward": "pipelines/train_roll_forward.py",
    "ptp_success": "pipelines/train_ptp_success.py",
}
_DAILY_SCORING_SCRIPT = "pipelines/daily_scoring.py"
_WEEKLY_MLOPS_SCRIPT = "pipelines/weekly_mlops.py"

_STDERR_TAIL_CHARS = 4000

# ── Module-level singleton job-state — lihat docstring modul di atas ──
_lock = threading.Lock()
_state = SyncJobState()


def _has_champion(model_type: str) -> bool:
    """Baca registry.json APA ADANYA (file biasa, bukan lewat modul ml/) —
    falsy `current_champion` (None/tidak ada key model_type-nya sama sekali)
    berarti model_type ini belum pernah dilatih sekalipun."""
    try:
        with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    return bool(data.get("model_types", {}).get(model_type, {}).get("current_champion"))


def _ml_python() -> str:
    """Interpreter Python utk subprocess ke app/machine-learning/ — configurable
    lewat ML_PYTHON_INTERPRETER (.env), default sys.executable (proses backend
    & ML share 1 venv saat ini, TIDAK di-hardcode supaya tetap bisa dipisah
    venv-nya nanti tanpa ubah kode)."""
    return settings.ml_python_interpreter or sys.executable


class AiIntelligenceSyncService:
    """Business logic tombol Sync AI Intelligence — lihat docstring modul ini
    untuk alur lengkap. Router TIDAK PERNAH subprocess/thread langsung (SRP,
    sama seperti service lain di backend ini)."""

    def __init__(self, sync_repository: IAiIntelligenceSyncRepository):
        self._repo = sync_repository

    # ── GET /ai-intelligence/sync/status ──

    def get_status(self) -> dict:
        # Baca last_scored_at DULU (real-time dari DB), baru snapshot state
        # in-memory — 2 hal ini SENGAJA independen (last_scored_at tetap
        # berguna walau tidak ada job yang pernah jalan lewat endpoint ini,
        # mis. scoring dijalankan manual lewat cron/CLI di luar backend).
        last_scored_at = self._repo.get_last_scored_at()
        with _lock:
            steps = []
            for s in _state.steps:
                step = asdict(s)
                step["started_at"] = s.started_at.isoformat() if s.started_at else None
                steps.append(step)
            status, started_at, finished_at, error = (
                _state.status,
                _state.started_at,
                _state.finished_at,
                _state.error,
            )
        return {
            "status": status,
            "started_at": started_at.isoformat() if started_at else None,
            "finished_at": finished_at.isoformat() if finished_at else None,
            "steps": steps,
            "last_scored_at": last_scored_at.isoformat() if last_scored_at else None,
            "error": error,
        }

    # ── POST /ai-intelligence/sync ──

    def start_sync(self) -> Tuple[bool, str]:
        """Return (True, job_id) kalau berhasil dimulai, atau (False,
        pesan_error) kalau ada job lain yang masih `running` — router yang
        menerjemahkan False jadi HTTP 409 (service tidak tahu soal
        HTTPException, pola yang sama dengan service lain di backend ini)."""
        global _state
        with _lock:
            if _state.status == "running":
                return False, "Sync AI Intelligence lain sedang berjalan, tunggu sampai selesai"

            job_id = str(uuid.uuid4())
            # Dihitung SEBELUM training mulai (registry.json belum berubah sama
            # sekali di titik ini). Dipakai HANYA untuk pelaporan (audit detail
            # + status job), BUKAN lagi untuk memutuskan apakah weekly_mlops.py
            # dijalankan — langkah itu sekarang selalu ada, lihat docstring modul.
            did_train_from_scratch = not all(_has_champion(mt) for mt in MODEL_TYPES)
            steps = [
                SyncStep(model_type=mt, action=("score_only" if _has_champion(mt) else "train_then_score"))
                for mt in MODEL_TYPES
            ]
            steps.append(SyncStep(model_type="daily_scoring", action="score"))
            steps.append(SyncStep(model_type="weekly_mlops", action="weekly_monitoring"))
            _state = SyncJobState(
                status="running",
                started_at=datetime.now(),
                steps=steps,
                did_train_from_scratch=did_train_from_scratch,
            )

        thread = threading.Thread(target=self._run_job, daemon=True)
        thread.start()
        return True, job_id

    # ── Internal: dijalankan di background thread ──

    def _run_job(self):
        try:
            for model_type in MODEL_TYPES:
                action = self._get_step_action(model_type)
                if action == "train_then_score":
                    self._set_step_status(model_type, "running")
                    ok, err_tail = self._run_script(_TRAIN_SCRIPT_BY_TYPE[model_type])
                    if not ok:
                        self._set_step_status(model_type, "failed")
                        self._fail_job(f"Training model_type='{model_type}' gagal:\n{err_tail}")
                        return
                # action == "score_only" -> tidak perlu training, langsung "done"
                # (skor-nya sendiri dihasilkan bareng di langkah daily_scoring).
                self._set_step_status(model_type, "done")

            self._set_step_status("daily_scoring", "running")
            ok, err_tail = self._run_script(_DAILY_SCORING_SCRIPT)
            if not ok:
                self._set_step_status("daily_scoring", "failed")
                self._fail_job(f"daily_scoring.py gagal:\n{err_tail}")
                return
            self._set_step_status("daily_scoring", "done")

            # SELALU dijalankan (bukan hanya saat training dari nol): drift dan
            # health dihitung dari hasil scoring, jadi harus ikut tiap scoring
            # baru — lihat docstring modul.
            self._set_step_status("weekly_mlops", "running")
            ok, err_tail = self._run_script(_WEEKLY_MLOPS_SCRIPT)
            if not ok:
                self._set_step_status("weekly_mlops", "failed")
                self._fail_job(f"weekly_mlops.py gagal:\n{err_tail}")
                return
            self._set_step_status("weekly_mlops", "done")

            with _lock:
                _state.status = "completed"
                _state.finished_at = datetime.now()
                trained = [s.model_type for s in _state.steps if s.action == "train_then_score"]
            self._log_event(
                "MODEL_SYNC",
                "Success",
                {"trained_from_scratch": trained, "scored": True, "monitoring": True},
            )
        except Exception as exc:  # thread daemon tidak boleh mati diam-diam tanpa mengubah status
            self._fail_job(f"Sync gagal tak terduga: {exc!r}")

    @staticmethod
    def _run_script(relative_path: str) -> Tuple[bool, Optional[str]]:
        result = subprocess.run(
            [_ml_python(), relative_path],
            cwd=_ML_ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "(tidak ada output)")[-_STDERR_TAIL_CHARS:]
            return False, tail
        return True, None

    @staticmethod
    def _get_step_action(model_type: str) -> Optional[str]:
        with _lock:
            for s in _state.steps:
                if s.model_type == model_type:
                    return s.action
        return None

    @staticmethod
    def _set_step_status(model_type: str, status: str):
        with _lock:
            for s in _state.steps:
                if s.model_type == model_type:
                    if status == "running":
                        s.started_at = datetime.now()
                    elif status in ("done", "failed") and s.started_at is not None:
                        s.duration_s = (datetime.now() - s.started_at).total_seconds()
                    s.status = status
                    break

    def _log_event(self, action: str, status: str, detail: dict):
        """Catat job ke audit log. Repository-nya sudah menelan error-nya
        sendiri (audit gagal tidak boleh menggagalkan job) — try/except di sini
        cuma jaring terakhir kalau repository-nya sendiri yang tidak tersedia."""
        try:
            self._repo.log_sync_event(action, status, detail)
        except Exception as exc:
            print(f"[sync-audit] tidak bisa mencatat '{action}': {exc!r}")

    def _fail_job(self, error: str):
        with _lock:
            _state.status = "failed"
            _state.finished_at = datetime.now()
            _state.error = error
            failed_step = next((s.model_type for s in _state.steps if s.status == "failed"), None)
        self._log_event("MODEL_SYNC", "Failed", {"failed_step": failed_step, "error": error})
