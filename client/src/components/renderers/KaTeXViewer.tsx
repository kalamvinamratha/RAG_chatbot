import React, { useMemo } from 'react';
import katex from 'katex';

interface KaTeXViewerProps {
  math: string;
  block?: boolean;
}

export const KaTeXViewer: React.FC<KaTeXViewerProps> = ({ math, block = true }) => {
  const html = useMemo(() => {
    try {
      return katex.renderToString(math, {
        displayMode: block,
        throwOnError: false,
        trust: false,
      });
    } catch (e) {
      console.warn('KaTeX render error:', e);
      return null;
    }
  }, [math, block]);

  if (html === null) return <code>{math}</code>;

  return (
    <div
      className={`my-3 p-3.5 rounded-xl bg-secondary/40  border border-primary/30  text-primary  font-mono text-sm overflow-x-auto shadow-xs transition-colors ${
        block ? 'text-center' : 'inline-block'
      }`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
};
