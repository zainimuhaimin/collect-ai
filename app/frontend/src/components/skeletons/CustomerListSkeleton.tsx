import Skeleton from '../Skeleton';

interface CustomerListSkeletonProps {
  readonly className?: string;
}

export default function CustomerListSkeleton({ className = '' }: CustomerListSkeletonProps) {
  return (
    <div className={`space-y-6 ${className}`}>
      <Skeleton className="h-10 w-full rounded-lg" />
      <Skeleton className="h-10 w-2/3 rounded-lg" />
      <Skeleton className="h-96 rounded-xl" />
      <Skeleton className="h-10 w-48 rounded-lg" />
    </div>
  );
}
