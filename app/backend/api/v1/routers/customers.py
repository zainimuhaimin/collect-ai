from typing import List

from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import get_customer_service
from schemas.customer import CustomerDetail, CustomerSummary
from services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get(
    "",
    response_model=List[CustomerSummary],
    summary="Daftar semua customer",
    description="Ambil seluruh customer dari `customer_master` (Postgres, sama dengan yang dipakai "
    "app/machine-learning/). Belum ada pagination — untuk dataset besar, batasi lewat query "
    "manual ke database kalau perlu.",
)
def get_all_customers(service: CustomerService = Depends(get_customer_service)):
    customers = service.list_customers()
    return [
        CustomerSummary(
            cust_id=c.cust_id,
            name=c.name,
            active_contract_count=c.active_contract_count,
        )
        for c in customers
    ]


@router.get(
    "/{cust_id}",
    response_model=CustomerDetail,
    summary="Detail satu customer",
    description="Termasuk `b_list_status` dan `behavioral_grade` dari customer_behavioral_standing (CBS) — "
    "hasil kalkulasi harian pipeline ML.",
    responses={404: {"description": "cust_id tidak ditemukan di customer_master"}},
)
def get_customer_detail(cust_id: str, service: CustomerService = Depends(get_customer_service)):
    customer = service.get_customer_detail(cust_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {cust_id} tidak ditemukan")

    return CustomerDetail(
        cust_id=customer.cust_id,
        name=customer.name,
        active_contract_count=customer.active_contract_count,
        b_list_status=customer.b_list_status,
        behavioral_grade=customer.behavioral_grade,
    )
