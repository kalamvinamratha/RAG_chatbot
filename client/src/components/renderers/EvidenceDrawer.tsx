import React, { useRef, useState } from 'react';
import { ArrowsOut, BookOpen, CheckCircle, Image as ImageIcon, X } from '@phosphor-icons/react';
import type { CitationItem } from '../../types';
import { useDialogFocus } from '../../hooks/useDialogFocus';

interface EvidenceDrawerProps {
  citation: CitationItem | null;
  onClose: () => void;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({ citation, onClose }) => {
  const [isLightboxOpen, setIsLightboxOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);
  const lightboxRef = useRef<HTMLDivElement>(null);
  useDialogFocus(drawerRef, !!citation && !isLightboxOpen, onClose);
  useDialogFocus(lightboxRef, !!citation && isLightboxOpen, () => setIsLightboxOpen(false));

  if (!citation) return null;

  const imageUrl = citation.image_path
    ? `/api/v1/documents/${citation.document_id}/assets/${encodeURIComponent(citation.image_path.split('\\').pop()?.split('/').pop() || '')}`
    : null;

  return (
    <>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Citation evidence"
        ref={drawerRef}
        tabIndex={-1}
        className="evidence-drawer fixed inset-y-0 right-0 w-96 max-w-full bg-card border-l border-border/90 shadow-2xl z-50 flex flex-col"
      >
        {/* Header */}
        <div className="p-4 border-b border-border/80  flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <BookOpen size={18} weight="duotone" className="text-primary " />
            <h3 className="workspace-title">Citation Evidence #{citation.citation_number}</h3>
          </div>
          <button
            onClick={onClose}
            aria-label="Close citation evidence"
            data-dialog-close
            className="text-muted-foreground hover:text-foreground  p-1 rounded-lg hover:bg-muted  transition-colors cursor-pointer"
          >
            <X size={16} weight="bold" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 p-5 overflow-y-auto space-y-4">
          {/* Document Metadata Card */}
          <div className="p-3.5 rounded-xl bg-background  border border-border/90 ">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold text-foreground  break-words">
                  {citation.filename}
                </p>
                {citation.page_number && (
                  <p className="text-xs text-primary  font-mono mt-0.5">
                    Page {citation.page_number}
                  </p>
                )}
              </div>
              <span className="text-xs px-2 py-0.5 rounded-full bg-secondary/40  text-primary  font-semibold border border-primary/30 ">
                Relevance {citation.score.toFixed(3)}
              </span>
            </div>

            <div className="flex items-center space-x-2 mt-3 pt-2.5 border-t border-border/80 ">
              <span className="text-xs text-muted-foreground  uppercase font-semibold tracking-wider">
                Retrieval Fusion:
              </span>
              <div className="flex items-center space-x-1.5">
                {citation.sources.map((s) => (
                  <span
                    key={s}
                    className="text-xs px-2 py-0.5 rounded-md bg-card  text-muted-foreground  border border-border/80  uppercase font-mono font-medium"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Excerpt */}
          <div>
            <label className="text-xs font-semibold text-muted-foreground  uppercase tracking-wider block mb-1.5">
              Verified Grounded Excerpt:
            </label>
            <div className="p-3.5 rounded-xl bg-background  border border-border/90  text-xs text-foreground  leading-relaxed font-sans shadow-xs">
              "{citation.excerpt}"
            </div>
          </div>

          {/* Multimodal Image Preview */}
          {imageUrl && (
            <div>
              <label className="text-xs font-semibold text-muted-foreground  uppercase tracking-wider flex items-center justify-between mb-1.5">
                <span className="flex items-center space-x-1.5">
                  <ImageIcon size={14} weight="duotone" className="text-primary " />
                  <span>Clinical Figure / Chart:</span>
                </span>
                <span className="text-xs text-primary  font-semibold cursor-pointer">
                  Click to Enlarge
                </span>
              </label>
              <button
                type="button"
                aria-label="Enlarge clinical figure"
                onClick={() => setIsLightboxOpen(true)}
                className="group relative p-2 rounded-xl bg-muted  border border-border  overflow-hidden cursor-pointer hover:border-primary/30 transition-all shadow-xs"
              >
                <img
                  src={imageUrl}
                  alt="Medical Chart Excerpt"
                  className="w-full h-auto rounded-lg object-contain bg-card  transition-transform duration-200 group-hover:scale-[1.02]"
                  onError={(e) => {
                    (e.target as HTMLElement).style.display = 'none';
                  }}
                />
                <div className="absolute inset-0 bg-card/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity rounded-xl">
                  <div className="flex items-center space-x-1.5 bg-card  text-primary  text-xs font-semibold px-3 py-1.5 rounded-lg border border-primary/30 shadow-lg">
                    <ArrowsOut size={14} weight="bold" />
                    <span>Expand Full Resolution</span>
                  </div>
                </div>
              </button>
            </div>
          )}

          {/* Clinical Reliability Notice */}
          <div className="p-3 rounded-xl bg-secondary/40  border border-primary/30  text-xs text-primary  flex items-start space-x-2">
            <CheckCircle size={16} weight="duotone" className="text-primary  shrink-0 mt-0.5" />
            <p>
              Retrieved source evidence. Relevance scores measure retrieval ranking, not clinical
              accuracy. Verify conclusions against the original record.
            </p>
          </div>
        </div>
      </div>

      {/* High-Resolution Medical Image Lightbox Modal */}
      {isLightboxOpen && imageUrl && (
        <div
          ref={lightboxRef}
          role="dialog"
          aria-modal="true"
          aria-label="Clinical figure preview"
          tabIndex={-1}
          className="dialog-overlay fixed inset-0 z-50 bg-background/80 backdrop-blur-md flex items-center justify-center p-4"
          onClick={() => setIsLightboxOpen(false)}
        >
          <div
            className="relative max-w-4xl w-full max-h-[90vh] bg-card  border border-border  rounded-2xl shadow-2xl p-6 flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between pb-4 border-b border-border ">
              <div className="flex items-center space-x-2.5">
                <ImageIcon size={20} weight="duotone" className="text-primary " />
                <h4 className="text-sm font-semibold text-foreground ">
                  Clinical Asset Preview: {citation.filename}{' '}
                  {citation.page_number ? `(Page ${citation.page_number})` : ''}
                </h4>
              </div>
              <button
                aria-label="Close figure preview"
                data-dialog-close
                onClick={() => setIsLightboxOpen(false)}
                className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground  hover:bg-muted  transition-colors cursor-pointer"
              >
                <X size={18} weight="bold" />
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4 flex items-center justify-center">
              <img
                src={imageUrl}
                alt="Enlarged Medical Diagram"
                className="max-h-[70vh] w-auto rounded-lg object-contain shadow-md"
              />
            </div>
            <div className="pt-3 border-t border-border  flex items-center justify-between text-xs text-muted-foreground ">
              <span>Multimodal Vision AI Extracted Asset</span>
              <button
                onClick={() => setIsLightboxOpen(false)}
                className="px-4 py-1.5 rounded-lg bg-primary hover:bg-primary text-primary-foreground font-medium transition-colors cursor-pointer shadow-xs"
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
