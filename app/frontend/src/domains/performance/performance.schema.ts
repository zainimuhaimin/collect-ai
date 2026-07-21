import { z } from 'zod';

export const performanceFiltersSchema = z.object({
  branches: z.array(z.string()),
  areas: z.array(z.string()),
  products: z.array(z.string()),
  dateRange: z.string(),
});
export type PerformanceFilters = z.infer<typeof performanceFiltersSchema>;

export const performanceSummarySchema = z.object({
  totalAchievement: z.string(),
  achievementChange: z.string(),
  activeCollectors: z.number(),
  activeCollectorsProgress: z.number(),
  avgProductivityIndex: z.number(),
});
export type PerformanceSummary = z.infer<typeof performanceSummarySchema>;

export const collectorSchema = z.object({
  rank: z.number(),
  name: z.string(),
  initials: z.string(),
  employeeId: z.string(),
  target: z.string(),
  achievement: z.string(),
  collectionRate: z.number(),
  productivityIndex: z.number(),
  ratingTone: z.enum(['good', 'fair', 'poor']),
});
export type Collector = z.infer<typeof collectorSchema>;

export const collectorRankingPageInfoSchema = z.object({
  showingFrom: z.number(),
  showingTo: z.number(),
  totalCollectors: z.number(),
  totalPages: z.number(),
});
export type CollectorRankingPageInfo = z.infer<typeof collectorRankingPageInfoSchema>;

export const collectorRankingResponseSchema = z.object({
  collectors: z.array(collectorSchema),
  pageInfo: collectorRankingPageInfoSchema,
});
export type CollectorRankingResponse = z.infer<typeof collectorRankingResponseSchema>;

export const operationalLogEntrySchema = z.object({
  id: z.string(),
  message: z.string(),
  timestamp: z.string(),
  tone: z.enum(['neutral', 'success', 'muted']),
});
export type OperationalLogEntry = z.infer<typeof operationalLogEntrySchema>;

export const performanceOperationalLogResponseSchema = z.array(operationalLogEntrySchema);
