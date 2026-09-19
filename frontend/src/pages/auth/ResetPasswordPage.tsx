import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Lock } from 'lucide-react';
import { Alert, Button, Card, Input } from '@/components';
import { Logo } from '@/components/Logo';
import { authService } from '@/services/authService';
import type { ApiError } from '@/types';

/** Reset password with a token from /reset-password/:token. */
export function ResetPasswordPage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();

  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (password !== passwordConfirm) {
      setError('Passwords do not match.');
      return;
    }
    setIsSubmitting(true);
    try {
      await authService.resetPassword(token ?? '', password, passwordConfirm);
      setSuccess(true);
      setTimeout(() => navigate('/login', { replace: true }), 2000);
    } catch (err) {
      setError((err as ApiError).message || 'Could not reset the password.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="page-enter mx-auto flex w-full max-w-md flex-col justify-center px-4 py-12 md:py-20">
      <div className="mb-8 flex flex-col items-center text-center">
        <Logo className="h-12 w-12" />
        <h1 className="mt-4 font-display text-2xl font-bold text-surface-900">
          Choose a new password
        </h1>
        <p className="mt-1 text-sm text-surface-500">
          Your reset link is valid for one hour and single-use
        </p>
      </div>

      <Card>
        <div className="p-5">
          {success ? (
            <div className="flex flex-col gap-4">
              <Alert tone="success" title="Password updated">
                Your password has been reset. Redirecting you to sign in…
              </Alert>
              <Link to="/login">
                <Button fullWidth>Go to sign in</Button>
              </Link>
            </div>
          ) : (
            <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
              {error && <Alert tone="danger">{error}</Alert>}
              <Input
                label="New password"
                type="password"
                name="password"
                autoComplete="new-password"
                placeholder="At least 8 characters"
                leadingIcon={<Lock className="h-4 w-4" />}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <Input
                label="Confirm new password"
                type="password"
                name="password_confirm"
                autoComplete="new-password"
                placeholder="Repeat your new password"
                leadingIcon={<Lock className="h-4 w-4" />}
                value={passwordConfirm}
                onChange={(e) => setPasswordConfirm(e.target.value)}
                required
              />
              <Button type="submit" fullWidth size="lg" isLoading={isSubmitting}>
                Reset password
              </Button>
            </form>
          )}
        </div>
      </Card>
    </div>
  );
}
