interface PaginationProps {
  readonly page: number;
  readonly totalPages: number;
  readonly onNext: () => void;
  readonly onPrevious: () => void;
  readonly onGoToPage: (page: number) => void;
}

export default function Pagination({ page, totalPages, onNext, onPrevious, onGoToPage }: PaginationProps) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        aria-label="Previous page"
        onClick={onPrevious}
        disabled={page === 1}
        className="w-8 h-8 flex items-center justify-center rounded-lg border border-outline-variant dark:border-outline-variant/30 text-on-surface-variant dark:text-surface-variant disabled:opacity-40"
      >
        <span className="material-symbols-outlined text-lg">chevron_left</span>
      </button>
      {Array.from({ length: totalPages }, (_, index) => index + 1).map((pageNumber) => (
        <button
          key={pageNumber}
          type="button"
          onClick={() => onGoToPage(pageNumber)}
          className={`w-8 h-8 flex items-center justify-center rounded-lg text-label-lg ${
            pageNumber === page
              ? 'bg-primary-container text-on-primary'
              : 'border border-outline-variant dark:border-outline-variant/30 text-on-surface dark:text-on-background'
          }`}
        >
          {pageNumber}
        </button>
      ))}
      <button
        type="button"
        aria-label="Next page"
        onClick={onNext}
        disabled={page === totalPages}
        className="w-8 h-8 flex items-center justify-center rounded-lg border border-outline-variant dark:border-outline-variant/30 text-on-surface-variant dark:text-surface-variant disabled:opacity-40"
      >
        <span className="material-symbols-outlined text-lg">chevron_right</span>
      </button>
    </div>
  );
}
