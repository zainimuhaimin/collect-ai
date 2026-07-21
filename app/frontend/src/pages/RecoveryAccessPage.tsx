import { Navigate } from 'react-router-dom';

interface RecoveryAccessPageProps {
  readonly className?: string;
}

// Stitch screen 8b2abda2...675a ships pixel-identical markup to the Login screen (ff5c0047...f481),
// so this route redirects to /login instead of rendering a duplicate UI.
export default function RecoveryAccessPage(_props: RecoveryAccessPageProps) {
  return <Navigate to="/login" replace />;
}
