import { useEffect, type ReactNode } from 'react';

interface ModalProps {
  readonly title: string;
  readonly onClose: () => void;
  readonly children: ReactNode;
}

// Small, generic modal shell — no existing modal component in this codebase yet.
// Closes on Escape or backdrop click, matching the same interaction convention as the
// TopBar's dropdown disclosure.
export default function Modal({ title, onClose, children }: ModalProps) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-inverse-surface/40 px-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-sm rounded-xl border border-outline-variant dark:border-outline-variant/30 bg-surface-container-lowest dark:bg-surface-container-high/20 shadow-lg"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-outline-variant dark:border-outline-variant/30">
          <p className="text-label-lg font-semibold text-on-surface dark:text-on-background">{title}</p>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-on-surface-variant dark:text-surface-variant"
          >
            <span className="material-symbols-outlined text-xl">close</span>
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}
