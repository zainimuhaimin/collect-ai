# AI Intelligence (Governance) API — Phase 1: Bobot CBS

## Overview

**Important naming note:** despite the name, this module is **not** the scoring pipeline in `app/machine-learning` (that's a nightly batch job with no HTTP surface). This module is the **governance/config screen** collectors' managers use to tune `customer_behavioral_standing`'s weighting constants, plus view model health and an audit log of changes.

**Scope for this phase (per `frontend-layout-upgrade-tasks.md` TASK-F):** Phase 1 is **Bobot CBS only** — the 4 real weighting constants that drive `behavioral_grade`. Two sections that existed in an earlier revision of this page were **removed from scope**, not just hidden:
- **Risk & Sub-model Thresholds** (`SCORE_THRESHOLD_WONT_PAY`/`CANNOT_PAY`/`SELF_CURE`, etc.) — dropped because changing these instantly reclassifies the entire portfolio's `risk_segment` (used across Dashboard/Customer/Contract), which is a much bigger blast radius than one customer's `behavioral_grade`, and there's no RBAC yet to gate who can touch it.
- **Local LLM System Prompt / Prompting Rules editor** — belongs to a separate, not-yet-approved task (`ai-reasoning-api-upgrade-tasks.md`).
- **Restructuring Policy governance** — planned as Phase 2 of this same module, not built yet.

**Backend status:** no backing table exists yet for Bobot CBS governance itself — per the design doc, `model_governance_config` (Postgres) should be built **alongside** this phase (not mocked first, then migrated later). `settings.py`'s `WEIGHT_PAYMENT_RATE`/`WEIGHT_PTP_RELIABILITY`/`WEIGHT_INTERACTION`/`WEIGHT_DELAY_SCORE` become the seed/default values only. Model health additionally needs `model_monitoring_log` (already exists) and `ai_reasoning_output` (new, tracked in `ai-reasoning-api-upgrade-tasks.md`).

**Consumed by:** `src/pages/AiIntelligencePage.tsx` (reads), `src/hooks/useWeightingParameters.ts` (wraps the query + the save mutation together)

**Frontend files:**
- Schema: `src/domains/ai-intelligence/aiIntelligence.schema.ts`
- API calls: `src/domains/ai-intelligence/aiIntelligence.api.ts`
- Hooks: `src/domains/ai-intelligence/useModelConfigQuery.ts`, `src/domains/ai-intelligence/useModelOperationalLogQuery.ts`, `src/domains/ai-intelligence/useSaveWeightingParametersMutation.ts`
- Mock: `src/mocks/fixtures/aiIntelligence.fixtures.ts`, `src/mocks/handlers/aiIntelligence.handlers.ts`

---

## `GET /ai-intelligence/model-config`

Returns everything on the page except the audit log: model name, the 4 CBS weighting sliders, and model health.

**Auth required:** Yes.

**Success response — `200`**

```json
{
  "modelInfo": {
    "name": "CBS-v1.0",
    "weightingSumLabel": "Sum of weights: 100%"
  },
  "weightingParameters": [
    { "label": "Payment Rate", "weight": 30, "description": "Seberapa besar pengaruh rajin bayar tepat waktu terhadap grade perilaku." },
    { "label": "PTP Reliability", "weight": 25, "description": "Seberapa besar pengaruh konsistensi menepati janji bayar." },
    { "label": "Interaction", "weight": 20, "description": "Seberapa besar pengaruh responsivitas saat dihubungi." },
    { "label": "Delay Score", "weight": 25, "description": "Seberapa besar pengaruh tren keterlambatan pembayaran." }
  ],
  "modelHealth": {
    "scoringModel": { "status": "Optimized", "accuracyLabel": "88% Prediction Accuracy across 12.4k cases.", "progress": 88 },
    "aiReasoning": { "available": false, "note": "Belum tersedia — menunggu ai_reasoning_output." }
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `modelInfo.name` | string | Shown as a badge in the page header. |
| `modelInfo.weightingSumLabel` | string | Currently unused display-wise (the frontend computes and shows its own live sum as sliders move) — safe to keep static, or drop from the response. |
| `weightingParameters` | array, **exactly 4 items** | `{ label: string, weight: number, description: string }`. `label` is the stable identifier used when saving edits (see `PUT` below) — map them to `settings.py`'s constants as: `"Payment Rate"` → `WEIGHT_PAYMENT_RATE`, `"PTP Reliability"` → `WEIGHT_PTP_RELIABILITY`, `"Interaction"` → `WEIGHT_INTERACTION`, `"Delay Score"` → `WEIGHT_DELAY_SCORE`. `weight` is 0-100 (i.e. already ×100 vs. the 0.30/0.25/0.20/0.25 decimal constants) and the 4 must sum to 100. Order = display order. |
| `modelHealth.scoringModel` | object | Health of the scoring pipeline from `model_monitoring_log` (AUC/drift-derived `status`, an `accuracyLabel` sentence, and a 0-100 `progress`). Same shape as the old flat `modelHealth` this replaces. |
| `modelHealth.aiReasoning` | object | `{ available: boolean, note: string }`. No backing table yet (`ai_reasoning_output`, tracked separately) — send `available: false` with an explanatory `note`; the frontend renders a muted "not available" state rather than a fake progress bar. Once `ai_reasoning_output` exists, flip `available: true` and extend this shape (status ratio OK/FALLBACK/FAILED) — that's a schema change to coordinate with the frontend at that time. |

**Removed from this response** (previously present, now gone — not optional/nullable, just absent): `riskThresholds` (`criticalLevel`/`escalationTrigger`/`note`) and `systemPrompt` (`version`/`content`/`affectedChannelsNote`). Do not send these fields; the frontend's Zod schema no longer declares them and extra fields are otherwise harmless, but there's no UI left to render them either way.

---

## `GET /ai-intelligence/operational-log`

Audit log of changes to this model's configuration. **Unchanged in shape** from the previous revision — just make sure log entries reference the new CBS actions (see example below) instead of the old generic "Risk Weight"/"System Prompt" ones.

**Auth required:** Yes.

**Success response — `200`**

```json
[
  { "timestamp": "2026-07-24 14:22:10", "action": "Payment Rate Weight Adjustment", "user": "admin_irwan", "status": "Success" },
  { "timestamp": "2026-07-22 09:12:00", "action": "Model Retraining Start", "user": "data_sci_team", "status": "In Progress" }
]
```

| Field | Type | Notes |
|---|---|---|
| `timestamp` | string | Pre-formatted, not parsed by the frontend. |
| `action` | string | e.g. `"Payment Rate Weight Adjustment"`, `"Delay Score Weight Adjustment"`, `"Model Retraining Start"`. |
| `user` | string | Username or system identifier that made the change. |
| `status` | `"Success" \| "In Progress" \| "Failed"` | Exact string values matter (title case, space in `"In Progress"`). |

---

## `PUT /ai-intelligence/weighting-parameters`

Saves an edited set of the 4 CBS weighting sliders to `model_governance_config` (audit-logged as part of the same write, per the design doc — not a follow-up).

**Auth required:** Yes.

**Request body** — the full array of 4 weighting parameters, same shape as `GET`'s `weightingParameters`:

```json
[
  { "label": "Payment Rate", "weight": 35, "description": "Seberapa besar pengaruh rajin bayar tepat waktu terhadap grade perilaku." },
  { "label": "PTP Reliability", "weight": 25, "description": "Seberapa besar pengaruh konsistensi menepati janji bayar." },
  { "label": "Interaction", "weight": 15, "description": "Seberapa besar pengaruh responsivitas saat dihubungi." },
  { "label": "Delay Score", "weight": 25, "description": "Seberapa besar pengaruh tren keterlambatan pembayaran." }
]
```

**Important:** the frontend sends the *entire array* on every save, and does **not** guarantee the 4 `weight` values sum to 100 before sending — validate/enforce that server-side (reject with a clear error if not, per the design doc's explicit call-out that this table doubles as a governance guardrail).

**Success response — `200`** — the saved array, echoed back.

**What the frontend does after a successful save**: invalidates `GET /ai-intelligence/model-config` and `GET /ai-intelligence/operational-log`, triggering a refetch of both — so a successful `PUT` should result in the next operational-log fetch including a new entry (e.g. `action: "Payment Rate Weight Adjustment"`).

**Error responses**

| Status | When | Frontend behavior |
|---|---|---|
| any non-2xx | Save failed | The Save button resets, the local edit draft is **not** cleared (user can retry). No visible error toast yet — a good follow-up. |

**Notes**
- "Reset to Default" is purely client-side (discards the local draft, falls back to the last `GET` response) — no endpoint call.
- "Deploy to Production" and the Risk Thresholds / System Prompt editors from the previous revision are **gone** from this page for this phase — see Overview above.
