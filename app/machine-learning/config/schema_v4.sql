-- config/schema_v4.sql
-- Round-4 faker leakage/realism rewrite (frontend-refinement-round4-tasks.md
-- is unrelated; this is the "cek generate-faker-realistic.py" follow-up) —
-- jalankan SETELAH schema_v3.

-- ── CONTRACT_SNAPSHOT: status kontrak ───────────────────────────────
-- feature_engineering.py:404 selama ini SELALU default ke 'aktif' karena
-- kolom ini tidak pernah ada. generate-faker-realistic.py sekarang men-
-- simulasikan status kontrak sungguhan ('aktif'/'lunas'/'write-off') dari
-- path pembayaran, jadi kolomnya perlu benar-benar ada.
ALTER TABLE contract_snapshot
  ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'aktif';
