import type { ChannelEfficiencyItem } from '../domains/dashboard/dashboard.schema';

interface ChannelEfficiencyChartProps {
  readonly channels: ChannelEfficiencyItem[];
}

// Replaces the old single "best channel" object with a ranked list — one horizontal
// bar per `channel_efficiency[]` entry, sized proportionally to `contact_success_rate`.
// The backend already sorts this list descending, so it's rendered in the order given.
export default function ChannelEfficiencyChart({ channels }: ChannelEfficiencyChartProps) {
  return (
    <div className="space-y-3">
      {channels.map((item) => {
        const widthPercent = Math.min(Math.max(item.contactSuccessRate * 100, 0), 100);
        return (
          <div key={item.treatmentType} className="flex items-center gap-3">
            <span className="w-24 shrink-0 text-label-md text-on-surface-variant dark:text-surface-variant">
              {item.treatmentType}
            </span>
            <div className="flex-1 h-6 rounded-md bg-surface-container-high dark:bg-surface-variant/10 overflow-hidden">
              <div
                className="h-full rounded-md bg-primary-container"
                style={{ width: `${widthPercent}%` }}
                title={`${(item.contactSuccessRate * 100).toFixed(2)}%`}
              />
            </div>
            <span className="w-14 shrink-0 text-right text-label-lg font-semibold text-on-surface dark:text-on-background">
              {widthPercent.toFixed(0)}%
            </span>
          </div>
        );
      })}
      {channels.length === 0 ? (
        <p className="text-body-md text-on-surface-variant dark:text-surface-variant">Belum ada data channel efficiency.</p>
      ) : null}
    </div>
  );
}
