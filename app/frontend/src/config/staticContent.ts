export interface NavItem {
  readonly label: string;
  readonly icon: string;
  readonly path: string;
}

export const navItems: NavItem[] = [
  { label: 'Dashboard', icon: 'grid_view', path: '/dashboard' },
  { label: 'Performance', icon: 'monitoring', path: '/performance' },
  { label: 'Collector Workbench', icon: 'work', path: '/workbench' },
  { label: 'Customer Detail', icon: 'people', path: '/customers/C-90218341' },
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
