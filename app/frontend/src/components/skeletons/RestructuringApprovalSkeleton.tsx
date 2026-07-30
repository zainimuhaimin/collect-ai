import Skeleton from '../Skeleton';

interface RestructuringApprovalSkeletonProps {
  readonly className?: string;
}

export default function RestructuringApprovalSkeleton({ className = '' }: RestructuringApprovalSkeletonProps) {
  return (
    <div className={`space-y-6 ${className}`}>
      <Skeleton className="h-10 w-64 rounded-lg" />
      <Skeleton className="h-96 rounded-xl" />
    </div>
  );
}
