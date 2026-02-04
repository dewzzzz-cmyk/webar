import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { Calendar, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { api } from '@/api/client';
import { Layout } from '@/components/layout/Layout';
import { useWebSocket } from '@/hooks/useWebSocket';
import { VIOLATION_LABELS } from '@/types';

const COLORS = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6', '#8b5cf6'];

export function AnalyticsPage() {
  const [period, setPeriod] = useState(24);
  const { isConnected } = useWebSocket();

  const { data: stats, isLoading } = useQuery({
    queryKey: ['stats', period],
    queryFn: () => api.getStatistics(period),
  });

  // Transform data for charts
  const typeData = stats?.by_type
    ? Object.entries(stats.by_type).map(([key, value]) => ({
        name: VIOLATION_LABELS[key as keyof typeof VIOLATION_LABELS] || key,
        value,
        key,
      }))
    : [];

  const cameraData = stats?.by_camera
    ? Object.entries(stats.by_camera)
        .map(([name, value]) => ({ name, value }))
        .sort((a, b) => b.value - a.value)
    : [];

  const hourlyData = stats?.by_hour
    ? Object.entries(stats.by_hour)
        .map(([hour, count]) => ({ hour, count }))
        .reverse()
    : [];

  // Calculate trend
  const trend = hourlyData.length >= 2
    ? hourlyData[0].count - hourlyData[hourlyData.length - 1].count
    : 0;

  return (
    <Layout isConnected={isConnected}>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Аналитика</h1>
          <p className="text-gray-600">Статистика и тренды нарушений СИЗ</p>
        </div>

        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-gray-400" />
          <select
            value={period}
            onChange={(e) => setPeriod(Number(e.target.value))}
            className="input w-48"
          >
            <option value={1}>Последний час</option>
            <option value={6}>Последние 6 часов</option>
            <option value={24}>Последние 24 часа</option>
            <option value={48}>Последние 48 часов</option>
            <option value={168}>Последняя неделя</option>
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 animate-pulse">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="card p-6 h-64 bg-gray-100" />
          ))}
        </div>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="card p-4">
              <p className="text-sm text-gray-600">Всего нарушений</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">{stats?.total || 0}</p>
            </div>
            <div className="card p-4">
              <p className="text-sm text-gray-600">Среднее в час</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">
                {hourlyData.length > 0
                  ? Math.round(hourlyData.reduce((s, h) => s + h.count, 0) / hourlyData.length)
                  : 0}
              </p>
            </div>
            <div className="card p-4">
              <p className="text-sm text-gray-600">Пик нарушений</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">
                {hourlyData.length > 0 ? Math.max(...hourlyData.map((h) => h.count)) : 0}
              </p>
            </div>
            <div className="card p-4">
              <p className="text-sm text-gray-600">Тренд</p>
              <div className="flex items-center gap-2 mt-1">
                {trend > 0 ? (
                  <>
                    <TrendingUp className="w-6 h-6 text-danger-500" />
                    <span className="text-2xl font-bold text-danger-600">+{trend}</span>
                  </>
                ) : trend < 0 ? (
                  <>
                    <TrendingDown className="w-6 h-6 text-success-500" />
                    <span className="text-2xl font-bold text-success-600">{trend}</span>
                  </>
                ) : (
                  <>
                    <Minus className="w-6 h-6 text-gray-400" />
                    <span className="text-2xl font-bold text-gray-500">0</span>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Hourly chart */}
            <div className="card p-6">
              <h3 className="font-semibold text-gray-900 mb-4">Нарушения по часам</h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={hourlyData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="hour" fontSize={12} tick={{ fill: '#6b7280' }} />
                    <YAxis fontSize={12} tick={{ fill: '#6b7280' }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#fff',
                        border: '1px solid #e5e7eb',
                        borderRadius: '8px',
                      }}
                    />
                    <Bar dataKey="count" fill="#ef4444" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* By type pie chart */}
            <div className="card p-6">
              <h3 className="font-semibold text-gray-900 mb-4">По типу нарушения</h3>
              <div className="h-64">
                {typeData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={typeData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={5}
                        dataKey="value"
                        label={({ name, percent }) =>
                          `${name} ${(percent * 100).toFixed(0)}%`
                        }
                        labelLine={false}
                      >
                        {typeData.map((_, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={COLORS[index % COLORS.length]}
                          />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-gray-500">
                    Нет данных
                  </div>
                )}
              </div>
            </div>

            {/* By camera chart */}
            <div className="card p-6">
              <h3 className="font-semibold text-gray-900 mb-4">По камерам</h3>
              <div className="h-64">
                {cameraData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={cameraData} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis type="number" fontSize={12} tick={{ fill: '#6b7280' }} />
                      <YAxis
                        dataKey="name"
                        type="category"
                        fontSize={12}
                        tick={{ fill: '#6b7280' }}
                        width={100}
                      />
                      <Tooltip />
                      <Bar dataKey="value" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-gray-500">
                    Нет данных
                  </div>
                )}
              </div>
            </div>

            {/* Type breakdown table */}
            <div className="card p-6">
              <h3 className="font-semibold text-gray-900 mb-4">Детализация по типам</h3>
              <div className="space-y-3">
                {typeData.length > 0 ? (
                  typeData.map((item, idx) => (
                    <div key={item.key} className="flex items-center gap-3">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: COLORS[idx % COLORS.length] }}
                      />
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-gray-900">
                            {item.name}
                          </span>
                          <span className="text-sm text-gray-600">{item.value}</span>
                        </div>
                        <div className="mt-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${(item.value / (stats?.total || 1)) * 100}%`,
                              backgroundColor: COLORS[idx % COLORS.length],
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center text-gray-500 py-8">Нет данных</div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </Layout>
  );
}
