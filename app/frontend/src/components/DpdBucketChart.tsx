import type { DpdBucket } from '../domains/dashboard/dashboard.schema';

interface DpdBucketChartProps {
  readonly buckets: DpdBucket[];
}

const MAX_HEIGHT_PX = 220;

export default function DpdBucketChart({ buckets }: DpdBucketChartProps) {
  return (
    <div>
      <div className="flex items-center gap-6 mb-6 text-label-lg text-on-surface-variant dark:text-surface-variant">
        <span className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-on-background dark:bg-on-surface" /> Settled
        </span>
        <span className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-primary-fixed-dim" /> Active PTP
        </span>
        <span className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-outline-variant" /> Broken
        </span>
      </div>
      <div className="flex items-end justify-between gap-6 h-[240px]">
        {buckets.map((bucket) => {
          const total = bucket.settled + bucket.activePtp + bucket.broken;
          return (
            <div key={bucket.label} className="flex-1 flex flex-col items-center gap-3">
              <div className="w-full flex flex-col-reverse rounded-t-lg overflow-hidden" style={{ height: MAX_HEIGHT_PX }}>
                <div className="bg-on-background dark:bg-on-surface" style={{ height: `${(bucket.settled / total) * 100}%` }} />
                <div className="bg-primary-fixed-dim" style={{ height: `${(bucket.activePtp / total) * 100}%` }} />
                <div className="bg-outline-variant" style={{ height: `${(bucket.broken / total) * 100}%` }} />
              </div>
              <p className="text-label-md text-on-surface-variant dark:text-surface-variant">{bucket.label}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
