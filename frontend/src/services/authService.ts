import { apiGet, apiPost, setAccessToken } from './api';

/** Safe user representation returned by the backend. */
export interface AuthUser {
  user_id: string;
  full_name: string;
  email: string;
  phone: string;
  referral_code: string;
  account_status: 'ACTIVE' | 'SUSPENDED' | 'BANNED';
  /** Staff flag — presentation routing only; the backend enforces everything. */
  is_staff?: boolean;
}

/** Standard backend envelope for auth endpoints. */
export interface AuthEnvelope<T = unknown> {
  success: boolean;
  message: string;
  errors?: Record<string, string[]>;
  data?: T;
}

interface TokenPayload {
  user: AuthUser;
  access: string;
}

export interface RegisterPayload {
  full_name: string;
  email: string;
  phone: string;
  password: string;
  password_confirm: string;
  referral_code?: string;
}

/**
 * All authentication calls live here — components never touch Axios
 * directly. Access tokens are held in-memory by the api module.
 */
export const authService = {
  async register(payload: RegisterPayload): Promise<AuthEnvelope<TokenPayload>> {
    const envelope = await apiPost<AuthEnvelope<TokenPayload>>('/auth/register/', payload);
    if (envelope.success && envelope.data?.access) {
      setAccessToken(envelope.data.access);
    }
    return envelope;
  },

  async login(identifier: string, password: string): Promise<AuthEnvelope<TokenPayload>> {
    const envelope = await apiPost<AuthEnvelope<TokenPayload>>('/auth/login/', {
      identifier,
      password,
    });
    if (envelope.success && envelope.data?.access) {
      setAccessToken(envelope.data.access);
    }
    return envelope;
  },

  /** Rotate the access token using the HttpOnly cookie. */
  async refresh(): Promise<boolean> {
    const { tryRefreshAccessToken } = await import('./api');
    return tryRefreshAccessToken();
  },

  async logout(): Promise<void> {
    try {
      await apiPost('/auth/logout/', {});
    } finally {
      setAccessToken(null);
    }
  },

  async me(): Promise<AuthUser> {
    const envelope = await apiGet<AuthEnvelope<{ user: AuthUser }>>('/auth/me/');
    return envelope.data!.user;
  },

  async forgotPassword(email: string): Promise<AuthEnvelope> {
    return apiPost<AuthEnvelope>('/auth/forgot-password/', { email });
  },

  async resetPassword(token: string, password: string, password_confirm: string): Promise<AuthEnvelope> {
    return apiPost<AuthEnvelope>('/auth/reset-password/', { token, password, password_confirm });
  },

  async changePassword(
    current_password: string,
    password: string,
    password_confirm: string,
  ): Promise<AuthEnvelope> {
    return apiPost<AuthEnvelope>('/auth/change-password/', {
      current_password,
      password,
      password_confirm,
    });
  },
};
