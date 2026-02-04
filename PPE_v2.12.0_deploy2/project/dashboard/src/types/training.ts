// Training Module Types
// ============================================================================

export interface TrainingImage {
  id: string;
  filename: string;
  original_filename: string;
  url?: string;
  width: number;
  height: number;
  file_size: number;
  status: 'pending' | 'annotated' | 'validated' | 'rejected';
  annotations: Annotation[];
  annotations_count: number;
  uploaded_at: string;
}

export interface Annotation {
  id: string;
  class_name: string;
  bbox: [number, number, number, number]; // x1, y1, x2, y2 (normalized 0-1)
  confidence?: number;
  created_by?: string;
  created_at?: string;
  verified?: boolean;
}

export interface TrainingDataset {
  id: string;
  name: string;
  description?: string;
  status: 'draft' | 'ready' | 'training' | 'completed' | 'archived' | 'active' | 'created';
  images_count: number;
  annotations_count: number;
  labeled_count?: number; // Number of images with at least one annotation
  created_by: string;
  created_at: string;
}

export interface TrainingJob {
  id: string;
  dataset_id: string;
  name?: string;
  status: 'pending' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  epochs_total: number;
  epochs_completed: number;
  batch_size: number;
  learning_rate: number;
  current_loss?: number;
  best_map50?: number;
  best_map50_95?: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
}

export interface TrainingLog {
  epoch: number;
  train_loss?: number;
  val_loss?: number;
  map50?: number;
  map50_95?: number;
  learning_rate?: number;
  timestamp: string;
}

export interface ModelVersion {
  id: string;
  name: string;
  description?: string;
  training_job_id?: string;
  map50: number;
  map50_95: number;
  precision_avg?: number;
  recall_avg?: number;
  is_active: boolean;
  is_default?: boolean;
  training_images_count?: number;
  created_at: string;
}

export interface TrainingParams {
  epochs: number;
  batch_size: number;
  learning_rate: number;
  image_size: number;
  augmentation: boolean;
  pretrained: boolean;
}

export interface HistoryEntry {
  id: string;
  action: 'create' | 'update' | 'delete';
  annotation_data: {
    id: string;
    class_name?: string;
    bbox?: [number, number, number, number];
    previous?: {
      class_name: string;
      bbox: [number, number, number, number];
    };
  };
  created_at: string;
}

export interface UploadResult {
  uploaded: Array<{
    id: string;
    filename: string;
    width: number;
    height: number;
  }>;
  errors: Array<{
    filename: string;
    error: string;
  }>;
  total_uploaded: number;
  total_errors: number;
}

export interface ClassDistribution {
  class_name: string;
  count: number;
  percentage: number;
}

export interface TrainingStats {
  datasets: number;
  images: number;
  annotations: number;
  completed_jobs: number;
  running_jobs: number;
  models: number;
}

// Class configuration
export interface ClassConfig {
  id: string;
  name: string;
  color: string;
  shortcut?: string;
}

export const PPE_CLASSES: ClassConfig[] = [
  { id: 'person', name: 'Человек', color: '#3B82F6', shortcut: '1' },
  { id: 'hardhat', name: 'Каска ✓', color: '#22C55E', shortcut: '2' },
  { id: 'no_hardhat', name: 'Без каски ❌', color: '#EF4444', shortcut: '3' },
  { id: 'vest', name: 'Жилет ✓', color: '#22C55E', shortcut: '4' },
  { id: 'no_vest', name: 'Без жилета ❌', color: '#EF4444', shortcut: '5' },
  { id: 'glasses', name: 'Очки ✓', color: '#22C55E', shortcut: '6' },
  { id: 'no_glasses', name: 'Без очков ❌', color: '#F97316', shortcut: '7' },
];

export const CLASS_COLORS: Record<string, string> = Object.fromEntries(
  PPE_CLASSES.map((c) => [c.id, c.color])
);

// Tool types
export type AnnotationTool = 'select' | 'draw' | 'pan';

// Drawing state
export interface DrawingState {
  isDrawing: boolean;
  startPoint: { x: number; y: number } | null;
  tempBox: [number, number, number, number] | null;
}

// ============================================================================
// Create/Update Params
// ============================================================================

export interface CreateDatasetParams {
  name: string;
  description?: string;
}

export interface CreateJobParams {
  dataset_id: string;
  name?: string;
  epochs?: number;
  batch_size?: number;
  learning_rate?: number;
  image_size?: number;
  augmentation?: boolean;
  pretrained?: boolean;
}

export interface CreateAnnotationParams {
  class_name: string;
  bbox_x1: number;
  bbox_y1: number;
  bbox_x2: number;
  bbox_y2: number;
}
