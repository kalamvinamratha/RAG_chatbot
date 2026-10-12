import { useEffect, useId, useRef } from 'react';
import { ArrowRight, CircleNotch } from '@phosphor-icons/react';
import type { HealthcareAgent } from '../types';
import { getCompanion } from '../lib/companions';
import { CompanionMascot } from './CompanionMascot';

interface CompanionLobbyProps {
  agents: HealthcareAgent[];
  loading: boolean;
  error: string;
  activeAgent: HealthcareAgent | null;
  onChoose: (agent: HealthcareAgent) => void;
  onRetry: () => void;
}

export function CompanionLobby({
  agents,
  loading,
  error,
  activeAgent,
  onChoose,
  onRetry,
}: CompanionLobbyProps) {
  const lobbyRef = useRef<HTMLElement>(null);
  const lobbyId = useId();
  useEffect(() => {
    lobbyRef.current?.focus();
  }, []);
  return (
    <main
      ref={lobbyRef}
      tabIndex={-1}
      aria-label="Choose your clinical companion"
      className="companion-lobby"
    >
      {loading ? (
        <div
          className="lobby-loading flex flex-col items-center justify-center py-16 gap-3"
          role="status"
        >
          <CircleNotch size={32} className="animate-spin text-primary" />
          <p className="text-sm font-medium text-foreground">Connecting to clinical companions…</p>
          <p className="text-xs text-muted-foreground">
            Initializing agent workspaces and knowledge models
          </p>
        </div>
      ) : error || agents.length === 0 ? (
        <div className="lobby-unavailable">
          <p role="alert">{error || 'No companions are available yet. Please try again.'}</p>
          <button type="button" className="ui-button" onClick={onRetry}>
            Try again
          </button>
        </div>
      ) : (
        <div className="companion-lineup" aria-label="Choose your clinical companion">
          {agents.map((agent, index) => {
            const companion = getCompanion(agent.domain_key);
            const resume = activeAgent?.id === agent.id;
            return (
              <button
                type="button"
                key={agent.id}
                className={`companion-choice companion-${companion.kind}`}
                onClick={() => onChoose(agent)}
                aria-label={`${resume ? 'Continue with' : 'Choose'} ${companion.name} — ${agent.specialty || agent.name}`}
                aria-describedby={`${lobbyId}-${index}`}
              >
                <span id={`${lobbyId}-${index}`} className="companion-bubble">
                  {companion.introduction}
                </span>
                <CompanionMascot kind={companion.kind} />
                <span className="companion-name">{companion.name}</span>
                <span className="companion-specialty">{agent.specialty || agent.name}</span>
                <span className="companion-invitation">
                  {resume ? 'Continue our conversation' : 'Say hello'} <ArrowRight size={15} />
                </span>
              </button>
            );
          })}
        </div>
      )}
    </main>
  );
}
