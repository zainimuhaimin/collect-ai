// Same simple localStorage-backed pattern as `auth/tokenStorage.ts` — read once on
// mount, write on every change. Keeps the sidebar's collapsed/expanded state across
// page reloads without needing a backend round-trip (purely a client-side UI
// preference).
const SIDEBAR_COLLAPSED_KEY = 'collectai.sidebar.collapsed';

export function getSidebarCollapsed(): boolean {
  return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true';
}

export function setSidebarCollapsed(collapsed: boolean): void {
  localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed));
}
