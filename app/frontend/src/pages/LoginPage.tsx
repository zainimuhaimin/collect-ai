import BrandShowcasePanel from '../components/BrandShowcasePanel';
import LoginForm from '../components/LoginForm';

interface LoginPageProps {
  readonly className?: string;
}

export default function LoginPage({ className = '' }: LoginPageProps) {
  return (
    <main className={`flex flex-col md:flex-row w-full min-h-screen bg-background ${className}`}>
      <BrandShowcasePanel />
      <LoginForm />
    </main>
  );
}
