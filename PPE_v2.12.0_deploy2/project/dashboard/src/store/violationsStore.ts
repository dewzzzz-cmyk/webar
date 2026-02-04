import { create } from 'zustand';
import { Violation } from '@/types';

interface ViolationsState {
  recentViolations: Violation[];
  unacknowledgedCount: number;
  addViolation: (violation: Violation) => void;
  acknowledgeViolation: (id: string) => void;
  setViolations: (violations: Violation[]) => void;
  clearViolations: () => void;
}

const MAX_RECENT = 50;

export const useViolationsStore = create<ViolationsState>((set) => ({
  recentViolations: [],
  unacknowledgedCount: 0,

  addViolation: (violation) =>
    set((state) => {
      const newViolations = [violation, ...state.recentViolations].slice(0, MAX_RECENT);
      const unacknowledgedCount = newViolations.filter((v) => !v.acknowledged).length;
      return { recentViolations: newViolations, unacknowledgedCount };
    }),

  acknowledgeViolation: (id) =>
    set((state) => {
      const newViolations = state.recentViolations.map((v) =>
        v.id === id ? { ...v, acknowledged: true } : v
      );
      const unacknowledgedCount = newViolations.filter((v) => !v.acknowledged).length;
      return { recentViolations: newViolations, unacknowledgedCount };
    }),

  setViolations: (violations) =>
    set({
      recentViolations: violations.slice(0, MAX_RECENT),
      unacknowledgedCount: violations.filter((v) => !v.acknowledged).length,
    }),

  clearViolations: () =>
    set({ recentViolations: [], unacknowledgedCount: 0 }),
}));
