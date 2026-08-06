-- config/schema_v6.sql
-- Hapus channel SMS, lebur ke WA (ai-reasoning-api-upgrade-tasks.md,
-- keputusan #7 / prasyarat P0-1) — jalankan SETELAH schema_v5.
--
-- SMS hilang dari CHANNEL_RANK (business_rules.py) menyebabkan jangkar
-- collection_sensitivity mati untuk nasabah SMS-preferring (temuan #14),
-- sehingga hyper-personalization bocor tanpa suara untuk populasi itu.
--
-- Trade-off yang diterima: informasi channel SMS yang sebenarnya dipakai
-- hilang permanen sesudah migrasi ini — tidak akan bisa lagi mengevaluasi
-- performa SMS vs WA secara terpisah. Dipilih secara sadar demi kesederhanaan.
--
-- Urutan WAJIB: migrasi baris dulu, baru perketat CHECK constraint — kalau
-- dibalik, ALTER TABLE ADD CONSTRAINT akan gagal terhadap baris SMS yang
-- masih ada.

-- ── 1. Migrasi baris SMS -> WA ──────────────────────────────────────────
UPDATE payment_history SET recovery_source = 'WA' WHERE recovery_source = 'SMS';
UPDATE lkp_interaction SET treatment_type = 'WA' WHERE treatment_type = 'SMS';

-- ── 2. Perketat CHECK constraint payment_history.recovery_source ───────
ALTER TABLE payment_history DROP CONSTRAINT IF EXISTS chk_recovery_source;
ALTER TABLE payment_history
  ADD CONSTRAINT chk_recovery_source
  CHECK (recovery_source IS NULL OR
         recovery_source IN ('WA', 'Deskcoll', 'Visit', 'Somasi'));
