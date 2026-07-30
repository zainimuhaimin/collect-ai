import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { CustomerContractSummary } from '../domains/customer/customer.schema';
import { useContractActivityLogQuery } from '../domains/contract/useContractActivityLogQuery';
import { RISK_SEGMENT_TONE } from '../domains/shared/riskSegment';
import Chip from './Chip';
import ActivityTimeline from './ActivityTimeline';

interface CustomerContractsListProps {
  readonly contracts: CustomerContractSummary[];
}

function ContractActivityLog({ contractNo, enabled }: { readonly contractNo: string; readonly enabled: boolean }) {
  const activityLogQuery = useContractActivityLogQuery(contractNo, { enabled });

  if (activityLogQuery.isLoading) {
    return <p className="text-body-md text-on-surface-variant dark:text-surface-variant py-4">Memuat log aktivitas...</p>;
  }
  if (activityLogQuery.isError || !activityLogQuery.data) {
    return <p className="text-body-md text-error py-4">Gagal memuat log aktivitas kontrak ini.</p>;
  }
  return (
    <div className="pt-4">
      <p className="text-label-md font-semibold text-on-surface dark:text-on-background mb-3">Log Aktivitas Kontrak Ini</p>
      <ActivityTimeline items={activityLogQuery.data} />
    </div>
  );
}

export default function CustomerContractsList({ contracts }: CustomerContractsListProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (contractNo: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(contractNo)) {
        next.delete(contractNo);
      } else {
        next.add(contractNo);
      }
      return next;
    });
  };

  if (contracts.length === 0) {
    return <p className="text-body-md text-on-surface-variant dark:text-surface-variant">Belum ada kontrak untuk customer ini.</p>;
  }

  return (
    <div className="divide-y divide-outline-variant dark:divide-outline-variant/30">
      {contracts.map((contract) => {
        const isExpanded = expanded.has(contract.contractNo);
        return (
          <div key={contract.contractNo} className="py-4">
            <button
              type="button"
              onClick={() => toggle(contract.contractNo)}
              className="w-full flex items-center gap-3 text-left"
            >
              <span className="material-symbols-outlined text-on-surface-variant dark:text-surface-variant">
                {isExpanded ? 'expand_more' : 'chevron_right'}
              </span>
              <span className="text-label-lg font-semibold text-on-surface dark:text-on-background w-36 shrink-0">
                {contract.contractNo}
              </span>
              <span className="text-body-md text-on-surface-variant dark:text-surface-variant w-32 shrink-0">
                {contract.productType}
              </span>
              <span className="text-body-md text-on-surface dark:text-on-background w-20 shrink-0">DPD {contract.dpdCurrent}</span>
              <span className="text-body-md text-on-surface dark:text-on-background w-36 shrink-0">{contract.outstanding}</span>
              {contract.riskSegment ? (
                <Chip tone={RISK_SEGMENT_TONE[contract.riskSegment]}>{contract.riskSegment}</Chip>
              ) : (
                <Chip tone="neutral">Belum discoring</Chip>
              )}
            </button>
            <div className="flex justify-end mt-2">
              <Link
                to={`/contracts/${contract.contractNo}`}
                className="text-label-lg font-semibold text-primary-container dark:text-primary-fixed-dim hover:underline"
              >
                Lihat Detail Kontrak →
              </Link>
            </div>
            {isExpanded ? <ContractActivityLog contractNo={contract.contractNo} enabled={isExpanded} /> : null}
          </div>
        );
      })}
    </div>
  );
}
