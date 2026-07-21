export const queryKeys = {
  auth: {
    currentUser: ['auth', 'currentUser'] as const,
  },
  dashboard: {
    summary: ['dashboard', 'summary'] as const,
  },
  performance: {
    filters: ['performance', 'filters'] as const,
    summary: ['performance', 'summary'] as const,
    collectorRanking: (page: number) => ['performance', 'collectorRanking', page] as const,
    operationalLog: ['performance', 'operationalLog'] as const,
  },
  aiIntelligence: {
    modelConfig: ['aiIntelligence', 'modelConfig'] as const,
    operationalLog: ['aiIntelligence', 'operationalLog'] as const,
  },
  workbench: {
    accounts: (filter: string, search: string) => ['workbench', 'accounts', filter, search] as const,
    activityLog: ['workbench', 'activityLog'] as const,
  },
  customer: {
    detail: (customerId: string) => ['customer', customerId, 'detail'] as const,
    timeline: (customerId: string) => ['customer', customerId, 'timeline'] as const,
  },
} as const;
