import { useAuthStore } from '@/store/authStore';
import type {
  Violation,
  ViolationStats,
  Camera,
  LoginRequest,
  TokenResponse,
} from '@/types';

const API_BASE = '/api';

class ApiClient {
  private isRefreshing = false;
  private refreshPromise: Promise<string | null> | null = null;

  private getHeaders(): HeadersInit {
    const token = useAuthStore.getState().token;
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  private async refreshToken(): Promise<string | null> {
    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: this.getHeaders(),
      });
      
      if (response.ok) {
        const data = await response.json();
        useAuthStore.getState().setToken(data.access_token);
        console.log('Token refreshed successfully');
        return data.access_token;
      }
      return null;
    } catch {
      return null;
    }
  }

  private async request<T>(
    endpoint: string,
    options?: RequestInit,
    isRetry = false
  ): Promise<T> {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        ...this.getHeaders(),
        ...options?.headers,
      },
    });

    if (response.status === 401 && !isRetry) {
      // Try to refresh token
      if (!this.isRefreshing) {
        this.isRefreshing = true;
        this.refreshPromise = this.refreshToken();
      }
      
      const newToken = await this.refreshPromise;
      this.isRefreshing = false;
      this.refreshPromise = null;
      
      if (newToken) {
        // Retry request with new token
        return this.request<T>(endpoint, options, true);
      }
      
      // Refresh failed, logout
      useAuthStore.getState().logout();
      throw new Error('Session expired. Please login again.');
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // Auth
  async login(data: LoginRequest): Promise<TokenResponse> {
    return this.request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getMe(): Promise<{ username: string }> {
    return this.request('/auth/me');
  }

  async refresh(): Promise<TokenResponse> {
    return this.request<TokenResponse>('/auth/refresh', {
      method: 'POST',
    });
  }

  // Violations
  async getViolations(params?: {
    limit?: number;
    offset?: number;
    camera_id?: string;
    violation_type?: string;
    acknowledged?: boolean;
    hours?: number;
  }): Promise<Violation[]> {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.set(key, String(value));
        }
      });
    }
    const query = searchParams.toString();
    return this.request(`/violations${query ? `?${query}` : ''}`);
  }

  async getViolation(id: string): Promise<Violation> {
    return this.request(`/violations/${id}`);
  }

  async acknowledgeViolation(
    id: string,
    data: { acknowledged_by: string; notes?: string }
  ): Promise<{ status: string }> {
    return this.request(`/violations/${id}/acknowledge`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  getViolationImageUrl(id: string): string {
    const token = useAuthStore.getState().token;
    return `${API_BASE}/violations/${id}/image?token=${token}`;
  }

  // Statistics
  async getStatistics(hours: number = 24): Promise<ViolationStats> {
    return this.request(`/statistics?hours=${hours}`);
  }

  // Cameras
  async getCameras(): Promise<Camera[]> {
    return this.request('/cameras');
  }

  getCameraStreamUrl(cameraId: string): string {
    const token = useAuthStore.getState().token;
    return `${API_BASE}/cameras/${cameraId}/stream?token=${token}`;
  }

  // Generic HTTP methods for flexible API calls
  async get<T>(endpoint: string): Promise<{ data: T }> {
    const data = await this.request<T>(endpoint);
    return { data };
  }

  async post<T>(endpoint: string, body?: unknown): Promise<{ data: T }> {
    const data = await this.request<T>(endpoint, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
    return { data };
  }

  async put<T>(endpoint: string, body?: unknown): Promise<{ data: T }> {
    const data = await this.request<T>(endpoint, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    });
    return { data };
  }

  async delete<T>(endpoint: string): Promise<{ data: T }> {
    const data = await this.request<T>(endpoint, {
      method: 'DELETE',
    });
    return { data };
  }
}

export const api = new ApiClient();
