import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Mail } from 'lucide-react';
import { Alert, Button, Card, Input } from '@/components';
import { Logo } from '@/components/Logo';
import { authService } from '@/services/authService';
import type { ApiError } from '@/types';

/**
 * Request a password reset. The backend always responds identically
 * whether or not the email exists — no account enumeration.
 */
export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (!email.trim()) {
      setError('Enter your email address.');
      return;
    }
    setIsSubmitting(true);
    try {
      await authService.forgotPassword(email.trim());
      setSubmitted(true);
    } catch (err) {
      setError((err as ApiError).message || 'Could not send the request. Try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="page-enter mx-auto flex w-full max-w-md flex-col justify-center px-4 py-12 md:py-20">
      <div className="mb-8 flex flex-col items-center text-center">
        <Logo className="h-12 w-12" />
        <h1 className="mt-4 font-display text-2xl font-bold text-surface-900">Forgot password</h1>
        <p className="mt-1 text-sm text-surface-500">
          We'll send reset instructions to your email
        </p>
      </div>

      <Card>
        <div className="p-5">
          {submitted ? (
            <div className="flex flex-col gap-4">
              <Alert tone="success" title="Check your inbox">
                If the account exists, password reset instructions have been sent.
              </Alert>
              <p className="text-xs text-surface-500">
                Development tip: the reset link is printed to the
                Django server console instead of being emailed.
              </p>
              <Link to="/login">
                <Button variant="outline" fullWidth>
                  Back to sign in
                </Button>
              </Link>
            </div>
          ) : (
            <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
              {error && <Alert tone="danger">{error}</Alert>}
              <Input
                label="Email address"
                type="email"
                name="email"
                autoComplete="email"
                placeholder="you@example.com"
                leadingIcon={<Mail className="h-4 w-4" />}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <Button type="submit" fullWidth size="lg" isLoading={isSubmitting}>
                Send reset link
              </Button>
            </form>
          )}
        </div>
      </Card>

      <p className="mt-6 text-center text-sm text-surface-500">
        Remembered it?{' '}
        <Link to="/login" className="font-semibold text-brand-700 hover:text-brand-600">
          Sign in
        </Link>
      </p>
    </div>
  );
}
