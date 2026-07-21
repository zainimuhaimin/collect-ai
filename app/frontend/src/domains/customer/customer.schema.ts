import { z } from 'zod';

export const customerDetailSchema = z.object({
  id: z.string(),
  name: z.string(),
  initials: z.string(),
  verified: z.boolean(),
  outstandingBalance: z.string(),
  balanceChange: z.string(),
  ptpHistory: z.object({
    success: z.number(),
    broken: z.number(),
    rate: z.string(),
  }),
  ptpMonths: z.array(
    z.object({
      month: z.string(),
      result: z.enum(['success', 'broken']),
    }),
  ),
  riskTier: z.enum(['HIGH RISK', 'MEDIUM RISK', 'LOW RISK']),
  riskTierLevel: z.string(),
  riskScore: z.number(),
  recoveryScore: z.number(),
  recoveryLabel: z.string(),
  selfCureProbability: z.string(),
  ptpSuccessProbability: z.string(),
  targetNbaAction: z.string(),
  aiJustification: z.string(),
});
export type CustomerDetail = z.infer<typeof customerDetailSchema>;

export const timelineEntrySchema = z.object({
  id: z.string(),
  icon: z.string(),
  title: z.string(),
  timestamp: z.string(),
  description: z.string(),
  tone: z.enum(['default', 'danger']),
  meta: z
    .object({
      label: z.string(),
      value: z.string(),
      tone: z.enum(['success', 'danger']),
    })
    .optional(),
});
export type TimelineEntry = z.infer<typeof timelineEntrySchema>;

export const customerTimelineResponseSchema = z.array(timelineEntrySchema);
