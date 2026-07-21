import { recoveryAccessStats, recoveryAccessCopy } from '../config/staticContent';

interface BrandShowcasePanelProps {
  readonly className?: string;
}

export default function BrandShowcasePanel({ className = '' }: BrandShowcasePanelProps) {
  return (
    <section
      className={`hidden md:flex md:w-1/2 lg:w-3/5 bg-primary-container relative overflow-hidden items-center justify-center p-margin-desktop ${className}`}
    >
      <div
        className="absolute inset-0 opacity-20 pointer-events-none"
        style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, #768dad 1px, transparent 0)', backgroundSize: '40px 40px' }}
      />
      <div className="absolute top-0 right-0 w-96 h-96 bg-primary rounded-full filter blur-[120px] opacity-30 -mr-48 -mt-48" />
      <div className="absolute bottom-0 left-0 w-64 h-64 bg-tertiary-container rounded-full filter blur-[100px] opacity-20 -ml-32 -mb-32" />

      <div className="relative z-10 max-w-xl">
        <div className="flex items-center gap-4 mb-8">
          <div className="w-16 h-16 bg-on-primary rounded-xl flex items-center justify-center shadow-lg">
            <span className="material-symbols-outlined text-primary-container text-4xl" style={{ fontVariationSettings: "'FILL' 1" }}>
              account_balance
            </span>
          </div>
          <div>
            <h1 className="text-title-lg font-bold text-on-primary leading-none tracking-tight">CollectAI</h1>
            <p className="text-label-lg text-on-primary-container mt-1">Enterprise Recovery</p>
          </div>
        </div>

        <h2 className="text-headline-lg text-white mb-6 leading-tight">{recoveryAccessCopy.title}</h2>
        <p className="text-body-lg text-on-primary-container mb-12 max-w-lg">{recoveryAccessCopy.description}</p>

        <div className="grid grid-cols-2 gap-8 border-t border-on-primary-container/20 pt-8">
          {recoveryAccessStats.map((stat) => (
            <div key={stat.label}>
              <p className="text-headline-sm text-white">{stat.value}</p>
              <p className="text-label-md text-on-primary-container uppercase tracking-wider mt-1">{stat.label}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
