import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Lock } from 'lucide-react';
import { Alert, Button, Card, Input } from '@/components';
import { PageContainer } from '@/components/PageContainer';
import { authService } from '@/services/authService';
import type { ApiError } from '@/types';

/** Authenticated password change (Account → Security). */
export function ChangePasswordPage() {
  const [currentPassword, setCurrentPassword] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    if (password !== passwordConfirm) {
      setError('Passwords do not match.');
      return;
    }
    setIsSubmitting(true);
    try {
      const envelope = await authService.changePassword(currentPassword, password, passwordConfirm);
      setSuccess(envelope.message || 'Password updated successfully.');
      setCurrentPassword('');
      setPassword('');
      setPasswordConfirm('');
    } catch (err) {
      setError((err as ApiError).message || 'Could not update the password.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <PageContainer
      title="Change password"
      subtitle="Use a strong password you don't reuse elsewhere."
    >
      <div className="max-w-md space-y-4">
        {success && <Alert tone="success">{success}</Alert>}
        {error && <Alert tone="danger">{error}</Alert>}

        <Card>
          <form className="flex flex-col gap-4 p-5" onSubmit={handleSubmit} noValidate>
            <Input
              label="Current password"
              type="password"
              name="current_password"
              autoComplete="current-password"
              leadingIcon={<Lock className="h-4 w-4" />}
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
            />
            <Input
              label="New password"
              type="password"
              name="password"
              autoComplete="new-password"
              hint="8+ characters with letters and numbers."
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
              leadingIcon={<Lock className="h-4 w-4" />}
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              required
            />
            <Button type="submit" isLoading={isSubmitting}>
              Update password
            </Button>
          </form>
        </Card>

        <p className="text-center text-sm text-surface-500">
          <Link to="/account" className="font-semibold text-brand-400 hover:text-brand-300">
            ← Back to account
          </Link>
        </p>
      </div>
    </PageContainer>
  );
}
