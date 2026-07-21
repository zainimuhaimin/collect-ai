import { Link } from 'react-router-dom';
import { navItems } from '../config/staticContent';
import { useActiveRoute } from '../hooks/useActiveRoute';
import { useCurrentUserQuery } from '../domains/auth/useCurrentUserQuery';
import Avatar from './Avatar';

interface SidebarProps {
  readonly className?: string;
}

export default function Sidebar({ className = '' }: SidebarProps) {
  const { isActive } = useActiveRoute();
  const { data: currentUser } = useCurrentUserQuery();

  return (
    <aside
      className={`hidden md:flex md:flex-col md:w-64 shrink-0 bg-surface dark:bg-surface-container-lowest border-r border-outline-variant dark:border-outline-variant/30 min-h-screen ${className}`}
    >
      <Link to="/dashboard" className="flex items-center gap-3 px-6 py-6">
        <div className="w-9 h-9 rounded-lg bg-primary-container flex items-center justify-center">
          <span className="material-symbols-outlined text-white text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>
            account_balance
          </span>
        </div>
        <div>
          <p className="text-title-md font-bold text-on-surface dark:text-on-background leading-none">CollectAI</p>
          <p className="text-label-sm text-on-surface-variant dark:text-surface-variant uppercase tracking-wide">
            Enterprise Recovery
          </p>
        </div>
      </Link>

      <nav className="flex-1 px-4 space-y-1">
        {navItems.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-label-lg transition-colors ${
              isActive(item.path)
                ? 'bg-primary-container text-on-primary'
                : 'text-on-surface-variant dark:text-surface-variant hover:bg-surface-container dark:hover:bg-surface-container-high/20'
            }`}
          >
            <span className="material-symbols-outlined text-xl">{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="px-4 pb-4">
        <div className="flex items-center gap-2 px-2 py-2 text-label-md text-on-surface-variant dark:text-surface-variant">
          <span className="w-2 h-2 rounded-full bg-success" />
          System Status: Optimal
        </div>
        <button
          type="button"
          className="w-full mb-4 py-2.5 rounded-lg bg-surface-container dark:bg-surface-container-high/30 text-label-lg text-on-surface dark:text-on-background"
        >
          Support Hub
        </button>
        <div className="flex items-center gap-3 border-t border-outline-variant dark:border-outline-variant/30 pt-4">
          <Avatar initials={currentUser?.initials ?? ''} size="sm" />
          <div>
            <p className="text-label-lg font-semibold text-on-surface dark:text-on-background">{currentUser?.name ?? 'Loading...'}</p>
            <p className="text-label-sm text-on-surface-variant dark:text-surface-variant">{currentUser?.role ?? ''}</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
