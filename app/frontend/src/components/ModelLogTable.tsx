import type { ModelLogEntry } from '../domains/ai-intelligence/aiIntelligence.schema';
import Chip from './Chip';

interface ModelLogTableProps {
  readonly entries: ModelLogEntry[];
}

const STATUS_TONE: Record<ModelLogEntry['status'], 'success' | 'medium' | 'danger'> = {
  Success: 'success',
  'In Progress': 'medium',
  Failed: 'danger',
};

export default function ModelLogTable({ entries }: ModelLogTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="text-label-md uppercase text-on-surface-variant dark:text-surface-variant border-b border-outline-variant dark:border-outline-variant/30">
            <th className="py-3 pr-4">Timestamp</th>
            <th className="py-3 pr-4">Action</th>
            <th className="py-3 pr-4">User</th>
            <th className="py-3 pr-4">Status</th>
            <th className="py-3 pr-4">Details</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={`${entry.timestamp}-${entry.action}`} className="border-b border-outline-variant dark:border-outline-variant/20">
              <td className="py-4 pr-4 text-body-md text-on-surface-variant dark:text-surface-variant">{entry.timestamp}</td>
              <td className="py-4 pr-4 text-label-lg font-semibold text-on-surface dark:text-on-background">{entry.action}</td>
              <td className="py-4 pr-4 text-body-md text-on-surface dark:text-on-background">{entry.user}</td>
              <td className="py-4 pr-4">
                <Chip tone={STATUS_TONE[entry.status]}>{entry.status}</Chip>
              </td>
              <td className="py-4 pr-4">
                <button type="button" className="text-label-lg font-semibold text-primary-container dark:text-primary-fixed-dim hover:underline">
                  {entry.status === 'In Progress' ? 'Monitor' : 'View Diff'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
