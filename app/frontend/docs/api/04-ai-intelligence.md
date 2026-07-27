# AI Intelligence (Governance) API

## Overview

**Important naming note:** despite the name, this module is **not** the scoring pipeline in `app/machine-learning` (that's a nightly batch job with no HTTP surface). This module is the **governance/config screen** collectors' managers use to tune the scoring model: adjust weighting sliders, set risk thresholds, edit the LLM system prompt, and view model health + an audit log of changes.

**Backend status:** no backing table exists for any of this today. This is a genuinely new contract — a small config/settings table (or a few) plus an audit log table need to be designed. Recommended sequencing: build this **after** Customer Detail and Dashboard, since it's this project's first endpoint that needs a write (`PUT`), and it's cleaner to validate the read-only query pattern on those two modules first.

**Consumed by:** `src/pages/AiIntelligencePage.tsx` (reads), `src/hooks/useWeightingParameters.ts` (wraps the query + the save mutation together)

**Frontend files:**
- Schema: `src/domains/ai-intelligence/aiIntelligence.schema.ts`
- API calls: `src/domains/ai-intelligence/aiIntelligence.api.ts`
- Hooks: `src/domains/ai-intelligence/useModelConfigQuery.ts`, `src/domains/ai-intelligence/useModelOperationalLogQuery.ts`, `src/domains/ai-intelligence/useSaveWeightingParametersMutation.ts`
- Mock: `src/mocks/fixtures/aiIntelligence.fixtures.ts`, `src/mocks/handlers/aiIntelligence.handlers.ts`

---

## `GET /ai-intelligence/model-config`

Returns everything on the page except the audit log: model name, weighting sliders, risk thresholds, model health, and the LLM system prompt.

**Auth required:** Yes.

**Success response — `200`**

```json
{
  "modelInfo": {
    "name": "Recovery-v4.2-Stable",
    "weightingSumLabel": "Sum of weights: 100%"
  },
  "weightingParameters": [
    { "label": "Risk Weight", "weight": 45, "description": "Impact of historical delinquency and credit bureau scores on prioritization." },
    { "label": "Propensity Weight", "weight": 30, "description": "Probability of payment based on recent engagement and communication responsiveness." },
    { "label": "Settlement Velocity", "weight": 25, "description": "Average time to resolution for similar portfolio segments." }
  ],
  "riskThresholds": {
    "criticalLevel": "15000000",
    "escalationTrigger": "5000000",
    "note": "Thresholds determine automatic task generation for human collectors."
  },
  "modelHealth": {
    "status": "Optimized",
    "accuracyLabel": "88% Prediction Accuracy across 12.4k cases.",
    "progress": 88
  },
  "systemPrompt": {
    "version": "Version: 02.11.A",
    "content": "# COLLECTAI SYSTEM PROMPT v4.2\n...",
    "affectedChannelsNote": "Changes to this prompt affect all automated WhatsApp and Email templates."
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `modelInfo.name` | string | Shown as a badge in the page header, e.g. `"Recovery-v4.2-Stable"`. |
| `modelInfo.weightingSumLabel` | string | Currently unused display-wise (the frontend computes and shows its own live sum as sliders move) — safe to keep static, or drop from the response if you'd rather the frontend own this copy entirely. |
| `weightingParameters` | array | Each item: `{ label: string, weight: number, description: string }`. `label` is used as the stable identifier when saving edits (see the `PUT` endpoint below) — **treat `label` as a semi-stable key**, not just display text. `weight` is 0–100. Order = display order (top to bottom slider order). |
| `riskThresholds.criticalLevel` / `.escalationTrigger` | string | **Numeric strings, no currency prefix**, e.g. `"15000000"` — the UI prepends "Rp" itself. Keep them as digit strings, not formatted numbers. |
| `riskThresholds.note` | string | Freeform helper text under the two threshold inputs. |
| `modelHealth.status` | string | Short status label, e.g. `"Optimized"`. |
| `modelHealth.accuracyLabel` | string | Pre-formatted sentence, e.g. `"88% Prediction Accuracy across 12.4k cases."`. |
| `modelHealth.progress` | number | 0–100, drives a progress bar. |
| `systemPrompt.version` | string | Display label, e.g. `"Version: 02.11.A"`. |
| `systemPrompt.content` | string | The full prompt text (multi-line). Rendered in an editable `<textarea>` — newlines are preserved as `\n`. |
| `systemPrompt.affectedChannelsNote` | string | Freeform helper text under the prompt editor. |

---

## `GET /ai-intelligence/operational-log`

Audit log of changes to this model's configuration.

**Auth required:** Yes.

**Success response — `200`**

An array, presumably newest-first (send in display order — the frontend does not sort):

```json
[
  { "timestamp": "2023-10-24 14:22:10", "action": "Risk Weight Adjustment", "user": "admin_irwan", "status": "Success" },
  { "timestamp": "2023-10-23 09:12:00", "action": "Model Retraining Start", "user": "data_sci_team", "status": "In Progress" }
]
```

| Field | Type | Notes |
|---|---|---|
| `timestamp` | string | Pre-formatted, e.g. `"2023-10-24 14:22:10"`. Not parsed by the frontend — send whatever format you want displayed. |
| `action` | string | e.g. `"Risk Weight Adjustment"`, `"System Prompt Deployment"`, `"Model Retraining Start"`. |
| `user` | string | Username or system identifier that made the change, e.g. `"admin_irwan"` or `"system_auto"`. |
| `status` | `"Success" \| "In Progress" \| "Failed"` | **Exact string values matter** (title case, with a space in `"In Progress"`) — drives both the chip color and the row's action button label (`"In Progress"` rows show a "Monitor" link, everything else shows "View Diff"). |

---

## `PUT /ai-intelligence/weighting-parameters`

Saves an edited set of weighting sliders. This is the module's only write endpoint today.

**Auth required:** Yes.

**Request body** — the full array of weighting parameters, in the same shape as `GET /ai-intelligence/model-config`'s `weightingParameters` field:

```json
[
  { "label": "Risk Weight", "weight": 50, "description": "Impact of historical delinquency and credit bureau scores on prioritization." },
  { "label": "Propensity Weight", "weight": 30, "description": "Probability of payment based on recent engagement and communication responsiveness." },
  { "label": "Settlement Velocity", "weight": 20, "description": "Average time to resolution for similar portfolio segments." }
]
```

**Important:** the frontend sends the *entire array* on every save (all parameters, not just the ones that changed), and it does **not** currently guarantee `weight` values sum to 100 before sending — validating/enforcing that (or rejecting with a clear error if they don't) should happen server-side.

**Success response — `200`** — the saved array, echoed back (same shape as the request body):

```json
[
  { "label": "Risk Weight", "weight": 50, "description": "..." },
  { "label": "Propensity Weight", "weight": 30, "description": "..." },
  { "label": "Settlement Velocity", "weight": 20, "description": "..." }
]
```

**What the frontend does after a successful save** (see `src/domains/ai-intelligence/useSaveWeightingParametersMutation.ts`): it invalidates its cached copies of both `GET /ai-intelligence/model-config` and `GET /ai-intelligence/operational-log`, triggering an automatic refetch of both. **This means a successful `PUT` should result in the next `GET /ai-intelligence/operational-log` including a new entry for this change** (e.g. `action: "Risk Weight Adjustment"`) — otherwise the audit log will look stale immediately after a save even though the numbers updated.

**Error responses**

| Status | When | Frontend behavior |
|---|---|---|
| any non-2xx | Save failed for any reason | The Save button shows its normal label again (no success state), and the local edit draft is **not** cleared — the user's in-progress edits stay in the sliders so they can retry. There's currently no visible error toast/message for a failed save — that would be a good follow-up once real failure modes are known (e.g. weights not summing to 100, concurrent edit conflict). |

**Notes**
- "Reset to Default" and "Deploy to Production" buttons exist in the UI. "Reset to Default" is currently **purely client-side** (discards the local draft and falls back to whatever `GET /ai-intelligence/model-config` last returned — it does not call any endpoint). "Deploy to Production" is **not wired to anything yet** — clarify with product whether that's a separate action from saving weights (e.g. promoting a "shadow" config to live) before building it.
- The risk threshold inputs and the system prompt textarea are visually editable but **not currently wired to any save action** — only the weighting sliders persist. If those need to be editable too, that's an additional endpoint (or an expanded `PUT` body) to design.
