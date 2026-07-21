import type { ReactNode } from 'react';
import Sidebar from '../components/Sidebar';
import TopBar from '../components/TopBar';

interface AppLayoutProps {
  readonly children: ReactNode;
  readonly title: string;
  readonly searchPlaceholder?: string;
  readonly badge?: string;
}

export default function AppLayout({ children, title, searchPlaceholder = 'Search...', badge }: AppLayoutProps) {
  return (
    <div className="flex min-h-screen bg-background dark:bg-on-background">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar title={title} searchPlaceholder={searchPlaceholder} badge={badge} />
        <main className="flex-1 p-6 max-w-container mx-auto w-full">{children}</main>
      </div>
    </div>
  );
}
