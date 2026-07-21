import type { OperationalLogEntry } from '../domains/performance/performance.schema';

interface OperationalLogListProps {
  readonly entries: OperationalLogEntry[];
}

const DOT_TONE: Record<OperationalLogEntry['tone'], string> = {
  neutral: 'bg-on-background dark:bg-on-surface',
  success: 'bg-success',
  muted: 'bg-outline-variant',
};

export default function OperationalLogList({ entries }: OperationalLogListProps) {
  return (
    <ul className="space-y-4">
      {entries.map((entry) => (
        <li key={entry.id} className="flex items-start gap-3">
          <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${DOT_TONE[entry.tone]}`} />
          <div>
            <p className="text-body-md text-on-surface dark:text-on-background">{entry.message}</p>
            <p className="text-label-sm text-on-surface-variant dark:text-surface-variant">{entry.timestamp}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}
