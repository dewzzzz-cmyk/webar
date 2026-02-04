import React, { useState, useEffect, useCallback } from 'react';
import {
  Camera, Cpu, Download, Trash2, Check, Loader2, Plus, X, Play,
  Settings, Zap, HardDrive, Thermometer, RefreshCw,
  Eye, EyeOff, AlertCircle, CheckCircle, Video, Save, ExternalLink,
  Image as ImageIcon, Database, List
} from 'lucide-react';
import { Layout } from '@/components/layout/Layout';
import { useWebSocket } from '@/hooks/useWebSocket';
import { api } from '@/api/client';
import { DatasetCatalog } from '@/components/training/DatasetCatalog';

// ============================================================================
// Types
// ============================================================================

interface ModelInfo {
  id: string;
  name: string;
  description: string;
  size_mb: number;
  speed: string;
  accuracy: string;
  recommended_gpu: string;
  is_downloaded: boolean;
  is_active: boolean;
  file_path: string | null;
  // v2.10.40 - HuggingFace catalog fields
  type?: string;
  source?: string;
  recommended?: boolean;
  warning?: string;
  classes?: string[] | number;
}

interface GPUInfo {
  available: boolean;
  name: string | null;
  memory_total_mb: number | null;
  memory_used_mb: number | null;
  memory_free_mb: number | null;
  cuda_version: string | null;
  driver_version: string | null;
  temperature: number | null;
  utilization: number | null;
}

interface CameraConfig {
  id: string;
  name: string;
  rtsp_url: string;
  fps: number;
  zone_id: string | null;
  enabled: boolean;
  status?: string;
}

interface DownloadProgress {
  model_id: string;
  status: string;
  progress: number;
  error: string | null;
}

// Model download URLs for manual download
const MODEL_URLS: Record<string, string> = {
  yolov8n: 'https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8n.pt',
  yolov8s: 'https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8s.pt',
  yolov8m: 'https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8m.pt',
  yolov8l: 'https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8l.pt',
  yolov8x: 'https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8x.pt',
  yolov11n: 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt',
  yolov11m: 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11m.pt',
  yolov11x: 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11x.pt',
};

// FALLBACK - показываем если API не вернул модели
const FALLBACK_MODELS: ModelInfo[] = [
  { id: 'yolov8n', name: 'YOLOv8 Nano', description: 'Быстрая модель для слабых GPU', size_mb: 6.3, speed: 'Быстрая', accuracy: 'Базовая', recommended_gpu: 'GTX 1650+', is_downloaded: false, is_active: false, file_path: null },
  { id: 'yolov8s', name: 'YOLOv8 Small', description: 'Баланс скорости и точности', size_mb: 22.5, speed: 'Средняя', accuracy: 'Хорошая', recommended_gpu: 'RTX 2060+', is_downloaded: false, is_active: false, file_path: null },
  { id: 'yolov8m', name: 'YOLOv8 Medium', description: 'Высокая точность', size_mb: 52.0, speed: 'Средняя', accuracy: 'Высокая', recommended_gpu: 'RTX 3060+', is_downloaded: false, is_active: false, file_path: null },
  { id: 'yolov8l', name: 'YOLOv8 Large', description: 'Максимальная точность', size_mb: 87.7, speed: 'Медленная', accuracy: 'Очень высокая', recommended_gpu: 'RTX 3080+', is_downloaded: false, is_active: false, file_path: null },
  { id: 'yolov8x', name: 'YOLOv8 XLarge', description: 'Максимум для RTX 4090/5090', size_mb: 136.7, speed: 'Медленная', accuracy: 'Максимальная', recommended_gpu: 'RTX 4080+', is_downloaded: false, is_active: false, file_path: null },
  { id: 'yolov11n', name: 'YOLOv11 Nano (NEW)', description: 'Новейшая архитектура, быстрая', size_mb: 5.4, speed: 'Очень быстрая', accuracy: 'Хорошая', recommended_gpu: 'GTX 1650+', is_downloaded: false, is_active: false, file_path: null },
  { id: 'yolov11m', name: 'YOLOv11 Medium (NEW)', description: 'Новейшая архитектура, баланс', size_mb: 38.8, speed: 'Средняя', accuracy: 'Высокая', recommended_gpu: 'RTX 3060+', is_downloaded: false, is_active: false, file_path: null },
  { id: 'yolov11x', name: 'YOLOv11 XLarge (NEW)', description: 'Новейшая архитектура для RTX 5090', size_mb: 109.3, speed: 'Медленная', accuracy: 'Максимальная', recommended_gpu: 'RTX 4080+', is_downloaded: false, is_active: false, file_path: null },
];

// ============================================================================
// API Functions
// ============================================================================

const settingsApi = {
  // Models (legacy endpoint)
  async getModels(): Promise<ModelInfo[]> {
    const response = await api.get<ModelInfo[]>('/settings/models');
    return response.data;
  },
  
  // Models Catalog (v2.10.40 - HuggingFace)
  async getModelsCatalog(): Promise<{ models: ModelInfo[]; total: number; active_model_id: string | null }> {
    const response = await api.get<{ models: ModelInfo[]; total: number; active_model_id: string | null }>('/models/catalog');
    return response.data;
  },
  
  async getActiveModel(): Promise<{ model_id: string | null; model_name: string | null; status: string }> {
    const response = await api.get<{ model_id: string | null; model_name: string | null; status: string }>('/models/active');
    return response.data;
  },
  
  async activateModelNew(modelId: string): Promise<{ success: boolean; message: string; model_id: string; model_name: string }> {
    const response = await api.post<{ success: boolean; message: string; model_id: string; model_name: string }>('/models/activate', { model_id: modelId });
    return response.data;
  },
  
  async getDetectorStatus(): Promise<{ status: string; model: string; fps: number }> {
    const response = await api.get<{ status: string; model: string; fps: number }>('/models/detector/status');
    return response.data;
  },
  
  // v2.10.46: Use new models API for download
  async downloadModel(modelId: string): Promise<{ status: string }> {
    // Try new HuggingFace-aware endpoint first
    try {
      const response = await api.post<{ status: string }>(`/models/${modelId}/download`);
      return response.data;
    } catch (err: any) {
      // Fallback to legacy endpoint for base models
      if (err.response?.status === 404) {
        const response = await api.post<{ status: string }>(`/settings/models/${modelId}/download`);
        return response.data;
      }
      throw err;
    }
  },
  
  async getDownloadStatus(modelId: string): Promise<DownloadProgress> {
    // Try new endpoint first
    try {
      const response = await api.get<DownloadProgress>(`/models/${modelId}/download-status`);
      return response.data;
    } catch {
      const response = await api.get<DownloadProgress>(`/settings/models/${modelId}/download-status`);
      return response.data;
    }
  },
  
  async activateModel(modelId: string): Promise<{ status: string }> {
    // Try new API first, fallback to legacy
    try {
      await settingsApi.activateModelNew(modelId);
      return { status: 'ok' };
    } catch {
      const response = await api.post<{ status: string }>(`/settings/models/${modelId}/activate`);
      return response.data;
    }
  },
  
  async deleteModel(modelId: string): Promise<{ status: string }> {
    // Try new endpoint first
    try {
      const response = await api.delete<{ status: string }>(`/models/${modelId}`);
      return response.data;
    } catch {
      const response = await api.delete<{ status: string }>(`/settings/models/${modelId}`);
      return response.data;
    }
  },
  
  // GPU
  async getGPUInfo(): Promise<GPUInfo> {
    const response = await api.get<GPUInfo>('/settings/gpu');
    return response.data;
  },
  
  // Cameras
  async getCameras(): Promise<CameraConfig[]> {
    const response = await api.get<CameraConfig[]>('/settings/cameras');
    return response.data;
  },
  
  async createCamera(camera: Omit<CameraConfig, 'status'>): Promise<CameraConfig> {
    const response = await api.post<CameraConfig>('/settings/cameras', camera);
    return response.data;
  },
  
  async updateCamera(id: string, camera: Partial<CameraConfig>): Promise<CameraConfig> {
    const response = await api.put<CameraConfig>(`/settings/cameras/${id}`, camera);
    return response.data;
  },
  
  async deleteCamera(id: string): Promise<void> {
    await api.delete<void>(`/settings/cameras/${id}`);
  },
  
  async testCamera(id: string): Promise<{ status: string; message: string }> {
    const response = await api.post<{ status: string; message: string }>(`/settings/cameras/${id}/test`);
    return response.data;
  },
};

// ============================================================================
// Camera Modal Component
// ============================================================================

interface CameraModalProps {
  camera: CameraConfig | null;
  onSave: (camera: Omit<CameraConfig, 'status'>) => Promise<void>;
  onClose: () => void;
  isLoading: boolean;
}

function CameraModal({ camera, onSave, onClose, isLoading }: CameraModalProps) {
  const [form, setForm] = useState({
    id: camera?.id || '',
    name: camera?.name || '',
    rtsp_url: camera?.rtsp_url || '',
    fps: camera?.fps || 5,
    zone_id: camera?.zone_id || '',
    enabled: camera?.enabled ?? true,
  });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generateId = (name: string) => {
    return 'cam_' + name
      .toLowerCase()
      .replace(/[а-яё]/gi, (char) => {
        const map: Record<string, string> = {
          'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
          'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
          'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
          'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
          'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        };
        return map[char.toLowerCase()] || char;
      })
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '')
      .substring(0, 30);
  };

  const handleNameChange = (name: string) => {
    setForm(prev => ({
      ...prev,
      name,
      id: camera ? prev.id : generateId(name)
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    
    if (!form.name.trim()) {
      setError('Введите название камеры');
      return;
    }
    if (!form.rtsp_url.trim()) {
      setError('Введите RTSP URL');
      return;
    }
    
    try {
      await onSave({
        id: form.id,
        name: form.name,
        rtsp_url: form.rtsp_url,
        fps: form.fps,
        zone_id: form.zone_id || null,
        enabled: form.enabled,
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Ошибка сохранения');
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">
            {camera ? 'Редактировать камеру' : 'Добавить камеру'}
          </h3>
          <button onClick={onClose} className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Название камеры *</label>
            <input
              type="text"
              className="input"
              value={form.name}
              onChange={(e) => handleNameChange(e.target.value)}
              placeholder="Входная группа"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">ID камеры</label>
            <input
              type="text"
              className="input bg-gray-100"
              value={form.id}
              readOnly={!!camera}
              onChange={(e) => !camera && setForm(prev => ({ ...prev, id: e.target.value }))}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">RTSP URL *</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                className="input pr-10 font-mono text-sm"
                value={form.rtsp_url}
                onChange={(e) => setForm(prev => ({ ...prev, rtsp_url: e.target.value }))}
                placeholder="rtsp://admin:password@192.168.1.100:554/stream"
              />
              <button
                type="button"
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-500 hover:text-gray-700"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <p className="mt-1 text-sm text-gray-500">
              Hikvision: rtsp://admin:pass@IP:554/Streaming/Channels/101
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">FPS</label>
              <input
                type="number"
                className="input"
                value={form.fps}
                onChange={(e) => setForm(prev => ({ ...prev, fps: parseInt(e.target.value) || 5 }))}
                min={1}
                max={30}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Зона</label>
              <select
                className="input"
                value={form.zone_id || ''}
                onChange={(e) => setForm(prev => ({ ...prev, zone_id: e.target.value }))}
              >
                <option value="">Без зоны</option>
                <option value="zone_welding">Сварочный участок</option>
                <option value="zone_entrance">Входная группа</option>
                <option value="zone_warehouse">Склад</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="camera-enabled"
              className="w-4 h-4 text-primary-600-600 border-gray-300 rounded focus:ring-primary-500"
              checked={form.enabled}
              onChange={(e) => setForm(prev => ({ ...prev, enabled: e.target.checked }))}
            />
            <label htmlFor="camera-enabled" className="text-sm font-medium text-gray-700 cursor-pointer">
              Камера активна
            </label>
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t border-gray-200">
            <button type="button" className="btn-ghost px-4 py-2" onClick={onClose}>Отмена</button>
            <button type="submit" className="btn-primary flex items-center gap-2" disabled={isLoading}>
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {camera ? 'Сохранить' : 'Добавить'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================================================
// Model Card Component  
// ============================================================================

interface ModelCardProps {
  model: ModelInfo;
  downloadProgress: DownloadProgress | null;
  onDownload: () => void;
  onActivate: () => void;
  onDelete: () => void;
  isDownloading: boolean;
}

// v2.10.55: Компактный ModelCard
function ModelCard({ model, downloadProgress, onDownload, onActivate, onDelete, isDownloading }: ModelCardProps) {
  const downloadUrl = MODEL_URLS[model.id];
  const [showUrl, setShowUrl] = useState(false);

  return (
    <div className={`bg-white border rounded-lg p-3 ${model.is_active ? 'border-primary-500 border-2 bg-primary-50/30' : 'border-gray-200'}`}>
      <div className="flex items-center justify-between gap-3">
        {/* Левая часть: название и бейджи */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-gray-900 truncate">{model.name}</span>
            <span className="text-xs text-gray-500">{model.size_mb || '?'} MB</span>
            {model.is_active && <span className="px-1.5 py-0.5 bg-primary-100 text-primary-700 text-xs rounded">✓ Активна</span>}
            {model.is_downloaded && !model.is_active && <span className="px-1.5 py-0.5 bg-green-100 text-green-700 text-xs rounded">Скачана</span>}
            {model.recommended && <span className="px-1.5 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded">⭐</span>}
            {model.type === 'ppe' && <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 text-xs rounded">PPE</span>}
          </div>
          <p className="text-xs text-gray-500 truncate mt-0.5">{model.description}</p>
          {model.warning && (
            <p className="text-xs text-amber-600 flex items-center gap-1 mt-0.5">
              <AlertCircle className="w-3 h-3 flex-shrink-0" />{model.warning}
            </p>
          )}
        </div>

        {/* Правая часть: кнопки */}
        <div className="flex items-center gap-1 flex-shrink-0">
          {downloadProgress && downloadProgress.status === 'downloading' ? (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>{downloadProgress.progress}%</span>
            </div>
          ) : !model.is_downloaded ? (
            <>
              <button 
                className="px-3 py-1.5 bg-primary-600 text-white text-xs rounded hover:bg-primary-700 flex items-center gap-1"
                onClick={onDownload} 
                disabled={isDownloading}
                title="Скачать через API"
              >
                <Download className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Скачать</span>
              </button>
              {downloadUrl && (
                <button 
                  className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded"
                  onClick={() => setShowUrl(!showUrl)}
                  title="Показать ссылку"
                >
                  <ExternalLink className="w-4 h-4" />
                </button>
              )}
            </>
          ) : model.is_active ? (
            <span className="px-3 py-1.5 bg-green-100 text-green-700 text-xs rounded flex items-center gap-1">
              <Check className="w-3.5 h-3.5" />Используется
            </span>
          ) : (
            <>
              <button 
                className="px-3 py-1.5 bg-primary-600 text-white text-xs rounded hover:bg-primary-700 flex items-center gap-1"
                onClick={onActivate}
                title="Активировать модель"
              >
                <Play className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Активировать</span>
              </button>
              <button 
                className="p-1.5 text-red-500 hover:text-red-700 hover:bg-red-50 rounded"
                onClick={onDelete}
                title="Удалить"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </>
          )}
        </div>
      </div>

      {/* Ошибка скачивания */}
      {downloadProgress && downloadProgress.status === 'error' && (
        <div className="mt-2 flex items-center gap-2 p-2 bg-red-50 border border-red-200 rounded text-red-700 text-xs">
          <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
          {downloadProgress.error}
        </div>
      )}

      {/* Прямая ссылка (сворачиваемая) */}
      {showUrl && downloadUrl && (
        <div className="mt-2 p-2 bg-gray-50 rounded border text-xs">
          <div className="flex items-center gap-2">
            <code className="flex-1 break-all select-all text-gray-600">{downloadUrl}</code>
            <button 
              className="p-1 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded flex-shrink-0"
              onClick={() => navigator.clipboard.writeText(downloadUrl)}
              title="Копировать"
            >
              📋
            </button>
            <a 
              href={downloadUrl} 
              target="_blank" 
              rel="noopener noreferrer" 
              className="p-1 text-primary-600 hover:text-primary-700 hover:bg-primary-50 rounded flex-shrink-0"
              title="Открыть"
            >
              ↗
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Settings Page
// ============================================================================

export function SettingsPage() {
  const { isConnected } = useWebSocket();
  
  // v2.10.59 - Переименовано models → detector для ясности
  const [activeTab, setActiveTab] = useState<'cameras' | 'detector' | 'datasets' | 'system'>('cameras');
  const [cameraModal, setCameraModal] = useState<{ open: boolean; camera: CameraConfig | null }>({ open: false, camera: null });
  const [batchCameraModal, setBatchCameraModal] = useState(false);
  const [batchUrls, setBatchUrls] = useState('');
  
  // Data states
  const [cameras, setCameras] = useState<CameraConfig[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [gpuInfo, setGpuInfo] = useState<GPUInfo | null>(null);
  
  // Detection settings state
  const [detectionSettings, setDetectionSettings] = useState({
    confidence_threshold: 0.5,
    device: 'auto',
    fp16: true
  });
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null);
  
  // Loading states
  const [loadingCameras, setLoadingCameras] = useState(true);
  const [loadingModels, setLoadingModels] = useState(true);
  const [loadingGpu, setLoadingGpu] = useState(true);
  const [savingCamera, setSavingCamera] = useState(false);
  const [downloadingModel, setDownloadingModel] = useState<string | null>(null);
  const [downloadProgress, setDownloadProgress] = useState<Record<string, DownloadProgress>>({});
  const [testResults, setTestResults] = useState<Record<string, { status: string; message: string }>>({});
  const [capturingScreenshots, setCapturingScreenshots] = useState(false);
  
  // Error states
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [camerasError, setCamerasError] = useState<string | null>(null);

  // Handle URL parameters (e.g., ?action=add_camera, ?camera=cam_1)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const action = params.get('action');
    const cameraId = params.get('camera');
    
    if (action === 'add_camera') {
      setActiveTab('cameras');
      setCameraModal({ open: true, camera: null });
      // Clean up URL
      window.history.replaceState({}, '', '/settings');
    } else if (cameraId) {
      setActiveTab('cameras');
      // Will open edit modal after cameras are loaded
      const checkAndOpenModal = () => {
        const camera = cameras.find(c => c.id === cameraId);
        if (camera) {
          setCameraModal({ open: true, camera });
          window.history.replaceState({}, '', '/settings');
        }
      };
      // Check immediately and after cameras load
      if (cameras.length > 0) {
        checkAndOpenModal();
      } else {
        const timer = setTimeout(checkAndOpenModal, 1000);
        return () => clearTimeout(timer);
      }
    }
  }, [cameras]);

  // Use fallback models if API fails or returns empty
  const displayModels = models.length > 0 ? models : FALLBACK_MODELS;
  
  // ========================================================================
  // Detection Settings Functions
  // ========================================================================
  
  const loadDetectionSettings = useCallback(async () => {
    try {
      const response = await fetch('/api/settings/detection', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      if (response.ok) {
        const data = await response.json();
        setDetectionSettings(data);
      }
    } catch (err) {
      console.error('Error loading detection settings:', err);
    }
  }, []);
  
  const saveDetectionSettings = async () => {
    setSavingSettings(true);
    try {
      const params = new URLSearchParams({
        confidence_threshold: detectionSettings.confidence_threshold.toString(),
        device: detectionSettings.device,
        fp16: detectionSettings.fp16.toString()
      });
      
      const response = await fetch(`/api/settings/detection?${params}`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      
      if (response.ok) {
        setSettingsMessage('✓ Настройки сохранены');
        setTimeout(() => setSettingsMessage(null), 3000);
      } else {
        setSettingsMessage('✗ Ошибка сохранения');
        setTimeout(() => setSettingsMessage(null), 3000);
      }
    } catch (err) {
      setSettingsMessage('✗ Ошибка сети');
      setTimeout(() => setSettingsMessage(null), 3000);
    } finally {
      setSavingSettings(false);
    }
  };
  
  // ========================================================================
  // Screenshots Function
  // ========================================================================
  
  const captureScreenshots = async () => {
    setCapturingScreenshots(true);
    try {
      const response = await fetch('/api/screenshots/capture', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        setSettingsMessage(`✓ Сохранено ${data.total} снимков`);
        setTimeout(() => setSettingsMessage(null), 3000);
      } else {
        setSettingsMessage('✗ Ошибка создания снимков');
        setTimeout(() => setSettingsMessage(null), 3000);
      }
    } catch (err) {
      setSettingsMessage('✗ Ошибка сети');
      setTimeout(() => setSettingsMessage(null), 3000);
    } finally {
      setCapturingScreenshots(false);
    }
  };
  
  // ========================================================================
  // Data Loading
  // ========================================================================

  const loadCameras = useCallback(async () => {
    try {
      setLoadingCameras(true);
      setCamerasError(null);
      const data = await settingsApi.getCameras();
      setCameras(data);
    } catch (err: any) {
      console.error('Error loading cameras:', err);
      setCamerasError(err.message || 'Ошибка загрузки камер');
    } finally {
      setLoadingCameras(false);
    }
  }, []);

  const loadModels = useCallback(async () => {
    try {
      setLoadingModels(true);
      setModelsError(null);
      
      // Try new HuggingFace catalog API first (v2.10.40)
      try {
        const catalog = await settingsApi.getModelsCatalog();
        // Transform to ModelInfo format
        const transformedModels: ModelInfo[] = catalog.models.map(m => ({
          id: m.id,
          name: m.name,
          description: m.description,
          size_mb: m.size_mb || 0,
          speed: m.type === 'ppe' ? 'Высокая' : 'Средняя',
          accuracy: m.recommended ? 'Высокая' : 'Средняя',
          recommended_gpu: m.size_mb && m.size_mb > 100 ? 'RTX 3060+' : 'GTX 1650+',
          is_downloaded: m.is_downloaded,
          is_active: m.is_active,
          file_path: null,
          // v2.10.40 fields
          type: m.type,
          source: m.source,
          recommended: m.recommended,
          warning: m.warning,
          classes: m.classes,
        }));
        setModels(transformedModels);
        return;
      } catch (catalogErr) {
        console.log('HuggingFace catalog API not available, falling back to legacy');
      }
      
      // Fallback to legacy API
      const data = await settingsApi.getModels();
      setModels(data);
    } catch (err: any) {
      console.error('Error loading models:', err);
      setModelsError(err.message || 'Ошибка загрузки моделей');
    } finally {
      setLoadingModels(false);
    }
  }, []);

  const loadGpuInfo = useCallback(async () => {
    try {
      setLoadingGpu(true);
      const data = await settingsApi.getGPUInfo();
      setGpuInfo(data);
    } catch (err) {
      console.error('Error loading GPU info:', err);
      setGpuInfo({ available: false, name: null, memory_total_mb: null, memory_used_mb: null, memory_free_mb: null, cuda_version: null, driver_version: null, temperature: null, utilization: null });
    } finally {
      setLoadingGpu(false);
    }
  }, []);

  useEffect(() => {
    loadCameras();
    loadModels();
    loadGpuInfo();
    loadDetectionSettings();
  }, [loadCameras, loadModels, loadGpuInfo, loadDetectionSettings]);

  // v2.10.67: Auto-refresh GPU stats every 30s
  useEffect(() => {
    const gpuInterval = setInterval(() => {
      loadGpuInfo();
    }, 30000);
    return () => clearInterval(gpuInterval);
  }, [loadGpuInfo]);

  // Poll download status
  useEffect(() => {
    if (!downloadingModel) return;
    
    const interval = setInterval(async () => {
      try {
        const status = await settingsApi.getDownloadStatus(downloadingModel);
        setDownloadProgress(prev => ({ ...prev, [downloadingModel]: status }));
        
        if (status.status === 'completed' || status.status === 'error') {
          setDownloadingModel(null);
          if (status.status === 'completed') {
            loadModels();
          }
        }
      } catch (err) {
        console.error('Error getting download status:', err);
      }
    }, 1000);
    
    return () => clearInterval(interval);
  }, [downloadingModel, loadModels]);

  // ========================================================================
  // Camera Actions
  // ========================================================================

  const handleSaveCamera = async (camera: Omit<CameraConfig, 'status'>) => {
    setSavingCamera(true);
    try {
      if (cameraModal.camera) {
        await settingsApi.updateCamera(camera.id, camera);
      } else {
        await settingsApi.createCamera(camera);
      }
      await loadCameras();
      setCameraModal({ open: false, camera: null });
    } finally {
      setSavingCamera(false);
    }
  };

  const handleDeleteCamera = async (id: string) => {
    if (!confirm('Удалить камеру?')) return;
    try {
      await settingsApi.deleteCamera(id);
      await loadCameras();
    } catch (err) {
      console.error('Error deleting camera:', err);
    }
  };

  const handleTestCamera = async (id: string) => {
    setTestResults(prev => ({ ...prev, [id]: { status: 'loading', message: 'Проверка...' } }));
    try {
      const result = await settingsApi.testCamera(id);
      setTestResults(prev => ({ ...prev, [id]: result }));
    } catch (err: any) {
      setTestResults(prev => ({ ...prev, [id]: { status: 'error', message: err.message || 'Ошибка' } }));
    }
  };

  // v2.10.55: Пакетное добавление камер
  const handleBatchAddCameras = async () => {
    const urls = batchUrls.split('\n').map(u => u.trim()).filter(u => u.length > 0);
    if (urls.length === 0) {
      alert('Введите хотя бы одну RTSP ссылку');
      return;
    }
    
    const maxCameras = 8 - cameras.length;
    if (urls.length > maxCameras) {
      alert(`Можно добавить максимум ${maxCameras} камер (лимит 8)`);
      return;
    }
    
    setSavingCamera(true);
    let added = 0;
    
    for (let i = 0; i < urls.length; i++) {
      const url = urls[i];
      // Определяем номер камеры
      const cameraNumber = cameras.length + i + 1;
      const cameraId = `cam_${cameraNumber}`;
      
      // Проверяем что такой ID ещё не существует
      if (cameras.some(c => c.id === cameraId)) {
        continue;
      }
      
      try {
        await settingsApi.createCamera({
          id: cameraId,
          name: `Камера ${cameraNumber}`,
          rtsp_url: url,
          enabled: true,
          fps: 5,
          zone_id: ''
        });
        added++;
      } catch (err) {
        console.error(`Error adding camera ${cameraNumber}:`, err);
      }
    }
    
    setSavingCamera(false);
    setBatchCameraModal(false);
    setBatchUrls('');
    await loadCameras();
    
    if (added > 0) {
      alert(`Добавлено ${added} камер`);
    }
  };

  // ========================================================================
  // Model Actions
  // ========================================================================

  const handleDownloadModel = async (modelId: string) => {
    try {
      setDownloadingModel(modelId);
      setDownloadProgress(prev => ({ ...prev, [modelId]: { model_id: modelId, status: 'pending', progress: 0, error: null } }));
      await settingsApi.downloadModel(modelId);
    } catch (err: any) {
      setDownloadProgress(prev => ({ ...prev, [modelId]: { model_id: modelId, status: 'error', progress: 0, error: err.message } }));
      setDownloadingModel(null);
    }
  };

  const handleActivateModel = async (modelId: string) => {
    try {
      await settingsApi.activateModel(modelId);
      await loadModels();
    } catch (err) {
      console.error('Error activating model:', err);
    }
  };

  const handleDeleteModel = async (modelId: string) => {
    if (!confirm('Удалить скачанную модель?')) return;
    try {
      await settingsApi.deleteModel(modelId);
      await loadModels();
    } catch (err) {
      console.error('Error deleting model:', err);
    }
  };

  const activeModel = displayModels.find(m => m.is_active);

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center gap-3 mb-6">
          <Settings className="w-8 h-8 text-primary-600" />
          <div>
            <h1 className="text-2xl font-bold">Настройки системы</h1>
            <p className="text-gray-500">Управление камерами, моделями и параметрами детекции</p>
          </div>
        </div>

        <div className="flex bg-gray-100 rounded-lg p-1 mb-6 bg-gray-100 p-1 w-fit">
          <button className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'cameras' ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'}`} onClick={() => setActiveTab('cameras')}>
            <Camera className="w-4 h-4 mr-2" />Камеры<span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 ml-2">{cameras.length}/8</span>
          </button>
          <button className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'detector' ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'}`} onClick={() => setActiveTab('detector')}>
            <Cpu className="w-4 h-4 mr-2" />Детектор
          </button>
          <button className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'datasets' ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'}`} onClick={() => setActiveTab('datasets')}>
            <Database className="w-4 h-4 mr-2" />Каталог
          </button>
          <button className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'system' ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'}`} onClick={() => setActiveTab('system')}>
            <Settings className="w-4 h-4 mr-2" />Система
          </button>
        </div>

        {/* Cameras Tab */}
        {activeTab === 'cameras' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-lg font-semibold">IP Камеры (RTSP)</h2>
                <p className="text-sm text-gray-500">Добавьте до 8 камер для мониторинга</p>
              </div>
              <div className="flex gap-2">
                <button className="btn-ghost text-sm px-3 py-1.5" onClick={loadCameras}>
                  <RefreshCw className={`w-4 h-4 ${loadingCameras ? 'animate-spin' : ''}`} />
                </button>
                <button className="btn-outline text-sm" onClick={() => setBatchCameraModal(true)} disabled={cameras.length >= 8}>
                  <List className="w-4 h-4" />Пакетом
                </button>
                <button className="btn-primary" onClick={() => setCameraModal({ open: true, camera: null })} disabled={cameras.length >= 8}>
                  <Plus className="w-4 h-4" />Добавить
                </button>
              </div>
            </div>

            {loadingCameras ? (
              <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-primary-600" /></div>
            ) : camerasError ? (
              <div className="card bg-white border border-red-300">
                <div className="p-4 items-center text-center py-12">
                  <AlertCircle className="w-16 h-16 text-red-600 mb-4" />
                  <h3 className="text-lg font-semibold text-red-600">Ошибка загрузки камер</h3>
                  <p className="text-gray-500 mb-2">{camerasError}</p>
                  <p className="text-sm text-gray-400 mb-4">
                    Проверьте что API сервис запущен: <code className="bg-gray-200 px-1 rounded">curl http://localhost:8000/health</code>
                  </p>
                  <button className="btn-outline" onClick={loadCameras}>
                    <RefreshCw className="w-4 h-4" />Повторить
                  </button>
                </div>
              </div>
            ) : cameras.length === 0 ? (
              <div className="card bg-white border border-gray-200">
                <div className="p-4 items-center text-center py-12">
                  <Video className="w-16 h-16 text-gray-300 mb-4" />
                  <h3 className="text-lg font-semibold">Камеры не настроены</h3>
                  <p className="text-gray-500">Добавьте RTSP камеры для начала мониторинга</p>
                  <button className="btn-primary mt-4" onClick={() => setCameraModal({ open: true, camera: null })}>
                    <Plus className="w-4 h-4" />Добавить первую камеру
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {cameras.map((camera) => (
                  <div key={camera.id} className="card bg-white border border-gray-200">
                    <div className="p-4 p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`w-3 h-3 rounded-full ${camera.enabled ? 'bg-green-500' : 'bg-gray-200'}`} />
                          <div>
                            <h3 className="font-semibold">{camera.name}</h3>
                            <p className="text-sm text-gray-500">{camera.id}</p>
                          </div>
                        </div>
                        <span className={`badge ${camera.enabled ? 'badge-success' : 'badge-ghost'}`}>
                          {camera.enabled ? 'Активна' : 'Отключена'}
                        </span>
                      </div>
                      <div className="mt-2 font-mono text-sm text-gray-600 bg-gray-100 px-3 py-2 rounded">
                        {camera.rtsp_url.replace(/:([^:@]+)@/, ':***@')}
                      </div>
                      <div className="flex items-center justify-between mt-2">
                        <span className="text-sm text-gray-500">{camera.fps} FPS</span>
                        {testResults[camera.id] && (
                          <span className={`text-sm flex items-center gap-1 ${
                            testResults[camera.id].status === 'success' ? 'text-green-600' :
                            testResults[camera.id].status === 'loading' ? 'text-yellow-600' : 'text-red-600'
                          }`}>
                            {testResults[camera.id].status === 'loading' ? <Loader2 className="w-4 h-4 animate-spin" /> :
                             testResults[camera.id].status === 'success' ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                            {testResults[camera.id].message}
                          </span>
                        )}
                      </div>
                      <div className="flex gap-2 mt-3 pt-3 border-t border-gray-200">
                        <button className="btn-ghost text-sm px-3 py-1.5" onClick={() => handleTestCamera(camera.id)}>
                          <Play className="w-4 h-4" />Тест
                        </button>
                        <button className="btn-ghost text-sm px-3 py-1.5" onClick={() => setCameraModal({ open: true, camera })}>
                          <Settings className="w-4 h-4" />Изменить
                        </button>
                        <button className="btn-ghost text-sm px-3 py-1.5 text-red-600" onClick={() => handleDeleteCamera(camera.id)}>
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Models Tab */}
        {/* Detector Tab - v2.10.59: Переименовано и улучшено */}
        {activeTab === 'detector' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              {/* Detection Settings Card */}
              <div className="card bg-white border border-gray-200 p-5">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <Settings className="w-5 h-5 text-primary-600" />
                  Настройки детекции
                </h2>
                
                <div className="space-y-4">
                  {/* Active Model */}
                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div>
                      <p className="text-sm text-gray-500">Активная модель</p>
                      <p className="font-semibold text-lg">{activeModel?.name || 'Не выбрана'}</p>
                    </div>
                    {activeModel && (
                      <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">
                        Активна
                      </span>
                    )}
                  </div>

                  {/* Confidence Threshold */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Порог уверенности (Confidence)
                    </label>
                    <div className="flex items-center gap-4">
                      <input
                        type="range"
                        min="0.1"
                        max="0.9"
                        step="0.05"
                        defaultValue="0.5"
                        className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                      />
                      <span className="text-sm font-mono bg-gray-100 px-3 py-1 rounded">50%</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      Минимальная уверенность для отображения детекции. Выше = меньше ложных срабатываний.
                    </p>
                  </div>

                  {/* IOU Threshold */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Порог IOU (перекрытие)
                    </label>
                    <div className="flex items-center gap-4">
                      <input
                        type="range"
                        min="0.1"
                        max="0.9"
                        step="0.05"
                        defaultValue="0.45"
                        className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                      />
                      <span className="text-sm font-mono bg-gray-100 px-3 py-1 rounded">45%</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      Порог перекрытия bounding box для NMS. Ниже = меньше дублирующих детекций.
                    </p>
                  </div>
                </div>
              </div>

              {/* Models List */}
              <div className="card bg-white border border-gray-200 p-5">
                <div className="flex justify-between items-center mb-4">
                  <div>
                    <h2 className="text-lg font-semibold">Доступные модели</h2>
                    <p className="text-sm text-gray-500">Выберите модель для активации</p>
                  </div>
                  <button className="btn-ghost text-sm px-3 py-1.5" onClick={loadModels}>
                    <RefreshCw className={`w-4 h-4 ${loadingModels ? 'animate-spin' : ''}`} />
                  </button>
                </div>

                {/* Tip for custom models */}
                <div className="flex items-center gap-3 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm mb-4">
                  <CheckCircle className="w-4 h-4 flex-shrink-0" />
                  <span>Обучили свою модель в разделе <strong>Обучение</strong>? Она появится здесь автоматически.</span>
                </div>

                {loadingModels ? (
                  <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-primary-600" /></div>
                ) : (
                  <>
                    {modelsError && (
                      <div className="flex items-center gap-3 p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-700 mb-4">
                        <AlertCircle className="w-5 h-5" />
                        <span>API недоступен. Показаны стандартные модели для ручного скачивания.</span>
                      </div>
                    )}
                    <div className="space-y-3">
                      {displayModels.map((model) => (
                        <ModelCard
                          key={model.id}
                          model={model}
                          downloadProgress={downloadProgress[model.id] || null}
                          onDownload={() => handleDownloadModel(model.id)}
                          onActivate={() => handleActivateModel(model.id)}
                          onDelete={() => handleDeleteModel(model.id)}
                          isDownloading={downloadingModel === model.id}
                        />
                      ))}
                    </div>
                  </>
                )}

                <div className="flex items-center gap-3 p-4 bg-blue-50 border border-blue-200 rounded-lg text-blue-700 mt-4">
                  <AlertCircle className="w-5 h-5 flex-shrink-0" />
                  <div>
                    <h4 className="font-semibold">Ручное скачивание</h4>
                    <p className="text-sm">Скачайте .pt файл по ссылке и поместите в папку <code className="bg-blue-100 px-1 rounded">models/</code></p>
                  </div>
                </div>
              </div>
            </div>

            {/* GPU Info */}
            <div className="space-y-4">
              <div className="card bg-white border border-gray-200">
                <div className="p-4">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold flex items-center gap-2"><Cpu className="w-5 h-5" />Видеокарта</h3>
                    <button className="p-1 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded" onClick={loadGpuInfo}>
                      <RefreshCw className={`w-3 h-3 ${loadingGpu ? 'animate-spin' : ''}`} />
                    </button>
                  </div>

                  {loadingGpu ? (
                    <div className="flex justify-center py-4"><Loader2 className="w-6 h-6 animate-spin" /></div>
                  ) : gpuInfo?.available ? (
                    <div className="space-y-3 mt-4">
                      <div className="text-lg font-semibold text-primary-600">{gpuInfo.name}</div>
                      {gpuInfo.cuda_version && (
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-500">CUDA</span>
                          <span>{gpuInfo.cuda_version}</span>
                        </div>
                      )}
                      {gpuInfo.memory_total_mb && (
                        <div>
                          <div className="flex justify-between text-sm mb-1">
                            <span className="text-gray-500 flex items-center gap-1"><HardDrive className="w-3 h-3" />Память</span>
                            <span>{gpuInfo.memory_used_mb != null ? gpuInfo.memory_used_mb : '...'} / {gpuInfo.memory_total_mb} MB</span>
                          </div>
                          <progress className="w-full h-2 bg-gray-200 rounded-full overflow-hidden w-full" value={gpuInfo.memory_used_mb || 0} max={gpuInfo.memory_total_mb} />
                        </div>
                      )}
                      {gpuInfo.temperature !== null && (
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-500 flex items-center gap-1"><Thermometer className="w-3 h-3" />Температура</span>
                          <span className={gpuInfo.temperature > 80 ? 'text-red-600' : ''}>{gpuInfo.temperature}°C</span>
                        </div>
                      )}
                      {gpuInfo.utilization !== null && (
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-500 flex items-center gap-1"><Zap className="w-3 h-3" />Нагрузка</span>
                          <span>{gpuInfo.utilization}%</span>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-center py-4">
                      <AlertCircle className="w-12 h-12 text-yellow-600 mx-auto mb-2" />
                      <p className="font-semibold">GPU не обнаружен</p>
                      <p className="text-sm text-gray-500">Используется CPU</p>
                    </div>
                  )}
                </div>
              </div>

              <div className="card bg-white border border-gray-200">
                <div className="p-4">
                  <h3 className="font-semibold flex items-center gap-2"><Zap className="w-5 h-5 text-yellow-600" />Рекомендации</h3>
                  <ul className="text-sm space-y-2 mt-2">
                    <li>• <strong>RTX 5090:</strong> YOLO11 XLarge</li>
                    <li>• <strong>RTX 4080:</strong> YOLOv8 Large</li>
                    <li>• <strong>RTX 3060:</strong> YOLOv8 Medium</li>
                    <li>• <strong>GTX 1650:</strong> YOLOv8 Nano</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Datasets Tab */}
        {activeTab === 'datasets' && (
          <div className="card bg-white border border-gray-200 p-6">
            <DatasetCatalog />
          </div>
        )}

        {/* System Tab */}
        {activeTab === 'system' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Settings notification */}
            {settingsMessage && (
              <div className="lg:col-span-2 bg-gray-900 text-white px-4 py-2 rounded-lg">
                {settingsMessage}
              </div>
            )}
            
            <div className="card bg-white border border-gray-200">
              <div className="p-4">
                <h3 className="font-semibold mb-4">Параметры детекции</h3>
                <div className="space-y-4">
                  <div>
                    <label className="block mb-1">
                      <span className="text-sm font-medium text-gray-700">Порог уверенности: </span>
                      <span className="text-sm text-primary-600 font-medium">{detectionSettings.confidence_threshold}</span>
                    </label>
                    <input 
                      type="range" 
                      className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary-600" 
                      min="10" 
                      max="100" 
                      value={detectionSettings.confidence_threshold * 100}
                      onChange={(e) => setDetectionSettings(prev => ({
                        ...prev,
                        confidence_threshold: parseInt(e.target.value) / 100
                      }))}
                    />
                  </div>
                  <div>
                    <label className="block mb-1"><span className="text-sm font-medium text-gray-700">Устройство</span></label>
                    <select 
                      className="input"
                      value={detectionSettings.device}
                      onChange={(e) => setDetectionSettings(prev => ({
                        ...prev,
                        device: e.target.value
                      }))}
                    >
                      <option value="auto">Автоматически</option>
                      <option value="cuda:0">GPU (CUDA)</option>
                      <option value="cpu">CPU</option>
                    </select>
                  </div>
                  <div className="flex items-center gap-3">
                    <input 
                      type="checkbox" 
                      id="fp16-toggle"
                      className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                      checked={detectionSettings.fp16}
                      onChange={(e) => setDetectionSettings(prev => ({
                        ...prev,
                        fp16: e.target.checked
                      }))}
                    />
                    <label htmlFor="fp16-toggle" className="text-sm font-medium text-gray-700 cursor-pointer">
                      FP16 (половинная точность)
                    </label>
                  </div>
                  
                  <button 
                    onClick={saveDetectionSettings}
                    disabled={savingSettings}
                    className="btn-primary w-full mt-4"
                  >
                    {savingSettings ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
                    Сохранить настройки
                  </button>
                </div>
              </div>
            </div>

            <div className="card bg-white border border-gray-200">
              <div className="p-4">
                <h3 className="font-semibold mb-4">Информация о системе</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Версия</span><span>v2.10.7</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">WebSocket</span>
                    <span className={isConnected ? 'text-green-600' : 'text-red-600'}>{isConnected ? 'Подключен' : 'Отключен'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Активная модель</span><span>{activeModel?.name || 'Не выбрана'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Камер</span><span>{cameras.length} / 8</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="card bg-white border border-gray-200">
              <div className="p-4">
                <h3 className="font-semibold mb-4 flex items-center gap-2"><ImageIcon className="w-5 h-5" />Снимки для обучения</h3>
                <p className="text-sm text-gray-500 mb-4">Скриншоты с камер для датасета</p>
                <button 
                  onClick={captureScreenshots}
                  disabled={capturingScreenshots}
                  className="btn-primary flex items-center gap-2"
                >
                  {capturingScreenshots ? <Loader2 className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />}
                  Сделать снимки
                </button>
                <p className="text-xs text-gray-400 mt-2">Сохраняются в training_data/screenshots/</p>
              </div>
            </div>

            {/* Telegram & API Settings */}
            <div className="card bg-white border border-gray-200 lg:col-span-2">
              <div className="p-4">
                <h3 className="font-semibold mb-4 flex items-center gap-2">
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/>
                  </svg>
                  Telegram и API
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Telegram */}
                  <div className="space-y-3">
                    <h4 className="text-sm font-medium text-gray-600">Telegram уведомления</h4>
                    <div className="">
                      <label className="block mb-1"><span className="text-xs text-gray-600">Bot Token</span></label>
                      <input 
                        type="password" 
                        className="input text-sm font-mono"
                        placeholder="Настройте в .env файле"
                        disabled
                        value="••••••••••••••••••"
                      />
                    </div>
                    <div className="">
                      <label className="block mb-1"><span className="text-xs text-gray-600">Chat ID</span></label>
                      <input 
                        type="text" 
                        className="input text-sm font-mono"
                        placeholder="Настройте в .env файле"
                        disabled
                        value="••••••••••"
                      />
                    </div>
                    <div className="flex items-center gap-3 p-4 bg-blue-50 border border-blue-200 rounded-lg text-blue-700 text-xs py-2">
                      <AlertCircle className="w-4 h-4" />
                      <span>Измените TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID в файле <code className="bg-gray-200 px-1 rounded">.env</code></span>
                    </div>
                  </div>

                  {/* API Credentials */}
                  <div className="space-y-3">
                    <h4 className="text-sm font-medium text-gray-600">API авторизация</h4>
                    <div className="">
                      <label className="block mb-1"><span className="text-xs text-gray-600">Логин</span></label>
                      <input 
                        type="text" 
                        className="input text-sm"
                        placeholder="admin"
                        disabled
                        value="admin"
                      />
                    </div>
                    <div className="">
                      <label className="block mb-1"><span className="text-xs text-gray-600">Пароль</span></label>
                      <input 
                        type="password" 
                        className="input text-sm"
                        disabled
                        value="••••••••"
                      />
                    </div>
                    <div className="flex items-center gap-3 p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-700 text-xs py-2">
                      <AlertCircle className="w-4 h-4" />
                      <span>Измените API_USERNAME и API_PASSWORD в <code className="bg-gray-200 px-1 rounded">.env</code> для безопасности!</span>
                    </div>
                  </div>
                </div>

                <div className="border-t border-gray-200 my-4"></div>
                
                <div className="text-xs text-gray-400">
                  <p className="mb-1"><strong>Расположение .env файла:</strong> корневая папка проекта</p>
                  <p>После изменения .env перезапустите систему: <code className="bg-gray-200 px-1 rounded">docker-compose restart</code></p>
                </div>
              </div>
            </div>

            {/* PPE Model & Dataset Guide */}
            <div className="card bg-white border border-gray-200 lg:col-span-2">
              <div className="p-4">
                <h3 className="font-semibold mb-4 flex items-center gap-2">
                  <Download className="w-5 h-5 text-green-600" />
                  🦺 Инструкция: PPE модели и датасеты
                </h3>
                
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5" />
                    <div>
                      <p className="font-medium text-amber-800">Важно!</p>
                      <p className="text-sm text-amber-700">
                        Стандартные модели YOLO (v8, v11) обучены на COCO датасете и распознают только общие объекты (person, car и т.д.).
                        Для детекции <strong>касок и жилетов</strong> нужна специализированная PPE-модель.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Ready PPE Models */}
                <div className="mb-6">
                  <h4 className="font-medium text-gray-800 mb-3 flex items-center gap-2">
                    <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs">Рекомендуется</span>
                    Готовые PPE-модели (скачать и использовать)
                  </h4>
                  <div className="space-y-3">
                    <div className="border border-gray-200 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2">
                        <div>
                          <span className="font-medium">Construction Site Safety (Kaggle)</span>
                          <span className="ml-2 text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">2801 изображений</span>
                        </div>
                        <a 
                          href="https://www.kaggle.com/datasets/snehilsanyal/construction-site-safety-image-dataset-roboflow" 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="btn-primary text-xs flex items-center gap-1"
                        >
                          <ExternalLink className="w-3 h-3" /> Kaggle
                        </a>
                      </div>
                      <p className="text-xs text-gray-500">Классы: Hardhat, NO-Hardhat, Safety Vest, NO-Safety Vest, Mask, Person, machinery, vehicle</p>
                      <p className="text-xs text-green-600 mt-1">✓ Включает обученную модель best.pt</p>
                    </div>

                    <div className="border border-gray-200 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2">
                        <div>
                          <span className="font-medium">Safety Helmet Dataset (GitHub)</span>
                          <span className="ml-2 text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">7581 изображений</span>
                        </div>
                        <a 
                          href="https://github.com/njvisionpower/Safety-Helmet-Wearing-Dataset" 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="btn-primary text-xs flex items-center gap-1"
                        >
                          <ExternalLink className="w-3 h-3" /> GitHub
                        </a>
                      </div>
                      <p className="text-xs text-gray-500">Классы: hat (каска), person (без каски)</p>
                      <p className="text-xs text-green-600 mt-1">✓ Включает pretrained модели</p>
                    </div>

                    <div className="border border-gray-200 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2">
                        <div>
                          <span className="font-medium">SH17 Dataset (17 классов PPE)</span>
                          <span className="ml-2 text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded">8099 изображений</span>
                        </div>
                        <a 
                          href="https://github.com/ahmadmughees/SH17dataset" 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="btn-primary text-xs flex items-center gap-1"
                        >
                          <ExternalLink className="w-3 h-3" /> GitHub
                        </a>
                      </div>
                      <p className="text-xs text-gray-500">Классы: helmet, vest, glasses, mask, gloves, safety shoes и др.</p>
                      <p className="text-xs text-green-600 mt-1">✓ Включает веса YOLOv8/v9/v10</p>
                    </div>

                    <div className="border border-gray-200 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2">
                        <div>
                          <span className="font-medium">Roboflow Universe PPE</span>
                          <span className="ml-2 text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded">4000+ изображений</span>
                        </div>
                        <a 
                          href="https://universe.roboflow.com/roboflow-universe-projects/construction-site-safety" 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="btn-primary text-xs flex items-center gap-1"
                        >
                          <ExternalLink className="w-3 h-3" /> Roboflow
                        </a>
                      </div>
                      <p className="text-xs text-gray-500">Множество PPE датасетов с готовыми моделями</p>
                      <p className="text-xs text-amber-600 mt-1">⚠ Требуется бесплатная регистрация</p>
                    </div>
                  </div>
                </div>

                {/* Installation Steps */}
                <div className="mb-6">
                  <h4 className="font-medium text-gray-800 mb-3">📋 Установка PPE-модели</h4>
                  <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                    <div className="flex gap-3">
                      <span className="bg-primary-600 text-white w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0">1</span>
                      <div>
                        <p className="font-medium">Скачайте модель</p>
                        <p className="text-sm text-gray-600">Скачайте файл <code className="bg-gray-200 px-1 rounded">best.pt</code> или <code className="bg-gray-200 px-1 rounded">weights.pt</code> с выбранного ресурса</p>
                      </div>
                    </div>
                    <div className="flex gap-3">
                      <span className="bg-primary-600 text-white w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0">2</span>
                      <div>
                        <p className="font-medium">Переименуйте файл</p>
                        <p className="text-sm text-gray-600">Переименуйте в <code className="bg-gray-200 px-1 rounded">ppe_model.pt</code></p>
                      </div>
                    </div>
                    <div className="flex gap-3">
                      <span className="bg-primary-600 text-white w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0">3</span>
                      <div>
                        <p className="font-medium">Поместите в папку models</p>
                        <p className="text-sm text-gray-600">Скопируйте в <code className="bg-gray-200 px-1 rounded">ppe_system/models/ppe_model.pt</code></p>
                      </div>
                    </div>
                    <div className="flex gap-3">
                      <span className="bg-primary-600 text-white w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0">4</span>
                      <div>
                        <p className="font-medium">Перезапустите detector</p>
                        <code className="block bg-gray-800 text-green-400 p-2 rounded text-xs mt-1">docker compose restart detector</code>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Fine-tuning Guide */}
                <div className="mb-6">
                  <h4 className="font-medium text-gray-800 mb-3">🎓 Дообучение на своих данных</h4>
                  <div className="bg-blue-50 rounded-lg p-4">
                    <ol className="space-y-2 text-sm">
                      <li><strong>1.</strong> Соберите изображения с ваших камер (кнопка "Снимки" выше)</li>
                      <li><strong>2.</strong> Разметьте в <a href="https://app.roboflow.com" target="_blank" rel="noopener noreferrer" className="text-primary-600 underline">Roboflow</a> или <a href="https://github.com/heartexlabs/labelImg" target="_blank" rel="noopener noreferrer" className="text-primary-600 underline">LabelImg</a></li>
                      <li><strong>3.</strong> Экспортируйте в формате YOLOv8</li>
                      <li><strong>4.</strong> Запустите обучение во вкладке "Обучение" или командой:</li>
                    </ol>
                    <code className="block bg-gray-800 text-green-400 p-2 rounded text-xs mt-2">
                      yolo train model=yolov8n.pt data=dataset.yaml epochs=100 imgsz=640
                    </code>
                    <p className="text-xs text-gray-600 mt-2">Результат: <code className="bg-gray-200 px-1 rounded">runs/detect/train/weights/best.pt</code> → скопируйте в <code className="bg-gray-200 px-1 rounded">models/ppe_model.pt</code></p>
                  </div>
                </div>

                {/* Class mapping info */}
                <div>
                  <h4 className="font-medium text-gray-800 mb-3">🏷️ Поддерживаемые классы</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                    <div className="bg-green-50 border border-green-200 rounded p-2 text-center">
                      <span className="text-green-700 font-medium">hardhat / helmet</span>
                      <p className="text-green-600">✓ Каска надета</p>
                    </div>
                    <div className="bg-red-50 border border-red-200 rounded p-2 text-center">
                      <span className="text-red-700 font-medium">no-hardhat / no-helmet</span>
                      <p className="text-red-600">✗ Без каски</p>
                    </div>
                    <div className="bg-green-50 border border-green-200 rounded p-2 text-center">
                      <span className="text-green-700 font-medium">vest / safety-vest</span>
                      <p className="text-green-600">✓ Жилет надет</p>
                    </div>
                    <div className="bg-red-50 border border-red-200 rounded p-2 text-center">
                      <span className="text-red-700 font-medium">no-vest / no-safety-vest</span>
                      <p className="text-red-600">✗ Без жилета</p>
                    </div>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">Система автоматически распознаёт эти классы в любом регистре</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {cameraModal.open && (
          <CameraModal
            camera={cameraModal.camera}
            onSave={handleSaveCamera}
            onClose={() => setCameraModal({ open: false, camera: null })}
            isLoading={savingCamera}
          />
        )}

        {/* v2.10.55: Модальное окно пакетного добавления камер */}
        {batchCameraModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
              <div className="flex items-center justify-between p-4 border-b">
                <div className="flex items-center gap-2">
                  <List className="w-5 h-5 text-primary-600" />
                  <h2 className="text-lg font-semibold">Пакетное добавление камер</h2>
                </div>
                <button onClick={() => setBatchCameraModal(false)} className="p-1 hover:bg-gray-100 rounded">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="p-4 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    RTSP ссылки (по одной на строку)
                  </label>
                  <textarea
                    className="w-full h-48 px-3 py-2 border border-gray-300 rounded-lg font-mono text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    placeholder={`rtsp://admin:password@192.168.1.101:554/stream1\nrtsp://admin:password@192.168.1.102:554/stream1\nrtsp://admin:password@192.168.1.103:554/stream1\n...`}
                    value={batchUrls}
                    onChange={(e) => setBatchUrls(e.target.value)}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Максимум {8 - cameras.length} камер. Камеры будут названы "Камера 1", "Камера 2" и т.д.
                  </p>
                </div>
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                  <p className="text-sm text-blue-700">
                    <strong>Подсказка:</strong> Вставьте список RTSP URL, каждый с новой строки. 
                    Пустые строки будут пропущены.
                  </p>
                </div>
              </div>
              <div className="flex justify-end gap-2 p-4 border-t bg-gray-50 rounded-b-xl">
                <button 
                  className="btn-ghost" 
                  onClick={() => { setBatchCameraModal(false); setBatchUrls(''); }}
                >
                  Отмена
                </button>
                <button 
                  className="btn-primary"
                  onClick={handleBatchAddCameras}
                  disabled={savingCamera || !batchUrls.trim()}
                >
                  {savingCamera ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  Добавить камеры
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}

export default SettingsPage;
