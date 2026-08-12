-- Audit query panas (post-presentation-review-tasks.md TASK-P2).
-- Jalankan pada rung yang cukup besar untuk mewakili (mis. 50-100 rb
-- customer via faker/bulk_clone.py) — di dataset kecil planner sering pilih
-- seq scan karena memang lebih murah untuk beberapa ribu baris, itu bukan
-- sinyal yang berguna untuk prioritas TASK-P5.
--
-- Pemakaian:
--   psql -h localhost -U postgres -d collect_ai -f perf/explain_queries.sql
--     > perf/results/explain_<tanggal>.txt

-- ── 1. Customer list — _CUSTOMER_LIST_BASE_CTE (customer_repository.py) ────
-- Filter "all" tanpa search, page 1 — jalur yang paling sering dipanggil
-- (halaman Customer List default).
EXPLAIN (ANALYZE, BUFFERS)
WITH primary_contract AS (
    SELECT DISTINCT ON (cs.cust_id)
        cs.cust_id,
        cs.dpd_current
    FROM contract_snapshot cs
    WHERE COALESCE(cs.closed_via_restructure, FALSE) = FALSE
    ORDER BY cs.cust_id, (COALESCE(cs.prnc_ots, 0) + COALESCE(cs.intr_ots, 0)) DESC
),
latest_score AS (
    SELECT DISTINCT ON (contract_no) contract_no, risk_segment
    FROM ai_intelligence_output
    ORDER BY contract_no, scoring_date DESC
),
contract_priority AS (
    SELECT
        cs.cust_id,
        CASE
            WHEN cs.dpd_current > 90 THEN 'Critical'
            WHEN cs.dpd_current BETWEEN 31 AND 90 THEN 'High'
            ELSE 'Medium'
        END AS priority_label
    FROM contract_snapshot cs
    LEFT JOIN latest_score ls ON ls.contract_no = cs.contract_no
    WHERE COALESCE(cs.closed_via_restructure, FALSE) = FALSE
),
customer_priority AS (
    SELECT cust_id, MAX(
        CASE priority_label WHEN 'Critical' THEN 3 WHEN 'High' THEN 2 ELSE 1 END
    ) AS priority_rank
    FROM contract_priority
    GROUP BY cust_id
),
base AS (
    SELECT
        cm.cust_id AS cust_id,
        COALESCE(cm.cust_name, cm.cust_id) AS name,
        COALESCE(cbs.active_contract_count, 0) AS active_contract_count,
        COALESCE(cbs.behavioral_grade, 'D') AS behavioral_grade,
        COALESCE(cbs.b_list_status, 'N') AS b_list_status,
        COALESCE(pc.dpd_current, 0) AS dpd_current,
        CASE COALESCE(cpr.priority_rank, 1)
            WHEN 3 THEN 'Critical'
            WHEN 2 THEN 'High'
            ELSE 'Medium'
        END AS priority
    FROM customer_master cm
    LEFT JOIN customer_behavioral_standing cbs ON cbs.cust_id = cm.cust_id
    LEFT JOIN primary_contract pc ON pc.cust_id = cm.cust_id
    LEFT JOIN customer_priority cpr ON cpr.cust_id = cm.cust_id
)
SELECT * FROM base WHERE TRUE ORDER BY cust_id LIMIT 20 OFFSET 0;

-- ── 2. Contract list — _CONTRACT_LIST_BASE_CTE (contract_repository.py) ───
EXPLAIN (ANALYZE, BUFFERS)
WITH latest_score AS (
    SELECT DISTINCT ON (contract_no) contract_no, risk_segment
    FROM ai_intelligence_output
    ORDER BY contract_no, scoring_date DESC
),
latest_ptp AS (
    SELECT DISTINCT ON (contract_no) contract_no, ptp_status
    FROM lkp_interaction
    ORDER BY contract_no, action_date DESC
),
base AS (
    SELECT
        cs.contract_no AS contract_no,
        cs.cust_id AS cust_id,
        COALESCE(cm.cust_name, cs.cust_id) AS cust_name,
        cs.product_type AS product_type,
        COALESCE(cs.dpd_current, 0) AS dpd_current,
        (COALESCE(cs.prnc_ots, 0) + COALESCE(cs.intr_ots, 0)) AS outstanding,
        ls.risk_segment AS risk_segment,
        cs.ambc AS ambc,
        lp.ptp_status AS ptp_status
    FROM contract_snapshot cs
    LEFT JOIN customer_master cm ON cm.cust_id = cs.cust_id
    LEFT JOIN latest_score ls ON ls.contract_no = cs.contract_no
    LEFT JOIN latest_ptp lp ON lp.contract_no = cs.contract_no
)
SELECT * FROM base WHERE TRUE ORDER BY contract_no LIMIT 20 OFFSET 0;

-- ── 3. Customer profile — LATERAL join get_customer_profile
--      (customer_repository.py, fix outstanding-aggregation TASK sebelumnya) ─
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    cm.cust_id, cm.cust_name, cbs.b_list_status, cbs.restructure_count,
    cbs.active_contract_count, cbs.behavioral_grade,
    ots.total_ots,
    ai.risk_segment, ai.recovery_score, ai.self_cure_probability,
    ai.roll_forward_risk, ai.ptp_success_probability, ai.nba_recommendation
FROM customer_master cm
LEFT JOIN customer_behavioral_standing cbs ON cbs.cust_id = cm.cust_id
LEFT JOIN LATERAL (
    SELECT COALESCE(SUM(COALESCE(prnc_ots, 0) + COALESCE(intr_ots, 0)), 0) AS total_ots
    FROM contract_snapshot
    WHERE cust_id = cm.cust_id AND COALESCE(closed_via_restructure, FALSE) = FALSE
) ots ON TRUE
LEFT JOIN LATERAL (
    SELECT contract_no
    FROM contract_snapshot
    WHERE cust_id = cm.cust_id AND COALESCE(closed_via_restructure, FALSE) = FALSE
    ORDER BY (COALESCE(prnc_ots, 0) + COALESCE(intr_ots, 0)) DESC
    LIMIT 1
) pc ON TRUE
LEFT JOIN LATERAL (
    SELECT risk_segment, recovery_score, self_cure_probability,
           roll_forward_risk, ptp_success_probability, nba_recommendation
    FROM ai_intelligence_output
    WHERE contract_no = pc.contract_no
    ORDER BY scoring_date DESC
    LIMIT 1
) ai ON TRUE
WHERE cm.cust_id = (SELECT cust_id FROM customer_master LIMIT 1);

-- ── 4. Dashboard summary — DPD bucket cross-tab (dashboard_repository.py) ──
-- latest_ptp: DISTINCT ON (contract_no) ... ORDER BY action_date DESC pada
-- SELURUH lkp_interaction — tabel terbesar (30.7 baris/customer), tanpa
-- index (contract_no, action_date) ini scan+sort seluruh tabel tiap panggilan
-- dashboard, salah satu kandidat index TASK-P5.
EXPLAIN (ANALYZE, BUFFERS)
WITH latest_ptp AS (
    SELECT DISTINCT ON (contract_no) contract_no, ptp_status
    FROM lkp_interaction ORDER BY contract_no, action_date DESC
),
bucketed AS (
    SELECT
        CASE
            WHEN cs.dpd_current BETWEEN 1 AND 30 THEN 'C0'
            WHEN cs.dpd_current BETWEEN 31 AND 60 THEN 'C1'
            WHEN cs.dpd_current BETWEEN 61 AND 90 THEN 'C2'
            WHEN cs.dpd_current > 90 THEN 'C3+'
        END AS bucket,
        lp.ptp_status
    FROM contract_snapshot cs
    LEFT JOIN latest_ptp lp ON lp.contract_no = cs.contract_no
)
SELECT bucket, count(*) FROM bucketed WHERE bucket IS NOT NULL GROUP BY bucket;

-- ── 5. Audit: index yang TIDAK PERNAH dipakai ──────────────────────────────
-- idx_scan=0 pada tabel besar = kandidat dihapus (index menambah beban
-- write + disk, dinding kedua di Area 1 — lihat TASK-P5 poin 3).
SELECT schemaname, relname AS table_name, indexrelname AS index_name, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY relname;

-- ── 6. Audit: seq scan pada tabel besar ────────────────────────────────────
-- seq_scan tinggi + relasi besar (lkp_interaction/payment_history) = kandidat
-- index baru (TASK-P5 poin 3: payment_history(contract_no),
-- lkp_interaction(contract_no, action_date)).
SELECT relname AS table_name, seq_scan, seq_tup_read, idx_scan,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_stat_user_tables
ORDER BY seq_scan DESC
LIMIT 15;
