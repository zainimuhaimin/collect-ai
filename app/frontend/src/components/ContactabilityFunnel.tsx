import type { FunnelStage } from '../domains/dashboard/dashboard.schema';

interface ContactabilityFunnelProps {
  readonly stages: FunnelStage[];
  readonly channel: string;
  readonly channelRate: string;
}

export default function ContactabilityFunnel({ stages, channel, channelRate }: ContactabilityFunnelProps) {
  return (
    <div>
      <div className="space-y-3">
        {stages.map((stage, index) => (
          <div key={stage.label} className="flex items-center gap-3">
            <div
              className="flex-1 py-3 px-4 rounded-md bg-primary-container text-on-primary text-label-lg font-semibold"
              style={{ width: `${100 - index * 12}%` }}
            >
              {stage.label}
            </div>
            <span className="text-label-lg text-on-surface-variant dark:text-surface-variant w-10 text-right">
              {stage.percentage}
            </span>
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between mt-6 pt-4 border-t border-outline-variant dark:border-outline-variant/30">
        <span className="text-body-md text-on-surface-variant dark:text-surface-variant">Channel Efficiency</span>
        <span className="text-label-lg font-bold text-on-surface dark:text-on-background">
          {channel} ({channelRate})
        </span>
      </div>
    </div>
  );
}
