import Skeleton from '../Skeleton';

interface AiIntelligenceSkeletonProps {
  readonly className?: string;
}

export default function AiIntelligenceSkeleton({ className = '' }: AiIntelligenceSkeletonProps) {
  return (
    <div className={`space-y-6 ${className}`}>
      <Skeleton className="h-16 w-full rounded-xl" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Skeleton className="lg:col-span-2 h-80 rounded-xl" />
        <Skeleton className="h-80 rounded-xl" />
      </div>
      <Skeleton className="h-56 rounded-xl" />
      <Skeleton className="h-48 rounded-xl" />
    </div>
  );
}
