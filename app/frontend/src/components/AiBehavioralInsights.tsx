import type { CustomerDetail } from '../domains/customer/customer.schema';
import ProgressBar from './ProgressBar';

interface AiBehavioralInsightsProps {
  readonly customer: CustomerDetail;
}

export default function AiBehavioralInsights({ customer }: AiBehavioralInsightsProps) {
  return (
    <div className="rounded-xl border border-outline-variant dark:border-outline-variant/30 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-outline-variant dark:border-outline-variant/30 bg-surface-container-lowest dark:bg-surface-container-high/10">
        <p className="text-label-lg font-semibold text-on-surface dark:text-on-background">AI Behavioral Insights</p>
        <p className="text-label-sm text-on-surface-variant dark:text-surface-variant">Last updated: Today, 08:30 AM</p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-5">
        <div>
          <p className="text-label-md text-on-surface-variant dark:text-surface-variant mb-2">Recovery Score</p>
          <div className="flex items-center gap-2">
            <span className="w-10 h-10 rounded-full border-2 border-primary-container dark:border-primary-fixed-dim flex items-center justify-center text-label-lg font-bold">
              {customer.recoveryScore}
            </span>
            <span className="text-body-md text-on-surface dark:text-on-background">{customer.recoveryLabel}</span>
          </div>
        </div>
        <div>
          <p className="text-label-md text-on-surface-variant dark:text-surface-variant mb-2">Self-Cure Prob %</p>
          <p className="text-body-md font-semibold text-on-surface dark:text-on-background mb-1">{customer.selfCureProbability}</p>
          <ProgressBar value={parseFloat(customer.selfCureProbability)} tone="primary" />
        </div>
        <div>
          <p className="text-label-md text-on-surface-variant dark:text-surface-variant mb-2">PTP Success Prob %</p>
          <p className="text-body-md font-semibold text-on-surface dark:text-on-background mb-1">{customer.ptpSuccessProbability}</p>
          <ProgressBar value={parseFloat(customer.ptpSuccessProbability)} tone="primary" />
        </div>
        <div>
          <p className="text-label-md text-on-surface-variant dark:text-surface-variant mb-2">Target NBA Action</p>
          <button
            type="button"
            className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg bg-primary-container text-on-primary text-label-lg font-semibold"
          >
            <span className="material-symbols-outlined text-lg">bolt</span>
            {customer.targetNbaAction}
          </button>
        </div>
      </div>
    </div>
  );
}
