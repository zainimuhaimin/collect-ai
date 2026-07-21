import type { Collector } from '../domains/performance/performance.schema';
import Avatar from './Avatar';
import ProgressBar from './ProgressBar';

interface CollectorRankingTableProps {
  readonly collectors: Collector[];
}

const RATE_TONE: Record<Collector['ratingTone'], 'success' | 'primary' | 'error'> = {
  good: 'success',
  fair: 'primary',
  poor: 'error',
};

export default function CollectorRankingTable({ collectors }: CollectorRankingTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="text-label-md uppercase text-on-surface-variant dark:text-surface-variant border-b border-outline-variant dark:border-outline-variant/30">
            <th className="py-3 pr-4">Rank</th>
            <th className="py-3 pr-4">Collector Name</th>
            <th className="py-3 pr-4">Target (Rp)</th>
            <th className="py-3 pr-4">Achievement (Rp)</th>
            <th className="py-3 pr-4">Collection %</th>
            <th className="py-3 pr-4">Productivity Index</th>
          </tr>
        </thead>
        <tbody>
          {collectors.map((collector) => (
            <tr key={collector.employeeId} className="border-b border-outline-variant dark:border-outline-variant/20">
              <td className="py-4 pr-4">
                <span className="w-6 h-6 flex items-center justify-center rounded-full bg-surface-container-high dark:bg-surface-variant/20 text-label-md font-semibold">
                  {collector.rank}
                </span>
              </td>
              <td className="py-4 pr-4">
                <div className="flex items-center gap-3">
                  <Avatar initials={collector.initials} size="sm" />
                  <div>
                    <p className="text-label-lg font-semibold text-on-surface dark:text-on-background">{collector.name}</p>
                    <p className="text-label-sm text-on-surface-variant dark:text-surface-variant">Emp ID: {collector.employeeId}</p>
                  </div>
                </div>
              </td>
              <td className="py-4 pr-4 text-body-md text-on-surface dark:text-on-background">{collector.target}</td>
              <td className="py-4 pr-4 text-label-lg font-semibold text-on-surface dark:text-on-background">
                {collector.achievement}
              </td>
              <td className="py-4 pr-4">
                <div className="flex items-center gap-2 w-32">
                  <span className="text-label-lg font-semibold text-on-surface dark:text-on-background">
                    {collector.collectionRate.toFixed(2)}%
                  </span>
                </div>
                <ProgressBar value={collector.collectionRate} tone={RATE_TONE[collector.ratingTone]} trackClassName="w-24 mt-1" />
              </td>
              <td className="py-4 pr-4 text-label-lg font-semibold text-on-surface dark:text-on-background">
                <span className="px-2 py-1 rounded-md bg-surface-container-high dark:bg-surface-variant/10">
                  {collector.productivityIndex}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
