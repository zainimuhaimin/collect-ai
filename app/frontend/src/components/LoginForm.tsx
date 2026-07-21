import { complianceBadges } from '../config/staticContent';
import { toDisplayMessage } from '../api/apiError';
import { useLoginForm } from '../hooks/useLoginForm';
import { usePasswordToggle } from '../hooks/usePasswordToggle';

interface LoginFormProps {
  readonly onAuthenticated?: () => void;
}

export default function LoginForm({ onAuthenticated }: LoginFormProps) {
  const { username, setUsername, password, setPassword, isAuthenticating, error, handleSubmit } = useLoginForm(onAuthenticated);
  const { inputType, toggle } = usePasswordToggle();

  return (
    <section className="flex-1 bg-surface flex items-center justify-center p-gutter-mobile md:p-margin-desktop">
      <div className="w-full max-w-md">
        <div className="md:hidden flex items-center gap-3 mb-12">
          <div className="w-10 h-10 bg-primary-container rounded-lg flex items-center justify-center">
            <span className="material-symbols-outlined text-white text-2xl" style={{ fontVariationSettings: "'FILL' 1" }}>
              account_balance
            </span>
          </div>
          <span className="text-title-lg font-bold text-primary">CollectAI</span>
        </div>

        <div className="mb-10">
          <h3 className="text-headline-lg text-on-surface mb-2">Secure Access</h3>
          <p className="text-body-md text-on-surface-variant">
            Enter your enterprise credentials to access the recovery dashboard.
          </p>
        </div>

        <form className="space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-2">
            <label className="text-label-lg text-on-surface-variant ml-1" htmlFor="username">
              Username or Employee ID
            </label>
            <div className="relative">
              <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-outline">person</span>
              <input
                id="username"
                type="text"
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="e.g. j.doe@collectai.com"
                className="w-full pl-12 pr-4 py-3.5 bg-surface-container-lowest border border-outline-variant rounded-lg text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between items-center px-1">
              <label className="text-label-lg text-on-surface-variant" htmlFor="password">
                Password
              </label>
              <a className="text-label-md text-primary-container hover:underline" href="#/forgot-password">
                Forgot?
              </a>
            </div>
            <div className="relative">
              <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-outline">lock</span>
              <input
                id="password"
                type={inputType}
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••••••"
                className="w-full pl-12 pr-12 py-3.5 bg-surface-container-lowest border border-outline-variant rounded-lg text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
              />
              <button
                type="button"
                onClick={toggle}
                aria-label="Toggle password visibility"
                className="absolute right-4 top-1/2 -translate-y-1/2 text-outline hover:text-on-surface transition-colors"
              >
                <span className="material-symbols-outlined">{inputType === 'password' ? 'visibility' : 'visibility_off'}</span>
              </button>
            </div>
          </div>

          <div className="flex items-center gap-3 px-1">
            <input id="remember" type="checkbox" className="w-4 h-4 rounded border-outline-variant text-primary focus:ring-primary" />
            <label className="text-label-md text-on-surface-variant" htmlFor="remember">
              Remember this workstation
            </label>
          </div>

          {error ? <p className="text-label-md text-error px-1">{toDisplayMessage(error)}</p> : null}

          <button
            type="submit"
            disabled={isAuthenticating}
            className="w-full bg-primary-container text-on-primary text-label-lg py-4 rounded-lg flex items-center justify-center gap-2 hover:bg-primary active:scale-[0.98] transition-all shadow-md mt-8 disabled:opacity-90"
          >
            <span>{isAuthenticating ? 'Authenticating...' : 'Sign In'}</span>
            {!isAuthenticating ? <span className="material-symbols-outlined">arrow_forward</span> : null}
          </button>
        </form>

        <div className="mt-12 pt-8 border-t border-outline-variant/30 text-center">
          <p className="text-label-md text-on-surface-variant mb-4">Authorized Personnel Only</p>
          <div className="flex items-center justify-center gap-6">
            {complianceBadges.map((badge) => (
              <div key={badge} className="flex items-center gap-1.5 grayscale opacity-50">
                <span className="material-symbols-outlined text-sm">{badge.includes('ISO') ? 'verified_user' : 'security'}</span>
                <span className="text-[10px] font-bold uppercase tracking-widest">{badge}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
