import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  RefreshCw, Volume2, VolumeX, Maximize, Minimize, X,
  Camera, AlertTriangle, Loader2, Settings, Grid2X2, Grid3X3,
  Plus, ImageIcon, Power
} from 'lucide-react';
import { api } from '@/api/client';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useViolationsStore } from '@/store/violationsStore';
import { Layout } from '@/components/layout/Layout';
import { ViolationCard } from '@/components/violations/ViolationCard';
import { StatsCards, SystemStatus } from '@/components/stats/StatsCards';
import type { Camera as CameraType } from '@/types';

// v2.10.40: Removed DEMO_CAMERAS - show only real cameras from API

// ============================================================================
// Camera Fullscreen Component
// ============================================================================

interface CameraFullscreenProps {
  camera: CameraType;
  onClose: () => void;
}

function CameraFullscreen({ camera, onClose }: CameraFullscreenProps) {
  const [frame, setFrame] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detections, setDetections] = useState<any[]>([]);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const prevBlobUrlRef = React.useRef<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const wsUrl = `ws://${window.location.host}/ws/camera/${camera.id}${token ? `?token=${token}` : ''}`;
    
    let ws: WebSocket | null = null;
    let reconnectTimeout: NodeJS.Timeout;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
          setIsLoading(false);
          setError(null);
        };
        
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.image) {
              // Конвертируем base64 в Blob для экономии памяти
              const byteCharacters = atob(data.image);
              const byteNumbers = new Array(byteCharacters.length);
              for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
              }
              const byteArray = new Uint8Array(byteNumbers);
              const blob = new Blob([byteArray], { type: 'image/jpeg' });
              
              // Освобождаем предыдущий URL
              if (prevBlobUrlRef.current) {
                URL.revokeObjectURL(prevBlobUrlRef.current);
              }
              
              // Создаём новый URL
              const blobUrl = URL.createObjectURL(blob);
              prevBlobUrlRef.current = blobUrl;
              setFrame(blobUrl);
            }
            if (data.detections) {
              setDetections(data.detections);
            }
          } catch (e) {
            console.error('Parse error:', e);
          }
        };
        
        ws.onerror = () => {
          setError('Ошибка подключения');
        };
        
        ws.onclose = () => {
          reconnectTimeout = setTimeout(connect, 3000);
        };
      } catch (e) {
        setError('Не удалось подключиться');
      }
    };
    
    connect();
    
    return () => {
      ws?.close();
      clearTimeout(reconnectTimeout);
      // Очищаем blob URL при размонтировании
      if (prevBlobUrlRef.current) {
        URL.revokeObjectURL(prevBlobUrlRef.current);
        prevBlobUrlRef.current = null;
      }
    };
  }, [camera.id]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'f' || e.key === 'F') toggleFullscreen();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  const toggleFullscreen = async () => {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
        setIsFullscreen(true);
      } else {
        await document.exitFullscreen();
        setIsFullscreen(false);
      }
    } catch (e) {}
  };

  return (
    <div className="fixed inset-0 bg-black z-50 flex flex-col">
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 p-4 flex items-center justify-between bg-gradient-to-b from-black/80 to-transparent z-10">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-red-500 animate-pulse" />
          <span className="text-white font-medium text-xl">{camera.name}</span>
          <span className="text-white/60">{camera.id}</span>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={toggleFullscreen}
            className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white"
            title="Полный экран (F)"
          >
            {isFullscreen ? <Minimize className="w-5 h-5" /> : <Maximize className="w-5 h-5" />}
          </button>
          <button
            onClick={onClose}
            className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white"
            title="Закрыть (Esc)"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>
      
      {/* Video */}
      <div className="flex-1 flex items-center justify-center">
        {isLoading && (
          <div className="text-center">
            <Loader2 className="w-16 h-16 text-white animate-spin mx-auto mb-4" />
            <p className="text-white/80 text-lg">Подключение к камере...</p>
          </div>
        )}
        
        {error && !frame && (
          <div className="text-center">
            <AlertTriangle className="w-16 h-16 text-red-500 mx-auto mb-4" />
            <p className="text-white text-lg mb-2">{error}</p>
            <p className="text-white/60">Повторное подключение...</p>
          </div>
        )}
        
        {frame && (
          <div className="relative w-full h-full flex items-center justify-center">
            <img
              src={frame}
              alt={camera.name}
              className="max-w-full max-h-full object-contain"
              style={{ width: '100%', height: '100%', objectFit: 'contain' }}
            />
            
            {/* Detection boxes */}
            {detections.length > 0 && (
              <svg className="absolute inset-0 w-full h-full pointer-events-none">
                {detections.map((det, idx) => {
                  const isViolation = det.class_name?.toLowerCase().includes('no_') || 
                                     det.class_name?.toLowerCase().includes('no-');
                  const [x1, y1, x2, y2] = det.bbox || [0, 0, 0, 0];
                  
                  return (
                    <g key={idx}>
                      <rect
                        x={`${x1 * 100}%`}
                        y={`${y1 * 100}%`}
                        width={`${(x2 - x1) * 100}%`}
                        height={`${(y2 - y1) * 100}%`}
                        fill="none"
                        stroke={isViolation ? '#ef4444' : '#22c55e'}
                        strokeWidth="3"
                      />
                    </g>
                  );
                })}
              </svg>
            )}
          </div>
        )}
        
        {!frame && !isLoading && !error && (
          <div className="text-center">
            <Camera className="w-16 h-16 text-white/40 mx-auto mb-4" />
            <p className="text-white/60">Ожидание видеопотока...</p>
          </div>
        )}
      </div>
      
      {/* Footer */}
      <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/80 to-transparent">
        <div className="flex items-center justify-between text-white/80">
          <div className="flex items-center gap-4">
            <span>Детекций: {detections.length}</span>
            {detections.some(d => d.class_name?.toLowerCase().includes('no_') || d.class_name?.toLowerCase().includes('no-')) && (
              <span className="flex items-center gap-1 text-red-400 font-medium">
                <AlertTriangle className="w-5 h-5" />
                Нарушения обнаружены!
              </span>
            )}
          </div>
          <span className="text-white/40 text-sm">ESC — закрыть | F — полный экран</span>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Camera Card Component (with click to fullscreen)
// ============================================================================

interface CameraCardProps {
  camera: CameraType;
  onClick: () => void;
  onScreenshot?: (cameraId: string) => void;
  onToggle?: (cameraId: string) => void;
}

function CameraCardNew({ camera, onClick, onScreenshot, onToggle }: CameraCardProps) {
  const [frame, setFrame] = useState<string | null>(null);
  const [status, setStatus] = useState<'loading' | 'connected' | 'error'>('loading');
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);
  const prevBlobUrlRef = React.useRef<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const wsUrl = `ws://${window.location.host}/ws/camera/${camera.id}${token ? `?token=${token}` : ''}`;
    
    let ws: WebSocket | null = null;
    let reconnectTimer: NodeJS.Timeout;
    
    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
          setStatus('connected');
        };
        
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.image) {
              // Конвертируем base64 в Blob для экономии памяти
              const byteCharacters = atob(data.image);
              const byteNumbers = new Array(byteCharacters.length);
              for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
              }
              const byteArray = new Uint8Array(byteNumbers);
              const blob = new Blob([byteArray], { type: 'image/jpeg' });
              
              // Освобождаем предыдущий URL
              if (prevBlobUrlRef.current) {
                URL.revokeObjectURL(prevBlobUrlRef.current);
              }
              
              // Создаём новый URL
              const blobUrl = URL.createObjectURL(blob);
              prevBlobUrlRef.current = blobUrl;
              setFrame(blobUrl);
            }
          } catch (e) {}
        };
        
        ws.onerror = () => {
          setStatus('error');
        };
        
        ws.onclose = () => {
          setStatus('error');
          // Переподключение через 3 сек
          reconnectTimer = setTimeout(connect, 3000);
        };
      } catch (e) {
        setStatus('error');
      }
    };
    
    connect();
    
    return () => {
      clearTimeout(reconnectTimer);
      ws?.close();
      // Очищаем blob URL при размонтировании
      if (prevBlobUrlRef.current) {
        URL.revokeObjectURL(prevBlobUrlRef.current);
        prevBlobUrlRef.current = null;
      }
    };
  }, [camera.id]);

  const handleScreenshot = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!onScreenshot) return;
    
    setSaving(true);
    try {
      await onScreenshot(camera.id);
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!onToggle) return;
    
    setToggling(true);
    try {
      await onToggle(camera.id);
    } finally {
      setToggling(false);
    }
  };

  return (
    <div
      className="relative aspect-video bg-gray-900 rounded-xl overflow-hidden cursor-pointer group hover:ring-2 hover:ring-primary-500 transition-all shadow-lg"
    >
      {/* Camera name */}
      <div className="absolute top-0 left-0 right-0 p-3 bg-gradient-to-b from-black/70 to-transparent z-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`w-2.5 h-2.5 rounded-full ${
              status === 'connected' ? 'bg-green-500' :
              status === 'loading' ? 'bg-yellow-500 animate-pulse' :
              'bg-gray-500'
            }`} />
            <span className="text-white font-medium truncate">{camera.name}</span>
          </div>
          <span className="text-white/60 text-xs">{camera.id}</span>
        </div>
      </div>
      
      {/* Video frame */}
      <div onClick={onClick} className="w-full h-full">
        {frame ? (
          <img
            src={frame}
            alt={camera.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            {status === 'loading' ? (
              <Loader2 className="w-10 h-10 text-white/30 animate-spin" />
            ) : (
              <div className="text-center">
                <Camera className="w-10 h-10 text-white/20 mx-auto mb-2" />
                <p className="text-white/40 text-sm">Нет сигнала</p>
              </div>
            )}
          </div>
        )}
      </div>
      
      {/* Action buttons - bottom */}
      <div className="absolute bottom-0 left-0 right-0 p-2 bg-gradient-to-t from-black/70 to-transparent opacity-0 group-hover:opacity-100 transition-opacity z-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1">
            <button
              onClick={handleScreenshot}
              disabled={saving || !frame}
              className="flex items-center gap-1 px-2 py-1 bg-white/20 hover:bg-white/30 rounded text-white text-xs disabled:opacity-50"
              title="Сохранить снимок для обучения"
            >
              {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <ImageIcon className="w-3 h-3" />}
              Снимок
            </button>
            <button
              onClick={handleToggle}
              disabled={toggling}
              className={`flex items-center gap-1 px-2 py-1 rounded text-white text-xs ${
                camera.status === 'connected' 
                  ? 'bg-green-500/30 hover:bg-red-500/50' 
                  : 'bg-red-500/30 hover:bg-green-500/50'
              }`}
              title={camera.status === 'connected' ? 'Выключить камеру' : 'Включить камеру'}
            >
              {toggling ? <Loader2 className="w-3 h-3 animate-spin" /> : <Power className="w-3 h-3" />}
            </button>
            <a
              href={`/settings?camera=${camera.id}`}
              className="flex items-center gap-1 px-2 py-1 bg-white/20 hover:bg-white/30 rounded text-white text-xs"
              title="Настройки камеры"
              onClick={(e) => e.stopPropagation()}
            >
              <Settings className="w-3 h-3" />
            </a>
          </div>
          <button
            onClick={onClick}
            className="flex items-center gap-1 px-2 py-1 bg-white/20 hover:bg-white/30 rounded text-white text-xs"
            title="Развернуть"
          >
            <Maximize className="w-3 h-3" />
            Открыть
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Dashboard Page
// ============================================================================

export function DashboardPage() {
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [selectedCamera, setSelectedCamera] = useState<CameraType | null>(null);
  const [gridColumns, setGridColumns] = useState<2 | 4>(4);
  const [screenshotMessage, setScreenshotMessage] = useState<string | null>(null);
  
  const { isConnected } = useWebSocket();
  const { recentViolations, setViolations } = useViolationsStore();

  // Fetch cameras
  const { data: cameras = [], refetch: refetchCameras } = useQuery({
    queryKey: ['cameras'],
    queryFn: () => api.getCameras(),
    refetchInterval: 10000,
  });

  // Fetch statistics
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['stats'],
    queryFn: () => api.getStatistics(24),
    refetchInterval: 30000,
  });

  // Fetch recent violations
  const { data: violations } = useQuery({
    queryKey: ['violations', 'recent'],
    queryFn: () => api.getViolations({ limit: 20, hours: 24 }),
    refetchInterval: 30000,
  });

  useEffect(() => {
    if (violations) {
      setViolations(violations);
    }
  }, [violations, setViolations]);

  // Screenshot function
  const handleScreenshot = async (cameraId: string) => {
    try {
      const response = await fetch(`/api/screenshots/camera/${cameraId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setScreenshotMessage(`✓ Снимок сохранён: ${data.filename}`);
        setTimeout(() => setScreenshotMessage(null), 3000);
      } else {
        // Показываем детальное сообщение об ошибке
        const errorMsg = data.detail || data.message || 'Ошибка сохранения снимка';
        setScreenshotMessage(`✗ ${errorMsg}`);
        setTimeout(() => setScreenshotMessage(null), 5000);
      }
    } catch (error) {
      setScreenshotMessage('✗ Ошибка сети');
      setTimeout(() => setScreenshotMessage(null), 3000);
    }
  };

  // Capture all screenshots
  const handleCaptureAll = async () => {
    try {
      const response = await fetch('/api/screenshots/capture', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });
      
      const data = await response.json();
      
      if (response.ok) {
        if (data.total > 0) {
          setScreenshotMessage(`✓ Сохранено ${data.total} снимков`);
        } else {
          setScreenshotMessage(`⚠ ${data.message || 'Нет доступных кадров'}`);
        }
        setTimeout(() => setScreenshotMessage(null), 3000);
      } else {
        setScreenshotMessage(`✗ ${data.detail || 'Ошибка'}`);
        setTimeout(() => setScreenshotMessage(null), 5000);
      }
    } catch (error) {
      setScreenshotMessage('✗ Ошибка сети');
      setTimeout(() => setScreenshotMessage(null), 3000);
    }
  };

  // Toggle camera enabled state
  const handleToggle = async (cameraId: string) => {
    try {
      const response = await fetch(`/api/settings/cameras/${cameraId}/toggle`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });
      
      if (response.ok) {
        const data = await response.json();
        setScreenshotMessage(data.enabled ? `✓ Камера ${cameraId} включена` : `✓ Камера ${cameraId} выключена`);
        setTimeout(() => setScreenshotMessage(null), 3000);
        // Обновляем список камер
        refetchCameras();
      } else {
        setScreenshotMessage('✗ Ошибка переключения камеры');
        setTimeout(() => setScreenshotMessage(null), 3000);
      }
    } catch (error) {
      setScreenshotMessage('✗ Ошибка сети');
      setTimeout(() => setScreenshotMessage(null), 3000);
    }
  };

  // v2.10.40: Show only real cameras from API (no demo mixing)
  const displayCameras: CameraType[] = cameras;

  const camerasOnline = cameras.filter((c: CameraType) => c.status === 'connected').length;

  return (
    <Layout isConnected={isConnected}>
      {/* Screenshot notification */}
      {screenshotMessage && (
        <div className="fixed top-4 right-4 z-50 bg-gray-900 text-white px-4 py-2 rounded-lg shadow-lg animate-slide-in">
          {screenshotMessage}
        </div>
      )}

      {/* Fullscreen camera view */}
      {selectedCamera && (
        <CameraFullscreen 
          camera={selectedCamera} 
          onClose={() => setSelectedCamera(null)} 
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Мониторинг</h1>
          <p className="text-gray-600">Контроль СИЗ в реальном времени • {cameras.length} камер</p>
        </div>
        <div className="flex items-center gap-2">
          {/* Grid toggle */}
          <div className="flex bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setGridColumns(2)}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors flex items-center gap-1 ${
                gridColumns === 2 ? 'bg-white shadow text-gray-900' : 'text-gray-500'
              }`}
              title="2 столбца"
            >
              <Grid2X2 className="w-4 h-4" />
            </button>
            <button
              onClick={() => setGridColumns(4)}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors flex items-center gap-1 ${
                gridColumns === 4 ? 'bg-white shadow text-gray-900' : 'text-gray-500'
              }`}
              title="4 столбца"
            >
              <Grid3X3 className="w-4 h-4" />
            </button>
          </div>
          
          <button
            onClick={() => setSoundEnabled(!soundEnabled)}
            className={`btn-ghost p-2 ${soundEnabled ? 'text-primary-600' : 'text-gray-400'}`}
            title={soundEnabled ? 'Выключить звук' : 'Включить звук'}
          >
            {soundEnabled ? <Volume2 className="w-5 h-5" /> : <VolumeX className="w-5 h-5" />}
          </button>
          
          <button
            onClick={handleCaptureAll}
            className="btn-outline"
            title="Сделать снимки со всех камер"
          >
            <ImageIcon className="w-4 h-4 mr-2" />
            Снимки
          </button>
          
          <button
            onClick={() => refetchCameras()}
            className="btn-outline"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Обновить
          </button>

          <a href="/settings" className="btn-primary">
            <Settings className="w-4 h-4 mr-2" />
            Настройки
          </a>
          
          <a href="/settings?action=add_camera" className="btn-success">
            <Plus className="w-4 h-4 mr-2" />
            Добавить камеру
          </a>
        </div>
      </div>

      {/* Statistics */}
      <div className="mb-6">
        <StatsCards stats={stats ?? null} loading={statsLoading} />
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        {/* Cameras grid - dynamic count */}
        <div className="xl:col-span-3">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Camera className="w-5 h-5 text-gray-400" />
              Камеры
              <span className="text-sm font-normal text-gray-500">
                {camerasOnline}/{displayCameras.length} онлайн
              </span>
            </h2>
            {displayCameras.length > 0 && (
              <p className="text-sm text-gray-500">
                👆 Нажмите на камеру для увеличения
              </p>
            )}
          </div>
          
          {displayCameras.length === 0 ? (
            <div className="card p-12 text-center">
              <Camera className="w-16 h-16 mx-auto mb-4 text-gray-300" />
              <p className="text-lg font-medium text-gray-500">Камеры не настроены</p>
              <p className="text-sm text-gray-400 mt-1">Добавьте камеры в configs/cameras.yaml</p>
            </div>
          ) : (
            <div className={`grid gap-4 ${
              gridColumns === 2 
                ? 'grid-cols-1 md:grid-cols-2' 
                : 'grid-cols-2 lg:grid-cols-4'
            }`}>
              {displayCameras.map((camera) => (
                <CameraCardNew
                  key={camera.id}
                  camera={camera}
                  onClick={() => setSelectedCamera(camera)}
                  onScreenshot={handleScreenshot}
                  onToggle={handleToggle}
                />
              ))}
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* System status */}
          <SystemStatus
            camerasOnline={camerasOnline}
            camerasTotal={displayCameras.length}
            isConnected={isConnected}
          />

          {/* Recent violations */}
          <div className="card">
            <div className="p-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-900">
                Последние нарушения
                {recentViolations.filter((v) => !v.acknowledged).length > 0 && (
                  <span className="ml-2 badge-danger">
                    {recentViolations.filter((v) => !v.acknowledged).length}
                  </span>
                )}
              </h2>
            </div>
            <div className="max-h-[400px] overflow-y-auto">
              {recentViolations.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  <p>Нарушений не обнаружено</p>
                  <p className="text-sm mt-1">Система работает штатно</p>
                </div>
              ) : (
                <div className="divide-y divide-gray-100">
                  {recentViolations.slice(0, 10).map((violation) => (
                    <div key={violation.id} className="p-2">
                      <ViolationCard violation={violation} compact />
                    </div>
                  ))}
                </div>
              )}
            </div>
            {recentViolations.length > 10 && (
              <div className="p-3 border-t border-gray-200 text-center">
                <a href="/violations" className="text-sm text-primary-600 hover:text-primary-700 font-medium">
                  Показать все →
                </a>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}
