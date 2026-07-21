import { authHandlers } from './auth.handlers';
import { customerHandlers } from './customer.handlers';
import { dashboardHandlers } from './dashboard.handlers';
import { aiIntelligenceHandlers } from './aiIntelligence.handlers';
import { performanceHandlers } from './performance.handlers';
import { workbenchHandlers } from './workbench.handlers';

// Each domain contributes its own handler array as it's migrated (see the implementation
// plan's migration order). Merge them here so mocks/browser.ts has one array to install.
export const handlers = [
  ...authHandlers,
  ...customerHandlers,
  ...dashboardHandlers,
  ...aiIntelligenceHandlers,
  ...performanceHandlers,
  ...workbenchHandlers,
];
