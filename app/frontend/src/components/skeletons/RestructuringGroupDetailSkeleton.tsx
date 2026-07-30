import Skeleton from '../Skeleton';

interface RestructuringGroupDetailSkeletonProps {
  readonly className?: string;
}

export default function RestructuringGroupDetailSkeleton({ className = '' }: RestructuringGroupDetailSkeletonProps) {
  return (
    <div className={`space-y-6 ${className}`}>
      <Skeleton className="h-20 w-full rounded-xl" />
      <Skeleton className="h-56 rounded-xl" />
      <Skeleton className="h-40 rounded-xl" />
    </div>
  );
}
