import { createContext, useContext } from 'react';

export type ThemeMode = 'light' | 'dark' | 'system';
interface ThemeContextType {
  theme: ThemeMode;
  resolvedTheme: 'light' | 'dark';
  setTheme: (theme: ThemeMode) => void;
}
export const ThemeContext = createContext<ThemeContextType | undefined>(undefined);
export function useTheme(): ThemeContextType {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useTheme must be used within a ThemeProvider');
  return context;
}
