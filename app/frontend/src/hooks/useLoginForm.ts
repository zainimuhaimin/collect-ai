import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLoginMutation } from '../domains/auth/useLoginMutation';

export function useLoginForm(onSuccess?: () => void) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();
  const loginMutation = useLoginMutation();

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    loginMutation.mutate(
      { username, password },
      {
        onSuccess: () => {
          onSuccess?.();
          navigate('/dashboard');
        },
      },
    );
  };

  return {
    username,
    setUsername,
    password,
    setPassword,
    isAuthenticating: loginMutation.isPending,
    error: loginMutation.error,
    handleSubmit,
  };
}
