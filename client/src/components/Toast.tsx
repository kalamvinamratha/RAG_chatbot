import { useEffect } from 'react';
import { ShieldWarning, WarningCircle, CheckCircle, Info, X } from '@phosphor-icons/react';

export interface ToastProps {
  message: string | null;
  title?: string;
  type?: 'error' | 'warning' | 'info' | 'success';
  onClose: () => void;
  autoCloseMs?: number;
}

export function Toast({ message, title, type = 'error', onClose, autoCloseMs = 9000 }: ToastProps) {
  useEffect(() => {
    if (!message || autoCloseMs <= 0) return;
    const timer = setTimeout(() => {
      onClose();
    }, autoCloseMs);
    return () => clearTimeout(timer);
  }, [message, autoCloseMs, onClose]);

  if (!message) return null;

  const isGuardrail =
    message.toLowerCase().includes('guardrail') ||
    message.toLowerCase().includes('detected domain') ||
    message.toLowerCase().includes('non-healthcare');

  const resolvedTitle =
    title ||
    (isGuardrail
      ? 'Document Rejected by Medical Guardrail'
      : type === 'error'
        ? 'Action Failed'
        : type === 'warning'
          ? 'Warning'
          : 'Notice');

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="fixed top-5 right-5 z-[9999] max-w-md w-[calc(100vw-2.5rem)] sm:w-auto sm:min-w-[22rem] p-4 rounded-xl shadow-2xl border border-destructive/40 bg-card text-card-foreground backdrop-blur-md transition-all duration-300 animate-in fade-in slide-in-from-top-4"
      style={{
        boxShadow:
          '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 10px 10px -5px rgba(0, 0, 0, 0.1), 0 0 0 1px var(--border)',
      }}
    >
      <div className="flex items-start gap-3">
        {isGuardrail ? (
          <ShieldWarning size={24} weight="fill" className="text-destructive shrink-0 mt-0.5" />
        ) : type === 'error' ? (
          <WarningCircle size={24} weight="fill" className="text-destructive shrink-0 mt-0.5" />
        ) : type === 'success' ? (
          <CheckCircle size={24} weight="fill" className="text-emerald-500 shrink-0 mt-0.5" />
        ) : (
          <Info size={24} weight="fill" className="text-sky-500 shrink-0 mt-0.5" />
        )}

        <div className="flex-1 min-w-0 pr-2">
          <h4 className="text-sm font-semibold text-destructive leading-tight">{resolvedTitle}</h4>
          <p className="mt-1.5 text-xs text-foreground/90 dark:text-foreground/90 leading-relaxed break-words whitespace-pre-wrap">
            {message}
          </p>
          {isGuardrail && (
            <div className="mt-2 text-[11px] font-medium text-muted-foreground bg-muted/50 rounded px-2 py-1">
              Tip: Only clinical records, medical trials, treatment protocols, and healthcare
              textbooks can be ingested.
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={onClose}
          className="shrink-0 p-1 text-muted-foreground hover:text-foreground hover:bg-muted/60 rounded-md transition-colors"
          aria-label="Dismiss notification"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
}
