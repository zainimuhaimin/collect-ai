import { type ReactNode, useEffect, useState } from 'react';
import Sidebar from '../components/Sidebar';
import TopBar from '../components/TopBar';
import { getSidebarCollapsed, setSidebarCollapsed } from './sidebarStorage';

interface AppLayoutProps {
  readonly children: ReactNode;
  readonly title: string;
  readonly searchPlaceholder?: string;
  readonly badge?: string;
  readonly actions?: ReactNode;
}

export default function AppLayout({ children, title, searchPlaceholder = 'Search...', badge, actions }: AppLayoutProps) {
  const [collapsed, setCollapsed] = useState(() => getSidebarCollapsed());

  useEffect(() => {
    setSidebarCollapsed(collapsed);
  }, [collapsed]);

  return (
    // h-screen + overflow-hidden (not min-h-screen) is what pins the header —
    // the Sidebar and TopBar both sit outside the one scrollable region below
    // (<main>, overflow-y-auto); without a fixed-height ancestor, the whole
    // page would grow with content and scroll as one block, taking the header
    // along with it.
    <div className="flex h-screen overflow-hidden bg-background dark:bg-on-background">
      <Sidebar collapsed={collapsed} onToggleCollapsed={() => setCollapsed((current) => !current)} />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar title={title} searchPlaceholder={searchPlaceholder} badge={badge} actions={actions} />
        <main className="flex-1 overflow-y-auto p-6 max-w-container mx-auto w-full">{children}</main>
      </div>
    </div>
  );
}
