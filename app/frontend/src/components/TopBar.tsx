import { useCurrentUserQuery } from '../domains/auth/useCurrentUserQuery';
import Avatar from './Avatar';

interface TopBarProps {
  readonly title: string;
  readonly searchPlaceholder?: string;
  readonly badge?: string;
}

export default function TopBar({ title, searchPlaceholder = 'Search...', badge }: TopBarProps) {
  const { data: currentUser } = useCurrentUserQuery();

  return (
    <header className="flex items-center justify-between gap-4 px-6 py-4 border-b border-outline-variant dark:border-outline-variant/30 bg-surface dark:bg-surface-container-lowest">
      <div className="flex items-center gap-3">
        <h1 className="text-title-lg font-bold text-on-surface dark:text-on-background">{title}</h1>
        {badge ? (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-secondary-container text-on-secondary-container dark:bg-secondary/20 dark:text-secondary-fixed text-label-md">
            <span className="w-1.5 h-1.5 rounded-full bg-secondary dark:bg-secondary-fixed" />
            {badge}
          </span>
        ) : null}
      </div>

      <div className="flex-1 max-w-md">
        <div className="relative">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-lg">
            search
          </span>
          <input
            type="search"
            placeholder={searchPlaceholder}
            className="w-full pl-10 pr-4 py-2 rounded-lg bg-surface-container-low dark:bg-surface-container-high/20 text-body-md text-on-surface dark:text-on-background placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary-container"
          />
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button type="button" aria-label="Notifications" className="text-on-surface-variant dark:text-surface-variant">
          <span className="material-symbols-outlined">notifications</span>
        </button>
        <button type="button" aria-label="Settings" className="text-on-surface-variant dark:text-surface-variant">
          <span className="material-symbols-outlined">settings</span>
        </button>
        <div className="hidden sm:flex items-center gap-2">
          <Avatar initials={currentUser?.initials ?? ''} size="sm" />
          <div className="text-left">
            <p className="text-label-lg font-semibold text-on-surface dark:text-on-background leading-none">
              {currentUser?.name ?? 'Loading...'}
            </p>
            <p className="text-label-sm text-on-surface-variant dark:text-surface-variant">{currentUser?.role ?? ''}</p>
          </div>
        </div>
      </div>
    </header>
  );
}
