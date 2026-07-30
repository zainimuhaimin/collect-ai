interface PaginationProps {
  readonly page: number;
  readonly totalPages: number;
  readonly onNext: () => void;
  readonly onPrevious: () => void;
  readonly onGoToPage: (page: number) => void;
}

// Fixed-length layout: "1 ... [w] [w+1] [w+2] ... n" — ALWAYS exactly 5 number
// slots + 2 ellipses once totalPages > 5, no matter which page is current, so
// the control never grows/shrinks width as the user pages through it (the
// previous "keep nearby + dedupe" version rendered anywhere from ~5 to ~9
// cells depending on how close `current` was to the edges).
//
// The 3-wide middle window is clamped to [2, total-1] so it can never
// literally repeat the fixed first/last slot — near the edges this means the
// window sits right next to "1"/"n" with an ellipsis that doesn't hide any
// page (e.g. "1 ... 2 3 4 ... 242"). That's a deliberate trade-off: constant
// width over a technically-redundant ellipsis in the boundary case.
function getMiddleWindow(current: number, total: number): number[] {
  const start = Math.min(Math.max(current - 1, 2), total - 3);
  return [start, start + 1, start + 2];
}

const CELL_CLASS =
  'w-8 h-8 flex items-center justify-center rounded-lg border border-outline-variant dark:border-outline-variant/30 text-on-surface-variant dark:text-surface-variant disabled:opacity-40';

function PageButton({ page, current, onClick }: { readonly page: number; readonly current: number; readonly onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={page === current ? 'page' : undefined}
      className={`w-8 h-8 flex items-center justify-center rounded-lg text-label-lg ${
        page === current
          ? 'bg-primary-container text-on-primary'
          : 'border border-outline-variant dark:border-outline-variant/30 text-on-surface dark:text-on-background'
      }`}
    >
      {page}
    </button>
  );
}

function Ellipsis() {
  return (
    <span className="w-8 h-8 flex items-center justify-center text-on-surface-variant dark:text-surface-variant">…</span>
  );
}

export default function Pagination({ page, totalPages, onNext, onPrevious, onGoToPage }: PaginationProps) {
  return (
    <div className="flex items-center gap-2">
      <button type="button" aria-label="Previous page" onClick={onPrevious} disabled={page === 1} className={CELL_CLASS}>
        <span className="material-symbols-outlined text-lg">chevron_left</span>
      </button>

      {totalPages <= 5 ? (
        Array.from({ length: totalPages }, (_, i) => i + 1).map((n) => (
          <PageButton key={n} page={n} current={page} onClick={() => onGoToPage(n)} />
        ))
      ) : (
        <>
          <PageButton page={1} current={page} onClick={() => onGoToPage(1)} />
          <Ellipsis />
          {getMiddleWindow(page, totalPages).map((n) => (
            <PageButton key={n} page={n} current={page} onClick={() => onGoToPage(n)} />
          ))}
          <Ellipsis />
          <PageButton page={totalPages} current={page} onClick={() => onGoToPage(totalPages)} />
        </>
      )}

      <button type="button" aria-label="Next page" onClick={onNext} disabled={page === totalPages} className={CELL_CLASS}>
        <span className="material-symbols-outlined text-lg">chevron_right</span>
      </button>
    </div>
  );
}
