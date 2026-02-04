import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import {
  Download,
  Filter,
  ChevronLeft,
  ChevronRight,
  Check,
  X,
  Image as ImageIcon,
  CheckSquare,
  Square,
  Loader2,
  RotateCcw,
} from 'lucide-react';
import { api } from '@/api/client';
import { Layout } from '@/components/layout/Layout';
import { useWebSocket } from '@/hooks/useWebSocket';
import { VIOLATION_LABELS, VIOLATION_ICONS, Violation } from '@/types';
import { useAuthStore } from '@/store/authStore';

const PAGE_SIZE = 20;

export function ViolationsPage() {
  const [page, setPage] = useState(0);
  const [filters, setFilters] = useState({
    camera_id: '',
    violation_type: '',
    acknowledged: undefined as boolean | undefined,
    hours: 24,
  });
  const [selectedViolation, setSelectedViolation] = useState<Violation | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isExporting, setIsExporting] = useState(false);
  
  const modalRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const username = useAuthStore((s) => s.username);
  const { isConnected } = useWebSocket();

  const { data: violations = [], isLoading, refetch } = useQuery({
    queryKey: ['violations', 'list', filters, page],
    queryFn: () =>
      api.getViolations({
        ...filters,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
  });

  const { data: cameras = [] } = useQuery({
    queryKey: ['cameras'],
    queryFn: () => api.getCameras(),
  });

  // Bulk acknowledge mutation
  const bulkAcknowledgeMutation = useMutation({
    mutationFn: async (ids: string[]) => {
      await Promise.all(
        ids.map((id) =>
          api.acknowledgeViolation(id, { acknowledged_by: username || 'operator' })
        )
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['violations'] });
      setSelectedIds(new Set());
    },
  });

  const handleFilterChange = (key: string, value: string | number | boolean | undefined) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(0);
    setSelectedIds(new Set());
  };

  const resetFilters = () => {
    setFilters({
      camera_id: '',
      violation_type: '',
      acknowledged: undefined,
      hours: 24,
    });
    setPage(0);
    setSelectedIds(new Set());
  };

  // Lazy load XLSX for better performance
  const handleExport = async () => {
    setIsExporting(true);
    try {
      // Dynamic import - only loads when needed
      const XLSX = await import('xlsx');
      
      const allViolations = await api.getViolations({
        ...filters,
        limit: 1000,
      });

      const data = allViolations.map((v) => ({
        ID: v.id,
        Дата: format(new Date(v.timestamp), 'dd.MM.yyyy', { locale: ru }),
        Время: format(new Date(v.timestamp), 'HH:mm:ss', { locale: ru }),
        Камера: v.camera_id,
        Нарушение: VIOLATION_LABELS[v.violation_type] || v.violation_type,
        Уверенность: `${Math.round(v.confidence * 100)}%`,
        Статус: v.acknowledged ? 'Подтверждено' : 'Новое',
        'Подтверждено кем': v.acknowledged_by || '',
      }));

      const ws = XLSX.utils.json_to_sheet(data);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, 'Нарушения');
      XLSX.writeFile(wb, `violations_${format(new Date(), 'yyyy-MM-dd')}.xlsx`);
    } catch (e) {
      console.error('Export failed:', e);
      alert('Ошибка экспорта. Попробуйте ещё раз.');
    } finally {
      setIsExporting(false);
    }
  };

  // Selection handlers
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    const unacknowledged = violations.filter((v) => !v.acknowledged);
    if (selectedIds.size === unacknowledged.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(unacknowledged.map((v) => v.id)));
    }
  };

  const handleBulkAcknowledge = () => {
    if (selectedIds.size === 0) return;
    bulkAcknowledgeMutation.mutate(Array.from(selectedIds));
  };

  // Focus trap for modal
  useEffect(() => {
    if (selectedViolation && modalRef.current) {
      const focusable = modalRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length > 0) {
        focusable[0].focus();
      }
    }
  }, [selectedViolation]);

  // Keyboard handler for modal
  const handleModalKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSelectedViolation(null);
      }
    },
    []
  );

  const unacknowledgedCount = violations.filter((v) => !v.acknowledged).length;
  const hasFilters = filters.camera_id || filters.violation_type || filters.acknowledged !== undefined || filters.hours !== 24;

  return (
    <Layout isConnected={isConnected}>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Журнал нарушений</h1>
        <p className="text-gray-600">История всех зафиксированных нарушений СИЗ</p>
      </div>

      {/* Filters */}
      <div className="card p-4 mb-6">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" aria-hidden="true" />
            <span className="text-sm font-medium text-gray-700">Фильтры:</span>
          </div>

          <select
            value={filters.hours}
            onChange={(e) => handleFilterChange('hours', Number(e.target.value))}
            className="input w-40"
            aria-label="Период времени"
          >
            <option value={1}>Последний час</option>
            <option value={24}>Последние 24ч</option>
            <option value={48}>Последние 48ч</option>
            <option value={168}>Последняя неделя</option>
          </select>

          <select
            value={filters.camera_id}
            onChange={(e) => handleFilterChange('camera_id', e.target.value)}
            className="input w-40"
            aria-label="Фильтр по камере"
          >
            <option value="">Все камеры</option>
            {cameras.map((cam) => (
              <option key={cam.id} value={cam.id}>
                {cam.name || cam.id}
              </option>
            ))}
          </select>

          <select
            value={filters.violation_type}
            onChange={(e) => handleFilterChange('violation_type', e.target.value)}
            className="input w-40"
            aria-label="Тип нарушения"
          >
            <option value="">Все типы</option>
            <option value="no_hardhat">Без каски</option>
            <option value="no_vest">Без жилета</option>
            <option value="no_glasses">Без очков</option>
            <option value="no_gloves">Без перчаток</option>
          </select>

          <select
            value={filters.acknowledged === undefined ? '' : String(filters.acknowledged)}
            onChange={(e) =>
              handleFilterChange(
                'acknowledged',
                e.target.value === '' ? undefined : e.target.value === 'true'
              )
            }
            className="input w-40"
            aria-label="Статус подтверждения"
          >
            <option value="">Все статусы</option>
            <option value="false">Новые</option>
            <option value="true">Подтверждённые</option>
          </select>

          {hasFilters && (
            <button
              onClick={resetFilters}
              className="btn-ghost text-sm text-gray-600"
              aria-label="Сбросить все фильтры"
            >
              <RotateCcw className="w-4 h-4 mr-1" aria-hidden="true" />
              Сбросить
            </button>
          )}

          <div className="flex-1" />

          <button 
            onClick={handleExport} 
            className="btn-outline"
            disabled={isExporting}
            aria-label="Экспортировать в Excel"
          >
            {isExporting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" aria-hidden="true" />
                Экспорт...
              </>
            ) : (
              <>
                <Download className="w-4 h-4 mr-2" aria-hidden="true" />
                Экспорт Excel
              </>
            )}
          </button>
        </div>
      </div>

      {/* Bulk actions bar */}
      {selectedIds.size > 0 && (
        <div className="card p-3 mb-4 bg-primary-50 border-primary-200 flex items-center justify-between" role="status">
          <span className="text-sm font-medium text-primary-700">
            Выбрано: {selectedIds.size} нарушени{selectedIds.size === 1 ? 'е' : selectedIds.size < 5 ? 'я' : 'й'}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSelectedIds(new Set())}
              className="btn-ghost text-sm"
              aria-label="Отменить выбор"
            >
              Отменить
            </button>
            <button
              onClick={handleBulkAcknowledge}
              className="btn-primary text-sm"
              disabled={bulkAcknowledgeMutation.isPending}
              aria-label={`Подтвердить ${selectedIds.size} выбранных нарушений`}
            >
              {bulkAcknowledgeMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" aria-hidden="true" />
                  Обработка...
                </>
              ) : (
                <>
                  <Check className="w-4 h-4 mr-1" aria-hidden="true" />
                  Подтвердить выбранные
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full" role="grid" aria-label="Таблица нарушений">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left w-10">
                  <button
                    onClick={toggleSelectAll}
                    className="p-1 rounded hover:bg-gray-200"
                    aria-label={selectedIds.size === unacknowledgedCount ? 'Снять выделение со всех' : 'Выбрать все неподтверждённые'}
                    disabled={unacknowledgedCount === 0}
                  >
                    {selectedIds.size === unacknowledgedCount && unacknowledgedCount > 0 ? (
                      <CheckSquare className="w-4 h-4 text-primary-600" aria-hidden="true" />
                    ) : (
                      <Square className="w-4 h-4 text-gray-400" aria-hidden="true" />
                    )}
                  </button>
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  #
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Время
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Камера
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Нарушение
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Уверенность
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Фото
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Статус
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-gray-500">
                    <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" aria-hidden="true" />
                    Загрузка...
                  </td>
                </tr>
              ) : violations.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-gray-500">
                    <p>Нарушений не найдено</p>
                    {hasFilters && (
                      <button onClick={resetFilters} className="text-primary-600 text-sm mt-2 hover:underline">
                        Сбросить фильтры
                      </button>
                    )}
                  </td>
                </tr>
              ) : (
                violations.map((v, idx) => (
                  <tr
                    key={v.id}
                    className={`hover:bg-gray-50 ${
                      !v.acknowledged ? 'bg-danger-50/50' : ''
                    } ${selectedIds.has(v.id) ? 'bg-primary-50' : ''}`}
                  >
                    <td className="px-4 py-3">
                      {!v.acknowledged && (
                        <button
                          onClick={() => toggleSelect(v.id)}
                          className="p-1 rounded hover:bg-gray-200"
                          aria-label={selectedIds.has(v.id) ? 'Снять выделение' : 'Выбрать для подтверждения'}
                        >
                          {selectedIds.has(v.id) ? (
                            <CheckSquare className="w-4 h-4 text-primary-600" aria-hidden="true" />
                          ) : (
                            <Square className="w-4 h-4 text-gray-400" aria-hidden="true" />
                          )}
                        </button>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {page * PAGE_SIZE + idx + 1}
                    </td>
                    <td 
                      className="px-4 py-3 cursor-pointer" 
                      onClick={() => setSelectedViolation(v)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => e.key === 'Enter' && setSelectedViolation(v)}
                    >
                      <div className="text-sm font-medium text-gray-900">
                        {format(new Date(v.timestamp), 'HH:mm:ss')}
                      </div>
                      <div className="text-xs text-gray-500">
                        {format(new Date(v.timestamp), 'd MMM yyyy', { locale: ru })}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">{v.camera_id}</td>
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-2">
                        <span aria-hidden="true">{VIOLATION_ICONS[v.violation_type] || '⚠️'}</span>
                        <span className="text-sm font-medium text-gray-900">
                          {VIOLATION_LABELS[v.violation_type] || v.violation_type}
                        </span>
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {Math.round(v.confidence * 100)}%
                    </td>
                    <td className="px-4 py-3">
                      {v.image_path ? (
                        <ImageIcon className="w-4 h-4 text-gray-400" aria-label="Есть фото" />
                      ) : (
                        <span className="text-gray-300" aria-label="Нет фото">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {v.acknowledged ? (
                        <span className="badge-success">
                          <Check className="w-3 h-3 mr-1" aria-hidden="true" />
                          Подтверждено
                          <span className="sr-only"> пользователем {v.acknowledged_by}</span>
                        </span>
                      ) : (
                        <span className="badge-danger">
                          Новое
                          <span className="sr-only"> - требует подтверждения</span>
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
          <div className="text-sm text-gray-500">
            Страница {page + 1}
            {violations.length > 0 && (
              <span className="ml-2">
                (показано {page * PAGE_SIZE + 1}-{page * PAGE_SIZE + violations.length})
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="btn-ghost p-2 disabled:opacity-50"
              aria-label="Предыдущая страница"
            >
              <ChevronLeft className="w-4 h-4" aria-hidden="true" />
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={violations.length < PAGE_SIZE}
              className="btn-ghost p-2 disabled:opacity-50"
              aria-label="Следующая страница"
            >
              <ChevronRight className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>

      {/* Detail modal with focus trap */}
      {selectedViolation && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setSelectedViolation(null)}
          onKeyDown={handleModalKeyDown}
          role="dialog"
          aria-modal="true"
          aria-labelledby="violation-modal-title"
        >
          <div
            ref={modalRef}
            className="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h3 id="violation-modal-title" className="font-semibold text-gray-900">
                Детали нарушения #{selectedViolation.id.slice(0, 8)}
              </h3>
              <button
                onClick={() => setSelectedViolation(null)}
                className="p-1 hover:bg-gray-100 rounded"
                aria-label="Закрыть детали нарушения"
                autoFocus
              >
                <X className="w-5 h-5" aria-hidden="true" />
              </button>
            </div>
            <div className="p-4">
              {selectedViolation.image_path && (
                <img
                  src={api.getViolationImageUrl(selectedViolation.id)}
                  alt={`Нарушение: ${VIOLATION_LABELS[selectedViolation.violation_type]} на камере ${selectedViolation.camera_id}`}
                  className="w-full rounded-lg mb-4"
                  onError={(e) => {
                    const target = e.currentTarget;
                    target.style.display = 'none';
                    const placeholder = target.nextElementSibling as HTMLElement;
                    if (placeholder) placeholder.style.display = 'flex';
                  }}
                />
              )}
              {selectedViolation.image_path && (
                <div
                  className="w-full rounded-lg mb-4 bg-gray-100 dark:bg-gray-700 items-center justify-center py-12"
                  style={{ display: 'none' }}
                >
                  <div className="text-center text-gray-400">
                    <svg className="w-12 h-12 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
                    </svg>
                    <p className="text-sm">Изображение недоступно</p>
                  </div>
                </div>
              )}
              {!selectedViolation.image_path && (
                <div className="w-full rounded-lg mb-4 bg-gray-100 dark:bg-gray-700 flex items-center justify-center py-12">
                  <div className="text-center text-gray-400">
                    <svg className="w-12 h-12 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
                    </svg>
                    <p className="text-sm">Фото не сохранено</p>
                  </div>
                </div>
              )}
              <dl className="grid grid-cols-2 gap-4">
                <div>
                  <dt className="text-sm text-gray-500">Время</dt>
                  <dd className="font-medium">
                    {format(new Date(selectedViolation.timestamp), 'dd.MM.yyyy HH:mm:ss')}
                  </dd>
                </div>
                <div>
                  <dt className="text-sm text-gray-500">Камера</dt>
                  <dd className="font-medium">{selectedViolation.camera_id}</dd>
                </div>
                <div>
                  <dt className="text-sm text-gray-500">Тип нарушения</dt>
                  <dd className="font-medium">
                    <span aria-hidden="true">{VIOLATION_ICONS[selectedViolation.violation_type]}</span>{' '}
                    {VIOLATION_LABELS[selectedViolation.violation_type]}
                  </dd>
                </div>
                <div>
                  <dt className="text-sm text-gray-500">Уверенность</dt>
                  <dd className="font-medium">
                    {Math.round(selectedViolation.confidence * 100)}%
                  </dd>
                </div>
                {selectedViolation.person_id && (
                  <div>
                    <dt className="text-sm text-gray-500">Track ID</dt>
                    <dd className="font-medium">#{selectedViolation.person_id}</dd>
                  </div>
                )}
                <div>
                  <dt className="text-sm text-gray-500">Статус</dt>
                  <dd>
                    {selectedViolation.acknowledged ? (
                      <span className="badge-success">Подтверждено</span>
                    ) : (
                      <span className="badge-danger">Новое</span>
                    )}
                  </dd>
                </div>
              </dl>

              {/* Acknowledge button */}
              {!selectedViolation.acknowledged && (
                <div className="mt-6 pt-4 border-t border-gray-200">
                  <button
                    onClick={async () => {
                      try {
                        await api.acknowledgeViolation(selectedViolation.id, {
                          acknowledged_by: username || 'operator',
                        });
                        refetch();
                        setSelectedViolation(null);
                      } catch (e) {
                        console.error('Failed to acknowledge:', e);
                        alert('Ошибка подтверждения. Попробуйте ещё раз.');
                      }
                    }}
                    className="w-full btn-primary"
                  >
                    <Check className="w-4 h-4 mr-2" aria-hidden="true" />
                    Подтвердить нарушение
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
