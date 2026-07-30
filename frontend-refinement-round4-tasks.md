# Frontend Refinement — Round 4 Tasks

Status: **IMPLEMENTED — verified 2026-07-29.**

This covers 6 items from the user's latest review pass. Each section states the root cause found during investigation, the decision made (where the user was asked), and the exact implementation plan.

---

## 0. Self-cure vs Can Pay (explanation only, no code change)

Not opposites — 2 of 4 buckets in one classification (`ai_intelligence_output.risk_segment`, computed in `app/machine-learning/src/business_rules.py:30-66`):

- **Won't Pay**: `recovery_score < 0.30` AND (high rejection count OR bad last contact result)
- **Cannot Pay**: `0.30 ≤ score < 0.50` AND (broken PTP OR bad income/debt ratio)
- **Self-cure**: `score ≥ 0.70` AND `dpd_current ≤ 7` AND `payment_rate ≥ 0.80` AND `self_cure_probability ≥ 0.70`
- **Can Pay**: residual/default bucket — everything else

Separately, the dashboard's **"Self-Cure Rate" KPI is an unrelated metric** — it's `payment_history.self_cure_flag` ratio over the trailing 30 days, not derived from this classification at all (already flagged in `riskSegment.ts:6-9`).

No action needed — decided we're replacing this KPI anyway (see #1).

---

## 1. Dashboard KPI: replace Self-Cure Rate with PTP Keep Rate

**Decision:** keep Total Outstanding, Active Delinquent Accounts, Manual Review Pending. Replace **Self-Cure Rate** with **PTP Keep Rate**.

PTP Keep Rate = `KEPT / (KEPT + BROKEN)` from `lkp_interaction.ptp_status`.

**Backend:**
- `app/backend/repositories/dashboard_repository.py` — replace the `self_cure_rate` query (lines ~55-66) with a `ptp_keep_rate` query: `count(*) FILTER (WHERE ptp_status = 'KEPT') / count(*) FILTER (WHERE ptp_status IN ('KEPT','BROKEN'))` from `lkp_interaction`. Decide on a time window consistent with the other KPIs (trailing 30 days by `contact_date`/equivalent — need to confirm the exact date column in `lkp_interaction` during implementation).
- `app/backend/schemas/dashboard.py` — rename `self_cure_rate` field to `ptp_keep_rate` in the KPI schema (breaking rename, no back-compat shim needed per project convention).

**Frontend:**
- `app/frontend/src/domains/dashboard/dashboard.schema.ts` — rename field to match.
- `app/frontend/src/pages/DashboardPage.tsx` — update `kpiCards` array: label "PTP Keep Rate", icon (e.g. `verified`), same `formatPercentFromDecimal` formatting.

---

## 2. Hover tooltips with exact values

No open decisions — straightforward additions using data already in scope:

- `app/frontend/src/components/DpdBucketChart.tsx` — add `title` per stacked-bar segment showing exact `settled`/`activePtp`/`broken` counts.
- `app/frontend/src/components/ChannelEfficiencyChart.tsx` — add `title` showing the unrounded `contactSuccessRate`.
- `app/frontend/src/components/ProgressBar.tsx` — add an optional `title` prop; wire it through from every caller (`CustomerSummaryCards.tsx`, `AiBehavioralInsights.tsx`, `ContractDetailPage.tsx`, `AiIntelligencePage.tsx`) passing the exact underlying value.
- AI Intelligence "Progres Sync" step rows (`AiIntelligencePage.tsx` `StepRow`) — **out of scope for now**: there's no timestamp on `SyncStep` today (`aiIntelligence.schema.ts:75-79` only has `modelType`/`action`/`status`), so an exact-value tooltip here would need a backend schema addition (start/end time per step). Deferred unless requested.
- Risk Segment Distribution pills already have this — no change needed.

---

## 3. AI Behavioral Insights — fix scale/rounding mismatch

**Decision:** this is a formatting bug, not a missing-milestone problem — the "tolak ukur tidak sesuai dengan angkanya" complaint is the progress bars/percentages not matching their true values, not a request for a new milestone section. No new UI section will be added.

**Root cause** (`app/frontend/src/components/AiBehavioralInsights.tsx`): backend sends fractions 0–1 (`selfCureProbability`, `rollForwardRisk`, `ptpSuccessProbability`), but the component renders them raw with zero formatting — e.g. `{customer.selfCureProbability}%` prints `"0.2345678%"` instead of `"23.46%"`, and feeds the raw 0–1 value straight into `ProgressBar` so the bar barely fills relative to what the number implies.

**Fix:** apply the same pattern already used correctly in `ContractDetailPage.tsx` (`value * 100`, rounded to **2 decimal places** per this round's instruction) to every percentage-based tile: `recoveryScore`, `selfCureProbability`, `rollForwardRisk`, `ptpSuccessProbability`. Pass the scaled 0–100 value to `ProgressBar` as well so the bar width matches the displayed number.

---

## 4. Payment history order — no change

**Decision:** keep current behavior (`ORDER BY due_date DESC`, newest at top). No code change for this item.

---

## 5. Collection Activity Timeline / per-contract activity log not showing

**Root cause (same bug, two symptoms):** `activityLogEntrySchema` (`app/frontend/src/domains/contract/contract.schema.ts:107-121`) requires a `description: z.string()` field. The backend (`ActivityLogEntrySchema` in `app/backend/schemas/contract.py:219-236`, built in `ContractService.get_activity_log`, `services/contract_service.py:54-65`) never sends `description` at all. Every response fails Zod validation → `ApiError` → the query goes into `isError`. This shows as:
- "Gagal memuat log aktivitas kontrak ini." in the per-contract log on Customer Detail (`CustomerContractsList.tsx`'s `ContractActivityLog`)
- The entire Contract Detail page blanking, because `ContractDetailPage.tsx`'s top-level `isError` check currently gates the **whole page** render, not just the timeline section.

**Fix:**
- `contract.schema.ts` — make `description` optional (`z.string().optional()`) to match what the backend actually sends. Also make `timestamp` nullable — backend emits `null` when `action_date` is null (`contract_service.py:61`), same failure mode.
- `ContractDetailPage.tsx` — isolate the activity-log/timeline section's error state so a failure there shows an inline `ErrorState` for just that card, not the entire page (mirror the pattern already used for the top-level `configQuery`/`operationalLogQuery` split in `AiIntelligencePage.tsx`).

**Additional finding — this is also why Contract Detail "works for some contract_no, not others":** the backend's own Pydantic model `ActivityLogEntrySchema` (`app/backend/schemas/contract.py:219-236`) declares `timestamp: str` (non-optional), but `contract_service.py:61` passes `None` whenever `lkp_interaction.action_date` is null. That's a **server-side 500**, not just a frontend parse failure — it only happens for contracts that have at least one activity/interaction row with a null date, which is exactly the "some contract_no work, some don't" symptom (contracts with zero interaction rows get `[]` and never hit this code path at all). Backend fix required in addition to the frontend one above:
- `app/backend/schemas/contract.py` — change `ActivityLogEntrySchema.timestamp` to `Optional[str]`, and add `description: Optional[str]` (currently missing entirely — see above).
- `app/backend/services/contract_service.py` — populate `description` (derive from the existing title/action data, e.g. the `_activity_title`-style logic) so the field is meaningful rather than always null.

---

## 6. Restructuring NPV display — show both NPV (risk-adjusted) and raw totals

**Decision (after discussion):** show **both** numbers side by side:
1. **NPV comparison, fixed** — apply `recovery_score` to both baseline and restructured for *display purposes only* (backend's internal ranking/guardrail logic in `restructuring_offer_calculator.py` is untouched — recovery_score is the same positive scalar for a given customer, so multiplying both sides doesn't change their ordering). This makes the NPV delta an honest "same risk assumption on both sides" comparison instead of the current inconsistency (baseline discounted, restructured not).
2. **Raw undiscounted totals** — total remaining amount owed under the current schedule (`current_installment × remaining_tenor`) vs. total amount owed under the new schedule (`new_installment × new_tenor`), no discounting at all. Simpler, but doesn't account for the fact that installments spread over more months are worth less in today's terms.

**Backend (`app/shared/restructuring_offer_calculator.py`):**
- Add `npv_restructured_risk_adjusted = npv_restructured * contract.recovery_score` as a new computed field (alongside existing `npv_baseline`, which is already risk-adjusted, and the existing raw `npv_restructured` which stays as-is for backend ranking).
- Add `total_remaining_current` and `total_new_schedule` raw sums.
- `app/backend/schemas/restructuring.py` — add these 3 new fields to the offer/group response schema.
- Propagate through `restructuring_offer_repository.py` and the relevant routers (`restructuring.py`, `restructuring_groups.py`) same as existing NPV fields.

**Frontend:**
- `app/frontend/src/domains/restructuring/restructuring.schema.ts` — add the 3 new fields.
- `RestructuringOptionsCard.tsx` and `RestructuringGroupDetailPage.tsx` — below/alongside the existing "Estimasi Hasil" NPV block, add a second compact row showing the raw total comparison, clearly labeled (e.g. "Total Tagihan (Tanpa Diskon)": current vs new), and update the NPV block's numbers to use `npvBaseline` vs `npvRestructuredRiskAdjusted` instead of raw `npvRestructured`.

**Post-implementation fix:** the batch-sourced restructuring groups (`restructuring_recommendation_output`, used by the actual Restructuring Approval list/detail pages — the pages this section was originally about) never stored `recovery_score` or a per-contract schedule, only the aggregate `npv_baseline`/`npv_restructured`. Left as originally scoped, this would have made the 3 new fields `null` for every batch group and non-null only for the on-demand assessment path (Customer Detail's restructuring card) — missing the actual page the user complained about. Fixed in `restructuring_offer_repository.py` by adding a `_GROUP_CONTRACT_STATS_CTE` subquery joining `restructuring_group_map` → `contract_snapshot` (installment/maturity-date, for `total_remaining_current`, using the same remaining-tenor math as `contract_repository._remaining_tenor_months`) and → `ai_intelligence_output` (avg `recovery_score` across the group's contracts, for `npv_restructured_risk_adjusted`); `total_new_schedule` is computed directly from the already-stored `recommended_new_installment × recommended_new_tenor`. Verified live: `GET /restructuring-groups` and `GET /restructuring-groups/{id}` both return real (non-null) values for all 3 fields.

---

## 7. Graceful degradation — fresh-demo state (only `customer_master`, `payment_history`, `lkp_interaction`, `contract_snapshot` populated)

**Goal:** every page should open and show real data from the 4 source tables even before the user has ever pressed Sync — with ML-derived sections (risk segment, AI scoring, restructuring) showing a "belum discoring" / placeholder state instead of crashing.

**Audited every page.** Most already degrade correctly (Dashboard, Customer List, Contract Detail, Restructuring Approval list/detail, AI Intelligence page all use `LEFT JOIN`/`COALESCE`/nullable schemas end-to-end already — confirmed clean, no action needed). Two real gaps found, both the same bug shape:

**7a. Customer Detail page — would fail entirely for every customer.**
- Backend correctly models `risk_segment`/`nba_recommendation` as `Optional[str]` (`app/backend/schemas/customer.py:105,111`) and passes `None` through untouched when no `ai_intelligence_output` row exists (`customer_repository.py:262-272`, `routers/customers.py:93,99`).
- Frontend schema does **not** match: `customerDetailSchema.riskSegment` uses the non-nullable `riskSegmentSchema` enum, and `nbaRecommendation: z.string()` is also non-nullable (`app/frontend/src/domains/customer/customer.schema.ts:16,22`). Every fresh-demo customer has no scoring row yet → Zod parse fails → `CustomerDetailPage.tsx` shows its `ErrorState` instead of the page.
- Same shape bug in the customer's own contract sub-list: `customerContractSummarySchema.riskSegment` (`customer.schema.ts:72`) is non-nullable while `CustomerContractItem.risk_segment` is `Optional[str]` backend-side (`schemas/customer.py:135`).
- **Fix:** make `riskSegment` `.nullable()` and `nbaRecommendation` `.nullable()` in both `customerDetailSchema` and `customerContractSummarySchema`; update `AiBehavioralInsights.tsx` and the contract sub-list row to render a "Belum discoring" placeholder chip when null (reusing the existing empty-state visual language already used elsewhere in the app, e.g. AI Intelligence page's "belum ada data monitoring" pattern).

**7b. Contract List page — would fail entirely.**
- `_row_to_contract_list_row` (`contract_repository.py:130-146`) sets `risk_segment=row.risk_segment` with no fallback, unlike its sibling `_row_to_contract` (line 73) which already does `row.risk_segment or "Can Pay"` for the detail path. Domain model and backend schema both correctly mark it `Optional[str]` (`domain/models.py:111`, `schemas/contract.py:30`), but `contractListItemSchema.riskSegment` in the frontend is the non-nullable enum (`contract.schema.ts:16`). With `ai_intelligence_output` empty, every row is `null` → the whole list page breaks.
- **Fix:** apply the same `row.risk_segment or "Can Pay"` default already used in `_row_to_contract`, inside `_row_to_contract_list_row` too, for consistency with the rest of the codebase's "unscored → conservative default" convention (simpler than making the frontend nullable here, since the list already has a working convention to reuse).

---

## 8. Sync button — run `weekly_mlops.py` after a from-scratch training run

**Correction:** the "weekly pipeline" script is `app/machine-learning/pipelines/weekly_mlops.py` (not `weekly_pipeline.py`) — confirmed as the sole writer of the drift/AUC monitoring data already referenced by `AiIntelligencePage.tsx`'s "belum ada data monitoring — pipelines/weekly_mlops.py belum pernah dijalankan" message.

**Current flow** (`app/backend/services/ai_intelligence_sync_service.py`): `start_sync()` (lines 130-150) precomputes, per model type in `MODEL_TYPES = ("recovery","self_cure","roll_forward","ptp_success")`, whether `_has_champion(model_type)` is true (→ `"score_only"`) or false (→ `"train_then_score"`), **before** any training starts. `_run_job()` (lines 154-181) then trains whichever model types need it, and finally runs `daily_scoring.py`.

**Change:** compute `did_train_from_scratch = not all(_has_champion(mt) for mt in MODEL_TYPES)` once at the very start of `start_sync()` (before training begins — reusing the exact same `_has_champion()` check already used per-model-type), store it on `_state`. After `daily_scoring.py` succeeds in `_run_job()`, if `did_train_from_scratch` is true, run `pipelines/weekly_mlops.py` as an additional step (same `_run_script()` helper, same subprocess pattern) before marking the job `"completed"`. Add a corresponding `SyncStep` (e.g. `modelType: "weekly_mlops"`, `action: "weekly_monitoring"`) so the frontend's existing step-list UI (`StepRow` in `AiIntelligencePage.tsx`) shows it without any new UI code — it already renders whatever steps the backend sends.

This directly fixes the "belum ada data monitoring" placeholder too — after a from-scratch Sync, the AI Intelligence page will show real AUC/drift data instead of the placeholder, since `weekly_mlops.py` is what populates that.

---

## Verification plan

- Backend: `pytest tests/ -q` full pass; add/update tests for the new `ptp_keep_rate` KPI query and the new NPV/raw-total fields in the restructuring calculator.
- Frontend: `npm run build` + `npm run lint` clean.
- Live smoke test via Vite dev proxy: Dashboard shows PTP Keep Rate with a plausible percentage; AI Behavioral Insights percentages/bars now match (e.g. 23.46% shows a ~23% filled bar); Contract Detail's activity timeline and Customer Detail's per-contract log both render entries instead of erroring; Restructuring Group Detail and the Customer Detail restructuring card show both the risk-adjusted NPV comparison and the raw total comparison with sensible numbers.
- Fresh-demo check: with `ai_intelligence_output`/`restructuring_recommendation_output`/etc. empty (only the 4 source tables populated), confirm Customer Detail, Customer's contract sub-list, and Contract List all open and render placeholders instead of erroring.
- Confirm `registry.json` still `{"model_types": {}}` before testing Sync, then press Sync once and verify: all 4 models train, `daily_scoring.py` runs, and — since this was a from-scratch run — `weekly_mlops.py` also runs afterward and the AI Intelligence page's monitoring section switches from the placeholder to real AUC/drift data.
