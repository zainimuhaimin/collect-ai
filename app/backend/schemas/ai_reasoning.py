from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from services.ai_reasoning_prompt import NBA_ACTIONS


class _GeminiPerContractFocusSchema(BaseModel):
    # Gemini dipaksa JSON mode via responseSchema (ai_reasoning_prompt.py::build_response_schema)
    # yang mendeklarasikan properti dalam camelCase (contractNo, dst) — alias
    # WAJIB cocok persis, kalau tidak SETIAP output Gemini yang valid pun akan
    # gagal validasi di sini (bug nyata yang ditemukan saat uji end-to-end
    # dengan fake client sebelum ada key Gemini sungguhan). Class INTERNAL
    # (prefix _), TIDAK dipakai sebagai response_model — FastAPI default
    # `response_model_by_alias=True` akan membuat field ber-alias ini
    # terserialisasi sebagai camelCase, memecah konsistensi snake_case
    # seluruh API lain. PerContractFocusSchema di bawah (tanpa alias) yang
    # dipakai untuk response outward.
    model_config = ConfigDict(populate_by_name=True)

    contract_no: str = Field(alias="contractNo")
    urgency: str = Field(description="LOW | MEDIUM | HIGH | CRITICAL")
    note: str


class GeminiReasoningOutputSchema(BaseModel):
    """Validasi ULANG hasil parse JSON dari Gemini sebelum disimpan — meski
    sudah dipaksa lewat responseSchema (JSON mode), jangan percaya buta pada
    satu lapis saja. Pelanggaran (enum salah, field hilang) melempar
    ValidationError, yang ditangkap ai_reasoning_service.py sebagai FALLBACK,
    bukan disimpan mentah atau membuat endpoint 500.

    Alias camelCase WAJIB cocok dengan build_response_schema() di
    ai_reasoning_prompt.py — itu yang menentukan bentuk JSON yang Gemini
    benar-benar kembalikan. Class INTERNAL (dipakai ai_reasoning_service.py
    lewat model_dump() TANPA by_alias, yang mengembalikan nama field
    snake_case) — TIDAK pernah dipakai sebagai response_model FastAPI."""

    model_config = ConfigDict(populate_by_name=True)

    summary: str
    customer_treatment_strategy: str = Field(alias="customerTreatmentStrategy")
    key_factors: List[str] = Field(alias="keyFactors")
    primary_nba_action: str = Field(alias="primaryNbaAction", description=f"Harus salah satu dari: {NBA_ACTIONS}")
    primary_nba_rationale: str = Field(alias="primaryNbaRationale")
    nba_agreement: str = Field(alias="nbaAgreement", description="AGREE | DIFFER")
    per_contract_focus: List[_GeminiPerContractFocusSchema] = Field(alias="perContractFocus")
    consistency_note: str = Field(alias="consistencyNote")


class PerContractFocusSchema(BaseModel):
    """Bentuk outward (response_model) — snake_case polos, konsisten dengan
    seluruh API lain. TERPISAH dari _GeminiPerContractFocusSchema supaya
    alias Gemini tidak pernah bocor ke response GET/POST endpoint ini."""

    contract_no: str
    urgency: str = Field(description="LOW | MEDIUM | HIGH | CRITICAL")
    note: str


class AiReasoningResponseSchema(BaseModel):
    """Bentuk response GET/POST /customers/{cust_id}/ai-reasoning."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "OK",
                "insufficient_reason": None,
                "stale": False,
                "generated_at": "2026-08-05T10:00:00",
                "prompt_version": "v1",
                "model_used": "gemini-2.0-flash",
                "summary": "Debitur memiliki 3 kontrak aktif dengan total OTS Rp 45 juta...",
                "customer_treatment_strategy": "Tangani sebagai satu debitur dengan pendekatan kunjungan langsung...",
                "key_factors": ["82% dari total OTS sedang menunggak"],
                "primary_nba_action": "Visit",
                "primary_nba_rationale": "Kontrak terburuk sudah C3+...",
                "nba_agreement": "DIFFER",
                "per_contract_focus": [
                    {"contract_no": "CTR-00029-2", "urgency": "CRITICAL", "note": "Sudah C3+..."}
                ],
                "consistency_note": "Ketiga kontrak ditangani dengan satu kunjungan...",
                "analyzed_contract_nos": ["CTR-00029-1", "CTR-00029-2", "CTR-00029-3"],
            }
        }
    )

    status: str = Field(
        description="NONE (belum pernah digenerate) | DISABLED | RUNNING | "
        "OK | FALLBACK | FAILED | INSUFFICIENT_DATA"
    )
    insufficient_reason: Optional[str] = Field(
        default=None, description="NO_CBS | TOO_FEW_PAYMENTS | NO_SCORE | TOO_MANY_CONTRACTS"
    )
    stale: bool = Field(
        default=False,
        description="True kalau hasil ini dihitung dari signature kontrak yang sudah berubah "
        "(skor diperbarui/kontrak baru/kontrak ditutup sejak digenerate)",
    )
    generated_at: Optional[str] = None
    prompt_version: Optional[str] = None
    model_used: Optional[str] = None
    summary: Optional[str] = None
    customer_treatment_strategy: Optional[str] = None
    key_factors: List[str] = []
    primary_nba_action: Optional[str] = None
    primary_nba_rationale: Optional[str] = None
    nba_agreement: Optional[str] = None
    per_contract_focus: List[PerContractFocusSchema] = []
    consistency_note: Optional[str] = None
    analyzed_contract_nos: List[str] = []
