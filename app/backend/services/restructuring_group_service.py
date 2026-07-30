from dataclasses import dataclass
from typing import List, Optional, Tuple

from domain.models import RestructuringGroupSummary, RestructuringOfferRecord
from repositories.interfaces import IRestructuringOfferRepository

DEFAULT_STATUSES = ["GENERATED"]


@dataclass
class ApprovalResult:
    """Hasil approve()/reject() — sama pola dengan CustomerResponseResult di
    restructuring_service.py: service TIDAK tahu soal HTTPException, router
    yang menerjemahkan error_code jadi status HTTP (Catatan #1
    backend-architecture-tasks.md)."""
    ok: bool
    record: Optional[RestructuringOfferRecord] = None
    error: Optional[str] = None
    error_code: Optional[str] = None  # 'NOT_FOUND' | 'INVALID_STATE'


class RestructuringGroupService:
    """Business logic TASK-E (Restructuring Approval) — approve/reject
    HANYA mengubah offer_status (GENERATED -> OFFERED/REJECTED) + audit,
    TIDAK PERNAH menghitung ulang angka tawaran (itu tetap murni tugas
    shared/restructuring_offer_calculator.py, dipakai RestructuringService
    yang terpisah)."""

    def __init__(self, offer_repository: IRestructuringOfferRepository):
        self._offers = offer_repository

    def list_groups(
        self,
        statuses: Optional[List[str]],
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[RestructuringGroupSummary], int]:
        return self._offers.list_offers(statuses or DEFAULT_STATUSES, search, page, page_size)

    def get_group(self, restructure_group_id: str) -> Optional[RestructuringGroupSummary]:
        return self._offers.get_offer_summary(restructure_group_id)

    def approve(self, restructure_group_id: str, performed_by: Optional[str]) -> ApprovalResult:
        return self._transition(restructure_group_id, "OFFERED", "APPROVE", performed_by)

    def reject(self, restructure_group_id: str, performed_by: Optional[str]) -> ApprovalResult:
        return self._transition(restructure_group_id, "REJECTED", "REJECT", performed_by)

    def _transition(
        self, restructure_group_id: str, new_status: str, action: str, performed_by: Optional[str]
    ) -> ApprovalResult:
        offer = self._offers.get_offer(restructure_group_id)
        if offer is None:
            return ApprovalResult(
                ok=False,
                error=f"Grup restrukturisasi {restructure_group_id} tidak ditemukan",
                error_code="NOT_FOUND",
            )
        if offer.offer_status != "GENERATED":
            return ApprovalResult(
                ok=False,
                error=f"Status saat ini '{offer.offer_status}' — hanya tawaran berstatus GENERATED yang bisa di-{action.lower()}",
                error_code="INVALID_STATE",
            )

        updated = self._offers.update_offer_status(restructure_group_id, new_status, action, performed_by)
        if not updated:
            # Race condition: status berubah di antara get_offer() di atas dan
            # UPDATE (mis. 2 supervisor approve bersamaan) — guard WHERE
            # offer_status='GENERATED' di UPDATE-nya sendiri yang menangkap ini.
            return ApprovalResult(
                ok=False,
                error="Status tawaran sudah berubah sebelum aksi ini selesai diproses, silakan refresh",
                error_code="INVALID_STATE",
            )

        return ApprovalResult(ok=True, record=self._offers.get_offer(restructure_group_id))
