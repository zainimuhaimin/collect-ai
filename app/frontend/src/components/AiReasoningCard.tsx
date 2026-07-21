interface AiReasoningCardProps {
  readonly reasoning: string;
  readonly recommendations: string[];
}

export default function AiReasoningCard({ reasoning, recommendations }: AiReasoningCardProps) {
  return (
    <div className="rounded-xl border border-outline-variant dark:border-outline-variant/30 bg-surface-container-lowest dark:bg-surface-container-high/10 p-5">
      <p className="text-body-md italic text-on-surface-variant dark:text-surface-variant">&ldquo;{reasoning}&rdquo;</p>
      <div className="border-t border-outline-variant dark:border-outline-variant/20 mt-4 pt-4">
        <p className="text-label-lg font-semibold text-on-surface dark:text-on-background mb-2">Rekomendasi Strategi:</p>
        <ul className="space-y-1.5 list-disc list-inside text-body-md text-on-surface-variant dark:text-surface-variant">
          {recommendations.map((recommendation) => (
            <li key={recommendation}>{recommendation}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
