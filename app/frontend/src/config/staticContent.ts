export interface NavItem {
  readonly label: string;
  readonly icon: string;
  readonly path: string;
}

// 5-menu scope per frontend-layout-upgrade-tasks.md TASK-A. Performance and
// Collector Workbench were dropped entirely (no backend was ever built for
// either). Restructuring Approval & AI Intelligence are shown to every
// logged-in user for now — RBAC was explicitly deferred, not implemented.
export const navItems: NavItem[] = [
  { label: 'Dashboard', icon: 'grid_view', path: '/dashboard' },
  { label: 'Customer', icon: 'people', path: '/customers' },
  { label: 'Contract', icon: 'description', path: '/contracts' },
  { label: 'Restructuring Approval', icon: 'fact_check', path: '/restructuring-approval' },
  { label: 'AI Intelligence', icon: 'psychology', path: '/ai-intelligence' },
];

export const complianceBadges = ['ISO 27001', 'SOC2 TYPE II'];

export const recoveryAccessStats = [
  { value: '98.4%', label: 'Recovery Rate' },
  { value: '2.4M', label: 'Managed Accounts' },
];

export const recoveryAccessCopy = {
  title: 'Intelligent Debt Recovery, Built for Institutional Trust.',
  description:
    'Manage high-stakes financial portfolios with a disciplined, data-driven approach. Our AI-powered platform transforms debt collection into a collaborative settlement process.',
};
