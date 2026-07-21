import { useState } from 'react';

export function usePagination(totalPages: number) {
  const [page, setPage] = useState(1);

  const goToPage = (target: number) => {
    setPage(Math.min(Math.max(target, 1), totalPages));
  };

  const nextPage = () => goToPage(page + 1);
  const previousPage = () => goToPage(page - 1);

  return { page, totalPages, goToPage, nextPage, previousPage };
}
