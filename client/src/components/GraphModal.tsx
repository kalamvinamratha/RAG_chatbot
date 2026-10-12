import React, { useEffect, useRef, useState } from 'react';
import {
  ArrowsClockwise,
  CircleNotch,
  Database,
  Graph,
  ShareNetwork,
  X,
} from '@phosphor-icons/react';
import type { GraphData } from '../types';
import { apiFetch } from '../lib/api';
import { useDialogFocus } from '../hooks/useDialogFocus';

interface GraphModalProps {
  isOpen: boolean;
  onClose: () => void;
  agentId?: string;
  documentIds?: string[];
}

export const GraphModal: React.FC<GraphModalProps> = ({
  isOpen,
  onClose,
  agentId,
  documentIds,
}) => {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const dialogRef = useRef<HTMLDivElement>(null);
  useDialogFocus(dialogRef, isOpen, onClose);
  const params = new URLSearchParams({ limit: '50' });
  if (agentId) params.set('agent_id', agentId);
  documentIds?.forEach((id) => params.append('document_ids', id));
  const url = `/api/v1/graph/subgraph?${params}`;

  const fetchGraph = () => {
    setIsLoading(true);
    setRefresh((value) => value + 1);
  };

  useEffect(() => {
    if (!isOpen) return;
    const controller = new AbortController();
    // An explicit empty selection means no evidence, not all documents.
    const request =
      documentIds?.length === 0
        ? Promise.resolve({ nodes: [], edges: [], total_nodes: 0, total_edges: 0 })
        : apiFetch(url, { signal: controller.signal }).then((r) => r.json());
    request
      .then((data: GraphData) => {
        if (!controller.signal.aborted) {
          setGraphData(data);
          setError('');
        }
      })
      .catch((e: Error) => {
        if (!controller.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });
    return () => controller.abort();
  }, [isOpen, url, documentIds?.length, refresh]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="graph-heading"
      aria-busy={isLoading}
      ref={dialogRef}
      tabIndex={-1}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      className="dialog-overlay fixed inset-0 z-50 flex items-center justify-center bg-background/70 backdrop-blur-sm p-4"
    >
      <div className="dialog-surface bg-card border border-border rounded-2xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-border/90  flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="h-8 w-8 rounded-lg bg-secondary/40  text-primary  flex items-center justify-center">
              <Graph size={20} weight="duotone" />
            </div>
            <div>
              <h3 id="graph-heading" className="workspace-title">
                Evidence connections
              </h3>
              <p className="text-xs text-muted-foreground ">
                Source-extracted entities and relationships
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={fetchGraph}
              disabled={isLoading}
              className="p-2 rounded-lg bg-muted hover:bg-muted   text-muted-foreground  transition-colors cursor-pointer"
              title="Refresh Graph"
            >
              <ArrowsClockwise
                size={16}
                weight="bold"
                className={isLoading ? 'animate-spin' : ''}
              />
            </button>
            <button
              onClick={onClose}
              data-dialog-close
              aria-label="Close knowledge graph"
              className="p-2 rounded-lg bg-muted hover:bg-muted   text-muted-foreground hover:text-foreground   transition-colors cursor-pointer"
            >
              <X size={16} weight="bold" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 p-6 overflow-y-auto space-y-6">
          {error && (
            <p role="alert" className="text-destructive">
              {error}
            </p>
          )}
          {isLoading && (
            <div
              className="flex flex-col items-center justify-center py-12 text-center"
              role="status"
            >
              <CircleNotch size={32} className="animate-spin text-primary mb-3" />
              <p className="text-sm font-medium text-foreground">
                Extracting evidence graph connections…
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Traversing entities and relationships from Neo4j
              </p>
            </div>
          )}
          {graphData && graphData.edges.length > 0 && (
            <>
              {/* Stats */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3.5 rounded-xl bg-background  border border-border/90 ">
                  <span className="text-xs text-muted-foreground  uppercase font-semibold tracking-wider">
                    Total Entities
                  </span>
                  <p className="text-lg font-semibold text-primary  mt-0.5">
                    {graphData.total_nodes}
                  </p>
                </div>
                <div className="p-3.5 rounded-xl bg-background  border border-border/90 ">
                  <span className="text-xs text-muted-foreground  uppercase font-semibold tracking-wider">
                    Clinical Relations
                  </span>
                  <p className="text-lg font-semibold text-primary  mt-0.5">
                    {graphData.total_edges}
                  </p>
                </div>
                <div className="p-3.5 rounded-xl bg-background  border border-border/90 ">
                  <span className="text-xs text-muted-foreground  uppercase font-semibold tracking-wider flex items-center space-x-1">
                    <Database size={12} weight="bold" />
                    <span>Graph Engine</span>
                  </span>
                  <p className="text-lg font-semibold text-primary  mt-0.5">Neo4j</p>
                </div>
                <div className="p-3.5 rounded-xl bg-background  border border-border/90 ">
                  <span className="text-xs text-muted-foreground  uppercase font-semibold tracking-wider flex items-center space-x-1">
                    <ShareNetwork size={12} weight="bold" />
                    <span>Traversal</span>
                  </span>
                  <p className="text-lg font-semibold text-primary  mt-0.5">Cypher</p>
                </div>
              </div>

              {/* Entity Badges */}
              <div>
                <h4 className="text-xs font-semibold text-foreground  uppercase tracking-wider mb-2">
                  Extracted Medical Entities:
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {graphData.nodes.map((n) => (
                    <span
                      key={n.id}
                      className="px-2.5 py-1 rounded-lg bg-background  border border-border  text-xs font-medium text-foreground  flex items-center space-x-1.5"
                    >
                      <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                      <span>{n.label}</span>
                      <span className="text-xs text-muted-foreground font-mono">({n.type})</span>
                    </span>
                  ))}
                </div>
              </div>

              {/* Relationships Table */}
              <div>
                <h4 className="text-xs font-semibold text-foreground  uppercase tracking-wider mb-2">
                  Clinical Knowledge Graph Triples:
                </h4>
                <div className="space-y-1.5">
                  {graphData.edges.map((e, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-xl bg-background  border border-border  text-xs flex items-center justify-between"
                    >
                      <span className="font-semibold text-foreground ">
                        {e.source.toUpperCase()}
                      </span>
                      <span className="px-2 py-0.5 rounded-md bg-secondary/40  text-primary  font-mono text-xs font-semibold border border-primary/30 ">
                        --[{e.label}]--&gt;
                      </span>
                      <span className="font-semibold text-primary ">{e.target.toUpperCase()}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {(!graphData || graphData.edges.length === 0) && !isLoading && !error && (
            <div className="text-center py-12 text-muted-foreground text-xs">
              No relationships to explore yet. Upload a document with clinical relationships, then
              select it for your consultation.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
