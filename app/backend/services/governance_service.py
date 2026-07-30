from dataclasses import dataclass
from typing import List, Optional, Tuple

from domain.models import CbsWeight, GovernanceAuditEntry, ModelHealthSnapshot
from repositories.interfaces import IGovernanceConfigRepository

WEIGHT_SUM_TOLERANCE = 0.01


@dataclass
class WeightingUpdateResult:
    ok: bool
    weights: Optional[List[CbsWeight]] = None
    error: Optional[str] = None


class GovernanceService:
    """Business logic TASK-F fase 1 (Bobot CBS). Validasi sum(weight)==100
    ada DI SINI (bukan di schema Pydantic) supaya pesan error bisa
    menyertakan total yang salah — lebih informatif untuk UI slider."""

    def __init__(self, governance_repository: IGovernanceConfigRepository):
        self._repo = governance_repository

    def get_cbs_weights(self) -> List[CbsWeight]:
        return self._repo.get_cbs_weights()

    def get_model_health(self) -> Optional[ModelHealthSnapshot]:
        return self._repo.get_model_health()

    def update_weights(self, weights: List[CbsWeight], performed_by: Optional[str]) -> WeightingUpdateResult:
        total = sum(w.weight for w in weights)
        if abs(total - 100.0) > WEIGHT_SUM_TOLERANCE:
            return WeightingUpdateResult(
                ok=False, error=f"Total bobot harus 100 (dapat {total:.2f}) — lihat WEIGHT_SUM_TOLERANCE"
            )
        saved = self._repo.save_cbs_weights(weights, performed_by)
        return WeightingUpdateResult(ok=True, weights=saved)

    def list_operational_log(self) -> List[GovernanceAuditEntry]:
        return self._repo.list_operational_log()
