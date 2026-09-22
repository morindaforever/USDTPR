/**
 * Shareable referral-link construction (Section 9).
 *
 * The link is built from the *runtime* browser origin (`window.location.origin`)
 * so it always matches the domain the app is actually served from —
 * localhost in development, the deployed production domain in production.
 * No environment variable or source change is needed when the domain changes.
 *
 * The referral code comes from the backend; only the base URL is client-built.
 */
export function buildReferralLink(code: string, origin: string = window.location.origin): string {
  return `${origin.replace(/\/$/, '')}/signup?ref=${encodeURIComponent(code)}`;
}
