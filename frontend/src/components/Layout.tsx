import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Outlet,
  useLocation,
} from 'react-router-dom';
import {
  LayoutDashboard,
  CheckSquare,
  Users,
  BrainCircuit,
  BarChart3,
  FileText,
  Webhook,
  Settings,
  Moon,
  Sun,
  Menu,
  X,
  LogOut,
  Database,
  Sparkles,
  BookOpen,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { SidebarNavItem } from './SidebarNavItem';
import { SidebarSection } from './SidebarSection';
import { WorkspaceProjectSelector } from './WorkspaceProjectSelector';
import { LanguageToggle } from './LanguageToggle';
import { useLanguage } from '../i18n/LanguageContext';
import { useTheme } from '../context/ThemeContext';
import { useSidebar } from '../context/SidebarContext';
import { useAuth } from '../context/AuthContext';
import { useWorkspaceContext } from '../context/WorkspaceContext';

export function Layout() {
  const { t } = useLanguage();
  const { sidebarOpen, setSidebarOpen, toggleSidebar, isMobile } = useSidebar();
  const { theme, toggleTheme } = useTheme();
  const { user, logoutUser } = useAuth();
  const { currentWorkspaceId } = useWorkspaceContext();
  const nextTheme = theme === 'dark' ? 'light' : 'dark';
  const lastScrollTop = useRef(0);
  const [mobileNavVisible, setMobileNavVisible] = useState(true);

  // Build prefix for workspace-scoped routes
  const prefix = currentWorkspaceId ? `/${currentWorkspaceId}` : '';

  // Swipe to open/close on mobile
  useEffect(() => {
    if (!isMobile) return;

    const EDGE_ZONE = 30;
    const MIN_DISTANCE = 50;
    const MAX_VERTICAL = 75;
    let startX = 0;
    let startY = 0;

    const onTouchStart = (e: TouchEvent) => {
      const t = e.touches[0]!;
      startX = t.clientX;
      startY = t.clientY;
    };

    const onTouchEnd = (e: TouchEvent) => {
      const t = e.changedTouches[0]!;
      const dx = t.clientX - startX;
      const dy = Math.abs(t.clientY - startY);
      if (dy > MAX_VERTICAL) return;
      if (!sidebarOpen && startX < EDGE_ZONE && dx > MIN_DISTANCE) {
        setSidebarOpen(true);
        return;
      }
      if (sidebarOpen && dx < -MIN_DISTANCE) {
        setSidebarOpen(false);
      }
    };

    document.addEventListener('touchstart', onTouchStart, { passive: true });
    document.addEventListener('touchend', onTouchEnd, { passive: true });
    return () => {
      document.removeEventListener('touchstart', onTouchStart);
      document.removeEventListener('touchend', onTouchEnd);
    };
  }, [isMobile, sidebarOpen, setSidebarOpen]);

  // Hide mobile nav on scroll down
  const updateMobileNavVisibility = useCallback((currentTop: number) => {
    const delta = currentTop - lastScrollTop.current;
    if (currentTop <= 24) setMobileNavVisible(true);
    else if (delta > 8) setMobileNavVisible(false);
    else if (delta < -8) setMobileNavVisible(true);
    lastScrollTop.current = currentTop;
  }, []);

  useEffect(() => {
    if (!isMobile) { setMobileNavVisible(true); lastScrollTop.current = 0; return; }
    const onScroll = () => {
      updateMobileNavVisibility(window.scrollY || document.documentElement.scrollTop || 0);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [isMobile, updateMobileNavVisibility]);

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = isMobile ? 'visible' : 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [isMobile]);

  const sidebar = (
    <aside className="w-60 h-full min-h-0 border-r border-border bg-background flex flex-col">
      {/* Header: workspace selector aligned with top */}
      <div className="flex items-center px-3 h-12 shrink-0 border-b border-border">
        <div className="flex-1 min-w-0">
          <WorkspaceProjectSelector compact />
        </div>
      </div>

      <nav className="flex-1 min-h-0 overflow-y-auto scrollbar-auto-hide flex flex-col gap-4 px-3 py-2">
        <div className="flex flex-col gap-0.5">
          <SidebarNavItem to={`${prefix}/ai`} label={t.appNav.aiAnalysis} icon={Sparkles} />
          <SidebarNavItem to={`${prefix}/dashboard`} label={t.appNav.dashboard} icon={LayoutDashboard} />
        </div>
        <SidebarSection label="Work">
          <SidebarNavItem to={`${prefix}/tasks`} label={t.appNav.tasks} icon={CheckSquare} />
          <SidebarNavItem to={`${prefix}/team`} label={t.appNav.teamMembers} icon={Users} />
          <SidebarNavItem to={`${prefix}/sources`} label={t.appNav.sources} icon={Database} />
        </SidebarSection>


        <SidebarSection label={t.settings.title}>
          <SidebarNavItem to={`${prefix}/documentation`} label={t.appNav.documentation} icon={BookOpen} />
          <SidebarNavItem to={`${prefix}/settings/webhooks`} label={t.appNav.webhooks} icon={Webhook} />
        </SidebarSection>
      </nav>

      {/* Footer: user + theme toggle */}
      <div className="border-t border-border px-3 py-2 shrink-0">
        <div className="flex items-center gap-1">
          <span className="flex-1 min-w-0 text-xs text-muted-foreground truncate px-2">
            {user?.email}
          </span>
          <button
            type="button"
            onClick={toggleTheme}
            className="flex items-center justify-center w-8 h-8 text-muted-foreground hover:bg-accent/50 hover:text-foreground transition-colors"
            aria-label={`Switch to ${nextTheme} mode`}
            title={`Switch to ${nextTheme} mode`}
          >
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          <LanguageToggle />
          <button
            type="button"
            onClick={() => void logoutUser()}
            className="flex items-center justify-center w-8 h-8 text-muted-foreground hover:bg-accent/50 hover:text-foreground transition-colors"
            aria-label="Sign out"
            title="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );

  return (
    <div
      className={cn(
        'bg-background text-foreground',
        isMobile ? 'min-h-dvh' : 'flex h-dvh flex-col overflow-hidden',
      )}
    >
      <div className={cn('min-h-0 flex-1', isMobile ? 'w-full' : 'flex overflow-hidden')}>
        {/* Mobile sidebar overlay */}
        {isMobile && sidebarOpen && (
          <button
            type="button"
            className="fixed inset-0 z-40 bg-black/50"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close sidebar"
          />
        )}

        {/* Sidebar */}
        {isMobile ? (
          <div
            className={cn(
              'fixed inset-y-0 left-0 z-50 flex flex-col overflow-hidden transition-transform duration-100 ease-out',
              sidebarOpen ? 'translate-x-0' : '-translate-x-full',
            )}
          >
            {sidebar}
          </div>
        ) : (
          <div className="flex h-full flex-col shrink-0">
            <div
              className={cn(
                'h-full overflow-hidden transition-[width] duration-100 ease-out',
                sidebarOpen ? 'w-60' : 'w-0',
              )}
            >
              {sidebar}
            </div>
          </div>
        )}

        {/* Main content */}
        <div className={cn('flex min-w-0 flex-col', isMobile ? 'w-full' : 'h-full flex-1')}>
          {/* Top bar */}
          <div className="flex items-center gap-2 h-12 px-4 border-b border-border shrink-0">
            <button
              type="button"
              onClick={toggleSidebar}
              className="flex items-center justify-center w-8 h-8 text-muted-foreground hover:bg-accent/50 hover:text-foreground transition-colors"
              aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
            >
              {sidebarOpen && !isMobile ? (
                <X className="h-4 w-4" />
              ) : (
                <Menu className="h-4 w-4" />
              )}
            </button>
            <BreadcrumbTitle />
          </div>

          <main
            className={cn(
              'flex-1 p-4 md:p-6',
              isMobile ? 'overflow-visible pb-20' : 'overflow-auto',
            )}
          >
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}

/** Simple breadcrumb that extracts the last path segment as the page title */
function BreadcrumbTitle() {
  const location = useLocation();
  const segments = location.pathname.split('/').filter(Boolean);
  // The first segment is the workspaceId, second is the page name
  const titleMap: Record<string, string> = {
    dashboard: 'Dashboard',
    tasks: 'Tasks',
    team: 'Team Members',
    review: 'Review Queue',
    ai: 'AI Analysis',
    sources: 'Sources',
    documentation: 'Documentation',
    webhooks: 'Webhooks',
  };
  
  // Special case for settings/webhooks
  let page = segments[1] ?? segments[0] ?? '';
  if (segments[1] === 'settings' && segments[2]) {
    page = segments[2];
  }
  
  const title = titleMap[page] ?? page;

  return (
    <span className="text-sm font-medium text-muted-foreground">
      {title}
    </span>
  );
}
