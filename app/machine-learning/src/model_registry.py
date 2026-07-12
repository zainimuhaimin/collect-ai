"""Model registry berbasis JSON untuk CollectAI."""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import REGISTRY_PATH, CHAMPION_MODEL_PATH


def _default_registry() -> dict:
    return {
        "current_champion": None,
        "current_challenger": None,
        "history": [],
    }


def _load_registry() -> dict:
    if not os.path.exists(REGISTRY_PATH):
        return _default_registry()
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_registry(registry: dict) -> None:
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)


def register_model(model_path, metadata, role="challenger") -> str:
    registry = _load_registry()
    version = f"v{len(registry.get('history', [])) + 1}"
    entry = {
        "version": version,
        "path": model_path,
        "role": role,
        "registered": datetime.now().isoformat(),
        **(metadata or {}),
    }
    registry.setdefault("history", []).append(entry)

    if role == "champion":
        registry["current_champion"] = entry
    elif role == "challenger":
        registry["current_challenger"] = entry
    else:
        raise ValueError("role harus champion atau challenger")

    _save_registry(registry)
    return version


def get_champion_path() -> str:
    registry = _load_registry()
    champ = registry.get("current_champion")
    if not champ:
        raise FileNotFoundError("Belum ada champion model di registry")
    return champ["path"]


def get_challenger_path() -> str | None:
    registry = _load_registry()
    challenger = registry.get("current_challenger")
    return challenger["path"] if challenger else None


def get_performance_history(last_n=10):
    registry = _load_registry()
    hist = registry.get("history", [])[-last_n:]
    print("\nModel Performance History")
    print(f"{'Ver':<6} {'Role':<12} {'AUC':<8} {'Samples':<10} {'Date'}")
    print("-" * 65)
    for e in hist:
        print(
            f"{e.get('version','-'):<6} {e.get('role','-'):<12} "
            f"{e.get('auc','-')!s:<8} {e.get('n_samples','-')!s:<10} "
            f"{str(e.get('registered',''))[:10]}"
        )
    return hist


def rollback_to_previous() -> dict:
    registry = _load_registry()
    current = registry.get("current_champion")
    history = registry.get("history", [])

    previous = [
        e for e in history
        if e.get("role") == "champion" and (not current or e.get("version") != current.get("version"))
    ]
    if not previous:
        raise ValueError("Tidak ada champion sebelumnya untuk rollback")

    prev = previous[-1]
    prev_path = prev.get("path")
    if not prev_path or not os.path.exists(prev_path):
        raise FileNotFoundError(f"Artifact champion sebelumnya tidak ditemukan: {prev_path}")

    if os.path.abspath(prev_path) != os.path.abspath(CHAMPION_MODEL_PATH):
        os.makedirs(os.path.dirname(CHAMPION_MODEL_PATH), exist_ok=True)
        shutil.copy(prev_path, CHAMPION_MODEL_PATH)
        prev = {**prev, "path": CHAMPION_MODEL_PATH}

    registry["current_champion"] = prev
    _save_registry(registry)
    return prev
