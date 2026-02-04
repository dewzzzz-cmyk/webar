/**
 * Dataset Catalog Component
 * =========================
 * 
 * Каталог готовых PPE датасетов для быстрой загрузки.
 * UX аналогичен каталогу моделей - выбрал, скачал, использовал.
 */

import { useState, useEffect } from 'react';
import {
  Download,
  Database,
  Loader2,
  Check,
  AlertCircle,
  ExternalLink,
  Trash2,
  RefreshCw,
  Package,
  Image as ImageIcon,
  Tag,
  Shield,
  Eye,
  EyeOff,
  Key,
  X,
  Edit2,
  Save,
  FolderOpen,
  CheckCircle,
  Plus,
} from 'lucide-react';

interface DatasetCatalogItem {
  id: string;
  name: string;
  description: string;
  source: string;
  url: string;
  size_mb: number;
  images_count: number;
  classes: string[];
  format: string;
  license: string;
  recommended_for: string;
  is_downloaded: boolean;
  local_path?: string;
  status?: string;  // 'instructions_only' when only manual instructions exist
  message?: string;
  images_found?: number;
}

interface DownloadProgress {
  dataset_id: string;
  status: 'idle' | 'downloading' | 'extracting' | 'converting' | 'completed' | 'error';
  progress: number;
  message: string;
  error?: string;
}

interface DatasetCatalogProps {
  onDatasetReady?: (datasetId: string) => void;
}

export function DatasetCatalog({ onDatasetReady }: DatasetCatalogProps) {
  const [catalog, setCatalog] = useState<DatasetCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState<Record<string, DownloadProgress>>({});
  const [apiKey, setApiKey] = useState('');
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [showApiKeyInput, setShowApiKeyInput] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Загрузка API key из localStorage и сервера
  useEffect(() => {
    loadApiKey();
  }, []);

  const loadApiKey = async () => {
    // Сначала пробуем загрузить с сервера
    try {
      const token = localStorage.getItem('token');
      const response = await fetch('/api/settings/roboflow-api-key', {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      });
      if (response.ok) {
        const data = await response.json();
        if (data.api_key) {
          setApiKey(data.api_key);
          setApiKeyInput(data.api_key);
          localStorage.setItem('roboflow_api_key', data.api_key);
          return;
        }
      }
    } catch (e) {
      console.warn('Failed to load API key from server:', e);
    }
    
    // Fallback на localStorage
    const savedApiKey = localStorage.getItem('roboflow_api_key');
    if (savedApiKey) {
      setApiKey(savedApiKey);
      setApiKeyInput(savedApiKey);
    }
  };

  // Сохранение API key
  const saveApiKey = async () => {
    const keyToSave = apiKeyInput.trim();
    if (!keyToSave) return;
    
    try {
      // Сохраняем на сервер
      const token = localStorage.getItem('token');
      await fetch('/api/settings/roboflow-api-key', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ api_key: keyToSave }),
      });
      
      setApiKey(keyToSave);
      localStorage.setItem('roboflow_api_key', keyToSave);
      setError(null);
    } catch (e) {
      // Fallback - сохраняем только в localStorage
      setApiKey(keyToSave);
      localStorage.setItem('roboflow_api_key', keyToSave);
    }
  };

  // Загрузка каталога
  useEffect(() => {
    fetchCatalog();
  }, []);

  const fetchCatalog = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/training/catalog/datasets');
      if (response.ok) {
        const data = await response.json();
        setCatalog(data);
      } else {
        throw new Error('Failed to fetch catalog');
      }
    } catch (err) {
      setError('Не удалось загрузить каталог датасетов');
      // Используем fallback данные
      setCatalog([
        {
          id: "coco128-demo",
          name: "🚀 COCO128 Demo (Быстрый старт)",
          description: "Демо-датасет для быстрого тестирования. НЕ требует API ключей!",
          source: "direct",
          url: "https://github.com/ultralytics/yolov5/releases/download/v1.0/coco128.zip",
          size_mb: 7,
          images_count: 128,
          classes: ["person"],
          format: "yolov8",
          license: "CC BY 4.0",
          recommended_for: "Быстрый старт и тестирование",
          is_downloaded: false
        },
        {
          id: "construction-ppe-skcet",
          name: "⭐ Construction PPE (8845 изобр.)",
          description: "Каски, жилеты, ботинки, перчатки - полный набор СИЗ. Требует Roboflow API ключ.",
          source: "roboflow",
          url: "https://universe.roboflow.com/skcet-g4h72/construction-ppe-rdhzo",
          size_mb: 500,
          images_count: 8845,
          classes: ["Helmet", "Safety Vest", "Gloves", "Safety Boot", "Human"],
          format: "yolov8",
          license: "CC BY 4.0",
          recommended_for: "Строительные площадки, производство",
          is_downloaded: false
        },
        {
          id: "helmetvest-v7",
          name: "Helmet & Vest Detection",
          description: "Каски и жилеты - 2286 изображений. Требует Roboflow API ключ.",
          source: "roboflow",
          url: "https://universe.roboflow.com/data-u4eek/helmetvest/dataset/7",
          size_mb: 150,
          images_count: 2286,
          classes: ["Helmet", "NoHelmet", "NoVest", "Vest"],
          format: "yolov8",
          license: "CC BY 4.0",
          recommended_for: "Базовая детекция касок и жилетов",
          is_downloaded: false
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const startDownload = async (datasetId: string, needsApiKey: boolean = false) => {
    // Если нужен API ключ и его нет - показать поле ввода
    if (needsApiKey && !apiKey) {
      setError('Введите API ключ Roboflow выше для загрузки датасета');
      return;
    }

    try {
      setError(null);
      setDownloading(prev => ({
        ...prev,
        [datasetId]: {
          dataset_id: datasetId,
          status: 'downloading',
          progress: 0,
          message: 'Начало загрузки...'
        }
      }));

      const url = `/api/training/catalog/datasets/${datasetId}/download${apiKey ? `?roboflow_api_key=${encodeURIComponent(apiKey)}` : ''}`;
      const response = await fetch(url, { method: 'POST' });

      if (!response.ok) {
        throw new Error('Download failed');
      }

      // Polling для прогресса
      const pollProgress = setInterval(async () => {
        try {
          const statusResponse = await fetch(`/api/training/catalog/datasets/${datasetId}/status`);
          if (statusResponse.ok) {
            const progress: DownloadProgress = await statusResponse.json();
            setDownloading(prev => ({ ...prev, [datasetId]: progress }));

            if (progress.status === 'completed') {
              clearInterval(pollProgress);
              fetchCatalog(); // Обновляем каталог
              onDatasetReady?.(datasetId);
            } else if (progress.status === 'error') {
              clearInterval(pollProgress);
            }
          }
        } catch (err) {
          clearInterval(pollProgress);
        }
      }, 1000);

      // Остановить polling через 10 минут максимум
      setTimeout(() => clearInterval(pollProgress), 600000);

    } catch (err) {
      setDownloading(prev => ({
        ...prev,
        [datasetId]: {
          dataset_id: datasetId,
          status: 'error',
          progress: 0,
          message: 'Ошибка загрузки',
          error: err instanceof Error ? err.message : 'Unknown error'
        }
      }));
    }
  };

  const importDataset = async (datasetId: string) => {
    try {
      setDownloading(prev => ({
        ...prev,
        [datasetId]: {
          dataset_id: datasetId,
          status: 'converting',
          progress: 50,
          message: 'Импорт изображений в систему...'
        }
      }));

      const response = await fetch(`/api/training/catalog/datasets/${datasetId}/import`, {
        method: 'POST'
      });

      if (!response.ok) {
        throw new Error('Import failed');
      }

      const result = await response.json();

      setDownloading(prev => ({
        ...prev,
        [datasetId]: {
          dataset_id: datasetId,
          status: 'completed',
          progress: 100,
          message: `Импортировано ${result.imported} изображений`
        }
      }));

      // Обновляем каталог
      setTimeout(() => {
        fetchCatalog();
        onDatasetReady?.(datasetId);
        setDownloading(prev => {
          const next = { ...prev };
          delete next[datasetId];
          return next;
        });
      }, 2000);

    } catch (err) {
      setDownloading(prev => ({
        ...prev,
        [datasetId]: {
          dataset_id: datasetId,
          status: 'error',
          progress: 0,
          message: 'Ошибка импорта',
          error: err instanceof Error ? err.message : 'Unknown error'
        }
      }));
    }
  };

  const deleteDataset = async (datasetId: string) => {
    if (!confirm('Удалить датасет? Все данные будут удалены.')) return;

    try {
      const response = await fetch(`/api/training/catalog/datasets/${datasetId}`, {
        method: 'DELETE'
      });
      if (response.ok) {
        fetchCatalog();
      }
    } catch (err) {
      setError('Не удалось удалить датасет');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-primary-600" />
        <span className="ml-2">Загрузка каталога...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Database className="w-5 h-5 text-primary-600" />
            Каталог PPE Датасетов
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            Выберите датасет и нажмите "Загрузить" — система настроит всё автоматически
          </p>
        </div>
        <button
          onClick={fetchCatalog}
          className="btn-secondary text-sm flex items-center gap-1"
        >
          <RefreshCw className="w-4 h-4" />
          Обновить
        </button>
      </div>

      {error && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 flex items-center gap-2 text-yellow-700 text-sm">
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* API Keys Section */}
      <ApiKeysSection 
        roboflowKey={apiKey}
        onRoboflowKeyChange={(key) => {
          setApiKey(key);
          setApiKeyInput(key);
        }}
      />

      {/* Dataset Cards */}
      <div className="grid gap-4">
        {catalog.map((dataset) => {
          const progress = downloading[dataset.id];
          const isDownloading = progress && !['completed', 'error', 'idle'].includes(progress.status);

          return (
            <div
              key={dataset.id}
              className={`
                border rounded-lg p-4 transition-all
                ${dataset.is_downloaded ? 'border-green-200 bg-green-50/30' : 'border-gray-200 hover:border-primary-200'}
              `}
            >
              <div className="flex items-start justify-between">
                {/* Info */}
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h4 className="font-semibold">{dataset.name}</h4>
                    {/* Source badge */}
                    {dataset.source === 'roboflow' && (
                      <span className="px-1.5 py-0.5 rounded text-xs bg-blue-100 text-blue-600" title="Требует Roboflow API ключ">
                        Roboflow
                      </span>
                    )}
                    {dataset.source === 'kaggle' && (
                      <span className="px-1.5 py-0.5 rounded text-xs bg-cyan-100 text-cyan-600" title="Требует Kaggle API ключ">
                        Kaggle
                      </span>
                    )}
                    {dataset.source === 'direct' && (
                      <span className="px-1.5 py-0.5 rounded text-xs bg-gray-100 text-gray-600" title="Прямая загрузка без API ключа">
                        Без ключа
                      </span>
                    )}
                    {dataset.is_downloaded && (
                      <span className="px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-700 flex items-center gap-1">
                        <Check className="w-3 h-3" />
                        Загружен ({dataset.images_found?.toLocaleString() || '?'} изобр.)
                      </span>
                    )}
                    {dataset.status === 'instructions_only' && (
                      <span className="px-2 py-0.5 rounded-full text-xs bg-yellow-100 text-yellow-700 flex items-center gap-1">
                        <AlertCircle className="w-3 h-3" />
                        Требуется ручная загрузка
                      </span>
                    )}
                    {dataset.id === 'construction-ppe-v1' && !dataset.is_downloaded && dataset.status !== 'instructions_only' && (
                      <span className="px-2 py-0.5 rounded-full text-xs bg-primary-100 text-primary-700">
                        Рекомендуем
                      </span>
                    )}
                  </div>
                  
                  <p className="text-sm text-gray-600 mt-1">{dataset.description}</p>
                  
                  {/* Manual download message */}
                  {dataset.status === 'instructions_only' && (
                    <div className="bg-yellow-50 border border-yellow-200 rounded p-2 mt-2 text-xs text-yellow-700">
                      <p className="font-medium">Инструкции для ручной загрузки созданы</p>
                      <p>
                        {apiKey 
                          ? 'API ключ настроен — нажмите "Загрузить" для повторной попытки автоматической загрузки'
                          : <>Введите API ключ Roboflow выше или <a href={dataset.url} target="_blank" rel="noopener noreferrer" className="underline">скачайте вручную</a></>
                        }
                      </p>
                    </div>
                  )}
                  
                  {/* Stats */}
                  <div className="flex flex-wrap gap-4 mt-3 text-sm text-gray-500">
                    <span className="flex items-center gap-1">
                      <ImageIcon className="w-4 h-4" />
                      {dataset.images_count.toLocaleString()} изображений
                    </span>
                    <span className="flex items-center gap-1">
                      <Tag className="w-4 h-4" />
                      {dataset.classes.length} классов
                    </span>
                    <span className="flex items-center gap-1">
                      <Package className="w-4 h-4" />
                      {dataset.size_mb} MB
                    </span>
                    <span className="flex items-center gap-1">
                      <Shield className="w-4 h-4" />
                      {dataset.license}
                    </span>
                  </div>

                  {/* Classes */}
                  <div className="flex flex-wrap gap-1 mt-2">
                    {dataset.classes.slice(0, 5).map((cls, i) => (
                      <span
                        key={i}
                        className={`px-2 py-0.5 rounded text-xs ${
                          cls.includes('NO-') || cls.includes('no_')
                            ? 'bg-red-100 text-red-700'
                            : 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {cls}
                      </span>
                    ))}
                    {dataset.classes.length > 5 && (
                      <span className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-500">
                        +{dataset.classes.length - 5}
                      </span>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex flex-col items-end gap-2 ml-4">
                  {(!dataset.is_downloaded || dataset.status === 'instructions_only') && !isDownloading && (
                    <>
                      <button
                        onClick={() => startDownload(dataset.id, dataset.source === 'roboflow')}
                        className="btn-primary text-sm flex items-center gap-2"
                      >
                        <Download className="w-4 h-4" />
                        Загрузить
                      </button>
                      {/* Кнопка импорта если папка существует */}
                      {(dataset.images_found ?? 0) > 0 && (
                        <button
                          onClick={() => importDataset(dataset.id)}
                          className="btn-secondary text-sm flex items-center gap-2"
                        >
                          <FolderOpen className="w-4 h-4" />
                          Импорт ({dataset.images_found} фото)
                        </button>
                      )}
                      <a
                        href={dataset.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-gray-500 hover:text-primary-600 flex items-center gap-1"
                      >
                        <ExternalLink className="w-3 h-3" />
                        Источник
                      </a>
                    </>
                  )}

                  {isDownloading && (
                    <div className="text-right">
                      <div className="flex items-center gap-2 text-sm text-blue-600">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        {progress.message}
                      </div>
                      <div className="w-32 h-2 bg-gray-200 rounded-full mt-2 overflow-hidden">
                        <div
                          className="h-full bg-blue-500 transition-all duration-300"
                          style={{ width: `${progress.progress}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500">{progress.progress.toFixed(0)}%</span>
                    </div>
                  )}

                  {dataset.is_downloaded && (
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-green-600 flex items-center gap-1">
                        <CheckCircle className="w-4 h-4" />
                        Готов ({dataset.images_found ?? 0} изобр.)
                      </span>
                      <button
                        onClick={() => importDataset(dataset.id)}
                        className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                        title="Импортировать в систему"
                      >
                        <RefreshCw className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => deleteDataset(dataset.id)}
                        className="p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                        title="Удалить"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  )}

                  {progress?.status === 'error' && (
                    <div className="text-right">
                      <span className="text-sm text-red-600">{progress.error}</span>
                      <button
                        onClick={() => startDownload(dataset.id)}
                        className="btn-secondary text-xs mt-1"
                      >
                        Повторить
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* API Key Input Modal */}
              {showApiKeyInput === dataset.id && (
                <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <p className="text-sm text-blue-800 mb-2">
                    Для загрузки с Roboflow нужен API ключ (бесплатно):
                  </p>
                  <ol className="text-xs text-blue-700 list-decimal list-inside mb-3 space-y-1">
                    <li>Зарегистрируйтесь на <a href="https://app.roboflow.com" target="_blank" className="underline">app.roboflow.com</a></li>
                    <li>Перейдите в Settings → API Keys</li>
                    <li>Скопируйте Private API Key</li>
                  </ol>
                  <div className="flex gap-2">
                    <input
                      type="password"
                      value={apiKeyInput}
                      onChange={(e) => setApiKeyInput(e.target.value)}
                      placeholder="Вставьте API ключ"
                      className="input flex-1 text-sm"
                    />
                    <button
                      onClick={() => {
                        if (apiKeyInput.trim()) {
                          saveApiKey();
                        }
                        setShowApiKeyInput(null);
                        startDownload(dataset.id, false);
                      }}
                      disabled={!apiKeyInput.trim()}
                      className="btn-primary text-sm"
                    >
                      Загрузить
                    </button>
                    <button
                      onClick={() => setShowApiKeyInput(null)}
                      className="btn-secondary text-sm"
                    >
                      Отмена
                    </button>
                  </div>
                  <p className="text-xs text-blue-600 mt-2">
                    Без API ключа будут созданы инструкции для ручной загрузки
                  </p>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Help */}
      <div className="bg-gray-50 rounded-lg p-4 text-sm">
        <h4 className="font-medium mb-2">💡 Как это работает:</h4>
        <ol className="list-decimal list-inside space-y-1 text-gray-600">
          <li>Выберите датасет из каталога</li>
          <li>Нажмите "Загрузить" — система скачает и настроит всё автоматически</li>
          <li>Перейдите в "Обучение" → датасет уже готов к использованию</li>
        </ol>
      </div>
    </div>
  );
}

// ============================================================================
// ApiKeysSection Component - Управление API ключами
// ============================================================================

interface ApiKeysSectionProps {
  roboflowKey: string;
  onRoboflowKeyChange: (key: string) => void;
}

interface ApiKeyState {
  roboflow: { exists: boolean; masked: string | null };
  kaggle_username: { exists: boolean; masked: string | null };
  kaggle_key: { exists: boolean; masked: string | null };
  huggingface: { exists: boolean; masked: string | null };
}

function ApiKeysSection({ roboflowKey, onRoboflowKeyChange }: ApiKeysSectionProps) {
  const [expanded, setExpanded] = useState(false);
  const [apiKeys, setApiKeys] = useState<ApiKeyState>({
    roboflow: { exists: !!roboflowKey, masked: roboflowKey ? `${roboflowKey.slice(0,4)}...${roboflowKey.slice(-4)}` : null },
    kaggle_username: { exists: false, masked: null },
    kaggle_key: { exists: false, masked: null },
    huggingface: { exists: false, masked: null },
  });
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [keyInput, setKeyInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // Загрузка ключей с сервера
  useEffect(() => {
    fetchApiKeys();
  }, []);

  const fetchApiKeys = async () => {
    try {
      const response = await fetch('/api/training/api-keys');
      if (response.ok) {
        const data = await response.json();
        setApiKeys(data);
        
        // Если есть roboflow ключ - получаем его полное значение
        if (data.roboflow?.exists) {
          const keyResponse = await fetch('/api/training/api-keys/roboflow/value');
          if (keyResponse.ok) {
            const keyData = await keyResponse.json();
            if (keyData.value) {
              onRoboflowKeyChange(keyData.value);
            }
          }
        }
      }
    } catch (e) {
      console.warn('Failed to fetch API keys:', e);
    }
  };

  const saveKey = async (keyType: string) => {
    if (!keyInput.trim()) return;
    
    setSaving(true);
    try {
      const response = await fetch(`/api/training/api-keys/${keyType}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: keyInput.trim() }),
      });
      
      if (response.ok) {
        await fetchApiKeys();
        if (keyType === 'roboflow') {
          onRoboflowKeyChange(keyInput.trim());
        }
        setEditingKey(null);
        setKeyInput('');
      }
    } catch (e) {
      console.error('Failed to save API key:', e);
    } finally {
      setSaving(false);
    }
  };

  const deleteKey = async (keyType: string) => {
    try {
      await fetch(`/api/training/api-keys/${keyType}`, { method: 'DELETE' });
      await fetchApiKeys();
      if (keyType === 'roboflow') {
        onRoboflowKeyChange('');
      }
    } catch (e) {
      console.error('Failed to delete API key:', e);
    }
  };

  const keyConfigs = [
    {
      id: 'roboflow',
      name: 'Roboflow',
      description: 'Для датасетов: Construction PPE, Helmet & Vest, PPE Workplace Safety',
      link: 'https://app.roboflow.com',
      linkText: 'app.roboflow.com → Settings → API Keys',
      color: 'blue',
    },
    {
      id: 'kaggle_username',
      name: 'Kaggle Username',
      description: 'Для датасетов: Safety Helmet & Jacket, Hard Hat Workers',
      link: 'https://www.kaggle.com/account',
      linkText: 'kaggle.com → Account → Create API Token',
      color: 'cyan',
    },
    {
      id: 'kaggle_key',
      name: 'Kaggle API Key',
      description: 'API ключ из kaggle.json (для тех же Kaggle датасетов)',
      link: 'https://www.kaggle.com/account',
      linkText: 'Скопируйте "key" из kaggle.json',
      color: 'cyan',
    },
    // v2.10.53: HuggingFace Token убран - не используется для датасетов
  ];

  const renderKeyRow = (config: typeof keyConfigs[0]) => {
    const state = apiKeys[config.id as keyof ApiKeyState];
    const isEditing = editingKey === config.id;

    return (
      <div key={config.id} className={`flex items-center justify-between py-3 ${config.id !== 'roboflow' ? 'border-t border-gray-100' : ''}`}>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm">{config.name}</span>
            {state?.exists && (
              <span className="text-xs text-green-600 bg-green-100 px-2 py-0.5 rounded flex items-center gap-1">
                <Check className="w-3 h-3" />
                Сохранён
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500 mt-0.5">{config.description}</p>
        </div>

        <div className="flex items-center gap-2 ml-4">
          {isEditing ? (
            <>
              <input
                type={showPassword ? 'text' : 'password'}
                value={keyInput}
                onChange={(e) => setKeyInput(e.target.value)}
                placeholder="Вставьте ключ"
                className="input text-sm w-48"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter') saveKey(config.id);
                  if (e.key === 'Escape') { setEditingKey(null); setKeyInput(''); }
                }}
              />
              <button onClick={() => setShowPassword(!showPassword)} className="p-1.5 text-gray-400 hover:text-gray-600">
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
              <button
                onClick={() => saveKey(config.id)}
                disabled={!keyInput.trim() || saving}
                className="btn-primary text-xs py-1.5 px-3"
              >
                {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
              </button>
              <button
                onClick={() => { setEditingKey(null); setKeyInput(''); }}
                className="p-1.5 text-gray-400 hover:text-gray-600"
              >
                <X className="w-4 h-4" />
              </button>
            </>
          ) : state?.exists ? (
            <>
              <span className="text-xs font-mono text-gray-500 bg-gray-100 px-2 py-1 rounded">
                {state.masked}
              </span>
              <button
                onClick={() => { setEditingKey(config.id); setKeyInput(''); }}
                className="p-1.5 text-gray-400 hover:text-blue-600"
                title="Изменить"
              >
                <Edit2 className="w-4 h-4" />
              </button>
              <button
                onClick={() => deleteKey(config.id)}
                className="p-1.5 text-gray-400 hover:text-red-600"
                title="Удалить"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </>
          ) : (
            <button
              onClick={() => { setEditingKey(config.id); setKeyInput(''); }}
              className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1"
            >
              <Plus className="w-3 h-3" />
              Добавить
            </button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg overflow-hidden">
      {/* Header - always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-blue-100/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Key className="w-5 h-5 text-blue-600" />
          <div className="text-left">
            <p className="font-medium text-blue-800">API ключи для загрузки датасетов</p>
            <p className="text-xs text-blue-600">
              {Object.values(apiKeys).filter(k => k.exists).length} из {Object.keys(apiKeys).length} настроено
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {apiKeys.roboflow?.exists && (
            <span 
              className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded cursor-help"
              title="Используется для: Construction PPE, Helmet & Vest, PPE Workplace Safety"
            >
              Roboflow ✓
            </span>
          )}
          {(apiKeys.kaggle_username?.exists && apiKeys.kaggle_key?.exists) && (
            <span 
              className="text-xs bg-cyan-100 text-cyan-700 px-2 py-1 rounded cursor-help"
              title="Используется для: Safety Helmet & Jacket, Hard Hat Workers"
            >
              Kaggle ✓
            </span>
          )}
          {apiKeys.huggingface?.exists && (
            <span 
              className="text-xs bg-yellow-100 text-yellow-700 px-2 py-1 rounded cursor-help"
              title="Используется для: загрузка моделей с HuggingFace Hub"
            >
              HuggingFace ✓
            </span>
          )}
          <svg 
            className={`w-5 h-5 text-blue-600 transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-blue-200 bg-white/50">
          {keyConfigs.map(renderKeyRow)}
          
          <div className="mt-3 pt-3 border-t border-gray-100">
            <p className="text-xs text-gray-500">
              💡 API ключи сохраняются на сервере и используются автоматически при загрузке датасетов
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default DatasetCatalog;
