import { useState, useEffect } from 'react';

export type Theme = 'dark' | 'light';

export function useThemeMode() {
  const [theme, setThemeState] = useState<Theme>(() => {
    const saved = localStorage.getItem('neurofin-theme');
    if (saved === 'dark' || saved === 'light') {
      return saved;
    }
    return 'dark';
  });

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
    localStorage.setItem('neurofin-theme', newTheme);
  };

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  };

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  return { theme, setTheme, toggleTheme };
}
