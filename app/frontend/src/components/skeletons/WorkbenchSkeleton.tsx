import Skeleton from '../Skeleton';

interface WorkbenchSkeletonProps {
  readonly className?: string;
}

export default function WorkbenchSkeleton({ className = '' }: WorkbenchSkeletonProps) {
  return (
    <div className={`grid grid-cols-1 lg:grid-cols-[1fr_420px] gap-6 ${className}`}>
      <Skeleton className="h-[480px] rounded-xl" />
      <div className="space-y-4">
        <Skeleton className="h-32 rounded-xl" />
        <Skeleton className="h-48 rounded-xl" />
        <Skeleton className="h-24 rounded-xl" />
        <Skeleton className="h-40 rounded-xl" />
      </div>
    </div>
  );
}
