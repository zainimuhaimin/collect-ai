import { type ReactNode, useEffect, useRef, useState } from 'react';
import { useCurrentUserQuery } from '../domains/auth/useCurrentUserQuery';
import { useAuthToken } from '../auth/useAuthToken';
import Avatar from './Avatar';
import Modal from './Modal';

interface TopBarProps {
  readonly title: string;
  readonly searchPlaceholder?: string;
  readonly badge?: string;
  // Page-specific controls rendered in the top-right corner, before the
  // notification/settings/profile icons — e.g. AI Intelligence's "Sync Now".
  readonly actions?: ReactNode;
}

export default function TopBar({ title, searchPlaceholder = 'Search...', badge, actions }: TopBarProps) {
  const { data: currentUser } = useCurrentUserQuery();
  const { logout } = useAuthToken();
  const [menuOpen, setMenuOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [menuOpen]);

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
        {actions}
        <button type="button" aria-label="Notifications" className="text-on-surface-variant dark:text-surface-variant">
          <span className="material-symbols-outlined">notifications</span>
        </button>
        <button type="button" aria-label="Settings" className="text-on-surface-variant dark:text-surface-variant">
          <span className="material-symbols-outlined">settings</span>
        </button>
        <div className="relative hidden sm:block" ref={menuRef}>
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            className="flex items-center gap-2"
          >
            <Avatar initials={currentUser?.initials ?? ''} size="sm" />
            <div className="text-left">
              <p className="text-label-lg font-semibold text-on-surface dark:text-on-background leading-none">
                {currentUser?.name ?? 'Loading...'}
              </p>
              <p className="text-label-sm text-on-surface-variant dark:text-surface-variant">{currentUser?.role ?? ''}</p>
            </div>
            <span className="material-symbols-outlined text-lg text-on-surface-variant dark:text-surface-variant">
              expand_more
            </span>
          </button>

          {menuOpen ? (
            <div
              role="menu"
              className="absolute right-0 top-full mt-2 w-48 rounded-lg border border-outline-variant dark:border-outline-variant/30 bg-surface-container-lowest dark:bg-surface-container-high/20 shadow-lg overflow-hidden z-40"
            >
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setProfileOpen(true);
                  setMenuOpen(false);
                }}
                className="flex items-center gap-2 w-full px-4 py-2.5 text-left text-label-lg text-on-surface dark:text-on-background hover:bg-surface-container dark:hover:bg-surface-container-high/30"
              >
                <span className="material-symbols-outlined text-lg">person</span>
                Profil Saya
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  logout();
                }}
                className="flex items-center gap-2 w-full px-4 py-2.5 text-left text-label-lg text-error hover:bg-surface-container dark:hover:bg-surface-container-high/30"
              >
                <span className="material-symbols-outlined text-lg">logout</span>
                Logout
              </button>
            </div>
          ) : null}
        </div>
      </div>

      {profileOpen ? (
        <Modal title="Profil Saya" onClose={() => setProfileOpen(false)}>
          <div className="flex items-center gap-3 mb-4">
            <Avatar initials={currentUser?.initials ?? ''} size="lg" />
            <div>
              <p className="text-title-md font-bold text-on-surface dark:text-on-background">
                {currentUser?.name ?? '—'}
              </p>
              <p className="text-label-md text-on-surface-variant dark:text-surface-variant">{currentUser?.role ?? '—'}</p>
            </div>
          </div>
          <dl className="space-y-2 text-body-md">
            <div className="flex items-center justify-between">
              <dt className="text-on-surface-variant dark:text-surface-variant">Name</dt>
              <dd className="font-semibold text-on-surface dark:text-on-background">{currentUser?.name ?? '—'}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-on-surface-variant dark:text-surface-variant">Role</dt>
              <dd className="font-semibold text-on-surface dark:text-on-background">{currentUser?.role ?? '—'}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-on-surface-variant dark:text-surface-variant">Initials</dt>
              <dd className="font-semibold text-on-surface dark:text-on-background">{currentUser?.initials ?? '—'}</dd>
            </div>
          </dl>
        </Modal>
      ) : null}
    </header>
  );
}
