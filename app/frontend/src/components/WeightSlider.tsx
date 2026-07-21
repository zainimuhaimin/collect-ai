import type { WeightParameter } from '../domains/ai-intelligence/aiIntelligence.schema';

interface WeightSliderProps {
  readonly parameter: WeightParameter;
  readonly onChange: (weight: number) => void;
}

export default function WeightSlider({ parameter, onChange }: WeightSliderProps) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-label-lg font-semibold text-on-surface dark:text-on-background">{parameter.label}</span>
        <span className="px-2.5 py-1 rounded-md bg-surface-container-high dark:bg-surface-variant/10 text-label-lg font-semibold">
          {parameter.weight}%
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        value={parameter.weight}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full accent-on-background dark:accent-on-surface"
      />
      <p className="text-label-md text-on-surface-variant dark:text-surface-variant mt-2">{parameter.description}</p>
    </div>
  );
}
