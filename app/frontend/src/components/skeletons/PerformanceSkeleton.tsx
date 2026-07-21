import Skeleton from '../Skeleton';

interface PerformanceSkeletonProps {
  readonly className?: string;
}

export default function PerformanceSkeleton({ className = '' }: PerformanceSkeletonProps) {
  return (
    <div className={`space-y-6 ${className}`}>
      <Skeleton className="h-24 w-full rounded-xl" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Skeleton className="h-28 rounded-xl" />
        <Skeleton className="h-28 rounded-xl" />
        <Skeleton className="h-28 rounded-xl" />
      </div>
      <Skeleton className="h-96 rounded-xl" />
      <Skeleton className="h-40 rounded-xl" />
    </div>
  );
}
