from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.dependencies import get_contract_service
from schemas.contract import (
    ActivityLogEntrySchema,
    AiScoringSchema,
    ContractDetailSchema,
    ContractListItem,
    ContractListResponse,
    ContractPageInfo,
    OutstandingBreakdown,
    PaymentHistoryItem,
    RestructuringStatusSchema,
)
from services.contract_service import VALID_CONTRACT_FILTERS, ContractService
from services.formatting import format_rupiah

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get(
    "",
    response_model=ContractListResponse,
    summary="Daftar Contract (filter chip + search + paginasi)",
    description=f"""
Mirip list Customer (TASK-C), tapi murni PER-BARIS — `ambc`/`ptp_status`
memang atribut kontrak, jadi tidak ada agregasi "punya kontrak yang...".

**`filter`** (single-select, default `all`): {', '.join(VALID_CONTRACT_FILTERS)}.

**`search`** — substring match ke `contract_no` ATAU `cust_id`.
""",
)
def list_contracts(
    filter: str = Query("all", description="all | dpd_30_plus | high_priority | broken_ptp | high_ambc"),
    search: Optional[str] = Query(None, description="Substring match ke contract_no atau cust_id"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    service: ContractService = Depends(get_contract_service),
):
    rows, page_info = service.list_contracts(filter, search, page, page_size)
    return ContractListResponse(
        contracts=[
            ContractListItem(
                contract_no=r.contract_no,
                cust_id=r.cust_id,
                cust_name=r.cust_name,
                product_type=r.product_type,
                dpd_current=r.dpd_current,
                outstanding=format_rupiah(r.outstanding),
                risk_segment=r.risk_segment,
            )
            for r in rows
        ],
        page_info=ContractPageInfo(
            showing_from=page_info.showing_from,
            showing_to=page_info.showing_to,
            total_contracts=page_info.total_count,
            total_pages=page_info.total_pages,
        ),
    )


@router.get(
    "/{contract_no}",
    response_model=ContractDetailSchema,
    summary="Detail penuh 1 kontrak (7 bagian)",
    description="Ringkasan kontrak + rincian outstanding + AI scoring + riwayat pembayaran (12 "
    "terakhir) + status restrukturisasi (read-only), digabung 1 payload (lihat catatan penutup "
    "frontend-layout-upgrade-tasks.md).",
    responses={404: {"description": "contract_no tidak ditemukan di contract_snapshot"}},
)
def get_contract_detail(contract_no: str, service: ContractService = Depends(get_contract_service)):
    detail = service.get_contract_detail(contract_no)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Contract {contract_no} tidak ditemukan")

    ai_scoring = None
    if detail.ai_scoring:
        ai_scoring = AiScoringSchema(
            recovery_score=detail.ai_scoring.recovery_score,
            risk_segment=detail.ai_scoring.risk_segment,
            self_cure_probability=detail.ai_scoring.self_cure_probability,
            roll_forward_risk=detail.ai_scoring.roll_forward_risk,
            ptp_success_probability=detail.ai_scoring.ptp_success_probability,
            nba_recommendation=detail.ai_scoring.nba_recommendation,
            confidence_level=detail.ai_scoring.confidence_level,
            scoring_date=detail.ai_scoring.scoring_date.isoformat() if detail.ai_scoring.scoring_date else None,
        )

    restructuring_status = None
    if detail.restructuring_status:
        restructuring_status = RestructuringStatusSchema(
            restructure_group_id=detail.restructuring_status.restructure_group_id,
            offer_status=detail.restructuring_status.offer_status,
            eligibility_tier=detail.restructuring_status.eligibility_tier,
        )

    return ContractDetailSchema(
        contract_no=detail.contract_no,
        cust_id=detail.cust_id,
        cust_name=detail.cust_name,
        product_type=detail.product_type,
        cycle=detail.cycle,
        prev_cycle=detail.prev_cycle,
        closed_via_restructure=detail.closed_via_restructure,
        new_contract_no=detail.new_contract_no,
        loan_amount=detail.loan_amount,
        installment_amount=detail.installment_amount,
        interest_rate=detail.interest_rate,
        maturity_date=detail.maturity_date.isoformat() if detail.maturity_date else None,
        remaining_tenor_months=detail.remaining_tenor_months,
        dpd_current=detail.dpd_current,
        overdue_installment_count=detail.overdue_installment_count,
        late_fee_amount=detail.late_fee_amount,
        ambc=detail.ambc,
        outstanding=OutstandingBreakdown(
            principal=detail.principal_ots,
            interest=detail.interest_ots,
            total=detail.principal_ots + detail.interest_ots,
        ),
        ai_scoring=ai_scoring,
        payment_history=[
            PaymentHistoryItem(
                due_date=p.due_date.isoformat() if p.due_date else None,
                actual_pay_date=p.actual_pay_date.isoformat() if p.actual_pay_date else None,
                payment_amount=p.payment_amount,
                pay_status=p.pay_status,
                delay_days=p.delay_days,
                recovery_source=p.recovery_source,
            )
            for p in detail.payment_history
        ],
        restructuring_status=restructuring_status,
    )


@router.get(
    "/{contract_no}/activity-log",
    response_model=List[ActivityLogEntrySchema],
    summary="Timeline aktivitas kontrak (lkp_interaction)",
    description="Endpoint yang SAMA dipakai 2 tempat: Contract Detail (timeline penuh) dan expand "
    "per-kontrak di Customer Detail — supaya datanya selalu konsisten (1 sumber kebenaran). "
    "ORDER BY action_date DESC.",
)
def get_contract_activity_log(contract_no: str, service: ContractService = Depends(get_contract_service)):
    return [ActivityLogEntrySchema(**entry) for entry in service.get_activity_log(contract_no)]
