-- ============================================================================
-- PPE Detection System - Database Initialization
-- ============================================================================

-- Таблица нарушений
CREATE TABLE IF NOT EXISTS violations (
    id VARCHAR(36) PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    camera_id VARCHAR(50) NOT NULL,
    zone_id VARCHAR(50),
    violation_type VARCHAR(50) NOT NULL,
    confidence REAL NOT NULL,
    person_id INTEGER,
    bbox_x1 INTEGER NOT NULL,
    bbox_y1 INTEGER NOT NULL,
    bbox_x2 INTEGER NOT NULL,
    bbox_y2 INTEGER NOT NULL,
    image_path VARCHAR(255),
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(100),
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    notes TEXT
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_violations_timestamp ON violations(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_violations_camera_id ON violations(camera_id);
CREATE INDEX IF NOT EXISTS idx_violations_zone_id ON violations(zone_id);
CREATE INDEX IF NOT EXISTS idx_violations_type ON violations(violation_type);
CREATE INDEX IF NOT EXISTS idx_violations_acknowledged ON violations(acknowledged);

-- Таблица статистики по часам
CREATE TABLE IF NOT EXISTS detection_stats (
    id SERIAL PRIMARY KEY,
    hour TIMESTAMP WITH TIME ZONE NOT NULL,
    camera_id VARCHAR(50) NOT NULL,
    persons_count INTEGER DEFAULT 0,
    violations_count INTEGER DEFAULT 0,
    hardhat_ok INTEGER DEFAULT 0,
    hardhat_missing INTEGER DEFAULT 0,
    vest_ok INTEGER DEFAULT 0,
    vest_missing INTEGER DEFAULT 0,
    UNIQUE(hour, camera_id)
);

CREATE INDEX IF NOT EXISTS idx_stats_hour ON detection_stats(hour DESC);
CREATE INDEX IF NOT EXISTS idx_stats_camera ON detection_stats(camera_id);

-- Таблица камер (для хранения конфигурации в БД)
CREATE TABLE IF NOT EXISTS cameras (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    rtsp_url TEXT NOT NULL,
    zone_id VARCHAR(50),
    fps INTEGER DEFAULT 5,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Таблица зон
CREATE TABLE IF NOT EXISTS zones (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    required_ppe TEXT[],
    alert_channels TEXT[],
    cooldown_seconds INTEGER DEFAULT 30,
    polygon JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Вставляем зону по умолчанию
INSERT INTO zones (id, name, required_ppe, alert_channels, cooldown_seconds)
VALUES ('default', 'Вся территория', ARRAY['hardhat', 'vest'], ARRAY['telegram'], 30)
ON CONFLICT (id) DO NOTHING;

-- Представление для дашборда
CREATE OR REPLACE VIEW violations_summary AS
SELECT 
    DATE_TRUNC('hour', timestamp) as hour,
    camera_id,
    violation_type,
    COUNT(*) as count,
    AVG(confidence) as avg_confidence
FROM violations
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', timestamp), camera_id, violation_type
ORDER BY hour DESC;

-- Функция для очистки старых данных
CREATE OR REPLACE FUNCTION cleanup_old_violations(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM violations 
    WHERE timestamp < NOW() - (days_to_keep || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Комментарии
COMMENT ON TABLE violations IS 'Таблица нарушений СИЗ';
COMMENT ON TABLE detection_stats IS 'Агрегированная статистика по часам';
COMMENT ON TABLE cameras IS 'Конфигурация камер';
COMMENT ON TABLE zones IS 'Зоны контроля с правилами СИЗ';
