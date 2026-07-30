"""Util format tampilan murni Python (tanpa FastAPI/DB) — dipakai bersama
oleh beberapa service (customer, contract) supaya format Rupiah selalu
konsisten di semua endpoint baru (TASK-C/D)."""


def format_rupiah(amount: float) -> str:
    """"Rp N" gaya Indonesia (titik sebagai pemisah ribuan, tanpa desimal).
    Belum ada kolom currency lain di skema saat ini jadi tidak perlu parameter
    mata uang — kalau nanti perlu, tambahkan di sini, bukan di caller."""
    return f"Rp {amount:,.0f}".replace(",", ".")
