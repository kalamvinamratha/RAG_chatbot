import React, { useState } from 'react';
import {
  CaretDown,
  CaretUp,
  FileText,
  Graph,
  Image as ImageIcon,
  Pill,
  Tag,
} from '@phosphor-icons/react';
import type { CitationItem, GraphTripleItem, MatchedKeywordItem } from '../../types';

interface ProvenanceInspectorProps {
  citations?: CitationItem[];
  graphTriples?: GraphTripleItem[];
  matchedKeywords?: MatchedKeywordItem[];
  onSelectCitation: (citation: CitationItem) => void;
}

export const ProvenanceInspector: React.FC<ProvenanceInspectorProps> = ({
  citations = [],
  graphTriples = [],
  matchedKeywords = [],
  onSelectCitation,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'docs' | 'keywords' | 'graph'>('docs');

  const hasCitations = citations.length > 0;
  const hasKeywords = matchedKeywords.length > 0;
  const hasGraph = graphTriples.length > 0;

  if (!hasCitations && !hasKeywords && !hasGraph) {
    return null;
  }

  const getEntityColor = (type?: string) => {
    switch (type?.toLowerCase()) {
      case 'disease':
      case 'condition':
        return 'bg-destructive/10  text-destructive  border-destructive/30 ';
      case 'medication':
      case 'drug':
        return 'bg-secondary/40  text-primary  border-primary/30 ';
      case 'symptom':
        return 'bg-secondary/40  text-primary  border-primary/30 ';
      case 'treatment':
      case 'labtest':
        return 'bg-secondary/40  text-primary  border-primary/30 ';
      default:
        return 'bg-muted  text-foreground  border-border ';
    }
  };

  const getRelationBadge = (rel: string) => {
    switch (rel.toUpperCase()) {
      case 'CONTRAINDICATES':
        return 'bg-destructive/10  text-destructive  border-destructive/30 ';
      case 'TREATS':
        return 'bg-secondary/40  text-primary  border-primary/30 ';
      case 'CAUSES':
        return 'bg-secondary/40  text-primary  border-primary/30 ';
      default:
        return 'bg-secondary/40  text-primary  border-primary/30 ';
    }
  };

  return (
    <div className="mt-4 pt-3.5 border-t border-border ">
      {/* Interactive Grounding Bar Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center space-x-1.5 text-xs">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground ">
            Grounding Provenance:
          </span>
          <div className="flex items-center space-x-1.5">
            {hasCitations && (
              <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md text-xs font-semibold bg-secondary/40  text-primary  border border-primary/30 ">
                <FileText size={12} weight="duotone" />
                <span>{citations.length} Docs</span>
              </span>
            )}
            {hasKeywords && (
              <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md text-xs font-semibold bg-secondary/40  text-primary  border border-primary/30 ">
                <Tag size={12} weight="duotone" />
                <span>{matchedKeywords.length} Keywords</span>
              </span>
            )}
            {hasGraph && (
              <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md text-xs font-semibold bg-secondary/40  text-primary  border border-primary/30 ">
                <Graph size={12} weight="duotone" />
                <span>{graphTriples.length} Graph Triples</span>
              </span>
            )}
          </div>
        </div>

        {/* Expand / Collapse Button */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-muted hover:bg-muted   text-foreground  transition-all cursor-pointer shadow-2xs"
        >
          <span>{isOpen ? 'Hide Matrix' : 'Inspect Evidence Matrix'}</span>
          {isOpen ? <CaretUp size={12} weight="bold" /> : <CaretDown size={12} weight="bold" />}
        </button>
      </div>

      {/* Expandable Evidence Matrix Card */}
      {isOpen && (
        <div className="mt-3 p-3.5 rounded-2xl bg-background/90  border border-border/90  shadow-xs animate-in fade-in duration-200">
          {/* Segmented Tab Navigation */}
          <div className="flex items-center space-x-2 border-b border-border/80  pb-2.5 mb-3">
            {hasCitations && (
              <button
                onClick={() => setActiveTab('docs')}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'docs'
                    ? 'bg-card  text-primary  shadow-xs border border-border/90 '
                    : 'text-muted-foreground hover:text-foreground '
                }`}
              >
                <FileText size={14} weight="duotone" />
                <span>Source Passages ({citations.length})</span>
              </button>
            )}

            {hasKeywords && (
              <button
                onClick={() => setActiveTab('keywords')}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'keywords'
                    ? 'bg-card  text-primary  shadow-xs border border-border/90 '
                    : 'text-muted-foreground hover:text-foreground '
                }`}
              >
                <Tag size={14} weight="duotone" />
                <span>Matched Keywords ({matchedKeywords.length})</span>
              </button>
            )}

            {hasGraph && (
              <button
                onClick={() => setActiveTab('graph')}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'graph'
                    ? 'bg-card  text-primary  shadow-xs border border-border/90 '
                    : 'text-muted-foreground hover:text-foreground '
                }`}
              >
                <Graph size={14} weight="duotone" />
                <span>Knowledge Graph Subgraph ({graphTriples.length})</span>
              </button>
            )}
          </div>

          {/* TAB 1: Source Passages & Documents */}
          {activeTab === 'docs' && hasCitations && (
            <div className="space-y-2.5 max-h-64 overflow-y-auto pr-1">
              {citations.map((cite) => (
                <button
                  type="button"
                  key={cite.citation_number}
                  aria-label={`View evidence passage ${cite.citation_number}: ${cite.filename}`}
                  onClick={() => onSelectCitation(cite)}
                  className="group block w-full text-left p-3 rounded-xl bg-card border border-border/90 hover:border-primary/30 transition-all cursor-pointer shadow-2xs"
                >
                  <span className="flex items-center justify-between mb-1.5">
                    <span className="flex items-center space-x-2">
                      <span className="font-semibold text-xs text-primary  font-mono">
                        #{cite.citation_number}
                      </span>
                      <span className="text-xs font-semibold text-foreground ">
                        {cite.filename}
                      </span>
                      {cite.page_number && (
                        <span className="text-xs text-muted-foreground font-mono bg-muted  px-1.5 py-0.5 rounded">
                          Page {cite.page_number}
                        </span>
                      )}
                    </span>
                    <span className="text-xs font-semibold text-primary  font-mono">
                      Relevance {cite.score.toFixed(3)}
                    </span>
                  </span>

                  <span className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                    "{cite.excerpt}"
                  </span>

                  <span className="mt-2 pt-2 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
                    <span className="flex items-center space-x-1.5">
                      <span>Sources:</span>
                      {cite.sources.map((s) => (
                        <span
                          key={s}
                          className="px-1.5 py-0.5 rounded bg-muted  text-muted-foreground  uppercase font-mono"
                        >
                          {s}
                        </span>
                      ))}
                    </span>
                    {cite.image_path && (
                      <span className="flex items-center space-x-1 text-primary  font-medium">
                        <ImageIcon size={12} weight="duotone" />
                        <span>Clinical Chart Figure</span>
                      </span>
                    )}
                  </span>
                </button>
              ))}
            </div>
          )}

          {/* TAB 2: Matched Clinical Keywords */}
          {activeTab === 'keywords' && hasKeywords && (
            <div>
              <p className="text-xs text-muted-foreground  mb-2.5">
                Exact clinical terms, medical abbreviations, and drug dosages matched via BM25 &
                Knowledge Graph indexing:
              </p>
              <div className="flex flex-wrap gap-2 max-h-60 overflow-y-auto">
                {matchedKeywords.map((kw, idx) => (
                  <div
                    key={idx}
                    className={`flex items-center space-x-2 px-3 py-1.5 rounded-xl border text-xs font-medium shadow-2xs ${getEntityColor(
                      kw.category
                    )}`}
                  >
                    <span className="font-semibold">{kw.term}</span>
                    {kw.category && (
                      <span className="text-xs opacity-75 font-mono">({kw.category})</span>
                    )}
                    {kw.source && (
                      <span className="text-xs px-1.5 py-0.2 rounded-md bg-card  opacity-90 uppercase tracking-tight">
                        {kw.source}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 3: Knowledge Graph Subgraph & Triples */}
          {activeTab === 'graph' && hasGraph && (
            <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
              <p className="text-xs text-muted-foreground  mb-2">
                Multi-hop relational pathways traversed in Neo4j to verify clinical safety and
                causal mechanisms:
              </p>
              {graphTriples.map((triple, idx) => (
                <div
                  key={idx}
                  className="p-2.5 rounded-xl bg-card  border border-border/90  flex items-center justify-between text-xs shadow-2xs gap-2"
                >
                  {/* Source Entity Node */}
                  <div
                    className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border font-semibold ${getEntityColor(
                      triple.source_type
                    )}`}
                  >
                    <Pill size={12} weight="duotone" />
                    <span>{triple.source}</span>
                    {triple.source_type && (
                      <span className="text-xs opacity-75 font-mono">({triple.source_type})</span>
                    )}
                  </div>

                  {/* Relational Predicate Arrow */}
                  <div className="flex items-center space-x-1 shrink-0">
                    <span className="text-muted-foreground  font-mono">──</span>
                    <span
                      className={`px-2 py-0.5 rounded-md font-mono text-xs font-semibold border uppercase ${getRelationBadge(
                        triple.relationship
                      )}`}
                    >
                      [{triple.relationship}]
                    </span>
                    <span className="text-muted-foreground  font-mono">──►</span>
                  </div>

                  {/* Target Entity Node */}
                  <div
                    className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border font-semibold ${getEntityColor(
                      triple.target_type
                    )}`}
                  >
                    <span>{triple.target}</span>
                    {triple.target_type && (
                      <span className="text-xs opacity-75 font-mono">({triple.target_type})</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
