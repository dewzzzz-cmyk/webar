import { useState, useEffect, useCallback, useRef } from 'react';

interface TrainingProgress {
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  event?: string;
  epoch?: number;
  progress?: number;
  train_loss?: number;
  val_loss?: number;
  map50?: number;
  map50_95?: number;
  best_map50?: number;
  learning_rate?: number;
  error?: string;
  model_id?: string;
}

interface UseTrainingProgressOptions {
  onProgress?: (progress: TrainingProgress) => void;
  onComplete?: (progress: TrainingProgress) => void;
  onError?: (error: string) => void;
}

interface UseTrainingProgressReturn {
  progress: TrainingProgress | null;
  isConnected: boolean;
  connect: () => void;
  disconnect: () => void;
}

export function useTrainingProgress(
  jobId: string | null,
  options: UseTrainingProgressOptions = {}
): UseTrainingProgressReturn {
  const [progress, setProgress] = useState<TrainingProgress | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  
  const { onProgress, onComplete, onError } = options;

  const connect = useCallback(() => {
    if (!jobId || wsRef.current?.readyState === WebSocket.OPEN) return;
    
    // Build WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/api/training/ws/progress/${jobId}`;
    
    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;
      
      ws.onopen = () => {
        console.log(`Training progress WebSocket connected for job ${jobId}`);
        setIsConnected(true);
        
        // Start ping interval
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, 25000);
      };
      
      ws.onmessage = (event) => {
        try {
          // Handle pong
          if (event.data === 'pong') return;
          
          const message = JSON.parse(event.data);
          
          if (message.type === 'progress' || message.type === 'state') {
            const data = message.data as TrainingProgress;
            setProgress(data);
            
            onProgress?.(data);
            
            if (data.status === 'completed') {
              onComplete?.(data);
            }
            
            if (data.status === 'failed' && data.error) {
              onError?.(data.error);
            }
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };
      
      ws.onclose = (event) => {
        console.log(`Training progress WebSocket closed: ${event.code}`);
        setIsConnected(false);
        
        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }
        
        // Reconnect if not intentional close
        if (event.code !== 1000 && event.code !== 1001) {
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, 3000);
        }
      };
      
      ws.onerror = (error) => {
        console.error('Training progress WebSocket error:', error);
        onError?.('WebSocket connection error');
      };
      
    } catch (e) {
      console.error('Failed to create WebSocket:', e);
      onError?.('Failed to connect to training progress');
    }
  }, [jobId, onProgress, onComplete, onError]);

  const disconnect = useCallback(() => {
    // Clear timeouts
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    
    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close(1000, 'Intentional disconnect');
      wsRef.current = null;
    }
    
    setIsConnected(false);
  }, []);

  // Connect when jobId changes
  useEffect(() => {
    if (jobId) {
      connect();
    }
    
    return () => {
      disconnect();
    };
  }, [jobId, connect, disconnect]);

  return {
    progress,
    isConnected,
    connect,
    disconnect,
  };
}

// Hook for polling training logs
export function useTrainingLogs(jobId: string | null, enabled: boolean = true) {
  const [logs, setLogs] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchLogs = useCallback(async () => {
    if (!jobId) return;
    
    try {
      setIsLoading(true);
      const response = await fetch(`/api/training/jobs/${jobId}/logs`);
      
      if (response.ok) {
        const data = await response.json();
        setLogs(data.logs || []);
      }
    } catch (e) {
      console.error('Failed to fetch training logs:', e);
    } finally {
      setIsLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    if (!jobId || !enabled) {
      setLogs([]);
      return;
    }
    
    // Initial fetch
    fetchLogs();
    
    // Poll every 5 seconds
    intervalRef.current = setInterval(fetchLogs, 5000);
    
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [jobId, enabled, fetchLogs]);

  return { logs, isLoading, refetch: fetchLogs };
}

export default useTrainingProgress;
