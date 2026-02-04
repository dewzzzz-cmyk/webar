// Violation types
export interface Violation {
  id: string;
  timestamp: string;
  camera_id: string;
  zone_id: string | null;
  violation_type: ViolationType;
  confidence: number;
  person_id: number | null;
  bbox: [number, number, number, number];
  image_path: string | null;
  acknowledged: boolean;
  acknowledged_by?: string;
  acknowledged_at?: string;
  notes?: string;
}

export type ViolationType = 'no_hardhat' | 'no_vest' | 'no_glasses' | 'no_gloves';

export const VIOLATION_LABELS: Record<ViolationType, string> = {
  no_hardhat: 'Без каски',
  no_vest: 'Без жилета',
  no_glasses: 'Без очков',
  no_gloves: 'Без перчаток',
};

export const VIOLATION_ICONS: Record<ViolationType, string> = {
  no_hardhat: '🪖',
  no_vest: '🦺',
  no_glasses: '🥽',
  no_gloves: '🧤',
};

// Camera types
export interface Camera {
  id: string;
  name: string;
  status: 'connected' | 'disconnected' | 'error';
  zone_id?: string;
  fps?: number;
  updated_at?: string;
}

// Statistics types
export interface ViolationStats {
  total: number;
  by_type: Record<string, number>;
  by_camera: Record<string, number>;
  by_hour: Record<string, number>;
}

// Detection event from WebSocket
export interface DetectionEvent {
  camera_id: string;
  timestamp: string;
  persons_count: number;
  violations_count: number;
  detections: Detection[];
  image?: string; // base64
}

export interface Detection {
  class_id: number;
  class_name: string;
  ppe_type: string;
  confidence: number;
  bbox: [number, number, number, number];
  track_id: number | null;
  camera_id: string;
}

// Auth types
export interface User {
  username: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// API Response types
export interface ApiError {
  detail: string;
}

// WebSocket message types
export interface WSMessage {
  type: 'violation' | 'ping' | 'detection';
  data?: Violation | DetectionEvent;
}
