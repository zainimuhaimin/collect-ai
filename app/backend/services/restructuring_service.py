import os
import sys
from dataclasses import dataclass
from datetime import date
from typing import Optional

from domain.models import Contract, Customer
from repositories.interfaces import (
    IContractRepository,
    ICustomerRepository,
    IRestructuringOfferRepository,
)

# app/ (parent of backend/ dan machine-learning/) perlu ada di sys.path supaya
# `shared` bisa diimport dari sini — shared/restructuring_offer_calculator.py
# adalah SATU-SATUNYA salinan modul ini, dipakai bersama oleh backend dan ML.
_APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from shared.restructuring_offer_calculator import (  # noqa: E402
    ContractInput,
    CustomerContext,
    RestructurePolicy,
    RestructuringAssessment,
    assess_restructuring_options,
)


@dataclass
class CustomerResponseResult:
    """Hasil submit_customer_response() — dipakai router untuk menentukan
    status code HTTP yang tepat, TANPA service perlu tahu soal HTTPException
    (itu urusan router, lihat Catatan #1 backend-architecture-tasks.md)."""
    ok: bool
    error: Optional[str] = None
    error_code: Optional[str] = None  # 'NOT_FOUND' | 'FORBIDDEN' | 'INVALID_STATE' | 'EXPIRED'


VALID_RESPONSES = ("ACCEPTED", "REJECTED")


class RestructuringService:
    """Menjembatani domain model backend dengan modul ml/ —
    ml/restructuring_offer_calculator.py TIDAK PERNAH tahu soal FastAPI,
    repository, atau database sama sekali (SRP). Modul itu murni fungsi
    dan bisa dites/dipakai berdiri sendiri di luar backend ini juga."""

    def __init__(
        self,
        customer_repository: ICustomerRepository,
        contract_repository: IContractRepository,
        restructuring_offer_repository: Optional[IRestructuringOfferRepository] = None,
    ):
        self._customers = customer_repository
        self._contracts = contract_repository
        self._offers = restructuring_offer_repository
        self._policy = RestructurePolicy()

    @staticmethod
    def _to_contract_input(contract: Contract) -> ContractInput:
        return ContractInput(
            contract_no=contract.contract_no,
            cust_id=contract.cust_id,
            product_type=contract.product_type,
            total_ots=contract.total_ots,
            principal_ots=contract.principal_ots,
            interest_rate=contract.interest_rate,
            remaining_tenor_months=contract.remaining_tenor_months,
            installment_amount=contract.installment_amount,
            dpd_current=contract.dpd_current,
            risk_segment=contract.risk_segment,
            recovery_score=contract.recovery_score,
            self_cure_probability=contract.self_cure_probability,
            closed_via_restructure=contract.closed_via_restructure,
        )

    @staticmethod
    def _to_customer_context(customer: Customer) -> CustomerContext:
        return CustomerContext(
            cust_id=customer.cust_id,
            b_list_status=customer.b_list_status,
            restructure_count=customer.restructure_count,
            active_contract_count=customer.active_contract_count,
        )

    def get_options_for_customer(self, cust_id: str) -> Optional[RestructuringAssessment]:
        customer = self._customers.get_customer(cust_id)
        contract = self._contracts.get_primary_contract_for_customer(cust_id)
        if not customer or not contract:
            return None

        siblings = self._contracts.get_sibling_contracts(cust_id, contract.contract_no)
        sibling_inputs = [self._to_contract_input(c) for c in siblings]

        return assess_restructuring_options(
            contract=self._to_contract_input(contract),
            customer=self._to_customer_context(customer),
            policy=self._policy,
            sibling_contracts=sibling_inputs or None,
        )

    def get_active_offer_reference(self, cust_id: str):
        """Group restructuring_recommendation_output TERBARU untuk customer ini,
        kalau ada — dipakai router untuk melengkapi on-demand assessment di atas
        dengan restructure_group_id/offer_status supaya frontend tahu apakah ada
        tawaran yang benar-benar bisa direspons (bukan cuma preview angka)."""
        if self._offers is None:
            return None
        return self._offers.find_latest_for_customer(cust_id)

    def submit_customer_response(
        self, cust_id: str, restructure_group_id: str, response: str, today: Optional[date] = None
    ) -> CustomerResponseResult:
        """Catat keputusan CUSTOMER (accept/reject) atas satu tawaran yang
        sudah OFFERED. Ini BEDA dari approval supervisor (TASK-60, belum
        dibangun) yang mengurus transisi GENERATED->OFFERED untuk tier
        MANUAL_REVIEW — endpoint ini murni mencatat respons nasabah setelah
        offer sudah ada di depan mereka.

        Eksekusi kontrak baru (origination) BUKAN tanggung jawab endpoint
        ini — itu tugas sistem core banking terpisah (app/core-banking/)
        yang memantau offer_status='ACCEPTED' dan mencairkan kontrak baru
        secara independen (lihat app/core-banking/README atau originator.py).
        """
        today = today or date.today()
        response = response.upper()

        if response not in VALID_RESPONSES:
            return CustomerResponseResult(
                ok=False, error=f"response harus salah satu dari {VALID_RESPONSES}", error_code="INVALID_STATE"
            )

        if self._offers is None:
            return CustomerResponseResult(
                ok=False, error="Restructuring offer repository tidak terkonfigurasi", error_code="NOT_FOUND"
            )

        offer = self._offers.get_offer(restructure_group_id)
        if offer is None:
            return CustomerResponseResult(ok=False, error="Tawaran tidak ditemukan", error_code="NOT_FOUND")

        if offer.cust_id != cust_id:
            return CustomerResponseResult(
                ok=False, error="Tawaran ini bukan milik customer tersebut", error_code="FORBIDDEN"
            )

        if offer.offer_status == "GENERATED":
            return CustomerResponseResult(
                ok=False,
                error="Tawaran ini masih menunggu approval supervisor (tier MANUAL_REVIEW), belum bisa direspons customer",
                error_code="INVALID_STATE",
            )

        if offer.expiry_date and offer.expiry_date < today:
            return CustomerResponseResult(ok=False, error="Tawaran sudah kedaluwarsa", error_code="EXPIRED")

        if offer.offer_status != "OFFERED":
            return CustomerResponseResult(
                ok=False,
                error=f"Tawaran berstatus '{offer.offer_status}', sudah tidak bisa direspons ulang",
                error_code="INVALID_STATE",
            )

        updated = self._offers.record_customer_response(restructure_group_id, response, today)
        if not updated:
            return CustomerResponseResult(ok=False, error="Gagal menyimpan respons", error_code="NOT_FOUND")

        return CustomerResponseResult(ok=True)
