import { apiGet } from './api';
import type { HealthStatus } from '@/types';

/**
 * Backend liveness check. Used by the landing page and future diagnostics
 * screens to confirm the API is reachable.
 */
export function fetchHealth(): Promise<HealthStatus> {
  return apiGet<HealthStatus>('/health/');
}
