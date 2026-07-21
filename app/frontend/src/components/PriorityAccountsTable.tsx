import { Link } from 'react-router-dom';
import type { PriorityAccount } from '../domains/dashboard/dashboard.schema';
import Avatar from './Avatar';
import Chip from './Chip';

interface PriorityAccountsTableProps {
  readonly accounts: PriorityAccount[];
}

export default function PriorityAccountsTable({ accounts }: PriorityAccountsTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="text-label-md uppercase text-on-surface-variant dark:text-surface-variant border-b border-outline-variant dark:border-outline-variant/30">
            <th className="py-3 pr-4">Customer ID</th>
            <th className="py-3 pr-4">Name</th>
            <th className="py-3 pr-4">Amount (RP)</th>
            <th className="py-3 pr-4">AMBC Value</th>
            <th className="py-3 pr-4">Last Action</th>
            <th className="py-3 pr-4">Actions</th>
          </tr>
        </thead>
        <tbody>
          {accounts.map((account) => (
            <tr key={account.customerId} className="border-b border-outline-variant dark:border-outline-variant/20">
              <td className="py-4 pr-4 text-body-md text-on-surface dark:text-on-background">{account.customerId}</td>
              <td className="py-4 pr-4">
                <div className="flex items-center gap-2">
                  <Avatar initials={account.initials} size="sm" />
                  <span className="text-label-lg font-semibold text-on-surface dark:text-on-background">{account.name}</span>
                </div>
              </td>
              <td className="py-4 pr-4 text-body-md text-on-surface dark:text-on-background">{account.amount}</td>
              <td className="py-4 pr-4">
                <Chip tone={account.ambcTier.toLowerCase() as 'high'}>
                  <span className="material-symbols-outlined text-xs">warning</span>
                  {account.ambcValue} {account.ambcTier}
                </Chip>
              </td>
              <td className="py-4 pr-4">
                <p className="text-body-md text-on-surface dark:text-on-background">{account.lastAction}</p>
                <p className="text-label-sm text-on-surface-variant dark:text-surface-variant">{account.lastActionDate}</p>
              </td>
              <td className="py-4 pr-4">
                <Link
                  to={`/customers/${account.customerId.replace('#CA-', 'C-')}`}
                  className="text-label-lg font-semibold text-primary-container dark:text-primary-fixed-dim hover:underline"
                >
                  Review
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
