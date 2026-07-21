interface FilterSelectRowProps {
  readonly filters: Array<{ label: string; options: string[] }>;
  readonly dateRangeLabel: string;
}

export default function FilterSelectRow({ filters, dateRangeLabel }: FilterSelectRowProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 bg-surface-container-lowest dark:bg-surface-container-high/20 border border-outline-variant dark:border-outline-variant/30 rounded-xl p-5">
      {filters.map((filter) => (
        <label key={filter.label} className="flex flex-col gap-1.5">
          <span className="text-label-md text-on-surface-variant dark:text-surface-variant">{filter.label}</span>
          <select className="bg-transparent border border-outline-variant dark:border-outline-variant/30 rounded-lg px-3 py-2 text-body-md text-on-surface dark:text-on-background focus:outline-none">
            {filter.options.map((option) => (
              <option key={option}>{option}</option>
            ))}
          </select>
        </label>
      ))}
      <label className="flex flex-col gap-1.5">
        <span className="text-label-md text-on-surface-variant dark:text-surface-variant">Date Range</span>
        <span className="flex items-center gap-2 border border-outline-variant dark:border-outline-variant/30 rounded-lg px-3 py-2 text-body-md text-on-surface dark:text-on-background">
          <span className="material-symbols-outlined text-lg text-outline">calendar_today</span>
          {dateRangeLabel}
        </span>
      </label>
    </div>
  );
}
