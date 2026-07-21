import type { WorkbenchAccount } from '../domains/workbench/workbench.schema';
import Chip from './Chip';

interface AccountListItemProps {
  readonly account: WorkbenchAccount;
  readonly isSelected: boolean;
  readonly onSelect: () => void;
}

const PRIORITY_TONE: Record<WorkbenchAccount['priority'], 'critical' | 'high' | 'medium'> = {
  Critical: 'critical',
  High: 'high',
  Medium: 'medium',
};

export default function AccountListItem({ account, isSelected, onSelect }: AccountListItemProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full grid grid-cols-[1fr_auto_auto_auto] items-center gap-4 px-4 py-4 text-left border-b border-outline-variant dark:border-outline-variant/20 ${
        isSelected ? 'bg-surface-container-low dark:bg-surface-container-high/20' : ''
      }`}
    >
      <div className="flex items-center gap-3 min-w-0">
        <span className="w-8 h-8 rounded-full bg-secondary-container text-on-secondary-container flex items-center justify-center text-label-md font-semibold shrink-0">
          {account.initials}
        </span>
        <div className="min-w-0">
          <p className="text-label-lg font-semibold text-on-surface dark:text-on-background truncate">{account.name}</p>
          <p className="text-label-sm text-on-surface-variant dark:text-surface-variant">{account.accountId}</p>
        </div>
      </div>
      <span className="text-body-md font-semibold text-error">{account.dpdDays} Hari</span>
      <span className="text-body-md text-on-surface dark:text-on-background">{account.amount}</span>
      <Chip tone={PRIORITY_TONE[account.priority]}>{account.priority}</Chip>
    </button>
  );
}
