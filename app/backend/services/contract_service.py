from typing import Dict, List, Optional, Tuple

from domain.models import ContractDetail, ContractListRow, PageInfo
from repositories.interfaces import IContractRepository
from services.pagination import build_page_info

VALID_CONTRACT_FILTERS = ("all", "dpd_30_plus", "high_priority", "broken_ptp", "high_ambc")

# Treatment_type nyata di lkp_interaction (lihat faker/generate-faker-realistic.py):
# WA, Deskcoll, Visit, Somasi, Pickup — TIDAK ada 'Call'/'WhatsApp'/'Telepon'
# seperti asumsi awal, mapping ini disesuaikan ke nilai asli yang benar-benar
# ada di database (bukan ditebak dari nama field). SMS dilebur ke WA (keputusan
# #7, ai-reasoning-api-upgrade-tasks.md P0-1) — tidak ada lagi baris SMS baru.
_TREATMENT_ICON_MAP = {
    "WA": "chat",
    "Visit": "home",
    "Deskcoll": "call",
    "Somasi": "gavel",
    "Pickup": "local_shipping",
}


def _activity_icon(treatment_type: Optional[str]) -> str:
    return _TREATMENT_ICON_MAP.get(treatment_type or "", "event_note")


def _activity_title(treatment_type: Optional[str], result_code: Optional[str], ptp_status: Optional[str]) -> str:
    treatment_label = treatment_type or "Aktivitas"
    result_label = result_code or "tidak ada hasil"
    if ptp_status == "BROKEN":
        return f"{treatment_label} — Broken Promise (PTP), hasil: {result_label}"
    return f"{treatment_label} — {result_label}"


_PTP_STATUS_PHRASE = {
    "KEPT": "janji bayar (PTP) ditepati",
    "BROKEN": "janji bayar (PTP) diingkari",
    "OPEN": "masih ada janji bayar (PTP) yang berjalan",
}


def _activity_description(treatment_type: Optional[str], result_code: Optional[str], ptp_status: Optional[str]) -> str:
    """Kalimat deskriptif lebih lengkap daripada _activity_title() di atas —
    dibangun dari kolom yang sama (lkp_interaction tidak punya kolom
    notes/remark bebas teks), tapi selalu terisi (tidak None) selama baris
    aktivitasnya sendiri ada (only truly missing data -> None di caller)."""
    treatment_label = treatment_type or "Aktivitas"
    result_label = result_code or "tidak ada hasil"
    description = f"Kontak via {treatment_label}, hasil: {result_label}"
    ptp_phrase = _PTP_STATUS_PHRASE.get(ptp_status or "")
    if ptp_phrase:
        description = f"{description} — {ptp_phrase}"
    return description


class ContractService:
    """Business logic layer untuk Contract (TASK-D) — router tidak pernah
    memanggil repository langsung (SRP, sama seperti CustomerService)."""

    def __init__(self, contract_repository: IContractRepository):
        self._repo = contract_repository

    def list_contracts(
        self, filter_key: str, search: Optional[str], page: int, page_size: int
    ) -> Tuple[List[ContractListRow], PageInfo]:
        filter_key = filter_key if filter_key in VALID_CONTRACT_FILTERS else "all"
        page = max(1, page)
        page_size = max(1, page_size)
        rows, total = self._repo.list_contracts_page(filter_key, search, page, page_size)
        return rows, build_page_info(total, page, page_size, len(rows))

    def get_contract_detail(self, contract_no: str) -> Optional[ContractDetail]:
        return self._repo.get_contract_detail(contract_no)

    def get_activity_log(self, contract_no: str) -> List[Dict]:
        entries = self._repo.get_activity_log(contract_no)
        return [
            {
                "id": e.lkp_id,
                "icon": _activity_icon(e.treatment_type),
                "title": _activity_title(e.treatment_type, e.result_code, e.ptp_status),
                "timestamp": e.action_date.strftime("%d %b %Y") if e.action_date else None,
                "description": _activity_description(e.treatment_type, e.result_code, e.ptp_status),
                "tone": "danger" if e.ptp_status == "BROKEN" else "default",
            }
            for e in entries
        ]
