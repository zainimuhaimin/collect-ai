import type { CustomerDetail } from '../domains/customer/customer.schema';
import { RISK_SEGMENT_TONE } from '../domains/shared/riskSegment';
import Chip from './Chip';
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
        <p className="text-label-md text-on-surface-variant dark:text-surface-variant mt-1">
          Across {customer.activeContractCount} active contract{customer.activeContractCount === 1 ? '' : 's'}
        </p>
      </div>

      <div className="rounded-xl border border-outline-variant dark:border-outline-variant/30 bg-surface-container-lowest dark:bg-surface-container-high/10 p-5">
        <p className="text-label-md uppercase text-on-surface-variant dark:text-surface-variant">Behavioral Standing (CBS)</p>
        <div className="flex items-center gap-3 mt-2">
          <span className="w-10 h-10 rounded-full border-2 border-primary-container dark:border-primary-fixed-dim flex items-center justify-center text-title-md font-bold text-on-surface dark:text-on-background">
            {customer.behavioralGrade}
          </span>
          <div>
            <p className="text-body-md text-on-surface dark:text-on-background">
              Direstrukturisasi {customer.restructureCount}x
            </p>
            {customer.bListStatus === 'Y' ? (
              <Chip tone="medium">B-List</Chip>
            ) : (
              <span className="text-label-md text-on-surface-variant dark:text-surface-variant">Not on B-List</span>
            )}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-outline-variant dark:border-outline-variant/30 bg-surface-container-lowest dark:bg-surface-container-high/10 p-5">
        <div className="flex items-center justify-between">
          <p className="text-label-md uppercase text-on-surface-variant dark:text-surface-variant">Risk Segment</p>
          <span className="material-symbols-outlined text-error">warning</span>
        </div>
        <p className="mt-1">
          {customer.riskSegment ? (
            <Chip tone={RISK_SEGMENT_TONE[customer.riskSegment]}>{customer.riskSegment}</Chip>
          ) : (
            <Chip tone="neutral">Belum discoring</Chip>
          )}
        </p>
        <ProgressBar
          value={customer.riskScore}
          tone="error"
          trackClassName="mt-3"
          title={`Risk score: ${customer.riskScore}`}
        />
        <p className="text-label-sm text-on-surface-variant dark:text-surface-variant mt-1">Risk score: {customer.riskScore}</p>
      </div>
    </div>
  );
}
