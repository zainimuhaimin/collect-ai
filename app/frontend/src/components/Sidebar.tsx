import { Link } from 'react-router-dom';
import { navItems } from '../config/staticContent';
import { useActiveRoute } from '../hooks/useActiveRoute';

interface SidebarProps {
  readonly className?: string;
  readonly collapsed: boolean;
  readonly onToggleCollapsed: () => void;
}

export default function Sidebar({ className = '', collapsed, onToggleCollapsed }: SidebarProps) {
  const { isActive } = useActiveRoute();

  return (
    <aside
      className={`hidden md:flex md:flex-col ${collapsed ? 'md:w-20' : 'md:w-64'} shrink-0 bg-surface dark:bg-surface-container-lowest border-r border-outline-variant dark:border-outline-variant/30 sticky top-0 h-screen overflow-y-auto transition-[width] duration-200 ${className}`}
    >
      {/* Pure toggle button — intentionally does NOT navigate anywhere. Dashboard is
          still reachable via the regular nav item below. */}
      <button
        type="button"
        onClick={onToggleCollapsed}
        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        className="flex items-center gap-3 px-6 py-6 text-left"
      >
        <div className="w-9 h-9 rounded-lg bg-primary-container flex items-center justify-center shrink-0">
          <span className="material-symbols-outlined text-white text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>
            account_balance
          </span>
        </div>
        {!collapsed ? (
          <div>
            <p className="text-title-md font-bold text-on-surface dark:text-on-background leading-none">CollectAI</p>
            <p className="text-label-sm text-on-surface-variant dark:text-surface-variant uppercase tracking-wide">
              Enterprise Recovery
            </p>
          </div>
        ) : null}
      </button>

      <nav className="flex-1 px-4 space-y-1">
        {navItems.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            title={item.label}
            className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-label-lg transition-colors ${
              collapsed ? 'justify-center' : ''
            } ${
              isActive(item.path)
                ? 'bg-primary-container text-on-primary'
                : 'text-on-surface-variant dark:text-surface-variant hover:bg-surface-container dark:hover:bg-surface-container-high/20'
            }`}
          >
            <span className="material-symbols-outlined text-xl">{item.icon}</span>
            {!collapsed ? item.label : null}
          </Link>
        ))}
      </nav>

      <div className="px-4 pb-4">
        <div
          className={`flex items-center gap-2 px-2 py-2 text-label-md text-on-surface-variant dark:text-surface-variant ${
            collapsed ? 'justify-center' : ''
          }`}
          title="System Status: Optimal"
        >
          <span className="w-2 h-2 rounded-full bg-success shrink-0" />
          {!collapsed ? 'System Status: Optimal' : null}
        </div>
        <button
          type="button"
          title="Support Hub"
          className="w-full py-2.5 rounded-lg bg-surface-container dark:bg-surface-container-high/30 text-label-lg text-on-surface dark:text-on-background"
        >
          {collapsed ? <span className="material-symbols-outlined text-xl">support_agent</span> : 'Support Hub'}
        </button>
      </div>
    </aside>
  );
}
