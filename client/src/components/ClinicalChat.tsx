import React, { lazy, Suspense, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ArrowRight,
  ArrowDown,
  Check,
  CircleNotch,
  ClockCounterClockwise,
  Copy,
  FileText,
  Graph,
  PaperPlaneRight,
  Sparkle,
} from '@phosphor-icons/react';
import type { ChatMessageItem, CitationItem, HealthcareAgent } from '../types';
import { ProvenanceInspector } from './renderers/ProvenanceInspector';
import { VoiceInput } from './VoiceInput';
import { CompanionMascot } from './CompanionMascot';
import { getCompanion } from '../lib/companions';
const MermaidViewer = lazy(() =>
  import('./renderers/MermaidViewer').then((module) => ({
    default: module.MermaidViewer,
  }))
);
const KaTeXViewer = lazy(() =>
  import('./renderers/KaTeXViewer').then((module) => ({
    default: module.KaTeXViewer,
  }))
);

interface ClinicalChatProps {
  agent: HealthcareAgent | null;
  messages: ChatMessageItem[];
  onSendMessage: (query: string) => void;
  onSelectCitation: (citation: CitationItem) => void;
  isStreaming: boolean;
  selectedDocCount: number;
  sourceNames?: string[];
  onOpenDocuments?: () => void;
  onOpenEvidence?: () => void;
  onToggleHistory?: () => void;
  historyOpen?: boolean;
  sessionCount?: number;
}

export const ClinicalChat: React.FC<ClinicalChatProps> = ({
  agent,
  messages,
  onSendMessage,
  onSelectCitation,
  isStreaming,
  selectedDocCount,
  sourceNames = [],
  onOpenDocuments,
  onOpenEvidence,
  onToggleHistory,
  historyOpen,
  sessionCount,
}) => {
  const [inputText, setInputText] = useState('');
  const companion = getCompanion(agent?.domain_key);
  const [showLatest, setShowLatest] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [copyError, setCopyError] = useState('');
  const feedRef = useRef<HTMLDivElement>(null);
  const followLatestRef = useRef(true);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (messages.length > 0 && followLatestRef.current) {
      // Streaming updates must not queue smooth scrolls or steal the reader's position.
      const feed = feedRef.current;
      if (feed) feed.scrollTop = feed.scrollHeight;
    }
  }, [messages]);
  useEffect(
    () => () => {
      if (copyTimer.current) clearTimeout(copyTimer.current);
    },
    []
  );

  const jumpToLatest = () => {
    followLatestRef.current = true;
    setShowLatest(false);
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    messagesEndRef.current?.scrollIntoView({
      behavior: reduced ? 'instant' : 'smooth',
      block: 'end',
    });
  };

  const copyAnswer = async (msg: ChatMessageItem) => {
    try {
      await navigator.clipboard.writeText(msg.content);
      setCopiedId(msg.id);
      setCopyError('');
      if (copyTimer.current) clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopiedId(null), 2000);
    } catch {
      setCopyError('Copy is unavailable. Select the answer text to copy it.');
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputText.trim() && !isStreaming) {
      followLatestRef.current = true;
      setShowLatest(false);
      onSendMessage(inputText.trim());
      setInputText('');
    }
  };

  const handleSuggestionClick = (question: string) => {
    if (!isStreaming) {
      followLatestRef.current = true;
      setShowLatest(false);
      onSendMessage(question);
    }
  };

  return (
    <div className="chat-panel desk-chat" data-empty={messages.length === 0}>
      {/* Top Specialty Banner */}
      {agent && (
        <header className="desk-session-label" aria-label="Consultation header">
          <div className="flex items-center gap-2.5 min-w-0">
            {onToggleHistory && (
              <button
                type="button"
                onClick={onToggleHistory}
                className={`text-xs px-2.5 py-1 rounded-full border transition-colors flex items-center gap-1.5 cursor-pointer shrink-0 ${
                  historyOpen
                    ? 'bg-primary/10 text-primary border-primary/25 font-medium'
                    : 'bg-secondary/40 hover:bg-secondary/70 text-foreground/80 border-border/70'
                }`}
                title={historyOpen ? 'Hide consultation history' : 'Show consultation history'}
                aria-label={historyOpen ? 'Hide consultation history' : 'Show consultation history'}
              >
                <ClockCounterClockwise size={13} weight="bold" />
                <span>History</span>
                {typeof sessionCount === 'number' && sessionCount > 0 && (
                  <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-primary/15 text-primary font-mono">
                    {sessionCount}
                  </span>
                )}
              </button>
            )}

            <div className="consultation-companion truncate">
              <span className="companion-context-name">{companion.name}</span>
              <span className="ui-label text-xs"> · {agent.specialty}</span>
            </div>

            {onOpenEvidence && (
              <button
                type="button"
                onClick={onOpenEvidence}
                className="text-xs px-2.5 py-1 rounded-full bg-secondary/40 hover:bg-secondary/70 text-primary border border-border/70 transition-colors flex items-center gap-1.5 cursor-pointer shrink-0 ml-1"
                title="View evidence knowledge graph"
              >
                <Graph size={13} weight="duotone" />
                <span>Evidence Graph</span>
              </button>
            )}
          </div>
        </header>
      )}

      {/* Message Feed */}
      <div
        ref={feedRef}
        className="chat-feed space-y-6"
        role="region"
        aria-label="Consultation messages"
        tabIndex={0}
        onScroll={(event) => {
          const feed = event.currentTarget;
          const nearBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 80;
          followLatestRef.current = nearBottom;
          const shouldShow = !nearBottom && messages.length > 0;
          setShowLatest((prev) => (prev !== shouldShow ? shouldShow : prev));
        }}
      >
        {messages.length === 0 && (
          <div className="desk-welcome">
            <span className="desk-eyebrow">{agent?.specialty || 'Your clinical companion'}</span>
            <h3 className="desk-greeting">{companion.greeting}</h3>
            <p className="text-sm text-muted-foreground leading-relaxed max-w-lg">
              Bring a document or ask a question. We’ll explore it together.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <article
            key={msg.id}
            className={`chat-message notebook-entry ${msg.role === 'user' ? 'notebook-question' : 'notebook-answer'}`}
            aria-label={msg.role === 'user' ? 'Your question' : `${companion.name}’s answer`}
          >
            {msg.role !== 'user' && (
              <div className="message-companion-avatar">
                <CompanionMascot kind={companion.kind} size="avatar" thinking={!!msg.isStreaming} />
              </div>
            )}

            <div className="notebook-content">
              <div className="flex items-center justify-between mb-2">
                <p className="notebook-author mb-0">
                  {msg.role === 'user' ? 'You asked' : companion.name}
                </p>
                {msg.role === 'assistant' && msg.isStreaming && (
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-primary/10 text-primary border border-primary/20 animate-pulse">
                    <CircleNotch size={11} className="animate-spin" />
                    <span>Live Clinical Stream</span>
                  </span>
                )}
              </div>

              {msg.role === 'user' ? (
                <div className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
                  {msg.content}
                </div>
              ) : msg.isStreaming && !msg.content ? (
                <div className="flex items-center gap-2.5 py-2.5 px-3.5 rounded-xl bg-primary/5 border border-primary/15 text-primary text-xs animate-pulse my-2">
                  <CircleNotch size={15} className="animate-spin text-primary shrink-0" />
                  <span className="font-medium">
                    Searching clinical evidence & generating answer…
                  </span>
                </div>
              ) : (
                <div className="markdown-body font-sans text-sm leading-relaxed text-foreground/90">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      a({ href, children, ...props }) {
                        if (href?.startsWith('#cite-')) {
                          const citeNum = Number(href.replace('#cite-', ''));
                          const citation = msg.citations?.find(
                            (item) => item.citation_number === citeNum
                          );
                          if (citation) {
                            return (
                              <button
                                type="button"
                                className="desk-inline-citation"
                                aria-label={`Open source ${citation.citation_number}: ${citation.filename}`}
                                onClick={() => onSelectCitation(citation)}
                              >
                                {children}
                              </button>
                            );
                          }
                        }
                        return (
                          <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary underline hover:text-primary/80 transition-colors font-medium"
                            {...props}
                          >
                            {children}
                          </a>
                        );
                      },
                      p({ children }) {
                        return <p className="mb-2 leading-relaxed text-sm last:mb-0">{children}</p>;
                      },
                      h1({ children }) {
                        return (
                          <h1 className="text-base font-serif font-bold text-foreground mt-3 mb-1.5 pb-1 border-b border-border/60">
                            {children}
                          </h1>
                        );
                      },
                      h2({ children }) {
                        return (
                          <h2 className="text-sm font-serif font-bold text-foreground mt-2.5 mb-1">
                            {children}
                          </h2>
                        );
                      },
                      h3({ children }) {
                        return (
                          <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground/80 mt-2 mb-1">
                            {children}
                          </h3>
                        );
                      },
                      ul({ children }) {
                        return (
                          <ul className="list-disc pl-5 space-y-1 my-2 text-sm">{children}</ul>
                        );
                      },
                      ol({ children }) {
                        return (
                          <ol className="list-decimal pl-5 space-y-1 my-2 text-sm">{children}</ol>
                        );
                      },
                      li({ children }) {
                        return <li className="leading-relaxed">{children}</li>;
                      },
                      strong({ children }) {
                        return (
                          <strong className="font-semibold text-foreground">{children}</strong>
                        );
                      },
                      blockquote({ children }) {
                        return (
                          <blockquote className="border-l-2 border-primary/50 pl-3 italic text-muted-foreground my-2">
                            {children}
                          </blockquote>
                        );
                      },
                      table({ children }) {
                        return (
                          <div className="overflow-x-auto my-3 border border-border rounded-lg shadow-2xs">
                            <table className="min-w-full text-xs divide-y divide-border text-foreground">
                              {children}
                            </table>
                          </div>
                        );
                      },
                      th({ children }) {
                        return (
                          <th className="px-3 py-1.5 bg-muted/60 font-semibold text-left text-foreground border-b border-border">
                            {children}
                          </th>
                        );
                      },
                      td({ children }) {
                        return (
                          <td className="px-3 py-1.5 border-t border-border/70">{children}</td>
                        );
                      },
                      code({ className, children, ...props }) {
                        const match = /language-(\w+)/.exec(className || '');
                        const childStr = String(children || '').replace(/\n$/, '');
                        const isMermaid =
                          (match && match[1] === 'mermaid') ||
                          /^\s*(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|journey|gantt|pie|gitGraph)\b/m.test(
                            childStr
                          );
                        if (isMermaid) {
                          return (
                            <Suspense
                              fallback={
                                <p className="text-xs text-muted-foreground animate-pulse my-2">
                                  Loading diagram…
                                </p>
                              }
                            >
                              <MermaidViewer chart={childStr} />
                            </Suspense>
                          );
                        }
                        const isBlock = /language-/.test(className || '');
                        return isBlock ? (
                          <div className="overflow-x-auto my-2 p-2.5 bg-muted/60 rounded-lg text-xs font-mono border border-border/50">
                            <code className={className} {...props}>
                              {children}
                            </code>
                          </div>
                        ) : (
                          <code
                            className="px-1.5 py-0.5 rounded bg-muted text-primary text-xs font-mono border border-border/40"
                            {...props}
                          >
                            {children}
                          </code>
                        );
                      },
                    }}
                  >
                    {msg.content.replace(/\[(\d+)\]/g, '[$1](#cite-$1)')}
                  </ReactMarkdown>
                  {msg.isStreaming && (
                    <span
                      className="inline-block w-1.5 h-3.5 ml-1 bg-primary/70 rounded-xs animate-pulse align-middle"
                      aria-label="Generating token…"
                    />
                  )}
                </div>
              )}

              {/* Visual Payload: KaTeX Formula */}
              {msg.visual_payload?.katex && (
                <div className="mt-3">
                  <Suspense fallback={<p>Loading formula…</p>}>
                    <KaTeXViewer math={msg.visual_payload.katex} />
                  </Suspense>
                </div>
              )}

              {/* Grounding Provenance Matrix: Docs, Keywords & Knowledge Graph Triples */}
              {msg.citations?.length ||
              msg.graph_triples?.length ||
              msg.matched_keywords?.length ? (
                <ProvenanceInspector
                  citations={msg.citations}
                  graphTriples={msg.graph_triples}
                  matchedKeywords={msg.matched_keywords}
                  onSelectCitation={onSelectCitation}
                />
              ) : null}

              {/* Follow-up question chips (Add-on Feature) */}
              {msg.follow_up_suggestions && msg.follow_up_suggestions.length > 0 && (
                <div className="mt-4 pt-3 border-t border-border ">
                  <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2 flex items-center space-x-1.5">
                    <Sparkle size={14} weight="duotone" className="text-primary " />
                    <span>Suggested Next Clinical Queries:</span>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    {msg.follow_up_suggestions.map((q: string, idx: number) => (
                      <button
                        key={idx}
                        onClick={() => handleSuggestionClick(q)}
                        disabled={isStreaming}
                        className="text-left text-xs px-3 py-1.5 rounded-lg bg-secondary/40 hover:bg-secondary/40   text-primary  border border-primary/30  hover:border-primary/30  transition-all flex items-center justify-between group cursor-pointer"
                      >
                        <span>{q}</span>
                        <ArrowRight
                          size={13}
                          weight="bold"
                          className="text-primary  opacity-0 group-hover:opacity-100 transition-opacity shrink-0 ml-2"
                        />
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {msg.role === 'assistant' && msg.content && !msg.isStreaming && (
                <div className="message-actions">
                  <button
                    type="button"
                    className="ui-button"
                    onClick={() => void copyAnswer(msg)}
                    aria-label="Copy answer"
                  >
                    {copiedId === msg.id ? <Check size={14} /> : <Copy size={14} />}
                    {copiedId === msg.id ? 'Copied' : 'Copy answer'}
                  </button>
                </div>
              )}
            </div>
          </article>
        ))}

        <div ref={messagesEndRef} />

        {showLatest && (
          <button
            type="button"
            className="ui-button jump-to-latest"
            onClick={jumpToLatest}
            aria-label="Jump to latest message"
          >
            <ArrowDown size={14} />
            <span>Latest</span>
          </button>
        )}
      </div>

      {/* Input Bar */}
      <div className="chat-composer desk-composer">
        <div className="composer-companion">
          <CompanionMascot kind={companion.kind} size="welcome" thinking={isStreaming} />
          <span className="composer-companion-name">{companion.name}</span>
        </div>
        <form onSubmit={handleSubmit}>
          {/* Clinical Voice Input (Add-on Feature) */}
          <VoiceInput
            onTranscribed={(transcript) => {
              setInputText((prev) => (prev ? `${prev} ${transcript}` : transcript));
            }}
            disabled={isStreaming}
          />

          <textarea
            rows={1}
            aria-label="Clinical question"
            aria-describedby="composer-help"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder={`Ask ${companion.name} about your documents…`}
            disabled={isStreaming}
            className="ui-input flex-1"
          />

          <button
            type="submit"
            aria-label="Send question"
            disabled={!inputText.trim() || isStreaming}
            className="ui-button ui-button-primary ui-icon-button"
          >
            {isStreaming ? (
              <CircleNotch size={18} className="animate-spin" />
            ) : (
              <PaperPlaneRight size={18} weight="fill" />
            )}
          </button>
        </form>
        <div className="desk-source-tray">
          <button type="button" className="desk-source-button" onClick={onOpenDocuments}>
            <FileText size={16} />
            <span>
              {selectedDocCount ? `${selectedDocCount} sources selected` : 'Bring a document'}
            </span>
          </button>
          {sourceNames.slice(0, 2).map((name, index) => (
            <button
              key={`${name}-${index}`}
              type="button"
              className="desk-source-sheet"
              title={name}
              onClick={onOpenDocuments}
            >
              {name}
            </button>
          ))}
          {sourceNames.length > 2 && (
            <span className="ui-label">+{sourceNames.length - 2} more</span>
          )}
          {onOpenEvidence && (
            <button
              type="button"
              className="desk-source-button ml-auto flex items-center gap-1.5 text-primary hover:text-primary/80 transition-colors cursor-pointer"
              onClick={onOpenEvidence}
              title="View evidence knowledge graph"
            >
              <Graph size={15} weight="duotone" />
              <span>Evidence Graph</span>
            </button>
          )}
        </div>
        {messages.length === 0 && (
          <div className="desk-prompts" aria-label="Suggested questions">
            <p className="ui-label">Or start with a little curiosity</p>
            {companion.prompts.map((sample) => (
              <button
                type="button"
                key={sample}
                onClick={() => handleSuggestionClick(sample)}
                disabled={isStreaming}
              >
                {sample}
                <ArrowRight size={14} />
              </button>
            ))}
          </div>
        )}
        <div className="flex items-center justify-between text-[11px] text-muted-foreground mt-1.5 mb-1 px-1">
          <span>AI can make mistakes · Verify clinical sources</span>
          <span className="hidden sm:inline">
            {copyError ||
              (copiedId
                ? 'Answer copied to clipboard'
                : isStreaming
                  ? 'Generating response…'
                  : 'Enter to send · Shift+Enter for newline')}
          </span>
        </div>
      </div>
    </div>
  );
};
