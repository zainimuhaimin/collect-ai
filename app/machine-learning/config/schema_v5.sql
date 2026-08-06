-- config/schema_v5.sql
-- Perbaikan temuan audit "AI Reasoning" (ai-reasoning-api-upgrade-tasks.md,
-- temuan #17) — jalankan SETELAH schema_v4.

-- ── CUSTOMER_BEHAVIORAL_STANDING: 2 kolom yang selama ini dibuang ───────
-- historical_default_count & income_debt_ratio SUDAH dihitung dengan benar
-- oleh compute_customer_features() (feature_engineering.py), tapi build_cbs()
-- membuang keduanya sebelum menulis ke tabel ini (cbs_builder.py out_cols).
-- Akibatnya daily_scoring.py memaksa 0.0 untuk keduanya di setiap scoring run
-- (fill_cols), dan cabang NBA "Pickup" di business_rules.py (butuh
-- historical_default_count >= 2) tidak pernah bisa terpicu meski ada kandidat
-- nyata. Kolom ini menyimpan nilai ASLI, bukan sekadar placeholder — begitu
-- CBS dibangun ulang (TRUNCATE + daily_scoring.py) dan 4 model dilatih ulang,
-- keduanya akan terisi nilai sesungguhnya.
ALTER TABLE customer_behavioral_standing
  ADD COLUMN IF NOT EXISTS historical_default_count INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS income_debt_ratio NUMERIC(10,4) DEFAULT 0;

-- ── AI_INTELLIGENCE_OUTPUT: jejak cabang NBA yang menang ────────────────
-- apply_nba() (business_rules.py) menimpa nba_recommendation lewat beberapa
-- assignment .loc berurutan (aturan dasar + 4 override) tanpa pernah mencatat
-- cabang mana yang menang (last-write-wins). Kolom ini menyimpan label singkat
-- cabang terakhir yang menulis nba_recommendation, supaya konsumen (termasuk
-- fitur AI Reasoning) tahu ALASAN rekomendasi tanpa merekonstruksi ulang
-- logika 8+ assignment berurutan itu dari luar.
ALTER TABLE ai_intelligence_output
  ADD COLUMN IF NOT EXISTS nba_trigger VARCHAR(60);
