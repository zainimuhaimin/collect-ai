export interface TimelineItem {
  readonly id: string;
  readonly icon?: string;
  readonly title: string;
  readonly timestamp: string;
  readonly description?: string;
  readonly tone: 'default' | 'danger' | 'muted';
  readonly meta?: { label: string; value: string; tone: 'success' | 'danger' };
}

interface ActivityTimelineProps {
  readonly items: TimelineItem[];
}

const DOT_TONE: Record<TimelineItem['tone'], string> = {
  default: 'bg-on-background dark:bg-on-surface',
  danger: 'bg-error text-on-error',
  muted: 'bg-outline-variant',
};

export default function ActivityTimeline({ items }: ActivityTimelineProps) {
  return (
    <ol className="relative border-l border-outline-variant dark:border-outline-variant/30 ml-3 space-y-6">
      {items.map((item) => (
        <li key={item.id} className="ml-6">
          <span
            className={`absolute -left-[7px] flex items-center justify-center w-3.5 h-3.5 rounded-full ${DOT_TONE[item.tone]}`}
          >
            {item.icon ? <span className="material-symbols-outlined text-[10px] text-white">{item.icon}</span> : null}
          </span>
          <div className="flex items-center justify-between gap-4">
            <p className={`text-label-lg font-semibold ${item.tone === 'danger' ? 'text-error' : 'text-on-surface dark:text-on-background'}`}>
              {item.title}
            </p>
            <span className="text-label-sm text-on-surface-variant dark:text-surface-variant whitespace-nowrap">
              {item.timestamp}
            </span>
          </div>
          {item.description ? (
            <div
              className={`mt-1 rounded-lg px-3 py-2 text-body-md text-on-surface-variant dark:text-surface-variant ${
                item.tone === 'danger' ? 'bg-error-container/40 dark:bg-error/10' : 'bg-surface-container-low dark:bg-surface-container-high/10'
              }`}
            >
              {item.description}
              {item.meta ? (
                <span className={`ml-1 font-semibold ${item.meta.tone === 'success' ? 'text-success' : 'text-error'}`}>
                  {item.meta.value}
                </span>
              ) : null}
            </div>
          ) : null}
        </li>
      ))}
    </ol>
  );
}
