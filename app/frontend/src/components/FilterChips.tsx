interface FilterChipsProps {
  readonly options: string[];
  readonly activeOption: string;
  readonly onSelect: (option: string) => void;
}

export default function FilterChips({ options, activeOption, onSelect }: FilterChipsProps) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      {options.map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => onSelect(option)}
          className={`px-3.5 py-1.5 rounded-full text-label-lg transition-colors ${
            option === activeOption
              ? 'bg-primary-container text-on-primary'
              : 'bg-surface-container dark:bg-surface-container-high/30 text-on-surface-variant dark:text-surface-variant'
          }`}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
