import {
  TrainingDataset,
  TrainingImage,
  Annotation,
  TrainingJob,
  TrainingLog,
  ModelVersion,
  UploadResult,
  ClassDistribution,
  TrainingStats,
  HistoryEntry,
} from '@/types/training';

const API_BASE = '/api/training';

// Helper for API calls
async function apiCall<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const token = localStorage.getItem('token');
  
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

// ============================================================================
// Dataset API
// ============================================================================

export const datasetApi = {
  list: (status?: string): Promise<TrainingDataset[]> => {
    const params = status ? `?status=${status}` : '';
    return apiCall(`/datasets${params}`);
  },

  get: (id: string): Promise<TrainingDataset> => {
    return apiCall(`/datasets/${id}`);
  },

  create: (data: { name: string; description?: string }): Promise<TrainingDataset> => {
    return apiCall('/datasets', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  update: (
    id: string,
    data: { name?: string; description?: string; status?: string }
  ): Promise<TrainingDataset> => {
    return apiCall(`/datasets/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  delete: (id: string): Promise<{ status: string }> => {
    return apiCall(`/datasets/${id}`, {
      method: 'DELETE',
    });
  },
};

// ============================================================================
// Image API
// ============================================================================

export const imageApi = {
  list: (
    datasetId: string,
    options?: { page?: number; pageSize?: number; status?: string }
  ): Promise<{
    items: TrainingImage[];
    total: number;
    total_annotated?: number;  // v2.10.56 - global annotated count
    page: number;
    page_size: number;
  }> => {
    const params = new URLSearchParams();
    if (options?.page) params.set('page', String(options.page));
    if (options?.pageSize) params.set('page_size', String(options.pageSize));
    if (options?.status) params.set('status', options.status);
    
    const queryString = params.toString();
    return apiCall(`/datasets/${datasetId}/images${queryString ? `?${queryString}` : ''}`);
  },

  upload: async (datasetId: string, files: FileList): Promise<UploadResult> => {
    const token = localStorage.getItem('token');
    const formData = new FormData();
    
    Array.from(files).forEach((file) => {
      formData.append('files', file);
    });

    const response = await fetch(`${API_BASE}/datasets/${datasetId}/images`, {
      method: 'POST',
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(error.detail);
    }

    return response.json();
  },

  getUrl: (imageId: string): string => {
    return `${API_BASE}/images/${imageId}`;
  },

  delete: (imageId: string): Promise<{ status: string }> => {
    return apiCall(`/images/${imageId}`, {
      method: 'DELETE',
    });
  },

  deleteBatch: async (imageIds: string[]): Promise<{ deleted: number }> => {
    const results = await Promise.allSettled(
      imageIds.map((id) => imageApi.delete(id))
    );
    const deleted = results.filter((r) => r.status === 'fulfilled').length;
    return { deleted };
  },
};

// ============================================================================
// Annotation API
// ============================================================================

export const annotationApi = {
  list: (imageId: string): Promise<Annotation[]> => {
    return apiCall(`/images/${imageId}/annotations`);
  },

  create: (
    imageId: string,
    data: {
      class_name: string;
      bbox_x1: number;
      bbox_y1: number;
      bbox_x2: number;
      bbox_y2: number;
    }
  ): Promise<Annotation> => {
    return apiCall(`/images/${imageId}/annotations`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  createBatch: (
    imageId: string,
    annotations: Array<{
      class_name: string;
      bbox_x1: number;
      bbox_y1: number;
      bbox_x2: number;
      bbox_y2: number;
    }>
  ): Promise<{ created: number; annotations: Annotation[] }> => {
    return apiCall(`/images/${imageId}/annotations/batch`, {
      method: 'POST',
      body: JSON.stringify({ annotations }),
    });
  },

  update: (
    annotationId: string,
    data: {
      class_name?: string;
      bbox_x1?: number;
      bbox_y1?: number;
      bbox_x2?: number;
      bbox_y2?: number;
    }
  ): Promise<Annotation> => {
    return apiCall(`/annotations/${annotationId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  delete: (annotationId: string): Promise<{ status: string }> => {
    return apiCall(`/annotations/${annotationId}`, {
      method: 'DELETE',
    });
  },

  // Auto-annotation using detector
  autoAnnotate: (
    imageId: string,
    threshold?: number
  ): Promise<{
    image_id: string;
    suggestions: Array<{
      class_name: string;
      bbox: [number, number, number, number];
      confidence: number;
    }>;
    count: number;
    threshold: number;
  }> => {
    const params = threshold ? `?threshold=${threshold}` : '';
    return apiCall(`/images/${imageId}/auto-annotate${params}`, {
      method: 'POST',
    });
  },

  // History / Undo
  getHistory: (imageId: string, limit?: number): Promise<HistoryEntry[]> => {
    const params = limit ? `?limit=${limit}` : '';
    return apiCall(`/images/${imageId}/history${params}`);
  },

  undo: (imageId: string): Promise<{ status: string; action: string }> => {
    return apiCall(`/images/${imageId}/undo`, {
      method: 'POST',
    });
  },
};

// ============================================================================
// Training Job API
// ============================================================================

export const trainingJobApi = {
  list: (status?: string, limit?: number): Promise<TrainingJob[]> => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (limit) params.set('limit', String(limit));
    
    const queryString = params.toString();
    return apiCall(`/jobs${queryString ? `?${queryString}` : ''}`);
  },

  get: (jobId: string): Promise<TrainingJob> => {
    return apiCall(`/jobs/${jobId}`);
  },

  create: (data: {
    dataset_id: string;
    name?: string;
    // Model selection
    model_type?: string;
    model_size?: string;
    // Data split
    train_split?: number;
    val_split?: number;
    test_split?: number;
    // Training params
    epochs?: number;
    batch_size?: number;
    learning_rate?: number;
    image_size?: number;
    augmentation?: boolean;
    pretrained?: boolean;
    // Advanced
    optimizer?: string;
    patience?: number;
  }): Promise<TrainingJob> => {
    return apiCall('/jobs', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  cancel: (jobId: string): Promise<{ status: string }> => {
    return apiCall(`/jobs/${jobId}/cancel`, {
      method: 'POST',
    });
  },

  getLogs: (jobId: string): Promise<{ logs: TrainingLog[] }> => {
    return apiCall(`/jobs/${jobId}/logs`);
  },
};

// ============================================================================
// Model API
// ============================================================================

export const modelApi = {
  list: (): Promise<ModelVersion[]> => {
    return apiCall('/models');
  },

  activate: (modelId: string): Promise<{ status: string; model_id: string }> => {
    return apiCall(`/models/${modelId}/activate`, {
      method: 'POST',
    });
  },

  getDownloadUrl: (modelId: string): string => {
    return `${API_BASE}/models/${modelId}/download`;
  },
};

// ============================================================================
// Statistics API
// ============================================================================

export const trainingStatsApi = {
  getOverview: (): Promise<TrainingStats> => {
    return apiCall('/stats/overview');
  },

  getClassDistribution: (datasetId?: string): Promise<{
    distribution: ClassDistribution[];
    total: number;
  }> => {
    const params = datasetId ? `?dataset_id=${datasetId}` : '';
    return apiCall(`/stats/class-distribution${params}`);
  },
};

// ============================================================================
// Combined Training API
// ============================================================================

export const trainingApi = {
  datasets: datasetApi,
  images: imageApi,
  annotations: annotationApi,
  jobs: trainingJobApi,
  models: modelApi,
  stats: trainingStatsApi,
};

export default trainingApi;
