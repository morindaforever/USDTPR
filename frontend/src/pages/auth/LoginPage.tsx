import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Lock, LogIn } from 'lucide-react';
import { Alert, Button, Card, Input } from '@/components';
import { Logo } from '@/components/Logo';
import { useAuth } from '@/context/AuthContext';
import type { ApiError } from '@/types';

/**
 * Login with email / phone / user ID + password. Generic error messages
 * only; rate-limit responses surface the backend's 429 message.
 */
export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = (location.state as { from?: string } | null)?.from ?? '/home';

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (!identifier.trim() || !password) {
      setError('Enter your credentials to continue.');
      return;
    }
    setIsSubmitting(true);
    try {
      await login(identifier.trim(), password);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message || 'Invalid credentials.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="page-enter mx-auto flex w-full max-w-md flex-col justify-center px-4 py-12 md:py-20">
      <div className="mb-8 flex flex-col items-center text-center">
        <Logo className="h-12 w-12" />
        <h1 className="mt-4 font-display text-2xl font-bold text-surface-900">Welcome back</h1>
        <p className="mt-1 text-sm text-surface-500">Sign in to your NexusUSDT account</p>
      </div>

      <Card>
        <form className="flex flex-col gap-4 p-5" onSubmit={handleSubmit} noValidate>
          {error && <Alert tone="danger">{error}</Alert>}
          <Input
            label="Email, phone, or user ID"
            type="text"
            name="identifier"
            autoComplete="username"
            placeholder="you@example.com"
            leadingIcon={<LogIn className="h-4 w-4" />}
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            required
          />
          <Input
            label="Password"
            type="password"
            name="password"
            autoComplete="current-password"
            placeholder="••••••••"
            leadingIcon={<Lock className="h-4 w-4" />}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <div className="flex justify-end">
            <Link
              to="/forgot-password"
              className="text-xs font-semibold text-brand-700 hover:text-brand-600"
            >
              Forgot password?
            </Link>
          </div>
          <Button type="submit" fullWidth size="lg" isLoading={isSubmitting}>
            Sign in
          </Button>
        </form>
      </Card>

      <p className="mt-6 text-center text-sm text-surface-500">
        New to NexusUSDT?{' '}
        <Link to="/signup" className="font-semibold text-brand-700 hover:text-brand-600">
          Create an account
        </Link>
      </p>
    </div>
  );
}
