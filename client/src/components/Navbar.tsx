import { useEffect, useState } from 'react';
import { DotsThree, SignOut, SquaresFour } from '@phosphor-icons/react';
interface NavbarProps {
  onSignOut: () => void;
  onChangeCompanion?: () => void;
}
export function Navbar({ onSignOut, onChangeCompanion }: NavbarProps) {
  const [healthy, setHealthy] = useState<boolean | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/health', { signal: controller.signal })
      .then((res) => res.json())
      .then((data) => {
        if (!controller.signal.aborted) setHealthy(data.status === 'healthy');
      })
      .catch(() => {
        if (!controller.signal.aborted) setHealthy(false);
      });
    return () => controller.abort();
  }, []);
  return (
    <div className="desk-corner">
      <span className="desk-brand">Helios</span>
      <details
        className="desk-menu"
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            event.currentTarget.open = false;
            event.currentTarget.querySelector('summary')?.focus();
          }
        }}
      >
        <summary aria-label="Workspace menu">
          <DotsThree size={24} weight="bold" />
        </summary>
        <div className="desk-menu-content">
          <p className="workspace-title">Helios Clinical AI</p>
          <p className="ui-label" role="status">
            {healthy === null
              ? 'Connecting…'
              : healthy
                ? 'All systems connected'
                : 'Service unavailable'}
          </p>
          {onChangeCompanion && (
            <button
              type="button"
              onClick={(e) => {
                const details = e.currentTarget.closest('details');
                if (details) details.open = false;
                onChangeCompanion();
              }}
            >
              <SquaresFour size={17} /> Companions
            </button>
          )}
          <button type="button" onClick={onSignOut}>
            <SignOut size={17} /> Sign out
          </button>
        </div>
      </details>
    </div>
  );
}
