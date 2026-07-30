export type ChipTone = 'critical' | 'high' | 'medium' | 'success' | 'danger' | 'neutral' | 'positive';

interface ChipProps {
  readonly children: React.ReactNode;
  readonly tone?: ChipTone;
}

const TONE_CLASSES: Record<ChipTone, string> = {
  critical: 'bg-error-container text-on-error-container dark:bg-error/20 dark:text-error-container',
  high: 'bg-error-container text-on-error-container dark:bg-error/20 dark:text-error-container',
  medium: 'bg-surface-container-high text-on-surface-variant dark:bg-surface-container-high/20 dark:text-surface-variant',
  success: 'bg-success-container text-on-success-container dark:bg-success/20 dark:text-success-container',
  danger: 'bg-error-container text-on-error-container dark:bg-error/20 dark:text-error-container',
  neutral: 'bg-surface-container text-on-surface-variant dark:bg-surface-container-high/30 dark:text-surface-variant',
  // Distinct from `success` (used by risk segment "Self-cure") — a calm secondary-teal
  // tone for the "Can Pay" risk segment, so the two positive-leaning segments don't
  // render visually identical. Judgment call: exact color not specified by design.
  positive: 'bg-secondary-container text-on-secondary-container dark:bg-secondary/20 dark:text-secondary-fixed',
};

export default function Chip({ children, tone = 'neutral' }: ChipProps) {
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-label-md font-medium ${TONE_CLASSES[tone]}`}>
      {children}
    </span>
  );
}
