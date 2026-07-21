interface ErrorStateProps {
  readonly message?: string;
  readonly onRetry?: () => void;
}

export default function ErrorState({ message = 'Something went wrong while loading data.', onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <span className="material-symbols-outlined text-4xl text-error">error</span>
      <p className="text-body-md text-on-surface-variant dark:text-surface-variant">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="px-5 py-2.5 rounded-lg bg-primary-container text-on-primary text-label-lg font-semibold"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}
