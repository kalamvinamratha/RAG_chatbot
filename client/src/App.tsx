import { useEffect, useRef, useState } from 'react';
import { CircleNotch, Sparkle, X } from '@phosphor-icons/react';
import { CompanionLobby } from './components/CompanionLobby';
import { CompanionMascot } from './components/CompanionMascot';
import { ClinicalChat } from './components/ClinicalChat';
import { DocumentDropzone } from './components/DocumentDropzone';
import { GraphModal } from './components/GraphModal';
import { Navbar } from './components/Navbar';
import { Toast } from './components/Toast';
import { ChatHistorySidebar } from './components/ChatHistorySidebar';
import { EvidenceDrawer } from './components/renderers/EvidenceDrawer';
import { apiFetch } from './lib/api';
import { readSSE } from './lib/sse';
import { useDialogFocus } from './hooks/useDialogFocus';
import type {
  ChatMessageItem,
  ChatSessionItem,
  CitationItem,
  DocumentItem,
  HealthcareAgent,
  GraphTripleItem,
  MatchedKeywordItem,
} from './types';

interface CitationEvent {
  citations: CitationItem[];
  graph_triples: GraphTripleItem[];
  matched_keywords: MatchedKeywordItem[];
}

function Workspace({ agent, visible }: { agent: HealthcareAgent; visible: boolean }) {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSessionItem[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState('');
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(null);
  const [graphOpen, setGraphOpen] = useState(false);
  const [documentsOpen, setDocumentsOpen] = useState(false);
  const documentsRef = useRef<HTMLDivElement>(null);
  useDialogFocus(documentsRef, visible && documentsOpen, () => setDocumentsOpen(false));
  const requests = useRef(new Set<AbortController>());
  const activeStream = useRef(false);
  const documentRequest = useRef(0);

  const refreshSessions = async (signal?: AbortSignal) => {
    try {
      const res = await apiFetch(`/api/v1/chat/sessions?agent_id=${agent.id}`, {
        signal,
      });
      if (res.ok) {
        const list: ChatSessionItem[] = await res.json();
        setSessions(list);
      }
    } catch {
      // background refresh error ignored
    }
  };

  const loadSessionMessages = async (id: string) => {
    const controller = new AbortController();
    requests.current.add(controller);
    try {
      setError('');
      const res = await apiFetch(`/api/v1/chat/sessions/${id}/messages`, {
        signal: controller.signal,
      });
      if (res.ok) {
        const msgs: Array<{
          id: string;
          role: 'user' | 'assistant' | 'system';
          content: string;
          visual_payload?: ChatMessageItem['visual_payload'];
          follow_up_suggestions?: string[];
          citations?: CitationItem[];
          created_at?: string;
        }> = await res.json();
        setSessionId(id);
        setMessages(
          msgs.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            visual_payload: m.visual_payload,
            follow_up_suggestions: m.follow_up_suggestions,
            citations: m.citations,
            created_at: m.created_at,
          }))
        );
      }
    } catch (e) {
      if (!controller.signal.aborted)
        setError(e instanceof Error ? e.message : 'Failed to load messages');
    } finally {
      requests.current.delete(controller);
    }
  };

  const handleNewSession = () => {
    setSessionId(null);
    setMessages([]);
    setSelectedCitation(null);
  };

  const handleDeleteSession = async (id: string) => {
    try {
      await apiFetch(`/api/v1/chat/sessions/${id}`, { method: 'DELETE' });
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (sessionId === id) {
        handleNewSession();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete session');
    }
  };

  useEffect(() => {
    const controllers = requests.current;
    const controller = new AbortController();
    controllers.add(controller);
    apiFetch(`/api/v1/documents?agent_id=${agent.id}`, {
      signal: controller.signal,
    })
      .then((r) => r.json())
      .then((docs: DocumentItem[]) => {
        if (controller.signal.aborted) return;
        setDocuments(docs);
        setSelectedDocIds(docs.filter((d) => d.status === 'completed').map((d) => d.id));
      })
      .catch((e: Error) => {
        if (!controller.signal.aborted) setError(e.message);
      });

    apiFetch(`/api/v1/chat/sessions?agent_id=${agent.id}`, {
      signal: controller.signal,
    })
      .then((r) => (r.ok ? r.json() : []))
      .then((list: ChatSessionItem[]) => {
        if (controller.signal.aborted) return;
        setSessions(list);
        setSessionsLoading(false);
      })
      .catch((e: Error) => {
        if (!controller.signal.aborted) {
          setError(e.message);
          setSessionsLoading(false);
        }
      });

    return () => {
      controllers.forEach((c) => c.abort());
      controllers.clear();
    };
  }, [agent.id]);

  const refreshDocuments = async (signal: AbortSignal) => {
    const request = ++documentRequest.current;
    const docs: DocumentItem[] = await (
      await apiFetch(`/api/v1/documents?agent_id=${agent.id}`, { signal })
    ).json();
    if (!signal.aborted && request === documentRequest.current) {
      setDocuments(docs);
      const available = new Set(docs.filter((d) => d.status === 'completed').map((d) => d.id));
      setSelectedDocIds((prev) => prev.filter((id) => available.has(id)));
    }
  };

  const documentAction = async (action: (signal: AbortSignal) => Promise<void>) => {
    const controller = new AbortController();
    requests.current.add(controller);
    setIsUploading(true);
    setError('');
    try {
      await action(controller.signal);
    } catch (e) {
      if (!controller.signal.aborted)
        setError(e instanceof Error ? e.message : 'Document operation failed');
    } finally {
      if (!controller.signal.aborted) {
        try {
          await refreshDocuments(controller.signal);
        } catch (e) {
          if (!controller.signal.aborted)
            setError(e instanceof Error ? e.message : 'Could not refresh documents');
        }
        setIsUploading(false);
      }
      requests.current.delete(controller);
    }
  };

  const handleSendMessage = async (query: string) => {
    if (activeStream.current) return;
    activeStream.current = true;
    const controller = new AbortController();
    requests.current.add(controller);
    const assistantId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: 'user', content: query },
      { id: assistantId, role: 'assistant', content: '', isStreaming: true },
    ]);
    setIsStreaming(true);
    setError('');
    const update = (fn: (message: ChatMessageItem) => ChatMessageItem) => {
      if (!controller.signal.aborted)
        setMessages((prev) => prev.map((m) => (m.id === assistantId ? fn(m) : m)));
    };
    try {
      const response = await apiFetch('/api/v1/chat/stream', {
        method: 'POST',
        signal: controller.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: agent.id,
          session_id: sessionId,
          message: query,
          document_ids: selectedDocIds,
        }),
      });
      if (!response.body) throw new Error('No response stream');
      let completed = false;
      for await (const event of readSSE(response.body)) {
        if (controller.signal.aborted) break;
        switch (event.event) {
          case 'session':
            setSessionId((event.data as { session_id: string }).session_id);
            break;
          case 'token':
            update((m) => ({
              ...m,
              content: m.content + (event.data as { token: string }).token,
            }));
            break;
          case 'citations': {
            const data = event.data as CitationEvent;
            update((m) => ({
              ...m,
              citations: data.citations,
              graph_triples: data.graph_triples,
              matched_keywords: data.matched_keywords,
            }));
            break;
          }
          case 'visual_payload':
            update((m) => ({
              ...m,
              visual_payload: event.data as ChatMessageItem['visual_payload'],
            }));
            break;
          case 'follow_up_suggestions':
            update((m) => ({
              ...m,
              follow_up_suggestions: event.data as string[],
            }));
            break;
          case 'error':
            throw new Error((event.data as { message: string }).message);
          case 'done':
            completed = true;
            void refreshSessions();
            break;
        }
      }
      if (!completed && !controller.signal.aborted)
        throw new Error('Response interrupted. Please retry.');
    } catch (e) {
      if (!controller.signal.aborted) {
        const message = e instanceof Error ? e.message : 'Chat failed';
        setError(message);
        update((m) => ({
          ...m,
          content: m.content + '\n\n[Response incomplete]',
        }));
      }
    } finally {
      update((m) => ({ ...m, isStreaming: false }));
      if (!controller.signal.aborted) setIsStreaming(false);
      activeStream.current = false;
      requests.current.delete(controller);
    }
  };

  return (
    <>
      <Toast message={error} onClose={() => setError('')} />
      <div className="desk-workspace">
        <ChatHistorySidebar
          agent={agent}
          sessions={sessions}
          activeSessionId={sessionId}
          loading={sessionsLoading}
          onSelectSession={(id) => void loadSessionMessages(id)}
          onNewSession={handleNewSession}
          onDeleteSession={(id) => void handleDeleteSession(id)}
          isOpen={historyOpen}
          onClose={() => setHistoryOpen(false)}
          documents={documents}
          selectedDocIds={selectedDocIds}
          onOpenDocuments={() => {
            setSelectedCitation(null);
            setGraphOpen(false);
            setDocumentsOpen(true);
          }}
          onOpenEvidence={() => {
            setSelectedCitation(null);
            setDocumentsOpen(false);
            setGraphOpen(true);
          }}
          totalMessagesCount={messages.length}
        />
        {documentsOpen && visible && (
          <div className="desk-document-overlay">
            <div
              className="desk-backdrop"
              aria-hidden="true"
              onClick={() => setDocumentsOpen(false)}
            />
            <div
              ref={documentsRef}
              role="dialog"
              aria-modal="true"
              aria-label="Document tray"
              tabIndex={-1}
              id="desk-documents"
              className="desk-documents"
            >
              <button
                type="button"
                data-dialog-close
                className="ui-button ui-icon-button desk-document-close"
                aria-label="Close documents"
                onClick={() => setDocumentsOpen(false)}
              >
                <X size={18} />
              </button>
              <DocumentDropzone
                documents={documents}
                selectedDocumentIds={selectedDocIds}
                onToggleSelectDocument={(id) =>
                  setSelectedDocIds((prev) =>
                    prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]
                  )
                }
                onSelectAllDocuments={(all) =>
                  setSelectedDocIds(
                    all ? documents.filter((d) => d.status === 'completed').map((d) => d.id) : []
                  )
                }
                onUpload={(file) =>
                  documentAction(async (signal) => {
                    const data = new FormData();
                    data.append('agent_id', agent.id);
                    data.append('file', file);
                    const response = await apiFetch('/api/v1/documents/upload', {
                      method: 'POST',
                      body: data,
                      signal,
                    });
                    const result: { document_id: string } = await response.json();
                    if (!signal.aborted) setSelectedDocIds((prev) => [...prev, result.document_id]);
                  })
                }
                onDelete={(id) =>
                  documentAction(async (signal) => {
                    await apiFetch(`/api/v1/documents/${id}`, {
                      method: 'DELETE',
                      signal,
                    });
                  })
                }
                onRetry={(id) =>
                  documentAction(async (signal) => {
                    await apiFetch(`/api/v1/documents/${id}/retry`, {
                      method: 'POST',
                      signal,
                    });
                  })
                }
                isUploading={isUploading}
                uploadError={error}
                onClearUploadError={() => setError('')}
              />
            </div>
          </div>
        )}
        <ClinicalChat
          agent={agent}
          messages={messages}
          onSendMessage={handleSendMessage}
          onSelectCitation={setSelectedCitation}
          isStreaming={isStreaming}
          selectedDocCount={selectedDocIds.length}
          sourceNames={documents
            .filter((doc) => selectedDocIds.includes(doc.id))
            .map((doc) => doc.filename)}
          onOpenDocuments={() => {
            setSelectedCitation(null);
            setGraphOpen(false);
            setDocumentsOpen(true);
          }}
          onOpenEvidence={() => {
            setSelectedCitation(null);
            setDocumentsOpen(false);
            setGraphOpen(true);
          }}
          onToggleHistory={() => setHistoryOpen((prev) => !prev)}
          historyOpen={historyOpen}
          sessionCount={sessions.length}
        />
      </div>
      <EvidenceDrawer
        citation={visible ? selectedCitation : null}
        onClose={() => setSelectedCitation(null)}
      />
      <GraphModal
        isOpen={visible && graphOpen}
        onClose={() => setGraphOpen(false)}
        agentId={agent.id}
        documentIds={selectedDocIds}
      />
    </>
  );
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [agents, setAgents] = useState<HealthcareAgent[]>([]);
  const [activeAgent, setActiveAgent] = useState<HealthcareAgent | null>(null);
  const [error, setError] = useState('');
  const [choosingCompanion, setChoosingCompanion] = useState(true);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const [agentsRevision, setAgentsRevision] = useState(0);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [signingIn, setSigningIn] = useState(false);
  const sessionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!choosingCompanion) sessionRef.current?.focus();
  }, [choosingCompanion, activeAgent]);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch('/api/v1/auth/session', { signal: controller.signal })
      .then(() => setAuthenticated(true))
      .catch(async () => {
        // Automatically connect to session without requiring manual access key entry
        try {
          await apiFetch('/api/v1/auth/session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
            signal: controller.signal,
          });
          setAuthenticated(true);
        } catch {
          // Allow manual Start button click if initial request failed
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setCheckingAuth(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!authenticated) return;
    const controller = new AbortController();
    apiFetch('/api/v1/agents', { signal: controller.signal })
      .then((r) => r.json())
      .then((data: HealthcareAgent[]) => {
        if (!controller.signal.aborted) {
          setAgents(data);
          setAgentsLoading(false);
        }
      })
      .catch((e: Error) => {
        if (!controller.signal.aborted) {
          setError(e.message);
          setAgentsLoading(false);
        }
      });
    return () => controller.abort();
  }, [authenticated, agentsRevision]);

  if (checkingAuth)
    return (
      <main
        className="app-startup flex flex-col items-center justify-center min-h-screen gap-3"
        role="status"
      >
        <CircleNotch size={36} className="animate-spin text-primary" />
        <p className="text-base font-serif font-medium text-foreground">Helios Clinical AI</p>
        <p className="text-xs text-muted-foreground">Opening your clinical workspace…</p>
      </main>
    );

  if (!authenticated)
    return (
      <main className="signin-layout">
        <section className="signin-story">
          <div className="flex items-center gap-3">
            <span className="workspace-title">Helios Clinical AI</span>
          </div>
          <div className="space-y-6 max-w-lg">
            <span className="ui-label uppercase tracking-widest">
              Your evidence. A clearer perspective.
            </span>
            <h2 className="display-heading">
              Big questions.
              <br />
              <em>Little companions.</em>
            </h2>
            <p className="text-sm leading-relaxed">
              Meet four curious companions for your clinical documents. Find your specialty, bring
              your sources, and explore the details together.
            </p>
            <div className="flex flex-wrap gap-2">
              <span className="ui-badge">Document search</span>
              <span className="ui-badge">Knowledge graphs</span>
              <span className="ui-badge">Source citations</span>
            </div>
            <div className="signin-companions" aria-hidden="true">
              <CompanionMascot kind="cardiology" size="welcome" />
              <CompanionMascot kind="gynaecology" size="welcome" />
              <CompanionMascot kind="general_medicine" size="welcome" />
              <CompanionMascot kind="neurology" size="welcome" />
            </div>
          </div>
          <footer className="ui-label">
            An assistance prototype, not a substitute for clinical judgment.
          </footer>
        </section>
        <section className="signin-form-area">
          <div className="signin-card">
            <div className="flex items-center gap-2 text-muted-foreground text-sm mb-4">
              <Sparkle size={18} /> Clinical AI Workspace
            </div>
            <h1>Welcome to your workspace.</h1>
            <p className="text-muted-foreground text-sm mt-3">
              Explore clinical guidelines, analyze patient documents, and consult with specialized
              domain companions.
            </p>
            <button
              className="ui-button ui-button-primary w-full mt-6 py-3 text-base flex items-center justify-center gap-2"
              type="button"
              disabled={signingIn}
              onClick={async () => {
                if (signingIn) return;
                setSigningIn(true);
                try {
                  await apiFetch('/api/v1/auth/session', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({}),
                  });
                  setError('');
                  setAuthenticated(true);
                } catch (e) {
                  setError(e instanceof Error ? e.message : 'Unable to open workspace');
                } finally {
                  setSigningIn(false);
                }
              }}
            >
              {signingIn ? (
                <>
                  <CircleNotch size={18} className="animate-spin" />
                  <span>Opening your workspace…</span>
                </>
              ) : (
                'Start — Select Your Agent'
              )}
            </button>
            {error && (
              <p role="alert" className="text-destructive mt-3">
                {error}
              </p>
            )}
          </div>
        </section>
      </main>
    );

  return (
    <div className="app-shell">
      {!choosingCompanion && (
        <Navbar
          onChangeCompanion={() => setChoosingCompanion(true)}
          onSignOut={async () => {
            try {
              await apiFetch('/api/v1/auth/session', { method: 'DELETE' });
              setAuthenticated(false);
              setAgents([]);
              setActiveAgent(null);
              setChoosingCompanion(true);
              setAgentsLoading(true);
            } catch (e) {
              setError(e instanceof Error ? e.message : 'Sign out failed');
            }
          }}
        />
      )}
      {error && !choosingCompanion && (
        <p role="alert" className="ui-error">
          {error}
        </p>
      )}
      {choosingCompanion && (
        <CompanionLobby
          agents={agents}
          loading={agentsLoading}
          error={error}
          activeAgent={activeAgent}
          onChoose={(agent) => {
            setActiveAgent(agent);
            setChoosingCompanion(false);
            setError('');
          }}
          onRetry={() => {
            setError('');
            setAgentsLoading(true);
            setAgentsRevision((revision) => revision + 1);
          }}
        />
      )}
      <div
        className="consultation-session"
        ref={sessionRef}
        tabIndex={-1}
        aria-label="Clinical consultation"
        hidden={choosingCompanion}
      >
        {activeAgent && (
          <Workspace key={activeAgent.id} agent={activeAgent} visible={!choosingCompanion} />
        )}
      </div>
    </div>
  );
}
