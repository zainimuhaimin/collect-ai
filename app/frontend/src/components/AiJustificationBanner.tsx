interface AiJustificationBannerProps {
  readonly justification: string;
}

export default function AiJustificationBanner({ justification }: AiJustificationBannerProps) {
  return (
    <div className="rounded-xl bg-primary-container text-on-primary p-6">
      <p className="flex items-center gap-2 text-label-lg font-semibold mb-3">
        <span className="material-symbols-outlined text-lg">auto_awesome</span>
        Justifikasi Strategi AI
      </p>
      <p className="text-body-md text-on-primary-container leading-relaxed">{justification}</p>
    </div>
  );
}
