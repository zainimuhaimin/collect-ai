interface ProgressBarProps {
  readonly value: number;
  readonly tone?: 'primary' | 'success' | 'warning' | 'error';
  readonly trackClassName?: string;
  readonly title?: string;
}

const TONE_CLASSES: Record<Required<ProgressBarProps>['tone'], string> = {
  primary: 'bg-primary-container dark:bg-primary-fixed-dim',
  success: 'bg-success dark:bg-success',
  warning: 'bg-warning dark:bg-warning',
  error: 'bg-error dark:bg-error',
};

export default function ProgressBar({ value, tone = 'primary', trackClassName = '', title }: ProgressBarProps) {
  return (
    <div
      className={`w-full h-1.5 rounded-full bg-surface-container-high dark:bg-surface-variant/30 overflow-hidden ${trackClassName}`}
      title={title}
    >
      <div
        className={`h-full rounded-full ${TONE_CLASSES[tone]}`}
        style={{ width: `${Math.min(Math.max(value, 0), 100)}%` }}
      />
    </div>
  );
}
