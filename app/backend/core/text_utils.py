"""Util teks murni Python (tanpa FastAPI/DB) — dipakai lebih dari 1 tempat
(auth.py utk UserOut.initials, customers.py utk CustomerProfileSchema.initials
di TASK-C), jadi diekstrak ke sini daripada diduplikasi."""


def compute_initials(name: str, max_letters: int = 2) -> str:
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][:max_letters].upper()
    return "".join(p[0].upper() for p in parts[:max_letters])
