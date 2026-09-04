import { useState, useCallback } from 'react';
import { APP_CONSTANTS } from '@/config/constants';

/**
 * Persists and manages the sidebar collapsed/expanded state.
 * State is stored in localStorage so it survives page reloads.
 */
export function useSidebarState() {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    const stored = localStorage.getItem(APP_CONSTANTS.SIDEBAR.STORAGE_KEY);
    return stored === 'true';
  });

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem(APP_CONSTANTS.SIDEBAR.STORAGE_KEY, String(next));
      return next;
    });
  }, []);

  return { collapsed, toggle };
}
