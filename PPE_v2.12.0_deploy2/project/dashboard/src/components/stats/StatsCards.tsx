import { HardHat, Shirt, AlertTriangle } from 'lucide-react';
import { ViolationStats } from '@/types';

interface StatsCardsProps {
  stats: ViolationStats | null;
  loading?: boolean;
}

export function StatsCards({ stats, loading }: StatsCardsProps) {
  const items = [
    {
      label: 'Всего нарушений',
      value: stats?.total ?? 0,
      icon: AlertTriangle,
      color: 'danger',
    },
    {
      label: 'Без каски',
      value: stats?.by_type?.['no_hardhat'] ?? 0,
      icon: HardHat,
      color: 'warning',
    },
    {
      label: 'Без жилета',
      value: stats?.by_type?.['no_vest'] ?? 0,
      icon: Shirt,
      color: 'primary',
    },
  ];

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="card p-4 animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-24 mb-2" />
            <div className="h-8 bg-gray-200 rounded w-16" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <div key={item.label} className="card p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">{item.label}</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">
                  {item.value}
                </p>
              </div>
              <div
                className={`p-3 rounded-xl ${
                  item.color === 'danger'
                    ? 'bg-danger-100 text-danger-600'
                    : item.color === 'warning'
                    ? 'bg-warning-100 text-warning-600'
                    : 'bg-primary-100 text-primary-600'
                }`}
              >
                <Icon className="w-6 h-6" aria-hidden="true" />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

interface SystemStatusProps {
  camerasOnline: number;
  camerasTotal: number;
  isConnected: boolean;
  fps?: number;
}

export function SystemStatus({
  camerasOnline,
  camerasTotal,
  isConnected,
  fps = 0,
}: SystemStatusProps) {
  return (
    <div className="card p-4">
      <h3 className="font-semibold text-gray-900 mb-3">Состояние системы</h3>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">Камеры</span>
          <span className="text-sm font-medium">
            {camerasOnline}/{camerasTotal}{' '}
            {camerasOnline === camerasTotal ? (
              <span className="text-success-600">🟢</span>
            ) : (
              <span className="text-warning-600">🟡</span>
            )}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">Детектор</span>
          <span className="text-sm font-medium">
            {isConnected ? (
              <>
                OK <span className="text-success-600">🟢</span>
              </>
            ) : (
              <>
                Offline <span className="text-danger-600">🔴</span>
              </>
            )}
          </span>
        </div>
        {fps > 0 && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">FPS</span>
            <span className="text-sm font-medium">{fps}</span>
          </div>
        )}
      </div>
    </div>
  );
}
