import { useEffect, useRef, useCallback, useState } from 'react';
import { useAuthStore } from '@/store/authStore';
import { useViolationsStore } from '@/store/violationsStore';
import type { WSMessage, Violation } from '@/types';

const WS_BASE = `ws://${window.location.host}/ws`;
const RECONNECT_DELAY = 3000;
const HEARTBEAT_INTERVAL = 30000;

// Sound for alerts
const alertSound = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdH2Onp+bmZmZm5ublZaUkI+RlJaYl5SSj42NjpCRkI6LiYiJi4yMi4mHhoaHiImJiIaEg4OEhYaGhYOBgIGChISEg4GAgIGDhYaGhYSCgYGChIWGhoWEg4KCg4WGh4eGhYSDg4SFhoeHhoWEg4OEhYaHh4aFhIODhIWGh4eGhYSEhISFhoeHhoWEhISEhYaHh4aFhISEhIWGh4eGhYSEhISFhoeHhoWEhIOEhYaGh4aFhIODhIWGhoeGhYSDg4SEhoaGhoWEg4OEhYaGhoWFhIODhIWFhoaFhYSDg4SEhYaGhYWEg4OEhIWFhoWFhIODg4SEhYWFhYSDg4ODhISFhYWEg4ODg4SEhIWFhIODg4OEhISFhYSDg4ODg4SEhISDg4ODg4OEhISEg4ODg4ODhISEhIODg4ODg4SEhISDg4ODg4OEhISEg4ODg4ODg4SEhIODg4ODg4OEhISEg4ODg4ODg4SEhISDg4ODg4ODhISEhIODg4ODg4OEhISEg4ODg4ODg4SEhISDg4ODg4ODg4SEhIODg4ODg4ODhISEhIODg4ODg4ODhIQ=');

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number>();
  const heartbeatRef = useRef<number>();
  
  const token = useAuthStore((state) => state.token);
  const addViolation = useViolationsStore((state) => state.addViolation);

  const connect = useCallback(() => {
    if (!token) return;

    try {
      const ws = new WebSocket(`${WS_BASE}?token=${token}`);

      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        
        // Start heartbeat
        heartbeatRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, HEARTBEAT_INTERVAL);
      };

      ws.onmessage = (event) => {
        try {
          const message: WSMessage = JSON.parse(event.data);
          setLastMessage(message);

          if (message.type === 'violation' && message.data) {
            const violation = message.data as Violation;
            addViolation(violation);
            
            // Play sound
            alertSound.play().catch(() => {});
          }
        } catch (e) {
          console.error('Failed to parse WS message:', e);
        }
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        
        if (heartbeatRef.current) {
          clearInterval(heartbeatRef.current);
        }

        // Reconnect
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, RECONNECT_DELAY);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      wsRef.current = ws;
    } catch (e) {
      console.error('Failed to connect WebSocket:', e);
    }
  }, [token, addViolation]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { isConnected, lastMessage };
}

// Hook for camera-specific WebSocket
export function useCameraStream(cameraId: string) {
  const [frame, setFrame] = useState<string | null>(null);
  const [stats, setStats] = useState({ persons: 0, violations: 0 });
  const wsRef = useRef<WebSocket | null>(null);
  const prevBlobUrlRef = useRef<string | null>(null);
  
  const token = useAuthStore((state) => state.token);

  useEffect(() => {
    if (!token || !cameraId) return;

    const ws = new WebSocket(`${WS_BASE}/camera/${cameraId}?token=${token}`);

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
        setStats({
          persons: data.persons_count || 0,
          violations: data.violations_count || 0,
        });
      } catch (e) {
        console.error('Failed to parse camera message:', e);
      }
    };

    wsRef.current = ws;

    return () => {
      ws.close();
      // Очищаем blob URL при размонтировании
      if (prevBlobUrlRef.current) {
        URL.revokeObjectURL(prevBlobUrlRef.current);
        prevBlobUrlRef.current = null;
      }
    };
  }, [token, cameraId]);

  return { frame, stats };
}
