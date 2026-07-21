interface AvatarProps {
  readonly initials: string;
  readonly size?: 'sm' | 'md' | 'lg';
}

const SIZE_CLASSES: Record<Required<AvatarProps>['size'], string> = {
  sm: 'w-8 h-8 text-label-md',
  md: 'w-10 h-10 text-label-lg',
  lg: 'w-16 h-16 text-title-lg',
};

export default function Avatar({ initials, size = 'md' }: AvatarProps) {
  return (
    <div
      className={`${SIZE_CLASSES[size]} flex items-center justify-center rounded-full bg-secondary-container text-on-secondary-container dark:bg-secondary/40 dark:text-secondary-fixed font-semibold shrink-0`}
    >
      {initials}
    </div>
  );
}
