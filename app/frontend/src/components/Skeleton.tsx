interface SkeletonProps {
  readonly className?: string;
}

export default function Skeleton({ className = '' }: SkeletonProps) {
  return <div className={`animate-pulse bg-surface-container-high dark:bg-surface-variant/10 rounded ${className}`} />;
}
