"""Model registry berbasis JSON untuk CollectAI.

Setiap model_type (recovery, self_cure, roll_forward, ptp_success) punya
riwayat versi dan slot champion/challenger sendiri-sendiri di dalam
registry.json (dikelompokkan di bawah key "model_types"). Ini memastikan
retrain salah satu sub-model tidak "mencuri" nomor versi model_type lain,
dan tiap model_type bisa di-rollback secara independen.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import REGISTRY_PATH, MODEL_TYPE_PATHS

DEFAULT_MODEL_TYPE = "recovery"


def _default_type_bucket() -> dict:
    return {"current_champion": None, "current_challenger": None, "history": []}


def _default_registry() -> dict:
    return {"model_types": {}}


def _load_registry() -> dict:
    if not os.path.exists(REGISTRY_PATH):
        return _default_registry()
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "model_types" not in data:
        # Format lama (1 counter versi global, tanpa pemisahan model_type).
        # Dibangun ulang bersih begitu model_type diregister lagi — history
        # lama tidak dipetakan otomatis karena skema versi/role-nya berbeda.
        data = _default_registry()
    return data


def _save_registry(registry: dict) -> None:
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, default=str)


def _bucket(registry: dict, model_type: str) -> dict:
    return registry.setdefault("model_types", {}).setdefault(model_type, _default_type_bucket())


def register_model(model_path, metadata, role="challenger", model_type=DEFAULT_MODEL_TYPE) -> str:
    """Daftarkan model ke registry. Versi (vN) dihitung per model_type,
    independen dari model_type lain (self_cure v1, v2, ... terpisah dari
    recovery v1, v2, ...)."""
    registry = _load_registry()
    bucket = _bucket(registry, model_type)
    version = f"v{len(bucket['history']) + 1}"
    entry = {
        "version": version,
        "path": model_path,
        "role": role,
        "model_type": model_type,
        "registered": datetime.now().isoformat(),
        **(metadata or {}),
    }
    bucket["history"].append(entry)

    if role == "champion":
        bucket["current_champion"] = entry
    elif role == "challenger":
        bucket["current_challenger"] = entry
    else:
        bucket[f"current_{role}"] = entry

    _save_registry(registry)
    return version


def get_champion_path(model_type=DEFAULT_MODEL_TYPE) -> str:
    registry = _load_registry()
    champ = registry.get("model_types", {}).get(model_type, {}).get("current_champion")
    if not champ:
        raise FileNotFoundError(f"Belum ada champion model untuk model_type='{model_type}'")
    return champ["path"]


def get_challenger_path(model_type=DEFAULT_MODEL_TYPE) -> str | None:
    registry = _load_registry()
    challenger = registry.get("model_types", {}).get(model_type, {}).get("current_challenger")
    return challenger["path"] if challenger else None


def get_performance_history(model_type=None, last_n=10):
    """Cetak riwayat performa model. Jika model_type None, semua model_type
    yang ada di registry ditampilkan, masing-masing dalam tabelnya sendiri
    (tidak dicampur jadi satu tabel dengan versi yang saling tumpang tindih)."""
    registry = _load_registry()
    model_types_data = registry.get("model_types", {})
    types_to_show = [model_type] if model_type else list(model_types_data.keys())

    all_hist = []
    for mtype in types_to_show:
        bucket = model_types_data.get(mtype, {})
        hist = bucket.get("history", [])[-last_n:]
        if not hist:
            continue
        print(f"\nModel Performance History — model_type='{mtype}'")
        print(f"{'Ver':<6} {'Role':<12} {'AUC':<8} {'Samples':<10} {'Date'}")
        print("-" * 65)
        for e in hist:
            print(
                f"{e.get('version','-'):<6} {e.get('role','-'):<12} "
                f"{e.get('auc','-')!s:<8} {e.get('n_samples','-')!s:<10} "
                f"{str(e.get('registered',''))[:10]}"
            )
        all_hist.extend(hist)
    return all_hist


def rollback_to_previous(model_type=DEFAULT_MODEL_TYPE) -> dict:
    """Rollback champion model_type tertentu ke versi champion sebelumnya."""
    registry = _load_registry()
    bucket = _bucket(registry, model_type)
    current = bucket.get("current_champion")
    history = bucket.get("history", [])

    previous = [
        e for e in history
        if e.get("role") == "champion" and (not current or e.get("version") != current.get("version"))
    ]
    if not previous:
        raise ValueError(f"Tidak ada champion sebelumnya untuk model_type='{model_type}'")

    prev = previous[-1]
    prev_path = prev.get("path")
    if not prev_path or not os.path.exists(prev_path):
        raise FileNotFoundError(f"Artifact champion sebelumnya tidak ditemukan: {prev_path}")

    target_path = MODEL_TYPE_PATHS.get(model_type, {}).get("champion", prev_path)
    if os.path.abspath(prev_path) != os.path.abspath(target_path):
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        shutil.copy(prev_path, target_path)
        prev = {**prev, "path": target_path}

    bucket["current_champion"] = prev
    _save_registry(registry)
    return prev
