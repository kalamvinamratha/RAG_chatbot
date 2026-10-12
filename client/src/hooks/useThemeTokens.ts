import { useMemo, useSyncExternalStore } from 'react';

const names = [
  '--primary',
  '--secondary',
  '--card',
  '--foreground',
  '--border',
  '--muted-foreground',
  '--font-sans',
] as const;
function snapshot() {
  const style = getComputedStyle(document.documentElement);
  return JSON.stringify(names.map((name) => style.getPropertyValue(name).trim()));
}
function subscribe(update: () => void) {
  // Theme classes and Vite CSS hot updates both invalidate rendered SVG colors.
  const observer = new MutationObserver(update);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['class', 'style'],
  });
  observer.observe(document.head, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
  });
  return () => observer.disconnect();
}
function toHex(color: string): string {
  const context = document.createElement('canvas').getContext('2d');
  if (!context) return color;
  context.fillStyle = color;
  context.fillRect(0, 0, 1, 1);
  const [r, g, b] = context.getImageData(0, 0, 1, 1).data;
  return '#' + [r, g, b].map((value) => value.toString(16).padStart(2, '0')).join('');
}
export function useThemeTokens() {
  const values = useSyncExternalStore(subscribe, snapshot);
  return useMemo(() => {
    const tokens = JSON.parse(values) as string[];
    return {
      primary: toHex(tokens[0]),
      secondary: toHex(tokens[1]),
      card: toHex(tokens[2]),
      foreground: toHex(tokens[3]),
      border: toHex(tokens[4]),
      mutedForeground: toHex(tokens[5]),
      font: tokens[6],
    };
  }, [values]);
}
