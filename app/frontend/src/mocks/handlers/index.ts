import { customerHandlers } from './customer.handlers';
import { dashboardHandlers } from './dashboard.handlers';
import { aiIntelligenceHandlers } from './aiIntelligence.handlers';
import { aiReasoningHandlers } from './aiReasoning.handlers';
import { contractHandlers } from './contract.handlers';
import { restructuringHandlers } from './restructuring.handlers';

// Auth (`authHandlers` from './auth.handlers') is intentionally NOT included below.
// A real backend now implements this module (app/backend, see
// docs/api/01-auth.md) — onUnhandledRequest: 'bypass' (src/main.tsx) lets
// unmatched /auth/* requests fall through to the real network, where the
// Vite dev-proxy (vite.config.ts) forwards them to the backend. Performance
// and Collector Workbench were dropped entirely (see
// frontend-layout-upgrade-tasks.md TASK-A) — no backend was ever built for
// either, and their UI patterns were folded into Customer/Contract instead.
export const handlers = [
  ...customerHandlers,
  ...dashboardHandlers,
  ...aiIntelligenceHandlers,
  ...aiReasoningHandlers,
  ...contractHandlers,
  ...restructuringHandlers,
];
