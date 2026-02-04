import { ReactNode, useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { useViolationsStore } from '@/store/violationsStore';
import {
  LayoutDashboard,
  FileText,
  BarChart3,
  Settings,
  LogOut,
  Bell,
  HardHat,
  Wifi,
  WifiOff,
  GraduationCap,
} from 'lucide-react';

interface LayoutProps {
  children: ReactNode;
  isConnected?: boolean;
}

const navItems = [
  { path: '/', icon: LayoutDashboard, label: 'Мониторинг' },
  { path: '/violations', icon: FileText, label: 'Журнал' },
  { path: '/analytics', icon: BarChart3, label: 'Аналитика' },
  { path: '/training', icon: GraduationCap, label: 'Обучение' },
  { path: '/settings', icon: Settings, label: 'Настройки' },
];

// Simple hook to get API version
function useApiVersion() {
  const [version, setVersion] = useState<string>('...');
  
  useEffect(() => {
    fetch('/api/health')
      .then(res => res.json())
      .then(data => setVersion(data.version || 'unknown'))
      .catch(() => setVersion('error'));
  }, []);
  
  return version;
}

export function Layout({ children, isConnected = false }: LayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { username, logout } = useAuthStore();
  const unacknowledgedCount = useViolationsStore((s) => s.unacknowledgedCount) ?? 0;
  const apiVersion = useApiVersion();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Skip link for keyboard users - A11y fix */}
      <a 
        href="#main-content" 
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 bg-primary-600 text-white px-4 py-2 rounded-lg font-medium"
      >
        Перейти к основному содержимому
      </a>

      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="flex items-center justify-between px-4 h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-3" aria-label="PPE Monitor - главная страница">
            <div className="w-10 h-10 bg-orange-500 rounded-lg flex items-center justify-center">
              <HardHat className="w-6 h-6 text-white" aria-hidden="true" />
            </div>
            <div>
              <h1 className="font-bold text-gray-900">PPE Monitor</h1>
              <p className="text-xs text-gray-500">Контроль СИЗ</p>
            </div>
          </Link>

          {/* Navigation */}
          <nav className="hidden md:flex items-center gap-1" aria-label="Основная навигация">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                  aria-current={isActive ? 'page' : undefined}
                >
                  <Icon className="w-4 h-4" aria-hidden="true" />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          {/* Right side */}
          <div className="flex items-center gap-4">
            {/* Connection status & Version */}
            <div className="flex items-center gap-2" role="status" aria-live="polite">
              {isConnected ? (
                <Wifi className="w-4 h-4 text-success-500" aria-hidden="true" />
              ) : (
                <WifiOff className="w-4 h-4 text-gray-400" aria-hidden="true" />
              )}
              <span className="text-xs text-gray-500">
                {isConnected ? 'Online' : 'Offline'}
              </span>
              <span className="text-xs text-gray-400 ml-1" title="Версия API">
                v{apiVersion}
              </span>
              <span className="sr-only">
                {isConnected ? 'Соединение активно' : 'Соединение потеряно'}
              </span>
            </div>

            {/* Notifications */}
            <button 
              className="relative p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
              aria-label={`Уведомления${unacknowledgedCount > 0 ? `, ${unacknowledgedCount} новых` : ''}`}
            >
              <Bell className="w-5 h-5" aria-hidden="true" />
              {unacknowledgedCount > 0 && (
                <span className="absolute -top-1 -right-1 w-5 h-5 bg-danger-500 text-white text-xs font-bold rounded-full flex items-center justify-center">
                  {unacknowledgedCount > 9 ? '9+' : unacknowledgedCount}
                </span>
              )}
            </button>

            {/* User menu */}
            <div className="flex items-center gap-3 pl-4 border-l border-gray-200">
              <div className="text-right">
                <p className="text-sm font-medium text-gray-900">{username}</p>
                <p className="text-xs text-gray-500">Администратор</p>
              </div>
              <button
                onClick={handleLogout}
                className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                aria-label="Выйти из системы"
              >
                <LogOut className="w-5 h-5" aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main id="main-content" className="p-6" tabIndex={-1}>{children}</main>
    </div>
  );
}
