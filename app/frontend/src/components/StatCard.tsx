import type { KpiStat } from '../domains/dashboard/dashboard.schema';

interface StatCardProps {
  readonly stat: KpiStat;
}

const TREND_ICON: Record<KpiStat['trend'], string> = {
  up: 'trending_up',
  down: 'trending_down',
  flat: 'trending_flat',
};

const TONE_TEXT: Record<KpiStat['tone'], string> = {
  positive: 'text-success dark:text-success-container',
  negative: 'text-error dark:text-error-container',
  neutral: 'text-on-surface-variant dark:text-surface-variant',
};

export default function StatCard({ stat }: StatCardProps) {
  return (
    <div className="bg-surface-container-lowest dark:bg-surface-container-high/20 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="w-9 h-9 rounded-lg bg-primary-container/10 dark:bg-primary-fixed-dim/10 flex items-center justify-center text-primary-container dark:text-primary-fixed-dim">
          <span className="material-symbols-outlined text-xl">{stat.icon}</span>
        </div>
        <span className={`inline-flex items-center gap-1 text-label-md font-semibold ${TONE_TEXT[stat.tone]}`}>
          {stat.change}
          <span className="material-symbols-outlined text-sm">{TREND_ICON[stat.trend]}</span>
        </span>
      </div>
      <div>
        <p className="text-body-md text-on-surface-variant dark:text-surface-variant">{stat.label}</p>
        <p className="text-title-lg font-bold text-on-surface dark:text-on-background mt-1">{stat.value}</p>
      </div>
    </div>
  );
}
