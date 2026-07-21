import type { CustomerDetail } from '../domains/customer/customer.schema';
import ProgressBar from './ProgressBar';

interface CustomerSummaryCardsProps {
  readonly customer: CustomerDetail;
}

export default function CustomerSummaryCards({ customer }: CustomerSummaryCardsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="rounded-xl border border-outline-variant dark:border-outline-variant/30 bg-surface-container-lowest dark:bg-surface-container-high/10 p-5">
        <p className="text-label-md uppercase text-on-surface-variant dark:text-surface-variant">Outstanding Balance</p>
        <p className="text-title-lg font-bold text-on-surface dark:text-on-background mt-1">{customer.outstandingBalance}</p>
        <p className="text-label-md text-error mt-1">{customer.balanceChange}</p>
      </div>

      <div className="rounded-xl border border-outline-variant dark:border-outline-variant/30 bg-surface-container-lowest dark:bg-surface-container-high/10 p-5">
        <p className="text-label-md uppercase text-on-surface-variant dark:text-surface-variant">PTP History (Last 12 mo)</p>
        <div className="flex items-end gap-1.5 h-12 mt-3 mb-2">
          {customer.ptpMonths.map((month) => (
            <div
              key={month.month}
              className={`flex-1 rounded-sm ${month.result === 'success' ? 'bg-success h-full' : 'bg-error h-1/3 self-end'}`}
              title={month.month}
            />
          ))}
        </div>
        <div className="flex items-center justify-between text-label-md text-on-surface-variant dark:text-surface-variant">
          <span>
            {customer.ptpHistory.success} Success / {customer.ptpHistory.broken} Broken
          </span>
          <span className="px-2 py-0.5 rounded-md bg-surface-container-high dark:bg-surface-variant/10 font-semibold">
            {customer.ptpHistory.rate} Rate
          </span>
        </div>
      </div>

      <div className="rounded-xl border border-outline-variant dark:border-outline-variant/30 bg-surface-container-lowest dark:bg-surface-container-high/10 p-5">
        <div className="flex items-center justify-between">
          <p className="text-label-md uppercase text-on-surface-variant dark:text-surface-variant">Risk Tier</p>
          <span className="material-symbols-outlined text-error">warning</span>
        </div>
        <p className="text-title-lg font-bold text-error mt-1">
          {customer.riskTier} <span className="text-body-md text-on-surface-variant dark:text-surface-variant">{customer.riskTierLevel}</span>
        </p>
        <ProgressBar value={customer.riskScore} tone="error" trackClassName="mt-3" />
      </div>
    </div>
  );
}
