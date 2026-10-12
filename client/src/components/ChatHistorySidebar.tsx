import React, { useMemo, useState } from 'react';
import {
  ChatCircleDots,
  ClockCounterClockwise,
  FileText,
  Graph,
  MagnifyingGlass,
  Plus,
  SidebarSimple,
  Trash,
  X,
} from '@phosphor-icons/react';
import type { ChatSessionItem, DocumentItem, HealthcareAgent } from '../types';
import { getCompanion } from '../lib/companions';
import { CompanionMascot } from './CompanionMascot';

interface ChatHistorySidebarProps {
  agent: HealthcareAgent;
  sessions: ChatSessionItem[];
  activeSessionId: string | null;
  loading: boolean;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onDeleteSession: (sessionId: string) => void;
  isOpen: boolean;
  onClose: () => void;
  // Related content
  documents: DocumentItem[];
  selectedDocIds: string[];
  onOpenDocuments: () => void;
  onOpenEvidence: () => void;
  totalMessagesCount: number;
}

function formatRelativeTime(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

export const ChatHistorySidebar: React.FC<ChatHistorySidebarProps> = ({
  agent,
  sessions,
  activeSessionId,
  loading,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  isOpen,
  onClose,
  documents,
  selectedDocIds,
  onOpenDocuments,
  onOpenEvidence,
  totalMessagesCount,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const companion = getCompanion(agent.domain_key);

  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    const q = searchQuery.toLowerCase();
    return sessions.filter((s) => s.title.toLowerCase().includes(q));
  }, [sessions, searchQuery]);

  // Group sessions by period
  const groupedSessions = useMemo(() => {
    const groups: { [key: string]: ChatSessionItem[] } = {
      Today: [],
      Yesterday: [],
      'Previous 7 Days': [],
      Older: [],
    };

    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterdayStart = todayStart - 86400000;
    const lastWeekStart = todayStart - 86400000 * 7;

    for (const session of filteredSessions) {
      const sessionTime = new Date(session.updated_at || session.created_at).getTime();
      if (sessionTime >= todayStart) {
        groups['Today'].push(session);
      } else if (sessionTime >= yesterdayStart) {
        groups['Yesterday'].push(session);
      } else if (sessionTime >= lastWeekStart) {
        groups['Previous 7 Days'].push(session);
      } else {
        groups['Older'].push(session);
      }
    }

    return groups;
  }, [filteredSessions]);

  const activeDocs = useMemo(() => {
    return documents.filter((d) => selectedDocIds.includes(d.id));
  }, [documents, selectedDocIds]);

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && <div className="history-mobile-backdrop" aria-hidden="true" onClick={onClose} />}

      <aside
        className={`history-sidebar ${isOpen ? 'is-open' : 'is-closed'}`}
        aria-label="Consultation History and Context"
      >
        {/* Top Header Bar */}
        <div className="history-header">
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <ClockCounterClockwise size={18} className="text-primary shrink-0" weight="bold" />
              <h2 className="history-title">Consultations</h2>
              {sessions.length > 0 && (
                <span className="history-count-badge">{sessions.length}</span>
              )}
            </div>
            <button
              type="button"
              onClick={onClose}
              className="history-collapse-btn"
              title="Close history sidebar"
              aria-label="Close history sidebar"
            >
              <SidebarSimple size={16} />
            </button>
          </div>

          {/* New Consultation CTA */}
          <button
            type="button"
            onClick={() => {
              onNewSession();
              // Auto close on mobile to let user chat
              if (window.innerWidth < 768) onClose();
            }}
            className="history-new-btn"
          >
            <Plus size={15} weight="bold" />
            <span>New Consultation</span>
          </button>

          {/* Filter/Search Bar */}
          {sessions.length > 3 && (
            <div className="history-search-wrapper">
              <MagnifyingGlass size={13} className="history-search-icon" />
              <input
                type="text"
                placeholder="Search history…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="history-search-input"
                aria-label="Search consultation history"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="history-search-clear"
                  aria-label="Clear search"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          )}
        </div>

        {/* Scrollable Sessions List */}
        <div className="history-list-container">
          {loading && sessions.length === 0 ? (
            <div className="history-empty-state animate-pulse">
              <p className="text-xs text-muted-foreground">Loading consultations…</p>
            </div>
          ) : filteredSessions.length === 0 ? (
            <div className="history-empty-state">
              <ChatCircleDots size={28} className="text-muted-foreground/50 mb-1.5" />
              <p className="text-xs font-medium text-foreground/80">No consultations found</p>
              <p className="text-[11px] text-muted-foreground leading-relaxed mt-0.5 max-w-[190px]">
                {searchQuery
                  ? 'Try a different search keyword'
                  : 'Start a consultation to store your history in the database.'}
              </p>
            </div>
          ) : (
            <div className="history-groups space-y-3.5 py-1">
              {Object.entries(groupedSessions).map(([period, items]) => {
                if (items.length === 0) return null;
                return (
                  <div key={period} className="history-group">
                    <h3 className="history-group-title">{period}</h3>
                    <ul className="space-y-1">
                      {items.map((session) => {
                        const isActive = session.id === activeSessionId;
                        return (
                          <li key={session.id} className="relative group">
                            <button
                              type="button"
                              onClick={() => {
                                onSelectSession(session.id);
                                if (window.innerWidth < 768) onClose();
                              }}
                              className={`history-session-item ${isActive ? 'is-active' : ''}`}
                              title={session.title}
                            >
                              <div className="history-item-content">
                                <span className="history-item-title">{session.title}</span>
                                <span className="history-item-time">
                                  {formatRelativeTime(session.updated_at || session.created_at)}
                                </span>
                              </div>
                            </button>

                            {/* Delete Action Button */}
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                if (window.confirm('Delete this consultation from database?')) {
                                  onDeleteSession(session.id);
                                }
                              }}
                              className="history-delete-btn"
                              title="Delete consultation"
                              aria-label={`Delete consultation ${session.title}`}
                            >
                              <Trash size={13} />
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Related Content & Context (Bottom Section) */}
        <div className="history-related-content">
          <div className="history-related-header">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Related Context
            </span>
          </div>

          {/* Active Companion Card */}
          <div className="history-companion-card">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full bg-secondary/80 flex items-center justify-center shrink-0 border border-border/80">
                <CompanionMascot kind={companion.kind} size="avatar" interactive={false} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-foreground truncate">{companion.name}</p>
                <p className="text-[10px] text-muted-foreground truncate">{agent.specialty}</p>
              </div>
            </div>
          </div>

          {/* Knowledge Sources Card */}
          <div className="history-sources-card">
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-1.5 text-xs font-medium text-foreground/90">
                <FileText size={13} className="text-primary" />
                <span>Knowledge Sources</span>
              </div>
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
                {activeDocs.length} active
              </span>
            </div>

            {activeDocs.length > 0 ? (
              <ul className="space-y-1 mb-2 max-h-20 overflow-y-auto pr-1">
                {activeDocs.slice(0, 3).map((doc) => (
                  <li
                    key={doc.id}
                    className="text-[11px] text-muted-foreground truncate flex items-center gap-1"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                    <span className="truncate">{doc.filename}</span>
                  </li>
                ))}
                {activeDocs.length > 3 && (
                  <li className="text-[10px] text-muted-foreground italic pl-2.5">
                    +{activeDocs.length - 3} more sources
                  </li>
                )}
              </ul>
            ) : (
              <p className="text-[11px] text-muted-foreground mb-2">No documents attached.</p>
            )}

            <div className="flex items-center gap-1.5 pt-1 border-t border-border/50">
              <button
                type="button"
                onClick={onOpenDocuments}
                className="text-[11px] px-2 py-1 rounded-md bg-secondary hover:bg-secondary/80 text-foreground transition-colors flex-1 text-center font-medium cursor-pointer"
              >
                Manage Sources
              </button>
              <button
                type="button"
                onClick={onOpenEvidence}
                className="text-[11px] px-2 py-1 rounded-md bg-secondary hover:bg-secondary/80 text-foreground transition-colors flex items-center justify-center gap-1 cursor-pointer"
                title="Open Evidence Graph"
              >
                <Graph size={12} />
                <span>Graph</span>
              </button>
            </div>
          </div>

          {/* Quick Metrics Bar */}
          {activeSessionId && totalMessagesCount > 0 && (
            <div className="history-session-stats">
              <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                <span>Current Session</span>
                <span className="font-mono text-foreground font-medium">
                  {totalMessagesCount} {totalMessagesCount === 1 ? 'message' : 'messages'}
                </span>
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
};
