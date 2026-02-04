import { useState } from 'react';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { Check, Clock, Image as ImageIcon, X } from 'lucide-react';
import { Violation, VIOLATION_LABELS, VIOLATION_ICONS } from '@/types';
import { api } from '@/api/client';
import { useViolationsStore } from '@/store/violationsStore';
import { useAuthStore } from '@/store/authStore';

interface ViolationCardProps {
  violation: Violation;
  compact?: boolean;
}

export function ViolationCard({ violation, compact = false }: ViolationCardProps) {
  const [showImage, setShowImage] = useState(false);
  const [acknowledging, setAcknowledging] = useState(false);
  const acknowledgeLocal = useViolationsStore((s) => s.acknowledgeViolation);
  const username = useAuthStore((s) => s.username);

  const icon = VIOLATION_ICONS[violation.violation_type] || '⚠️';
  const label = VIOLATION_LABELS[violation.violation_type] || violation.violation_type;
  const time = format(new Date(violation.timestamp), 'HH:mm:ss', { locale: ru });
  const date = format(new Date(violation.timestamp), 'd MMM', { locale: ru });

  const handleAcknowledge = async () => {
    if (acknowledging || violation.acknowledged) return;
    setAcknowledging(true);
    try {
      await api.acknowledgeViolation(violation.id, {
        acknowledged_by: username || 'unknown',
      });
      acknowledgeLocal(violation.id);
    } catch (e) {
      console.error('Failed to acknowledge:', e);
    } finally {
      setAcknowledging(false);
    }
  };

  if (compact) {
    return (
      <div
        className={`flex items-center gap-3 p-3 rounded-lg transition-all ${
          violation.acknowledged
            ? 'bg-gray-50'
            : 'bg-danger-50 border-l-4 border-danger-500'
        }`}
      >
        <span className="text-2xl">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm text-gray-900">{label}</span>
            <span className="text-xs text-gray-500">{violation.camera_id}</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Clock className="w-3 h-3" />
            <span>{time}</span>
            <span>•</span>
            <span>{Math.round(violation.confidence * 100)}%</span>
          </div>
        </div>
        {!violation.acknowledged && (
          <button
            onClick={handleAcknowledge}
            disabled={acknowledging}
            className="p-2 text-success-600 hover:bg-success-100 rounded-lg transition-colors"
            aria-label={`Подтвердить нарушение: ${label}`}
          >
            <Check className="w-4 h-4" aria-hidden="true" />
          </button>
        )}
      </div>
    );
  }

  return (
    <>
      <div
        className={`card overflow-hidden transition-all ${
          violation.acknowledged ? '' : 'ring-2 ring-danger-500'
        }`}
      >
        <div className="flex">
          {/* Image thumbnail */}
          {violation.image_path && (
            <button
              onClick={() => setShowImage(true)}
              className="relative w-24 h-24 bg-gray-100 flex-shrink-0"
            >
              <img
                src={api.getViolationImageUrl(violation.id)}
                alt="Нарушение"
                className="w-full h-full object-cover"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none';
                }}
              />
              <div className="absolute inset-0 flex items-center justify-center bg-black/0 hover:bg-black/30 transition-colors">
                <ImageIcon className="w-6 h-6 text-white opacity-0 hover:opacity-100" />
              </div>
            </button>
          )}

          {/* Content */}
          <div className="flex-1 p-4">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xl">{icon}</span>
                  <span className="font-semibold text-gray-900">{label}</span>
                  {!violation.acknowledged && (
                    <span className="badge-danger">Новое</span>
                  )}
                </div>
                <div className="mt-1 text-sm text-gray-600">
                  Камера: {violation.camera_id}
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-medium text-gray-900">{time}</div>
                <div className="text-xs text-gray-500">{date}</div>
              </div>
            </div>

            <div className="mt-3 flex items-center justify-between">
              <div className="flex items-center gap-4 text-sm text-gray-500">
                <span>Уверенность: {Math.round(violation.confidence * 100)}%</span>
                {violation.person_id && <span>ID: #{violation.person_id}</span>}
              </div>

              {!violation.acknowledged && (
                <button
                  onClick={handleAcknowledge}
                  disabled={acknowledging}
                  className="btn-primary text-sm py-1.5"
                >
                  {acknowledging ? (
                    'Обработка...'
                  ) : (
                    <>
                      <Check className="w-4 h-4 mr-1" />
                      Подтвердить
                    </>
                  )}
                </button>
              )}

              {violation.acknowledged && (
                <span className="badge-success">
                  <Check className="w-3 h-3 mr-1" />
                  Подтверждено
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Image modal with focus trap */}
      {showImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          onClick={() => setShowImage(false)}
          role="dialog"
          aria-modal="true"
          aria-label={`Изображение нарушения: ${label}`}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setShowImage(false);
          }}
        >
          <div className="relative max-w-4xl max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => setShowImage(false)}
              className="absolute -top-10 right-0 text-white hover:text-gray-300 focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-black rounded"
              aria-label="Закрыть изображение"
              autoFocus
            >
              <X className="w-6 h-6" aria-hidden="true" />
            </button>
            <img
              src={api.getViolationImageUrl(violation.id)}
              alt={`Нарушение: ${label} на камере ${violation.camera_id}`}
              className="max-w-full max-h-[85vh] rounded-lg"
            />
            <div className="absolute bottom-4 left-4 bg-black/70 text-white px-3 py-2 rounded-lg">
              <div className="font-medium">
                {icon} {label}
              </div>
              <div className="text-sm text-gray-300">
                {time} • {violation.camera_id}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
