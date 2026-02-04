-- ============================================================================
-- PPE Detection System - Training Module Database Schema
-- Version: 1.0
-- Date: 2026-01-23
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- DATASETS
-- ============================================================================
CREATE TABLE IF NOT EXISTS training_datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_by VARCHAR(100) NOT NULL DEFAULT 'system',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    images_count INTEGER DEFAULT 0,
    annotations_count INTEGER DEFAULT 0,
    labeled_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'draft',
    source VARCHAR(50) DEFAULT 'user',
    path VARCHAR(500),
    classes JSONB DEFAULT '[]'::jsonb
);

-- Миграция для существующих баз данных
DO $$ 
BEGIN
    BEGIN ALTER TABLE training_datasets ADD COLUMN labeled_count INTEGER DEFAULT 0; EXCEPTION WHEN duplicate_column THEN NULL; END;
    BEGIN ALTER TABLE training_datasets ADD COLUMN source VARCHAR(50) DEFAULT 'user'; EXCEPTION WHEN duplicate_column THEN NULL; END;
    BEGIN ALTER TABLE training_datasets ADD COLUMN path VARCHAR(500); EXCEPTION WHEN duplicate_column THEN NULL; END;
    BEGIN ALTER TABLE training_datasets ADD COLUMN classes JSONB DEFAULT '[]'::jsonb; EXCEPTION WHEN duplicate_column THEN NULL; END;
END $$;

-- ============================================================================
-- IMAGES
-- ============================================================================
CREATE TABLE IF NOT EXISTS training_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID REFERENCES training_datasets(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    mime_type VARCHAR(50) DEFAULT 'image/jpeg',
    storage_path VARCHAR(500) NOT NULL,
    checksum VARCHAR(64),
    uploaded_by VARCHAR(100) NOT NULL DEFAULT 'admin',
    uploaded_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'pending'
);

-- ============================================================================
-- ANNOTATIONS
-- ============================================================================
CREATE TABLE IF NOT EXISTS annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    image_id UUID REFERENCES training_images(id) ON DELETE CASCADE,
    class_name VARCHAR(50) NOT NULL,
    bbox_x1 FLOAT NOT NULL,
    bbox_y1 FLOAT NOT NULL,
    bbox_x2 FLOAT NOT NULL,
    bbox_y2 FLOAT NOT NULL,
    confidence FLOAT,
    created_by VARCHAR(100) NOT NULL DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    verified BOOLEAN DEFAULT FALSE,
    verified_by VARCHAR(100),
    verified_at TIMESTAMP
);

-- ============================================================================
-- TRAINING JOBS
-- ============================================================================
CREATE TABLE IF NOT EXISTS training_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID REFERENCES training_datasets(id),
    name VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending',
    progress FLOAT DEFAULT 0,
    epochs_total INTEGER NOT NULL DEFAULT 50,
    epochs_completed INTEGER DEFAULT 0,
    batch_size INTEGER DEFAULT 16,
    learning_rate FLOAT DEFAULT 0.001,
    image_size INTEGER DEFAULT 640,
    augmentation BOOLEAN DEFAULT TRUE,
    pretrained BOOLEAN DEFAULT TRUE,
    current_loss FLOAT,
    best_loss FLOAT,
    current_map50 FLOAT,
    best_map50 FLOAT,
    error_message TEXT,
    created_by VARCHAR(100) NOT NULL DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- ============================================================================
-- TRAINING LOGS (для графиков прогресса)
-- ============================================================================
CREATE TABLE IF NOT EXISTS training_logs (
    id SERIAL PRIMARY KEY,
    job_id UUID REFERENCES training_jobs(id) ON DELETE CASCADE,
    epoch INTEGER NOT NULL,
    step INTEGER,
    train_loss FLOAT,
    val_loss FLOAT,
    map50 FLOAT,
    map50_95 FLOAT,
    learning_rate FLOAT,
    gpu_memory_mb FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_training_logs_job ON training_logs(job_id);
CREATE INDEX IF NOT EXISTS idx_training_logs_epoch ON training_logs(job_id, epoch);

-- ============================================================================
-- MODEL VERSIONS
-- ============================================================================
CREATE TABLE IF NOT EXISTS model_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    training_job_id UUID REFERENCES training_jobs(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    model_path VARCHAR(500) NOT NULL,
    map50 FLOAT NOT NULL DEFAULT 0,
    map50_95 FLOAT NOT NULL DEFAULT 0,
    precision_avg FLOAT,
    recall_avg FLOAT,
    metrics_per_class JSONB,
    train_images_count INTEGER,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    activated_at TIMESTAMP,
    activated_by VARCHAR(100)
);

-- ============================================================================
-- ANNOTATION HISTORY (для Undo/Redo)
-- ============================================================================
CREATE TABLE IF NOT EXISTS annotation_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    image_id UUID REFERENCES training_images(id) ON DELETE CASCADE,
    user_id VARCHAR(100) NOT NULL DEFAULT 'admin',
    action VARCHAR(20) NOT NULL,
    annotation_id UUID,
    old_data JSONB,
    new_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- AUDIT LOG
-- ============================================================================
CREATE TABLE IF NOT EXISTS training_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,
    details JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- INDEXES
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_training_images_dataset ON training_images(dataset_id);
CREATE INDEX IF NOT EXISTS idx_training_images_status ON training_images(status);
CREATE INDEX IF NOT EXISTS idx_annotations_image ON annotations(image_id);
CREATE INDEX IF NOT EXISTS idx_annotations_class ON annotations(class_name);
CREATE INDEX IF NOT EXISTS idx_training_jobs_status ON training_jobs(status);
CREATE INDEX IF NOT EXISTS idx_annotation_history_image ON annotation_history(image_id);
CREATE INDEX IF NOT EXISTS idx_model_versions_active ON model_versions(is_active);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Update dataset counters
CREATE OR REPLACE FUNCTION update_dataset_counts() RETURNS TRIGGER AS $$
BEGIN
    UPDATE training_datasets SET 
        images_count = (SELECT COUNT(*) FROM training_images WHERE dataset_id = COALESCE(NEW.dataset_id, OLD.dataset_id)),
        updated_at = NOW()
    WHERE id = COALESCE(NEW.dataset_id, OLD.dataset_id);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_dataset_counts ON training_images;
CREATE TRIGGER trg_update_dataset_counts
AFTER INSERT OR DELETE ON training_images
FOR EACH ROW EXECUTE FUNCTION update_dataset_counts();

-- Update annotation counters
CREATE OR REPLACE FUNCTION update_annotation_counts() RETURNS TRIGGER AS $$
DECLARE v_dataset_id UUID;
BEGIN
    SELECT dataset_id INTO v_dataset_id FROM training_images WHERE id = COALESCE(NEW.image_id, OLD.image_id);
    IF v_dataset_id IS NOT NULL THEN
        UPDATE training_datasets SET 
            annotations_count = (SELECT COUNT(*) FROM annotations a JOIN training_images i ON a.image_id = i.id WHERE i.dataset_id = v_dataset_id),
            updated_at = NOW()
        WHERE id = v_dataset_id;
    END IF;
    UPDATE training_images SET status = CASE WHEN (SELECT COUNT(*) FROM annotations WHERE image_id = COALESCE(NEW.image_id, OLD.image_id)) > 0 THEN 'annotated' ELSE 'pending' END
    WHERE id = COALESCE(NEW.image_id, OLD.image_id);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_annotation_counts ON annotations;
CREATE TRIGGER trg_update_annotation_counts
AFTER INSERT OR DELETE ON annotations
FOR EACH ROW EXECUTE FUNCTION update_annotation_counts();

-- Record annotation history
CREATE OR REPLACE FUNCTION record_annotation_history() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO annotation_history (image_id, user_id, action, annotation_id, new_data)
        VALUES (NEW.image_id, NEW.created_by, 'create', NEW.id, row_to_json(NEW));
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO annotation_history (image_id, user_id, action, annotation_id, old_data, new_data)
        VALUES (NEW.image_id, NEW.created_by, 'update', NEW.id, row_to_json(OLD), row_to_json(NEW));
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO annotation_history (image_id, user_id, action, annotation_id, old_data)
        VALUES (OLD.image_id, OLD.created_by, 'delete', OLD.id, row_to_json(OLD));
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_annotation_history ON annotations;
CREATE TRIGGER trg_annotation_history
AFTER INSERT OR UPDATE OR DELETE ON annotations
FOR EACH ROW EXECUTE FUNCTION record_annotation_history();

-- ============================================================================
-- INITIAL DATA
-- ============================================================================
INSERT INTO training_datasets (id, name, description, created_by, status)
VALUES ('00000000-0000-0000-0000-000000000001', 'Default Dataset', 'Default PPE training dataset', 'system', 'draft')
ON CONFLICT DO NOTHING;

INSERT INTO model_versions (id, name, description, model_path, map50, map50_95, train_images_count, is_active)
VALUES ('00000000-0000-0000-0000-000000000001', 'PPE Base Model (YOLOv8n)', 'Pretrained YOLOv8 nano model', '/app/models/ppe_model.pt', 0.85, 0.72, 5000, TRUE)
ON CONFLICT DO NOTHING;
