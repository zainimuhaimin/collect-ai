import { customerHandlers } from './customer.handlers';
import { dashboardHandlers } from './dashboard.handlers';
import { aiIntelligenceHandlers } from './aiIntelligence.handlers';
import { performanceHandlers } from './performance.handlers';
import { workbenchHandlers } from './workbench.handlers';

// Auth (`authHandlers` from './auth.handlers') is intentionally NOT included below.
// A real backend now implements this module (app/backend, see
// docs/api/01-auth.md) — onUnhandledRequest: 'bypass' (src/main.tsx) lets
// unmatched /auth/* requests fall through to the real network, where the
// Vite dev-proxy (vite.config.ts) forwards them to the backend. The other
// five modules below have no real backend yet and remain mocked.
export const handlers = [
  ...customerHandlers,
  ...dashboardHandlers,
  ...aiIntelligenceHandlers,
  ...performanceHandlers,
  ...workbenchHandlers,
];
