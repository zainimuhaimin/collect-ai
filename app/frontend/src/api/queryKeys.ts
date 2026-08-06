export const queryKeys = {
  auth: {
    currentUser: ['auth', 'currentUser'] as const,
  },
  dashboard: {
    summary: ['dashboard', 'summary'] as const,
  },
  aiIntelligence: {
    modelConfig: ['aiIntelligence', 'modelConfig'] as const,
    operationalLog: ['aiIntelligence', 'operationalLog'] as const,
    syncStatus: ['aiIntelligence', 'syncStatus'] as const,
    llmSystemPrompt: ['aiIntelligence', 'llmSystemPrompt'] as const,
  },
  customer: {
    detail: (customerId: string) => ['customer', customerId, 'detail'] as const,
    list: (filter: string, search: string, page: number, pageSize: number) =>
      ['customer', 'list', filter, search, page, pageSize] as const,
    contracts: (customerId: string) => ['customer', customerId, 'contracts'] as const,
  },
  contract: {
    list: (filter: string, search: string, page: number, pageSize: number) =>
      ['contract', 'list', filter, search, page, pageSize] as const,
    detail: (contractNo: string) => ['contract', contractNo, 'detail'] as const,
    activityLog: (contractNo: string) => ['contract', contractNo, 'activityLog'] as const,
  },
  restructuring: {
    options: (customerId: string) => ['restructuring', customerId, 'options'] as const,
    groups: (status: string, search: string, page: number, pageSize: number) =>
      ['restructuring', 'groups', status, search, page, pageSize] as const,
    groupDetail: (groupId: string) => ['restructuring', 'groups', 'detail', groupId] as const,
  },
  aiReasoning: {
    detail: (customerId: string) => ['aiReasoning', customerId] as const,
  },
} as const;
