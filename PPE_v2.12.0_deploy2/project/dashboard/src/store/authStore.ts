import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

interface AuthState {
  token: string | null;
  username: string | null;
  isAuthenticated: boolean;
  login: (token: string, username: string) => void;
  logout: () => void;
  setToken: (token: string) => void;
}

// Синхронизация токена в localStorage для обратной совместимости
const syncTokenToLocalStorage = (token: string | null) => {
  if (token) {
    localStorage.setItem('token', token);
  } else {
    localStorage.removeItem('token');
  }
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      username: null,
      isAuthenticated: false,
      login: (token, username) => {
        syncTokenToLocalStorage(token);
        set({ token, username, isAuthenticated: true });
      },
      logout: () => {
        syncTokenToLocalStorage(null);
        set({ token: null, username: null, isAuthenticated: false });
      },
      setToken: (token) => {
        syncTokenToLocalStorage(token);
        set((state) => ({ ...state, token }));
      },
    }),
    {
      name: 'ppe-auth',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        token: state.token,
        username: state.username,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

// При загрузке модуля - синхронизируем токен
if (typeof window !== 'undefined') {
  // Подписываемся на изменения store
  useAuthStore.subscribe((state) => {
    syncTokenToLocalStorage(state.token);
  });
  
  // Инициализация при загрузке
  const initialToken = useAuthStore.getState().token;
  if (initialToken) {
    syncTokenToLocalStorage(initialToken);
  }
}
