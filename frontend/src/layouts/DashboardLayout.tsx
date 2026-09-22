import { Outlet } from 'react-router-dom';
import { BottomNavigation } from './BottomNavigation';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

/**
 * Shell for all authenticated screens. Desktop uses a fixed left sidebar;
 * mobile uses a sticky header and bottom tab bar. Page content renders
 * through the router outlet.
 */
export function DashboardLayout() {
  return (
    <div className="min-h-dvh bg-surface-950">
      <Sidebar />
      <div className="lg:pl-60">
        <Header />
        <main className="mx-auto w-full max-w-6xl px-4 pb-28 pt-5 md:px-8 md:pb-14 md:pt-8">
          <Outlet />
        </main>
      </div>
      <BottomNavigation />
    </div>
  );
}
