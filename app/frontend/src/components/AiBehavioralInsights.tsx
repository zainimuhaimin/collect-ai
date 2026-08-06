import type { CustomerDetail } from '../domains/customer/customer.schema';
import { formatPercentFromDecimal } from '../lib/format';
import ProgressBar from './ProgressBar';

interface AiBehavioralInsightsProps {
  readonly customer: CustomerDetail;
}

export default function AiBehavioralInsights({ customer }: AiBehavioralInsightsProps) {
  // Backend sends 0-1 fractions for all 4 of these — scale to 0-100 and round to 2
  // decimal places for display, and feed the SAME scaled value into ProgressBar so the
  // bar width matches the displayed number (mirrors the pattern already used correctly
  // in ContractDetailPage.tsx for contract.aiScoring.*).
  const selfCureProbabilityPct = customer.selfCureProbability * 100;
  const rollForwardRiskPct = customer.rollForwardRisk * 100;
  const ptpSuccessProbabilityPct = customer.ptpSuccessProbability * 100;

  return (
    <div className="rounded-xl border border-outline-variant dark:border-outline-variant/30 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-outline-variant dark:border-outline-variant/30 bg-surface-container-lowest dark:bg-surface-container-high/10">
        <p className="text-label-lg font-semibold text-on-surface dark:text-on-background">AI Behavioral Insights</p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-5">
        <div>
          <p className="text-label-md text-on-surface-variant dark:text-surface-variant mb-2">Recovery Score</p>
          <span
            className="w-10 h-10 rounded-full border-2 border-primary-container dark:border-primary-fixed-dim inline-flex items-center justify-center text-label-lg font-bold"
            title={`Recovery score: ${(customer.recoveryScore * 100).toFixed(2)}`}
          >
            {Math.round(customer.recoveryScore * 100)}
          </span>
        </div>
        <div>
          <p className="text-label-md text-on-surface-variant dark:text-surface-variant mb-2">Self-Cure Prob %</p>
          <p className="text-body-md font-semibold text-on-surface dark:text-on-background mb-1">
            {formatPercentFromDecimal(customer.selfCureProbability)}
          </p>
          <ProgressBar
            value={selfCureProbabilityPct}
            tone="primary"
            title={`${selfCureProbabilityPct.toFixed(2)}%`}
          />
        </div>
        <div>
          <p className="text-label-md text-on-surface-variant dark:text-surface-variant mb-2">Roll-Forward Risk %</p>
          <p className="text-body-md font-semibold text-on-surface dark:text-on-background mb-1">
            {formatPercentFromDecimal(customer.rollForwardRisk)}
          </p>
          <ProgressBar
            value={rollForwardRiskPct}
            tone="error"
            title={`${rollForwardRiskPct.toFixed(2)}%`}
          />
        </div>
        <div>
          <p className="text-label-md text-on-surface-variant dark:text-surface-variant mb-2">PTP Success Prob %</p>
          <p className="text-body-md font-semibold text-on-surface dark:text-on-background mb-1">
            {formatPercentFromDecimal(customer.ptpSuccessProbability)}
          </p>
          <ProgressBar
            value={ptpSuccessProbabilityPct}
            tone="primary"
            title={`${ptpSuccessProbabilityPct.toFixed(2)}%`}
          />
        </div>
      </div>
    </div>
  );
}
