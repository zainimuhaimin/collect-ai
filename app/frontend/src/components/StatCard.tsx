interface StatCardProps {
  readonly icon: string;
  readonly label: string;
  readonly value: string;
}

// Simplified per the real `/dashboard/summary` contract: the backend only sends a raw
// value per KPI (no `change`/`trend`/`icon` — those were fabricated by the old mock), so
// this card just shows a label + value. `icon` is chosen client-side per KPI (see
// DashboardPage.tsx) purely for visual consistency with the rest of the app, not backend
// data.
export default function StatCard({ icon, label, value }: StatCardProps) {
  return (
    <div className="bg-surface-container-lowest dark:bg-surface-container-high/20 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-5 flex flex-col gap-4">
      <div className="w-9 h-9 rounded-lg bg-primary-container/10 dark:bg-primary-fixed-dim/10 flex items-center justify-center text-primary-container dark:text-primary-fixed-dim">
        <span className="material-symbols-outlined text-xl">{icon}</span>
      </div>
      <div>
        <p className="text-body-md text-on-surface-variant dark:text-surface-variant">{label}</p>
        <p className="text-title-lg font-bold text-on-surface dark:text-on-background mt-1">{value}</p>
      </div>
    </div>
  );
}
