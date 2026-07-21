import Skeleton from '../Skeleton';

interface CustomerDetailSkeletonProps {
  readonly className?: string;
}

export default function CustomerDetailSkeleton({ className = '' }: CustomerDetailSkeletonProps) {
  return (
    <div className={`space-y-6 ${className}`}>
      <Skeleton className="h-24 w-full rounded-xl" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Skeleton className="h-32 rounded-xl" />
        <Skeleton className="h-32 rounded-xl" />
        <Skeleton className="h-32 rounded-xl" />
      </div>
      <Skeleton className="h-40 rounded-xl" />
      <Skeleton className="h-24 rounded-xl" />
      <Skeleton className="h-64 rounded-xl" />
    </div>
  );
}
