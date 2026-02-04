import React, { useState, useRef, useCallback, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Upload,
  Image as ImageIcon,
  Play,
  Square,
  Trash2,
  Check,
  Loader2,
  Download,
  FolderOpen,
  Tag,
  Cpu,
  TrendingUp,
  AlertCircle,
  CheckCircle,
  Layers,
  ZoomIn,
  ZoomOut,
  MousePointer,
  Plus,
  X,
  StopCircle,
  ChevronLeft,
  ChevronRight,
  Trophy,
  Wand2,
  Edit3,
} from 'lucide-react';
import { Layout } from '@/components/layout/Layout';
import { useWebSocket } from '@/hooks/useWebSocket';
import { trainingApi } from '@/api/training';
import { useTrainingProgress } from '@/hooks/useTrainingProgress';
import type { TrainingImage } from '@/types/training';
import { PPE_CLASSES, CLASS_COLORS } from '@/types/training';
import { ModelSelector, SplitSelector, AdvancedOptions, type ModelType } from '@/components/training/ModelSelector';
import { WizardStepper, WizardNavigation, getDefaultSteps } from '@/components/training/WizardStepper';

// Re-export CLASSES for local use - now supports custom classes
const DEFAULT_CLASSES = PPE_CLASSES;

// Custom class type
interface CustomClass {
  id: string;
  name: string;
  color: string;
}

export function TrainingPage() {
  const [activeTab, setActiveTab] = useState<'upload' | 'annotate' | 'train' | 'models'>('upload');
  const [selectedImages, setSelectedImages] = useState<Set<string>>(new Set());
  const [currentImage, setCurrentImage] = useState<TrainingImage | null>(null);
  const [selectedClass, setSelectedClass] = useState<string>('no_hardhat');
  const [isDrawing, setIsDrawing] = useState(false);
  const [tempBox, setTempBox] = useState<[number, number, number, number] | null>(null);
  const [zoom, setZoom] = useState(1);
  const [tool, setTool] = useState<'select' | 'draw'>('draw');
  
  // Dataset state
  const [currentDatasetId, setCurrentDatasetId] = useState<string | null>(null);
  const [showDatasetModal, setShowDatasetModal] = useState(false);
  const [newDatasetName, setNewDatasetName] = useState('');
  
  // Pagination state (v2.10.40)
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(50);
  
  // v2.10.61: Custom classes state
  const [customClasses, setCustomClasses] = useState<CustomClass[]>(() => {
    const saved = localStorage.getItem('ppe_custom_classes');
    return saved ? JSON.parse(saved) : [];
  });
  const [showClassModal, setShowClassModal] = useState(false);
  const [newClassName, setNewClassName] = useState('');
  const [newClassColor, setNewClassColor] = useState('#3B82F6');
  const [editingAnnotation, setEditingAnnotation] = useState<string | null>(null);
  
  // v2.10.61: Auto-annotation state
  const [isAutoAnnotating, setIsAutoAnnotating] = useState(false);
  const [autoAnnotateSuggestions, setAutoAnnotateSuggestions] = useState<Array<{
    class_name: string;
    bbox: [number, number, number, number];
    confidence: number;
  }>>([]);
  const [showAutoAnnotateModal, setShowAutoAnnotateModal] = useState(false);
  const autoAnnotateThreshold = 0.3; // Fixed threshold for now
  
  // Combined classes (default + custom)
  const allClasses = [...DEFAULT_CLASSES, ...customClasses.map(c => ({ ...c, shortcut: undefined }))];
  const CLASSES = allClasses;
  
  // Dynamic CLASS_COLORS including custom classes - v2.10.61
  const ALL_CLASS_COLORS: Record<string, string> = {
    ...CLASS_COLORS,
    ...Object.fromEntries(customClasses.map(c => [c.id, c.color]))
  };
  
  // Save custom classes to localStorage
  useEffect(() => {
    localStorage.setItem('ppe_custom_classes', JSON.stringify(customClasses));
  }, [customClasses]);
  
  // Refs for annotation drawing (v2.10.46 - simplified div-based approach)
  const imageContainerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const { isConnected } = useWebSocket();
  
  // Drawing state (v2.10.46 - simplified)
  const [drawStartPos, setDrawStartPos] = useState<{ x: number; y: number } | null>(null);

  // ============================================================================
  // API Queries - Real data from backend
  // ============================================================================
  
  // Fetch datasets
  const { data: datasets = [], isLoading: datasetsLoading } = useQuery({
    queryKey: ['training-datasets'],
    queryFn: () => trainingApi.datasets.list(),
  });

  // Auto-select first dataset if none selected
  useEffect(() => {
    if (!currentDatasetId && datasets.length > 0) {
      setCurrentDatasetId(datasets[0].id);
    }
  }, [datasets, currentDatasetId]);

  // Reset page when dataset changes (v2.10.40)
  useEffect(() => {
    setCurrentPage(1);
  }, [currentDatasetId]);

  // Fetch images for current dataset with pagination (v2.10.40)
  const { data: imagesData, isLoading: imagesLoading } = useQuery({
    queryKey: ['training-images', currentDatasetId, currentPage, pageSize],
    queryFn: async () => {
      if (!currentDatasetId) return { items: [], total: 0, page: 1, page_size: pageSize };
      return trainingApi.images.list(currentDatasetId, { page: currentPage, pageSize });
    },
    enabled: !!currentDatasetId,
  });
  
  const images = imagesData?.items ?? [];
  const totalImages = imagesData?.total ?? 0;
  const totalAnnotatedFromApi = imagesData?.total_annotated ?? 0;
  const totalPages = Math.ceil(totalImages / pageSize);

  // ============================================================================
  // Sync currentImage with images (v2.10.45 - fix annotation display)
  // ============================================================================
  // When images array updates (e.g., after adding/deleting annotation),
  // sync currentImage to show updated annotations on canvas
  useEffect(() => {
    if (currentImage && images.length > 0) {
      const updatedImage = images.find(img => img.id === currentImage.id);
      if (updatedImage) {
        // Compare annotations by ID set - handles add, delete, and replace
        const currentAnnIds = new Set((currentImage.annotations || []).map(a => a.id));
        const updatedAnnIds = new Set((updatedImage.annotations || []).map(a => a.id));
        
        // Check if sets are different (different size or different IDs)
        const setsAreDifferent = 
          currentAnnIds.size !== updatedAnnIds.size ||
          [...currentAnnIds].some(id => !updatedAnnIds.has(id)) ||
          [...updatedAnnIds].some(id => !currentAnnIds.has(id));
        
        if (setsAreDifferent) {
          console.log('🔄 Syncing currentImage with updated annotations:', {
            id: currentImage.id,
            oldIds: [...currentAnnIds],
            newIds: [...updatedAnnIds]
          });
          setCurrentImage(updatedImage);
        }
      }
    }
  }, [images, currentImage]);

  // Fetch current training job (running or most recent)
  const { data: trainingJobs = [] } = useQuery({
    queryKey: ['training-jobs'],
    queryFn: () => trainingApi.jobs.list(undefined, 5),
    refetchInterval: 5000, // Poll every 5 seconds
  });
  
  const trainingJob = trainingJobs.find(j => j.status === 'running') || trainingJobs[0] || null;

  // Use WebSocket for real-time training progress - triggers UI updates
  const { progress: wsProgress } = useTrainingProgress(
    trainingJob?.status === 'running' ? trainingJob.id : null
  );

  // When websocket gives progress, invalidate queries for fresh data
  useEffect(() => {
    if (wsProgress) {
      queryClient.invalidateQueries({ queryKey: ['training-jobs'] });
    }
  }, [wsProgress, queryClient]);

  // Fetch models
  const { data: models = [], isLoading: modelsLoading } = useQuery({
    queryKey: ['training-models'],
    queryFn: () => trainingApi.models.list(),
  });

  // ============================================================================
  // Mutations - Real API calls
  // ============================================================================

  // Create dataset mutation
  const createDatasetMutation = useMutation({
    mutationFn: (data: { name: string; description?: string }) => 
      trainingApi.datasets.create(data),
    onSuccess: (newDataset) => {
      queryClient.invalidateQueries({ queryKey: ['training-datasets'] });
      setCurrentDatasetId(newDataset.id);
      setShowDatasetModal(false);
      setNewDatasetName('');
    },
    onError: (error: Error) => {
      console.error('Failed to create dataset:', error);
      alert(`Не удалось создать датасет: ${error.message}`);
    },
  });

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: async (files: FileList) => {
      if (!currentDatasetId) {
        throw new Error('Выберите или создайте датасет');
      }
      return trainingApi.images.upload(currentDatasetId, files);
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['training-images', currentDatasetId] });
      queryClient.invalidateQueries({ queryKey: ['training-datasets'] });
      if (result.total_errors > 0) {
        console.warn('Some files failed to upload:', result.errors);
      }
    },
  });

  // Delete images mutation
  const deleteImagesMutation = useMutation({
    mutationFn: async (imageIds: string[]) => {
      return trainingApi.images.deleteBatch(imageIds);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['training-images', currentDatasetId] });
      queryClient.invalidateQueries({ queryKey: ['training-datasets'] });
      setSelectedImages(new Set());
    },
  });

  // Add annotation mutation
  const addAnnotationMutation = useMutation({
    mutationFn: async ({ imageId, annotation }: { 
      imageId: string; 
      annotation: { class_name: string; bbox_x1: number; bbox_y1: number; bbox_x2: number; bbox_y2: number } 
    }) => {
      return trainingApi.annotations.create(imageId, annotation);
    },
    onSuccess: () => {
      // v2.10.53: Инвалидируем и images и datasets для обновления счётчиков
      queryClient.invalidateQueries({ queryKey: ['training-images', currentDatasetId] });
      queryClient.invalidateQueries({ queryKey: ['training-datasets'] });
    },
  });

  // Delete annotation mutation
  const deleteAnnotationMutation = useMutation({
    mutationFn: (annotationId: string) => trainingApi.annotations.delete(annotationId),
    onSuccess: () => {
      // v2.10.53: Инвалидируем и images и datasets для обновления счётчиков
      queryClient.invalidateQueries({ queryKey: ['training-images', currentDatasetId] });
      queryClient.invalidateQueries({ queryKey: ['training-datasets'] });
    },
  });

  // Start training mutation
  const startTrainingMutation = useMutation({
    mutationFn: async (params: { 
      // Model selection
      model_type: string;
      model_size: string;
      // Data split
      train_split: number;
      val_split: number;
      test_split: number;
      // Training params
      epochs: number; 
      batch_size: number; 
      learning_rate: number;
      image_size?: number;
      augmentation?: boolean;
      pretrained?: boolean;
      // Advanced
      optimizer?: string;
      patience?: number;
    }) => {
      console.log('[Training] Starting mutation with params:', params);
      console.log('[Training] currentDatasetId:', currentDatasetId);
      
      if (!currentDatasetId) {
        console.error('[Training] No dataset selected!');
        throw new Error('Выберите датасет');
      }
      
      const requestData = {
        dataset_id: currentDatasetId,
        ...params,
      };
      console.log('[Training] API request data:', requestData);
      
      const result = await trainingApi.jobs.create(requestData);
      console.log('[Training] API response:', result);
      return result;
    },
    onSuccess: (data) => {
      console.log('[Training] Mutation success:', data);
      alert(`Обучение запущено! Job ID: ${data.id}\nМодель: ${trainingParams.model_type} ${trainingParams.model_size}\nСтатус: ${data.status}`);
      queryClient.invalidateQueries({ queryKey: ['training-jobs'] });
    },
    onError: (error) => {
      console.error('[Training] Mutation error:', error);
      alert(`Ошибка запуска обучения: ${error.message}`);
    },
  });

  // Cancel training mutation
  const cancelTrainingMutation = useMutation({
    mutationFn: (jobId: string) => trainingApi.jobs.cancel(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['training-jobs'] });
    },
  });

  // Activate model mutation
  const activateModelMutation = useMutation({
    mutationFn: (modelId: string) => trainingApi.models.activate(modelId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['training-models'] });
    },
  });

  // Handle file upload
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      uploadMutation.mutate(e.target.files);
    }
  };

  // Handle drag and drop
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      uploadMutation.mutate(e.dataTransfer.files);
    }
  }, [uploadMutation]);

  // ============================================================================
  // Drawing handlers (v2.10.46 - simplified div-based approach)
  // ============================================================================
  
  // Get relative position within container (0-1 normalized)
  const getRelativePosition = (e: React.MouseEvent): { x: number; y: number } => {
    if (!imageContainerRef.current) return { x: 0, y: 0 };
    const rect = imageContainerRef.current.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height)),
    };
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (tool !== 'draw' || !currentImage) return;
    e.preventDefault();
    const pos = getRelativePosition(e);
    console.log('🖱️ MouseDown at:', pos);
    setDrawStartPos(pos);
    setIsDrawing(true);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDrawing || !drawStartPos) return;
    const pos = getRelativePosition(e);
    // Calculate bbox as [x1, y1, x2, y2] normalized
    setTempBox([
      Math.min(drawStartPos.x, pos.x),
      Math.min(drawStartPos.y, pos.y),
      Math.max(drawStartPos.x, pos.x),
      Math.max(drawStartPos.y, pos.y),
    ]);
  };

  const handleMouseUp = () => {
    if (isDrawing && tempBox && currentImage) {
      const boxWidth = tempBox[2] - tempBox[0];
      const boxHeight = tempBox[3] - tempBox[1];
      
      if (boxWidth > 0.01 && boxHeight > 0.01) {
        console.log('✅ Saving annotation:', { class: selectedClass, bbox: tempBox });
        addAnnotationMutation.mutate({
          imageId: currentImage.id,
          annotation: {
            class_name: selectedClass,
            bbox_x1: tempBox[0],
            bbox_y1: tempBox[1],
            bbox_x2: tempBox[2],
            bbox_y2: tempBox[3],
          },
        }, {
          onSuccess: () => {
            console.log('✅ Аннотация сохранена');
          },
          onError: (error) => {
            console.error('❌ Ошибка сохранения:', error);
            alert('Не удалось сохранить аннотацию');
          }
        });
      } else {
        console.log('⚠️ Box too small, skipping');
      }
    }
    
    setIsDrawing(false);
    setDrawStartPos(null);
    setTempBox(null);
  };

  // Delete annotation handler
  const handleDeleteAnnotation = (annotationId: string) => {
    deleteAnnotationMutation.mutate(annotationId);
  };

  // v2.10.61: Auto-annotation handler
  const handleAutoAnnotate = async () => {
    if (!currentImage) return;
    
    setIsAutoAnnotating(true);
    setAutoAnnotateSuggestions([]);
    
    try {
      const result = await trainingApi.annotations.autoAnnotate(currentImage.id, autoAnnotateThreshold);
      
      if (result.suggestions.length > 0) {
        setAutoAnnotateSuggestions(result.suggestions);
        setShowAutoAnnotateModal(true);
      } else {
        // Show toast notification
        alert('Объекты не найдены. Попробуйте уменьшить порог детекции.');
      }
    } catch (error) {
      console.error('Auto-annotate error:', error);
      alert('Ошибка авто-разметки. Убедитесь что детектор запущен.');
    } finally {
      setIsAutoAnnotating(false);
    }
  };

  // v2.10.61: Apply auto-annotation suggestions
  const handleApplyAutoAnnotations = async (selectedIndexes: number[]) => {
    if (!currentImage) return;
    
    for (const idx of selectedIndexes) {
      const suggestion = autoAnnotateSuggestions[idx];
      if (suggestion) {
        try {
          await trainingApi.annotations.create(currentImage.id, {
            class_name: suggestion.class_name,
            bbox_x1: suggestion.bbox[0],
            bbox_y1: suggestion.bbox[1],
            bbox_x2: suggestion.bbox[2],
            bbox_y2: suggestion.bbox[3],
          });
        } catch (error) {
          console.error('Failed to create annotation:', error);
        }
      }
    }
    
    // Refresh data
    queryClient.invalidateQueries({ queryKey: ['training-images'] });
    setShowAutoAnnotateModal(false);
    setAutoAnnotateSuggestions([]);
  };

  // v2.10.61: Add custom class
  const handleAddClass = () => {
    if (!newClassName.trim()) return;
    
    const newClass: CustomClass = {
      id: newClassName.toLowerCase().replace(/\s+/g, '_'),
      name: newClassName.trim(),
      color: newClassColor,
    };
    
    setCustomClasses(prev => [...prev, newClass]);
    setNewClassName('');
    setNewClassColor('#3B82F6');
    setShowClassModal(false);
  };

  // v2.10.61: Delete custom class
  const handleDeleteClass = (classId: string) => {
    setCustomClasses(prev => prev.filter(c => c.id !== classId));
    // Reset selected class if deleted
    if (selectedClass === classId) {
      setSelectedClass('no_hardhat');
    }
  };

  // v2.10.61: Update annotation class
  const handleUpdateAnnotationClass = async (annotationId: string, newClass: string) => {
    try {
      await trainingApi.annotations.update(annotationId, { class_name: newClass });
      queryClient.invalidateQueries({ queryKey: ['training-images'] });
      setEditingAnnotation(null);
    } catch (error) {
      console.error('Failed to update annotation:', error);
    }
  };

  // Training parameters
  const [trainingParams, setTrainingParams] = useState({
    // Model selection
    model_type: 'yolov8' as string,
    model_size: 'n' as string,
    // Data split
    train_split: 0.7,
    val_split: 0.2,
    test_split: 0.1,
    // Training params
    epochs: 50,
    batch_size: 16,
    learning_rate: 0.001,
    image_size: 640,
    augmentation: true,
    pretrained: true,
    // Advanced
    optimizer: 'auto',
    patience: 50,
  });

  // Calculate stats - v2.10.56: используем total_annotated из API для глобального счёта
  const currentDataset = datasets.find(ds => ds.id === currentDatasetId);
  
  // Подсчёт по текущей странице (fallback если API не вернул total_annotated)
  const pageAnnotatedCount = images.filter((img) => (img.annotations_count || img.annotations?.length || 0) > 0).length;
  const pageTotalAnnotations = images.reduce((sum, img) => sum + (img.annotations_count || img.annotations?.length || 0), 0);
  
  // v2.10.56: Приоритет - total_annotated из API, затем из датасета, затем подсчёт по странице
  const annotatedCount = totalAnnotatedFromApi > 0 
    ? totalAnnotatedFromApi
    : (currentDataset?.labeled_count && currentDataset.labeled_count > 0)
      ? currentDataset.labeled_count
      : pageAnnotatedCount;
  const totalAnnotations = (currentDataset?.annotations_count && currentDataset.annotations_count > 0)
    ? currentDataset.annotations_count
    : pageTotalAnnotations;
  
  // Minimum requirements - reduced for testing
  const MIN_IMAGES = 10;
  const MIN_ANNOTATIONS = 20;

  return (
    <Layout isConnected={isConnected}>
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Обучение модели</h1>
            <p className="text-gray-600">Загрузите изображения, разметьте данные и обучите модель на своих данных</p>
          </div>
          
          {/* Dataset selector */}
          <div className="flex items-center gap-3">
            <label className="text-sm font-medium text-gray-700">Датасет:</label>
            <select
              value={currentDatasetId || ''}
              onChange={(e) => setCurrentDatasetId(e.target.value || null)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              disabled={datasetsLoading}
            >
              {datasets.length === 0 && (
                <option value="">Нет датасетов</option>
              )}
              {datasets.map((ds) => (
                <option key={ds.id} value={ds.id}>
                  {ds.name} ({ds.images_count} изобр.)
                </option>
              ))}
            </select>
            <button
              onClick={() => setShowDatasetModal(true)}
              className="btn-outline text-sm"
              title="Создать новый датасет"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Dataset Create Modal */}
      {showDatasetModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Новый датасет</h2>
              <button onClick={() => setShowDatasetModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Название</label>
                <input
                  type="text"
                  value={newDatasetName}
                  onChange={(e) => setNewDatasetName(e.target.value)}
                  placeholder="Например: Цех №1 - Январь 2026"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => setShowDatasetModal(false)}
                  className="flex-1 btn-outline"
                >
                  Отмена
                </button>
                <button
                  onClick={() => createDatasetMutation.mutate({ name: newDatasetName })}
                  disabled={!newDatasetName.trim() || createDatasetMutation.isPending}
                  className="flex-1 btn-primary"
                >
                  {createDatasetMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    'Создать'
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Wizard Stepper - v2.10.57 */}
      <WizardStepper
        steps={getDefaultSteps(
          totalImages,
          annotatedCount,
          totalImages,
          models.length,
          activeTab
        )}
        onStepClick={(stepId) => setActiveTab(stepId as any)}
        className="mb-6"
      />

      {/* Upload Tab */}
      {activeTab === 'upload' && (
        <div className="space-y-6">
          {/* Warning if no dataset */}
          {!currentDatasetId && (
            <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-yellow-600" />
              <span className="text-yellow-800">Создайте или выберите датасет для загрузки изображений</span>
            </div>
          )}
          
          {/* Drop zone */}
          <div
            className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors ${
              !currentDatasetId 
                ? 'border-gray-200 bg-gray-50 cursor-not-allowed' 
                : uploadMutation.isPending
                  ? 'border-primary-300 bg-primary-50'
                  : 'border-gray-300 hover:border-primary-400 hover:bg-gray-50'
            }`}
            onDrop={currentDatasetId ? handleDrop : undefined}
            onDragOver={(e) => e.preventDefault()}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*"
              onChange={handleFileUpload}
              className="hidden"
              aria-label="Выбрать изображения для загрузки"
              disabled={!currentDatasetId}
            />
            
            {uploadMutation.isPending ? (
              <div className="flex flex-col items-center">
                <Loader2 className="w-12 h-12 text-primary-500 animate-spin mb-4" />
                <p className="text-lg font-medium text-gray-900">Загрузка...</p>
              </div>
            ) : (
              <div className="flex flex-col items-center">
                <Upload className={`w-12 h-12 mb-4 ${currentDatasetId ? 'text-gray-400' : 'text-gray-300'}`} />
                <p className={`text-lg font-medium mb-2 ${currentDatasetId ? 'text-gray-900' : 'text-gray-400'}`}>
                  {currentDatasetId ? 'Перетащите изображения сюда' : 'Сначала выберите датасет'}
                </p>
                {currentDatasetId && (
                  <>
                    <p className="text-gray-500 mb-4">или</p>
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="btn-primary"
                      disabled={!currentDatasetId}
                    >
                      <FolderOpen className="w-4 h-4 mr-2" />
                      Выбрать файлы
                    </button>
                    <p className="text-xs text-gray-400 mt-4">
                      PNG, JPG, JPEG до 10MB каждый
                    </p>
                  </>
                )}
              </div>
            )}
            
            {/* Upload errors */}
            {uploadMutation.isError && (
              <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
                Ошибка загрузки: {(uploadMutation.error as Error)?.message}
              </div>
            )}
          </div>

          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="card p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-blue-100">
                  <ImageIcon className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{totalImages}</p>
                  <p className="text-sm text-gray-500">Изображений</p>
                </div>
              </div>
            </div>
            <div className="card p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-green-100">
                  <Tag className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{annotatedCount}</p>
                  <p className="text-sm text-gray-500">Размечено</p>
                </div>
              </div>
            </div>
            <div className="card p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-purple-100">
                  <Square className="w-5 h-5 text-purple-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{totalAnnotations}</p>
                  <p className="text-sm text-gray-500">Аннотаций</p>
                </div>
              </div>
            </div>
            <div className="card p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-orange-100">
                  <AlertCircle className="w-5 h-5 text-orange-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{totalImages - annotatedCount}</p>
                  <p className="text-sm text-gray-500">Без разметки</p>
                </div>
              </div>
            </div>
          </div>

          {/* Images grid */}
          {images.length > 0 && (
            <div className="card">
              <div className="p-4 border-b border-gray-200 flex items-center justify-between">
                <h2 className="font-semibold">
                  Загруженные изображения
                  <span className="text-sm font-normal text-gray-500 ml-2">
                    ({totalImages} всего)
                  </span>
                </h2>
                {selectedImages.size > 0 && (
                  <button 
                    className="btn-ghost text-danger-600 text-sm"
                    onClick={() => deleteImagesMutation.mutate(Array.from(selectedImages))}
                    disabled={deleteImagesMutation.isPending}
                  >
                    {deleteImagesMutation.isPending ? (
                      <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4 mr-1" />
                    )}
                    Удалить выбранные ({selectedImages.size})
                  </button>
                )}
              </div>
              <div className="p-4 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {images.map((image) => (
                  <div
                    key={image.id}
                    className={`relative aspect-square rounded-lg overflow-hidden border-2 cursor-pointer ${
                      selectedImages.has(image.id) ? 'border-primary-500' : 'border-transparent'
                    }`}
                    onClick={() => {
                      setSelectedImages((prev) => {
                        const next = new Set(prev);
                        if (next.has(image.id)) {
                          next.delete(image.id);
                        } else {
                          next.add(image.id);
                        }
                        return next;
                      });
                    }}
                  >
                    <img
                      src={image.url}
                      alt={image.filename}
                      className="w-full h-full object-cover"
                    />
                    {image.annotations.length > 0 && (
                      <div className="absolute top-2 right-2 px-2 py-0.5 bg-green-500 text-white text-xs rounded-full">
                        {image.annotations.length}
                      </div>
                    )}
                    {selectedImages.has(image.id) && (
                      <div className="absolute inset-0 bg-primary-500/20 flex items-center justify-center">
                        <CheckCircle className="w-8 h-8 text-primary-600" />
                      </div>
                    )}
                  </div>
                ))}
              </div>
              
              {/* Pagination (v2.10.40) */}
              {totalPages > 1 && (
                <div className="p-4 border-t border-gray-200 flex items-center justify-center gap-4">
                  <button
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                    className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="w-5 h-5" />
                  </button>
                  <span className="text-sm text-gray-600">
                    Страница {currentPage} из {totalPages}
                  </span>
                  <button
                    onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                    disabled={currentPage === totalPages}
                    className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronRight className="w-5 h-5" />
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Empty state */}
          {images.length === 0 && !imagesLoading && (
            <div className="text-center py-12 text-gray-500">
              <ImageIcon className="w-16 h-16 mx-auto mb-4 text-gray-300" />
              <p className="text-lg font-medium">Нет загруженных изображений</p>
              <p className="text-sm">Загрузите изображения для начала обучения</p>
            </div>
          )}
          
          {/* Navigation buttons - v2.10.57 */}
          <WizardNavigation
            currentStep={1}
            totalSteps={4}
            onPrevious={() => {}}
            onNext={() => setActiveTab('annotate')}
            canGoNext={totalImages >= 10}
            showPrevious={false}
          />
        </div>
      )}

      {/* Annotate Tab */}
      {activeTab === 'annotate' && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Image list with pagination - v2.10.53: используем глобальный счётчик */}
          <div className="lg:col-span-1 card flex flex-col">
            <div className="p-3 border-b border-gray-200 flex items-center justify-between">
              <h3 className="font-medium text-sm">Изображения</h3>
              <span className="text-xs text-gray-500">
                {annotatedCount} / {totalImages} размечено
              </span>
            </div>
            <div className="flex-1 overflow-y-auto" style={{ maxHeight: '500px' }}>
              {images.length === 0 ? (
                <div className="p-4 text-center text-gray-500 text-sm">
                  Сначала загрузите изображения
                </div>
              ) : (
                images.map((image) => (
                  <button
                    key={image.id}
                    onClick={() => setCurrentImage(image)}
                    className={`w-full p-2 flex items-center gap-3 hover:bg-gray-50 border-l-2 ${
                      currentImage?.id === image.id
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-transparent'
                    }`}
                  >
                    <img
                      src={image.url}
                      alt={image.filename}
                      className="w-20 h-20 rounded object-cover flex-shrink-0"
                    />
                    <div className="flex-1 text-left min-w-0">
                      <p className="text-sm truncate font-medium">{image.filename}</p>
                      <p className="text-xs text-gray-500">
                        {image.annotations.length} аннотаций
                      </p>
                    </div>
                    {image.annotations.length > 0 ? (
                      <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />
                    ) : (
                      <AlertCircle className="w-5 h-5 text-orange-400 flex-shrink-0" />
                    )}
                  </button>
                ))
              )}
            </div>
            {/* Pagination for Annotate tab - v2.10.51 */}
            {totalPages > 1 && (
              <div className="p-3 border-t border-gray-200 flex items-center justify-center gap-2">
                <button
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-xs text-gray-600 min-w-[80px] text-center">
                  {currentPage} / {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>

          {/* Canvas area */}
          <div className="lg:col-span-2 card">
            <div className="p-3 border-b border-gray-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setTool('select')}
                  className={`p-2 rounded ${tool === 'select' ? 'bg-primary-100 text-primary-600' : 'hover:bg-gray-100'}`}
                  aria-label="Инструмент выбора"
                  aria-pressed={tool === 'select'}
                >
                  <MousePointer className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setTool('draw')}
                  className={`p-2 rounded ${tool === 'draw' ? 'bg-primary-100 text-primary-600' : 'hover:bg-gray-100'}`}
                  aria-label="Инструмент рисования"
                  aria-pressed={tool === 'draw'}
                >
                  <Square className="w-4 h-4" />
                </button>
                <div className="w-px h-6 bg-gray-200 mx-2" />
                <button
                  onClick={() => setZoom((z) => Math.min(3, z + 0.25))}
                  className="p-2 rounded hover:bg-gray-100"
                  aria-label="Увеличить"
                >
                  <ZoomIn className="w-4 h-4" />
                </button>
                <span className="text-sm text-gray-500 w-12 text-center">{Math.round(zoom * 100)}%</span>
                <button
                  onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}
                  className="p-2 rounded hover:bg-gray-100"
                  aria-label="Уменьшить"
                >
                  <ZoomOut className="w-4 h-4" />
                </button>
              </div>
              {currentImage && (
                <span className="text-sm text-gray-500">
                  {currentImage.width} × {currentImage.height}
                </span>
              )}
            </div>
            
            <div className="relative bg-gray-900 overflow-auto" style={{ height: '600px' }}>
              {currentImage ? (
                <div className="w-full h-full flex items-center justify-center p-2">
                  {/* Zoomable container - events are captured here */}
                  <div
                    ref={imageContainerRef}
                    className="relative inline-block cursor-crosshair"
                    style={{ 
                      transform: `scale(${zoom})`, 
                      transformOrigin: 'center center',
                    }}
                    onMouseDown={handleMouseDown}
                    onMouseMove={handleMouseMove}
                    onMouseUp={handleMouseUp}
                    onMouseLeave={handleMouseUp}
                  >
                    {/* Image - fits container at zoom=1 */}
                    <img
                      src={currentImage.url}
                      alt={currentImage.filename}
                      className="block max-h-[560px] select-none pointer-events-none"
                      draggable={false}
                      onDragStart={(e) => e.preventDefault()}
                    />
                    
                    {/* Render existing annotations as divs */}
                    {currentImage.annotations.map((ann) => (
                      <div
                        key={ann.id}
                        className="absolute border-2 pointer-events-none"
                        style={{
                          left: `${ann.bbox[0] * 100}%`,
                          top: `${ann.bbox[1] * 100}%`,
                          width: `${(ann.bbox[2] - ann.bbox[0]) * 100}%`,
                          height: `${(ann.bbox[3] - ann.bbox[1]) * 100}%`,
                          borderColor: ALL_CLASS_COLORS[ann.class_name] || '#888',
                        }}
                      >
                        <span
                          className="absolute -top-5 left-0 px-1 text-xs text-white rounded whitespace-nowrap"
                          style={{ 
                            backgroundColor: ALL_CLASS_COLORS[ann.class_name] || '#888',
                            transform: `scale(${1/zoom})`,
                            transformOrigin: 'left bottom',
                          }}
                        >
                          {ann.class_name}
                        </span>
                      </div>
                    ))}
                    
                    {/* Temp box while drawing */}
                    {tempBox && (
                      <div
                        className="absolute border-2 border-dashed pointer-events-none"
                        style={{
                          left: `${tempBox[0] * 100}%`,
                          top: `${tempBox[1] * 100}%`,
                          width: `${(tempBox[2] - tempBox[0]) * 100}%`,
                          height: `${(tempBox[3] - tempBox[1]) * 100}%`,
                          borderColor: ALL_CLASS_COLORS[selectedClass] || '#888',
                          backgroundColor: `${ALL_CLASS_COLORS[selectedClass]}20`,
                        }}
                      />
                    )}
                    
                    {/* Draw mode indicator overlay */}
                    {tool === 'draw' && (
                      <div className="absolute inset-0 pointer-events-none border-2 border-dashed border-primary-400 opacity-30" />
                    )}
                  </div>
                </div>
              ) : (
                <div className="absolute inset-0 flex items-center justify-center text-gray-500">
                  <div className="text-center">
                    <ImageIcon className="w-12 h-12 mx-auto mb-2 text-gray-600" />
                    <p>Выберите изображение для разметки</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Classes & annotations panel */}
          <div className="lg:col-span-1 space-y-4">
            {/* Auto-annotation button - v2.10.61 */}
            {currentImage && (
              <div className="card p-3">
                <button
                  onClick={handleAutoAnnotate}
                  disabled={isAutoAnnotating}
                  className="w-full btn btn-secondary flex items-center justify-center gap-2"
                >
                  {isAutoAnnotating ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Wand2 className="w-4 h-4" />
                  )}
                  {isAutoAnnotating ? 'Анализ...' : 'Авто-разметка'}
                </button>
                <p className="text-xs text-gray-500 mt-2 text-center">
                  Использует текущую модель детектора
                </p>
              </div>
            )}

            {/* Class selector */}
            <div className="card">
              <div className="p-3 border-b border-gray-200 flex items-center justify-between">
                <h3 className="font-medium text-sm">Класс объекта</h3>
                <button
                  onClick={() => setShowClassModal(true)}
                  className="p-1 hover:bg-gray-100 rounded text-gray-500"
                  title="Добавить класс"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>
              <div className="p-2 max-h-60 overflow-y-auto">
                {CLASSES.map((cls) => (
                  <div
                    key={cls.id}
                    className={`w-full p-2 flex items-center gap-2 rounded text-sm ${
                      selectedClass === cls.id
                        ? 'bg-gray-100 font-medium'
                        : 'hover:bg-gray-50'
                    }`}
                  >
                    <button
                      onClick={() => setSelectedClass(cls.id)}
                      className="flex-1 flex items-center gap-2 text-left"
                    >
                      <span
                        className="w-3 h-3 rounded flex-shrink-0"
                        style={{ backgroundColor: cls.color }}
                      />
                      <span className="truncate">{cls.name}</span>
                    </button>
                    {/* Delete button for custom classes */}
                    {customClasses.some(c => c.id === cls.id) && (
                      <button
                        onClick={() => handleDeleteClass(cls.id)}
                        className="p-1 text-gray-400 hover:text-red-500"
                        title="Удалить класс"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Current image annotations */}
            {currentImage && (
              <div className="card">
                <div className="p-3 border-b border-gray-200 flex items-center justify-between">
                  <h3 className="font-medium text-sm">Аннотации</h3>
                  <span className="text-xs text-gray-500">
                    {currentImage.annotations.length}
                  </span>
                </div>
                <div className="max-h-64 overflow-y-auto">
                  {currentImage.annotations.length === 0 ? (
                    <div className="p-4 text-center text-gray-500 text-sm">
                      Нарисуйте рамку вокруг объекта
                    </div>
                  ) : (
                    currentImage.annotations.map((ann) => (
                      <div
                        key={ann.id}
                        className="p-2 flex items-center justify-between hover:bg-gray-50 border-b border-gray-100"
                      >
                        <div className="flex items-center gap-2 flex-1 min-w-0">
                          <span
                            className="w-2 h-2 rounded flex-shrink-0"
                            style={{ backgroundColor: ALL_CLASS_COLORS[ann.class_name] || '#888' }}
                          />
                          {editingAnnotation === ann.id ? (
                            <select
                              value={ann.class_name}
                              onChange={(e) => handleUpdateAnnotationClass(ann.id, e.target.value)}
                              className="text-sm border rounded px-1 py-0.5 flex-1"
                              autoFocus
                              onBlur={() => setEditingAnnotation(null)}
                            >
                              {CLASSES.map((cls) => (
                                <option key={cls.id} value={cls.id}>
                                  {cls.name}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <span 
                              className="text-sm truncate cursor-pointer hover:text-primary-600"
                              onClick={() => setEditingAnnotation(ann.id)}
                              title="Нажмите для изменения класса"
                            >
                              {ann.class_name}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1 flex-shrink-0">
                          <button
                            className="p-1 text-gray-400 hover:text-primary-500 rounded"
                            aria-label="Изменить класс"
                            onClick={() => setEditingAnnotation(ann.id)}
                          >
                            <Edit3 className="w-3 h-3" />
                          </button>
                          <button
                            className="p-1 text-gray-400 hover:text-danger-500 rounded"
                            aria-label="Удалить аннотацию"
                            onClick={() => handleDeleteAnnotation(ann.id)}
                            disabled={deleteAnnotationMutation.isPending}
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* Keyboard shortcuts */}
            <div className="card p-3">
              <h3 className="font-medium text-sm mb-2">Горячие клавиши</h3>
              <div className="text-xs text-gray-500 space-y-1">
                <div className="flex justify-between">
                  <span>Рисовать</span>
                  <kbd className="px-1 bg-gray-100 rounded">D</kbd>
                </div>
                <div className="flex justify-between">
                  <span>Выбрать</span>
                  <kbd className="px-1 bg-gray-100 rounded">V</kbd>
                </div>
                <div className="flex justify-between">
                  <span>Удалить</span>
                  <kbd className="px-1 bg-gray-100 rounded">Del</kbd>
                </div>
                <div className="flex justify-between">
                  <span>След. изображение</span>
                  <kbd className="px-1 bg-gray-100 rounded">→</kbd>
                </div>
              </div>
            </div>
          </div>
          
          {/* Navigation buttons - v2.10.57 */}
          <div className="lg:col-span-4">
            <WizardNavigation
              currentStep={2}
              totalSteps={4}
              onPrevious={() => setActiveTab('upload')}
              onNext={() => setActiveTab('train')}
              canGoNext={annotatedCount >= 20}
            />
          </div>
        </div>
      )}

      {/* Train Tab */}
      {activeTab === 'train' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Model Selection & Training parameters */}
          <div className="lg:col-span-2 space-y-6">
            {/* Model Selection */}
            <div className="card">
              <div className="p-4 border-b border-gray-200">
                <h3 className="font-semibold">Выбор модели</h3>
                <p className="text-sm text-gray-500">Выберите архитектуру и размер модели YOLO</p>
              </div>
              <div className="p-4">
                <ModelSelector
                  selectedModel={trainingParams.model_type as ModelType}
                  selectedSize={trainingParams.model_size}
                  onModelChange={(model) => setTrainingParams(p => ({ ...p, model_type: model }))}
                  onSizeChange={(size) => setTrainingParams(p => ({ ...p, model_size: size }))}
                />
              </div>
            </div>

            {/* Data Split */}
            <div className="card">
              <div className="p-4 border-b border-gray-200">
                <h3 className="font-semibold">Разделение данных</h3>
              </div>
              <div className="p-4">
                <SplitSelector
                  trainSplit={trainingParams.train_split}
                  valSplit={trainingParams.val_split}
                  testSplit={trainingParams.test_split}
                  onTrainChange={(v) => setTrainingParams(p => ({ ...p, train_split: v }))}
                  onValChange={(v) => setTrainingParams(p => ({ ...p, val_split: v }))}
                  onTestChange={(v) => setTrainingParams(p => ({ ...p, test_split: v }))}
                />
              </div>
            </div>

            {/* Advanced Options (collapsible) */}
            <details className="card">
              <summary className="p-4 border-b border-gray-200 cursor-pointer">
                <span className="font-semibold">Дополнительные настройки</span>
              </summary>
              <div className="p-4">
                <AdvancedOptions
                  optimizer={trainingParams.optimizer}
                  patience={trainingParams.patience}
                  onOptimizerChange={(v) => setTrainingParams(p => ({ ...p, optimizer: v }))}
                  onPatienceChange={(v) => setTrainingParams(p => ({ ...p, patience: v }))}
                />
              </div>
            </details>
          </div>

          {/* Right sidebar - Parameters & Start */}
          <div className="lg:col-span-1 space-y-4">
            <div className="card">
              <div className="p-4 border-b border-gray-200">
                <h3 className="font-semibold">Параметры обучения</h3>
              </div>
              <div className="p-4 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Эпохи
                  </label>
                  <input
                    type="number"
                    value={trainingParams.epochs}
                    onChange={(e) => setTrainingParams((p) => ({ ...p, epochs: Number(e.target.value) }))}
                    className="input"
                    min={1}
                    max={500}
                  />
                  <p className="text-xs text-gray-500 mt-1">Рекомендуется: 50-100</p>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Batch Size
                  </label>
                  <select
                    value={trainingParams.batch_size}
                    onChange={(e) => setTrainingParams((p) => ({ ...p, batch_size: Number(e.target.value) }))}
                    className="input"
                  >
                    <option value={4}>4 (мало VRAM)</option>
                    <option value={8}>8</option>
                    <option value={16}>16 (рекомендуется)</option>
                    <option value={32}>32</option>
                    <option value={64}>64</option>
                    <option value={128}>128 (много VRAM)</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Image Size
                  </label>
                  <select
                    value={trainingParams.image_size}
                    onChange={(e) => setTrainingParams((p) => ({ ...p, image_size: Number(e.target.value) }))}
                    className="input"
                  >
                    <option value={320}>320 (быстро)</option>
                    <option value={480}>480</option>
                    <option value={640}>640 (рекомендуется)</option>
                    <option value={800}>800</option>
                    <option value={1024}>1024 (точно)</option>
                    <option value={1280}>1280 (максимум)</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Learning Rate
                  </label>
                  <select
                    value={trainingParams.learning_rate}
                    onChange={(e) => setTrainingParams((p) => ({ ...p, learning_rate: Number(e.target.value) }))}
                    className="input"
                  >
                    <option value={0.01}>0.01 (высокий)</option>
                    <option value={0.001}>0.001 (стандартный)</option>
                    <option value={0.0001}>0.0001 (низкий)</option>
                  </select>
                </div>
                
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="augmentation"
                    checked={trainingParams.augmentation}
                    onChange={(e) => setTrainingParams((p) => ({ ...p, augmentation: e.target.checked }))}
                    className="rounded"
                  />
                  <label htmlFor="augmentation" className="text-sm text-gray-700">
                    Аугментация данных
                  </label>
                </div>
                
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="pretrained"
                    checked={trainingParams.pretrained}
                    onChange={(e) => setTrainingParams((p) => ({ ...p, pretrained: e.target.checked }))}
                    className="rounded"
                  />
                  <label htmlFor="pretrained" className="text-sm text-gray-700">
                    Использовать pretrained веса
                  </label>
                </div>
              </div>
              <div className="p-4 border-t border-gray-200">
                {trainingJob?.status === 'running' ? (
                  <button
                    onClick={() => cancelTrainingMutation.mutate(trainingJob.id)}
                    disabled={cancelTrainingMutation.isPending}
                    className="w-full btn-outline text-danger-600 border-danger-300 hover:bg-danger-50"
                  >
                    {cancelTrainingMutation.isPending ? (
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <StopCircle className="w-4 h-4 mr-2" />
                    )}
                    Остановить обучение
                  </button>
                ) : (
                  <button
                    onClick={() => startTrainingMutation.mutate(trainingParams)}
                    disabled={annotatedCount < MIN_IMAGES || totalAnnotations < MIN_ANNOTATIONS || startTrainingMutation.isPending}
                    className="w-full btn-primary"
                  >
                    {startTrainingMutation.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Запуск...
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4 mr-2" />
                        Начать обучение
                      </>
                    )}
                  </button>
                )}
                {annotatedCount < MIN_IMAGES && (
                  <p className="text-xs text-orange-500 mt-2 text-center">
                    Нужно минимум {MIN_IMAGES} размеченных изображений (сейчас: {annotatedCount})
                  </p>
                )}
                {annotatedCount >= MIN_IMAGES && totalAnnotations < MIN_ANNOTATIONS && (
                  <p className="text-xs text-orange-500 mt-2 text-center">
                    Нужно минимум {MIN_ANNOTATIONS} аннотаций (сейчас: {totalAnnotations}). Выберите датасет с разметкой.
                  </p>
                )}
                {startTrainingMutation.isError && (
                  <p className="text-xs text-red-500 mt-2 text-center font-medium">
                    Ошибка: {(startTrainingMutation.error as Error)?.message}
                  </p>
                )}
              </div>
            </div>

            {/* Requirements */}
            <div className="card p-4">
              <h3 className="font-medium text-sm mb-3">Требования</h3>
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  {annotatedCount >= MIN_IMAGES ? (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-orange-400" />
                  )}
                  <span>Минимум {MIN_IMAGES} изображений ({annotatedCount}/{MIN_IMAGES})</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  {totalAnnotations >= MIN_ANNOTATIONS ? (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-orange-400" />
                  )}
                  <span>Минимум {MIN_ANNOTATIONS} аннотаций ({totalAnnotations}/{MIN_ANNOTATIONS})</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  <span>GPU доступен</span>
                </div>
              </div>
            </div>
          </div>

          {/* Training progress */}
          <div className="lg:col-span-2 space-y-4">
            {trainingJob ? (
              <>
                {/* Progress card */}
                <div className="card p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold">Прогресс обучения</h3>
                    <span className={`badge ${
                      trainingJob.status === 'running' ? 'badge-primary' :
                      trainingJob.status === 'completed' ? 'badge-success' :
                      trainingJob.status === 'failed' ? 'badge-danger' : 'bg-gray-100'
                    }`}>
                      {trainingJob.status === 'running' && <Loader2 className="w-3 h-3 mr-1 animate-spin" />}
                      {trainingJob.status === 'running' ? 'Обучается' :
                       trainingJob.status === 'completed' ? 'Завершено' :
                       trainingJob.status === 'failed' ? 'Ошибка' : 'Ожидание'}
                    </span>
                  </div>
                  
                  {/* Progress bar */}
                  <div className="mb-4">
                    <div className="flex justify-between text-sm mb-1">
                      <span>Эпоха {trainingJob.epochs_completed}/{trainingJob.epochs_total}</span>
                      <span>{Math.round(trainingJob.progress)}%</span>
                    </div>
                    <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary-500 transition-all duration-300"
                        style={{ width: `${trainingJob.progress}%` }}
                      />
                    </div>
                  </div>
                  
                  {/* Metrics */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 bg-gray-50 rounded-lg">
                      <p className="text-sm text-gray-500">Loss</p>
                      <p className="text-xl font-bold">{trainingJob.current_loss?.toFixed(4) || '-'}</p>
                    </div>
                    <div className="p-3 bg-gray-50 rounded-lg">
                      <p className="text-sm text-gray-500">Best mAP@50</p>
                      <p className="text-xl font-bold">{trainingJob.best_map50 ? (trainingJob.best_map50 * 100).toFixed(1) + '%' : '-'}</p>
                    </div>
                  </div>
                  
                  {trainingJob.status === 'failed' && trainingJob.error_message && (
                    <div className="mt-4 p-3 bg-danger-50 text-danger-700 rounded-lg text-sm">
                      {trainingJob.error_message}
                    </div>
                  )}
                </div>

                {/* Training chart placeholder */}
                <div className="card p-6">
                  <h3 className="font-semibold mb-4">График обучения</h3>
                  <div className="h-64 bg-gray-50 rounded-lg flex items-center justify-center text-gray-400">
                    <TrendingUp className="w-12 h-12" />
                    <span className="ml-2">Loss / mAP график</span>
                  </div>
                </div>
              </>
            ) : (
              <div className="card p-12 text-center">
                <Cpu className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  Готово к обучению
                </h3>
                <p className="text-gray-500 mb-4">
                  Настройте параметры и нажмите "Начать обучение"
                </p>
                <div className="text-sm text-gray-400">
                  <p>Размечено: {annotatedCount} изображений</p>
                  <p>Всего аннотаций: {totalAnnotations}</p>
                </div>
              </div>
            )}
          </div>
          
          {/* Navigation buttons - v2.10.57 */}
          <WizardNavigation
            currentStep={3}
            totalSteps={4}
            onPrevious={() => setActiveTab('annotate')}
            onNext={() => setActiveTab('models')}
            canGoNext={models.length > 0}
            nextLabel="Результаты →"
          />
        </div>
      )}

      {/* Models Tab - Renamed to "Результаты" in v2.10.57 */}
      {activeTab === 'models' && (
        <div className="space-y-6">
          {/* Success Banner if has trained models */}
          {models.length > 0 && (
            <div className="p-4 bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-xl">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-100 rounded-full">
                  <Trophy className="w-6 h-6 text-green-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-green-900">Обучение завершено успешно!</h3>
                  <p className="text-sm text-green-700">У вас есть {models.length} обученных моделей. Активируйте нужную в Настройках → Детектор.</p>
                </div>
              </div>
            </div>
          )}

          {/* Trained Custom Models */}
          <div className="card">
            <div className="p-4 border-b border-gray-200 bg-green-50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Layers className="w-5 h-5 text-green-600" />
                  <h3 className="font-semibold">Обученные модели</h3>
                  <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">{models.length}</span>
                </div>
                {modelsLoading && <Loader2 className="w-4 h-4 animate-spin text-gray-400" />}
              </div>
              <p className="text-sm text-gray-500 mt-1">Модели, обученные на ваших данных</p>
            </div>
            <div className="divide-y divide-gray-100">
              {models.length > 0 ? (
                models.map((model) => (
                  <div
                    key={model.id}
                    className={`p-4 ${model.is_active ? 'bg-green-50' : 'hover:bg-gray-50'} transition-colors`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className={`p-3 rounded-lg ${model.is_active ? 'bg-green-100' : 'bg-gray-100'}`}>
                          <Layers className={`w-6 h-6 ${model.is_active ? 'text-green-600' : 'text-gray-600'}`} />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="font-semibold">{model.name}</h4>
                            {model.is_active && (
                              <span className="px-2 py-0.5 bg-green-500 text-white text-xs rounded-full">✓ Активная</span>
                            )}
                          </div>
                          <p className="text-sm text-gray-500">
                            Создана: {new Date(model.created_at).toLocaleDateString('ru')}
                            {model.training_images_count && ` • ${model.training_images_count} изображений`}
                          </p>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-6">
                        <div className="text-center">
                          <p className="text-2xl font-bold text-green-600">{(model.map50 * 100).toFixed(1)}%</p>
                          <p className="text-xs text-gray-500">mAP@50</p>
                        </div>
                        <div className="text-center">
                          <p className="text-2xl font-bold">{(model.map50_95 * 100).toFixed(1)}%</p>
                          <p className="text-xs text-gray-500">mAP@50-95</p>
                        </div>
                        
                        <div className="flex items-center gap-2">
                          {!model.is_active && (
                            <button 
                              className="btn-primary text-sm"
                              onClick={() => activateModelMutation.mutate(model.id)}
                              disabled={activateModelMutation.isPending}
                            >
                              {activateModelMutation.isPending ? (
                                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                              ) : (
                                <Check className="w-4 h-4 mr-1" />
                              )}
                              Активировать
                            </button>
                          )}
                          <a 
                            href={trainingApi.models.getDownloadUrl(model.id)}
                            className="btn-outline text-sm"
                            download
                          >
                            <Download className="w-4 h-4 mr-1" />
                            Скачать
                          </a>
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-8 text-center text-gray-500">
                  <Layers className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                  <p className="font-medium">Нет обученных моделей</p>
                  <p className="text-sm">Перейдите на вкладку "Обучение" чтобы создать свою первую модель</p>
                </div>
              )}
            </div>
          </div>

          {/* Info Block */}
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="font-medium text-blue-900">Как работает обучение?</h4>
                <ul className="text-sm text-blue-800 mt-2 space-y-1">
                  <li>1. <strong>Шаг "Данные"</strong> — загрузите изображения с камер или файлы</li>
                  <li>2. <strong>Шаг "Разметка"</strong> — отметьте объекты на изображениях (мин. 20 аннотаций)</li>
                  <li>3. <strong>Шаг "Обучение"</strong> — выберите модель и запустите обучение</li>
                  <li>4. <strong>Шаг "Результаты"</strong> — просмотрите метрики и активируйте модель</li>
                </ul>
                <p className="text-xs text-blue-600 mt-3">
                  💡 Для активации модели перейдите в Настройки → Детектор
                </p>
              </div>
            </div>
          </div>
          
          {/* Navigation buttons - v2.10.57 */}
          <WizardNavigation
            currentStep={4}
            totalSteps={4}
            onPrevious={() => setActiveTab('train')}
            onNext={() => {}}
            showNext={false}
          />
        </div>
      )}

      {/* Modal: Add Custom Class - v2.10.61 */}
      {showClassModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Добавить класс</h3>
              <button
                onClick={() => setShowClassModal(false)}
                className="p-1 hover:bg-gray-100 rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Название класса</label>
                <input
                  type="text"
                  value={newClassName}
                  onChange={(e) => setNewClassName(e.target.value)}
                  placeholder="Например: gloves, boots, mask"
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-1">Цвет</label>
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={newClassColor}
                    onChange={(e) => setNewClassColor(e.target.value)}
                    className="w-12 h-10 rounded cursor-pointer"
                  />
                  <input
                    type="text"
                    value={newClassColor}
                    onChange={(e) => setNewClassColor(e.target.value)}
                    className="flex-1 px-3 py-2 border rounded-lg"
                  />
                </div>
              </div>
              
              {/* Preset colors */}
              <div>
                <label className="block text-sm font-medium mb-2">Быстрый выбор</label>
                <div className="flex flex-wrap gap-2">
                  {['#EF4444', '#F97316', '#EAB308', '#22C55E', '#3B82F6', '#8B5CF6', '#EC4899', '#6B7280'].map((color) => (
                    <button
                      key={color}
                      onClick={() => setNewClassColor(color)}
                      className={`w-8 h-8 rounded-full border-2 ${newClassColor === color ? 'border-gray-800' : 'border-transparent'}`}
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </div>
              </div>
            </div>
            
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowClassModal(false)}
                className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
              >
                Отмена
              </button>
              <button
                onClick={handleAddClass}
                disabled={!newClassName.trim()}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
              >
                Добавить
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Auto-Annotation Results - v2.10.61 */}
      {showAutoAnnotateModal && autoAnnotateSuggestions.length > 0 && (
        <AutoAnnotateModal
          suggestions={autoAnnotateSuggestions}
          classes={CLASSES}
          onApply={handleApplyAutoAnnotations}
          onClose={() => {
            setShowAutoAnnotateModal(false);
            setAutoAnnotateSuggestions([]);
          }}
        />
      )}
    </Layout>
  );
}

// Auto-Annotate Modal Component - v2.10.61
function AutoAnnotateModal({
  suggestions,
  classes,
  onApply,
  onClose,
}: {
  suggestions: Array<{ class_name: string; bbox: [number, number, number, number]; confidence: number }>;
  classes: Array<{ id: string; name: string; color: string }>;
  onApply: (selectedIndexes: number[]) => void;
  onClose: () => void;
}) {
  const [selectedIndexes, setSelectedIndexes] = useState<Set<number>>(
    new Set(suggestions.map((_, i) => i)) // Select all by default
  );

  const toggleSelection = (index: number) => {
    setSelectedIndexes(prev => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const selectAll = () => setSelectedIndexes(new Set(suggestions.map((_, i) => i)));
  const deselectAll = () => setSelectedIndexes(new Set());

  const getClassColor = (className: string) => {
    const cls = classes.find(c => c.id === className);
    return cls?.color || '#888';
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg p-6 max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Wand2 className="w-5 h-5 text-primary-600" />
            Результаты авто-разметки
          </h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-sm text-gray-600 mb-4">
          Найдено {suggestions.length} объект(ов). Выберите, какие добавить:
        </p>

        <div className="flex items-center gap-2 mb-3">
          <button
            onClick={selectAll}
            className="text-xs text-primary-600 hover:underline"
          >
            Выбрать все
          </button>
          <span className="text-gray-300">|</span>
          <button
            onClick={deselectAll}
            className="text-xs text-gray-500 hover:underline"
          >
            Снять выделение
          </button>
          <span className="ml-auto text-xs text-gray-500">
            Выбрано: {selectedIndexes.size} / {suggestions.length}
          </span>
        </div>

        <div className="flex-1 overflow-y-auto border rounded-lg divide-y">
          {suggestions.map((suggestion, index) => (
            <label
              key={index}
              className={`flex items-center gap-3 p-3 cursor-pointer hover:bg-gray-50 ${
                selectedIndexes.has(index) ? 'bg-primary-50' : ''
              }`}
            >
              <input
                type="checkbox"
                checked={selectedIndexes.has(index)}
                onChange={() => toggleSelection(index)}
                className="w-4 h-4 rounded text-primary-600"
              />
              <span
                className="w-3 h-3 rounded flex-shrink-0"
                style={{ backgroundColor: getClassColor(suggestion.class_name) }}
              />
              <span className="flex-1 text-sm font-medium">
                {suggestion.class_name}
              </span>
              <span className="text-xs text-gray-500">
                {Math.round(suggestion.confidence * 100)}%
              </span>
            </label>
          ))}
        </div>

        <div className="flex justify-end gap-3 mt-4 pt-4 border-t">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
          >
            Отмена
          </button>
          <button
            onClick={() => onApply(Array.from(selectedIndexes))}
            disabled={selectedIndexes.size === 0}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center gap-2"
          >
            <Check className="w-4 h-4" />
            Добавить ({selectedIndexes.size})
          </button>
        </div>
      </div>
    </div>
  );
}
