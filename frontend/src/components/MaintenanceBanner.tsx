import { useDashboardData } from '@/hooks';
import { siteService } from '@/services';
import { Alert } from '@/components';

/**
 * Maintenance notice (Section 15 §37). The flag comes from the backend
 * SiteSetting `platform.maintenance_mode`, toggled in the admin panel —
 * never a frontend-only switch. Renders nothing while the flag is false or
 * still loading, so normal operation is unaffected.
 */
export function MaintenanceBanner() {
  const { data } = useDashboardData<{ maintenance: boolean }>(() => siteService.status());

  if (!data?.maintenance) return null;

  return (
    <Alert tone="warning" title="Scheduled maintenance" className="mb-5">
      The platform may be temporarily unavailable while we perform
      maintenance. Your balances and data are not affected.
    </Alert>
  );
}
