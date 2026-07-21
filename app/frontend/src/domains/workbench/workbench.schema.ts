import { z } from 'zod';

export const workbenchFilterKeySchema = z.enum(['all', 'dpd_30_plus', 'high_amount']);
export type WorkbenchFilterKey = z.infer<typeof workbenchFilterKeySchema>;

export const workbenchAccountSchema = z.object({
  id: z.string(),
  accountId: z.string(),
  name: z.string(),
  initials: z.string(),
  dpdDays: z.number(),
  amount: z.string(),
  priority: z.enum(['Critical', 'High', 'Medium']),
  location: z.string(),
  paymentProbability: z.number(),
  employmentStatus: z.string(),
  lastPaymentDate: z.string(),
  aiReasoning: z.string(),
  aiRecommendations: z.array(z.string()),
});
export type WorkbenchAccount = z.infer<typeof workbenchAccountSchema>;

export const workbenchAccountsResponseSchema = z.object({
  accounts: z.array(workbenchAccountSchema),
  totalCount: z.number(),
});
export type WorkbenchAccountsResponse = z.infer<typeof workbenchAccountsResponseSchema>;

export const workbenchLogEntrySchema = z.object({
  id: z.string(),
  title: z.string(),
  timestamp: z.string(),
  tone: z.enum(['sent', 'missed']),
});
export type WorkbenchLogEntry = z.infer<typeof workbenchLogEntrySchema>;

export const workbenchActivityLogResponseSchema = z.array(workbenchLogEntrySchema);
