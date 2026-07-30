import { z } from 'zod';
import type { ChipTone } from '../../components/Chip';

// Real enum values from the DB (`customer_behavioral_standing`/`ai_intelligence_output`
// .risk_segment column) — displayed AS-IS everywhere in the UI. Do NOT translate these
// into invented strings like "HIGH RISK"/"LOW RISK" (that was the old, wrong schema).
// NOTE: 'Self-cure' (hyphenated, lowercase "c") is the exact raw DB spelling — do not
// "fix" it back to "Self Cure", and do not confuse it with the model-predicted
// self_cure_rate KPI on the Dashboard (see dashboard.schema.ts), a different metric.
export const riskSegmentSchema = z.enum(['Cannot Pay', 'Self-cure', "Won't Pay", 'Can Pay']);
export type RiskSegment = z.infer<typeof riskSegmentSchema>;

export const RISK_SEGMENT_TONE: Record<RiskSegment, ChipTone> = {
  'Cannot Pay': 'danger',
  'Self-cure': 'success',
  "Won't Pay": 'medium',
  'Can Pay': 'positive',
};
