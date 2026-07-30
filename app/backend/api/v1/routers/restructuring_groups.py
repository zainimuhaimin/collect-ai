from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.dependencies import get_current_user, get_restructuring_group_service
from domain.models import User
from schemas.restructuring_group import (
    RestructuringGroupActionResult,
    RestructuringGroupItem,
    RestructuringGroupListResponse,
    RestructuringGroupPageInfo,
)
from services.restructuring_group_service import RestructuringGroupService

router = APIRouter(prefix="/restructuring-groups", tags=["restructuring-approval"])

_ERROR_CODE_TO_STATUS = {"NOT_FOUND": 404, "INVALID_STATE": 409}


def _to_item(record) -> RestructuringGroupItem:
    return RestructuringGroupItem(
        restructure_group_id=record.restructure_group_id,
        cust_id=record.cust_id,
        contract_nos=record.contract_nos,
        offer_type=record.offer_type,
        eligibility_tier=record.eligibility_tier,
        eligibility_reasons=record.eligibility_reasons,
        npv_baseline=record.npv_baseline,
        npv_restructured=record.npv_restructured,
        npv_restructured_risk_adjusted=record.npv_restructured_risk_adjusted,
        total_remaining_current=record.total_remaining_current,
        total_new_schedule=record.total_new_schedule,
        generated_date=record.generated_date.isoformat(),
        offer_status=record.offer_status,
    )


@router.get(
    "",
    response_model=RestructuringGroupListResponse,
    summary="Queue approval Restructuring (TASK-E) — paginasi",
    description="""
Default `status=GENERATED` (antrean approval supervisor). Terima
comma-separated untuk tab histori, mis. `status=OFFERED,REJECTED`.

Setiap grup menyertakan `contract_nos` (bisa >1 untuk `offer_type=CONSOLIDATE`,
dari `restructuring_group_map`).

**`search`** (opsional) — substring match ke `restructure_group_id` ATAU
`cust_id`. Dipaginasi sama seperti Customer/Contract list (`page`/`page_size`).
""",
)
def list_restructuring_groups(
    status: Optional[str] = Query(None, description="Comma-separated, default GENERATED"),
    search: Optional[str] = Query(None, description="Substring match ke restructure_group_id atau cust_id"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: RestructuringGroupService = Depends(get_restructuring_group_service),
):
    statuses = [s.strip() for s in status.split(",") if s.strip()] if status else None
    groups, total = service.list_groups(statuses, search, page, page_size)
    total_pages = max(1, (total + page_size - 1) // page_size)
    showing_from = 0 if total == 0 else (page - 1) * page_size + 1
    showing_to = min(page * page_size, total)
    return RestructuringGroupListResponse(
        groups=[_to_item(r) for r in groups],
        page_info=RestructuringGroupPageInfo(
            showing_from=showing_from,
            showing_to=showing_to,
            total_groups=total,
            total_pages=total_pages,
        ),
    )


@router.get(
    "/{restructure_group_id}",
    response_model=RestructuringGroupItem,
    summary="Detail 1 grup restrukturisasi",
    description="Bentuk response SAMA dengan 1 item di GET /restructuring-groups (list), "
    "cuma untuk 1 restructure_group_id spesifik.",
    responses={404: {"description": "restructure_group_id tidak ditemukan"}},
)
def get_restructuring_group_detail(
    restructure_group_id: str,
    service: RestructuringGroupService = Depends(get_restructuring_group_service),
):
    record = service.get_group(restructure_group_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Grup restrukturisasi {restructure_group_id} tidak ditemukan",
        )
    return _to_item(record)


@router.post(
    "/{restructure_group_id}/approve",
    response_model=RestructuringGroupActionResult,
    summary="Approve tawaran (GENERATED -> OFFERED)",
    description="Tampil ke semua user login TANPA pembatasan role (RBAC ditunda, lihat TASK-A) — "
    "`Depends(get_current_user)` di sini HANYA untuk audit trail (siapa yang approve), bukan gate akses. "
    "Mencatat 1 baris `restructuring_approval_log` (action=APPROVE).",
    responses={
        404: {"description": "restructure_group_id tidak ditemukan"},
        409: {"description": "Status saat ini bukan GENERATED (sudah pernah diproses)"},
    },
)
def approve_restructuring_group(
    restructure_group_id: str,
    service: RestructuringGroupService = Depends(get_restructuring_group_service),
    current_user: User = Depends(get_current_user),
):
    result = service.approve(restructure_group_id, current_user.username)
    if not result.ok:
        raise HTTPException(status_code=_ERROR_CODE_TO_STATUS.get(result.error_code, 400), detail=result.error)
    return _to_action_result(result.record)


@router.post(
    "/{restructure_group_id}/reject",
    response_model=RestructuringGroupActionResult,
    summary="Reject tawaran (GENERATED -> REJECTED)",
    description="Tanpa body/alasan wajib (keputusan final, lihat TASK-E). Mencatat 1 baris "
    "`restructuring_approval_log` (action=REJECT). Sama seperti approve, tidak ada gate role.",
    responses={
        404: {"description": "restructure_group_id tidak ditemukan"},
        409: {"description": "Status saat ini bukan GENERATED (sudah pernah diproses)"},
    },
)
def reject_restructuring_group(
    restructure_group_id: str,
    service: RestructuringGroupService = Depends(get_restructuring_group_service),
    current_user: User = Depends(get_current_user),
):
    result = service.reject(restructure_group_id, current_user.username)
    if not result.ok:
        raise HTTPException(status_code=_ERROR_CODE_TO_STATUS.get(result.error_code, 400), detail=result.error)
    return _to_action_result(result.record)


def _to_action_result(record) -> RestructuringGroupActionResult:
    return RestructuringGroupActionResult(
        restructure_group_id=record.restructure_group_id,
        cust_id=record.cust_id,
        offer_type=record.offer_type,
        offer_status=record.offer_status,
        generated_date=record.generated_date.isoformat(),
        expiry_date=record.expiry_date.isoformat() if record.expiry_date else None,
    )
