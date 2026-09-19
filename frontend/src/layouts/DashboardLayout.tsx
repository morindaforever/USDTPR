import { Outlet } from 'react-router-dom';
import { BottomNavigation } from './BottomNavigation';
import { Header } from './Header';

/**
 * Shell for all authenticated screens (Sections 2+). The header carries
 * desktop navigation, the bottom bar carries mobile navigation, and page
 * content renders through the router outlet.
 */
export function DashboardLayout() {
  return (
    <div className="flex min-h-dvh flex-col bg-surface-50">
      <Header />
      <main className="flex-1">
        <Outlet />
      </main>
      <BottomNavigation />
    </div>
  );
}
