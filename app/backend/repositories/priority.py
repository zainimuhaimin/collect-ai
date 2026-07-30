"""Derivasi `priority` (Critical/High/Medium) — dipakai bersama oleh
CustomerRepository (agregat per primary contract) dan ContractRepository
(per-baris kontrak), jadi satu fungsi SQL saja supaya 2 tempat itu tidak
bisa diam-diam berbeda logika.

ASUMSI BISNIS (tidak dispesifikasi presisi di frontend-layout-upgrade-tasks.md,
lihat catatan TASK-C) — gampang diretune belakangan kalau product owner mau
angka lain:
    Critical: risk_segment == 'Cannot Pay' AND dpd_current >= 90
    High:     risk_segment == 'Cannot Pay' OR dpd_current >= 60
    Medium:   selain itu (default)
"""

# Fragmen SQL (bukan fungsi Python) supaya bisa dipakai langsung di WHERE/SELECT
# tanpa fetch-all-lalu-filter-di-Python (dataset bisa besar, filter di DB lebih murah).
PRIORITY_CASE_SQL = """
    CASE
        WHEN risk_segment = 'Cannot Pay' AND dpd_current >= 90 THEN 'Critical'
        WHEN risk_segment = 'Cannot Pay' OR dpd_current >= 60 THEN 'High'
        ELSE 'Medium'
    END
"""


def derive_priority(risk_segment, dpd_current: int) -> str:
    """Versi Python murni dari PRIORITY_CASE_SQL — dipakai saat baris sudah
    di tangan (mis. row-to-dataclass mapper), bukan di query builder."""
    dpd_current = dpd_current or 0
    if risk_segment == "Cannot Pay" and dpd_current >= 90:
        return "Critical"
    if risk_segment == "Cannot Pay" or dpd_current >= 60:
        return "High"
    return "Medium"
