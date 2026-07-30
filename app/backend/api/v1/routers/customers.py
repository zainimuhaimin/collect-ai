from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.dependencies import get_customer_service
from core.text_utils import compute_initials
from schemas.customer import (
    CustomerContractItem,
    CustomerListItem,
    CustomerListResponse,
    CustomerPageInfo,
    CustomerProfileSchema,
)
from services.customer_service import VALID_CUSTOMER_FILTERS, CustomerService
from services.formatting import format_rupiah

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get(
    "",
    response_model=CustomerListResponse,
    summary="Daftar Customer (filter chip + search + paginasi)",
    description=f"""
Daftar customer dari `customer_master` + `customer_behavioral_standing`.
`priority` adalah level-Customer: MAX() priority di antara SEMUA kontrak
AKTIF (belum `closed_via_restructure`) milik customer tersebut (Critical >
High > Medium), BUKAN dari 1 kontrak yang dipilih arbitrer seperti versi
sebelumnya. `dpd_30_plus` TETAP memakai kontrak UTAMA (primary contract —
kontrak aktif dengan total OTS terbesar) untuk kriteria filternya, kolom itu
sendiri tidak diekspos di response.

**`filter`** (single-select, default `all`): {', '.join(VALID_CUSTOMER_FILTERS)}.
- `dpd_30_plus` — kontrak utama `dpd_current >= 30`.
- `high_priority` — customer punya **>=1 kontrak aktif** dengan priority
  High/Critical (EXISTS, konsisten dengan definisi `priority` di atas).
- `broken_ptp` — customer punya **>=1 kontrak apa saja** (bukan cuma kontrak
  utama) dengan `ptp_status` TERAKHIR = `BROKEN`.
- `high_ambc` — customer punya >=1 kontrak dengan `ambc` di atas persentil-75
  seluruh kontrak.

**`search`** — substring match ke `cust_id`.
""",
)
def list_customers(
    filter: str = Query("all", description="all | dpd_30_plus | high_priority | broken_ptp | high_ambc"),
    search: Optional[str] = Query(None, description="Substring match ke cust_id"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    service: CustomerService = Depends(get_customer_service),
):
    rows, page_info = service.list_customers_page(filter, search, page, page_size)
    return CustomerListResponse(
        customers=[
            CustomerListItem(
                cust_id=r.cust_id,
                name=r.name,
                active_contract_count=r.active_contract_count,
                behavioral_grade=r.behavioral_grade,
                b_list_status=r.b_list_status,
                priority=r.priority,
            )
            for r in rows
        ],
        page_info=CustomerPageInfo(
            showing_from=page_info.showing_from,
            showing_to=page_info.showing_to,
            total_customers=page_info.total_count,
            total_pages=page_info.total_pages,
        ),
    )


@router.get(
    "/{cust_id}",
    response_model=CustomerProfileSchema,
    summary="Detail 360° satu customer",
    description="Join `customer_master` + `customer_behavioral_standing` + kontrak utama (primary "
    "contract) + skor `ai_intelligence_output` kontrak itu. `risk_segment` apa adanya dari DB, "
    "TIDAK diterjemahkan jadi label lain.",
    responses={404: {"description": "cust_id tidak ditemukan di customer_master"}},
)
def get_customer_detail(cust_id: str, service: CustomerService = Depends(get_customer_service)):
    profile = service.get_customer_profile(cust_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Customer {cust_id} tidak ditemukan")

    return CustomerProfileSchema(
        cust_id=profile.cust_id,
        name=profile.name,
        initials=compute_initials(profile.name),
        outstanding_balance=format_rupiah(profile.outstanding_balance),
        risk_segment=profile.risk_segment,
        risk_score=round(profile.recovery_score * 100),
        recovery_score=profile.recovery_score,
        self_cure_probability=profile.self_cure_probability,
        roll_forward_risk=profile.roll_forward_risk,
        ptp_success_probability=profile.ptp_success_probability,
        nba_recommendation=profile.nba_recommendation,
        behavioral_grade=profile.behavioral_grade,
        b_list_status=profile.b_list_status,
        restructure_count=profile.restructure_count,
        active_contract_count=profile.active_contract_count,
    )


@router.get(
    "/{cust_id}/contracts",
    response_model=List[CustomerContractItem],
    summary="Daftar ringan kontrak milik 1 customer",
    description="Dipakai expandable contract list di Customer Detail (TASK-C). ORDER BY "
    "dpd_current DESC. List kosong VALID kalau customer ada tapi belum punya kontrak — 404 "
    "hanya kalau cust_id sama sekali tidak ada di customer_master.",
    responses={404: {"description": "cust_id tidak ditemukan di customer_master"}},
)
def list_customer_contracts(cust_id: str, service: CustomerService = Depends(get_customer_service)):
    contracts = service.list_contracts_for_customer(cust_id)
    if contracts is None:
        raise HTTPException(status_code=404, detail=f"Customer {cust_id} tidak ditemukan")

    return [
        CustomerContractItem(
            contract_no=c.contract_no,
            product_type=c.product_type,
            dpd_current=c.dpd_current,
            outstanding=format_rupiah(c.outstanding),
            risk_segment=c.risk_segment,
        )
        for c in contracts
    ]
