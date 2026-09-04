import { useContext } from 'react';
import { ThemeContext } from '@/contexts/ThemeContext';
import type { Theme } from '@/types/common.types';

interface UseThemeReturn {
  theme: Theme;
  isDark: boolean;
  isLight: boolean;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

/**
 * Hook to access the current theme and toggle/set it.
 * Must be used inside <ThemeProvider>.
 */
export function useTheme(): UseThemeReturn {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }

  return {
    theme: context.theme,
    isDark: context.theme === 'dark',
    isLight: context.theme === 'light',
    toggleTheme: context.toggleTheme,
    setTheme: context.setTheme,
  };
}
