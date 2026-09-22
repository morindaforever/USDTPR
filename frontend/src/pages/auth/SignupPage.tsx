import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Lock, Mail, Phone, User } from 'lucide-react';
import { Alert, Button, Card, Input } from '@/components';
import { Logo } from '@/components/Logo';
import { useAuth } from '@/context/AuthContext';
import type { ApiError } from '@/types';

interface FieldErrors {
  full_name?: string;
  email?: string;
  phone?: string;
  password?: string;
  password_confirm?: string;
  referral_code?: string;
}

const PHONE_PATTERN = /^\+?[0-9]{7,15}$/;

/** Password strength: 8+ chars with letters and digits (mirrors backend). */
function passwordProblem(password: string): string | null {
  if (password.length < 8) return 'Password must be at least 8 characters.';
  if (!/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) {
    return 'Password must contain both letters and numbers.';
  }
  return null;
}

/** Signup with full client-side validation mirroring the backend rules. */
export function SignupPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    phone: '',
    password: '',
    password_confirm: '',
    referral_code: '',
  });
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Section 9 §5: /signup?ref=CODE prefills the referral code from the
  // shareable link. The backend still validates the code on registration.
  useEffect(() => {
    const ref = searchParams.get('ref');
    if (ref) {
      setForm((prev) => ({ ...prev, referral_code: ref.toUpperCase() }));
    }
  }, [searchParams]);

  const set = (field: keyof typeof form) => (value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setFieldErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  const validate = (): boolean => {
    const errors: FieldErrors = {};
    if (!form.full_name.trim()) errors.full_name = 'Full name cannot be empty.';
    if (!form.email.trim()) errors.email = 'Email is required.';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
      errors.email = 'Enter a valid email address.';
    }
    if (!form.phone.trim()) errors.phone = 'Phone number is required.';
    else if (!PHONE_PATTERN.test(form.phone.trim())) {
      errors.phone = 'Enter a valid phone number (7–15 digits).';
    }
    const pwdProblem = passwordProblem(form.password);
    if (pwdProblem) errors.password = pwdProblem;
    if (form.password !== form.password_confirm) {
      errors.password_confirm = 'Passwords do not match.';
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const applyServerErrors = (err: ApiError): void => {
    const detail = err.detail as
      | { errors?: Record<string, string[]>; message?: string }
      | undefined;
    const serverErrors = detail?.errors ?? {};
    const mapped: FieldErrors = {};
    for (const [key, messages] of Object.entries(serverErrors)) {
      if (Array.isArray(messages) && messages.length > 0) {
        mapped[key as keyof FieldErrors] = messages[0];
      }
    }
    setFieldErrors(mapped);
    if (Object.keys(mapped).length === 0) {
      setFormError(detail?.message || err.message || 'Could not create your account.');
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    if (!validate()) return;
    setIsSubmitting(true);
    try {
      await register({
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim(),
        password: form.password,
        password_confirm: form.password_confirm,
        referral_code: form.referral_code.trim() || undefined,
      });
      navigate('/home', { replace: true });
    } catch (err) {
      applyServerErrors(err as ApiError);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="page-enter mx-auto flex w-full max-w-md flex-col justify-center px-4 py-12 md:py-16">
      <div className="mb-8 flex flex-col items-center text-center">
        <Logo className="h-12 w-12" />
        <h1 className="mt-4 font-display text-2xl font-bold text-surface-800">
          Create your account
        </h1>
        <p className="mt-1 text-sm text-surface-500">
          Free to join — your wallet starts at zero
        </p>
      </div>

      <Card>
        <form className="flex flex-col gap-4 p-5" onSubmit={handleSubmit} noValidate>
          {formError && <Alert tone="danger">{formError}</Alert>}

          <Input
            label="Full name"
            type="text"
            name="full_name"
            autoComplete="name"
            placeholder="Alex Jordan"
            leadingIcon={<User className="h-4 w-4" />}
            value={form.full_name}
            onChange={(e) => set('full_name')(e.target.value)}
            error={fieldErrors.full_name}
            required
          />
          <Input
            label="Email address"
            type="email"
            name="email"
            autoComplete="email"
            placeholder="you@example.com"
            leadingIcon={<Mail className="h-4 w-4" />}
            value={form.email}
            onChange={(e) => set('email')(e.target.value)}
            error={fieldErrors.email}
            required
          />
          <Input
            label="Phone number"
            type="tel"
            name="phone"
            autoComplete="tel"
            placeholder="+15551234567"
            hint="Include country code, e.g. +1… or +91…"
            leadingIcon={<Phone className="h-4 w-4" />}
            value={form.phone}
            onChange={(e) => set('phone')(e.target.value)}
            error={fieldErrors.phone}
            required
          />
          <Input
            label="Password"
            type="password"
            name="password"
            autoComplete="new-password"
            placeholder="At least 8 characters"
            hint="Use 8+ characters with letters and numbers."
            leadingIcon={<Lock className="h-4 w-4" />}
            value={form.password}
            onChange={(e) => set('password')(e.target.value)}
            error={fieldErrors.password}
            required
          />
          <Input
            label="Confirm password"
            type="password"
            name="password_confirm"
            autoComplete="new-password"
            placeholder="Repeat your password"
            leadingIcon={<Lock className="h-4 w-4" />}
            value={form.password_confirm}
            onChange={(e) => set('password_confirm')(e.target.value)}
            error={fieldErrors.password_confirm}
            required
          />
          <Input
            label="Referral code (optional)"
            type="text"
            name="referral_code"
            placeholder="e.g. HX8K29P"
            value={form.referral_code}
            onChange={(e) => set('referral_code')(e.target.value.toUpperCase())}
            error={fieldErrors.referral_code}
          />

          <Button type="submit" fullWidth size="lg" isLoading={isSubmitting}>
            Create account
          </Button>
        </form>
      </Card>

      <p className="mt-6 text-center text-sm text-surface-500">
        Already have an account?{' '}
        <Link to="/login" className="font-semibold text-brand-400 hover:text-brand-300">
          Sign in
        </Link>
      </p>
    </div>
  );
}
