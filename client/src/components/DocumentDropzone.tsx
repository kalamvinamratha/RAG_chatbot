import { useId, useRef, useState } from 'react';
import {
  ArrowsClockwise,
  CircleNotch,
  CaretDown,
  FileText,
  Folders,
  ShieldWarning,
  Trash,
  UploadSimple,
  WarningOctagon,
  X,
} from '@phosphor-icons/react';
import type { DocumentItem } from '../types';

interface DocumentDropzoneProps {
  documents: DocumentItem[];
  selectedDocumentIds: string[];
  onToggleSelectDocument: (docId: string) => void;
  onSelectAllDocuments: (all: boolean) => void;
  onUpload: (file: File) => Promise<void>;
  onDelete: (docId: string) => Promise<void>;
  onRetry: (docId: string) => Promise<void>;
  isUploading: boolean;
  uploadError?: string | null;
  onClearUploadError?: () => void;
}

export function DocumentDropzone({
  documents,
  selectedDocumentIds,
  onToggleSelectDocument,
  onSelectAllDocuments,
  onUpload,
  onDelete,
  onRetry,
  isUploading,
  uploadError,
  onClearUploadError,
}: DocumentDropzoneProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const contentId = useId();
  const available = documents.filter((doc) => doc.status === 'completed');
  const allSelected =
    available.length > 0 && available.every((doc) => selectedDocumentIds.includes(doc.id));

  return (
    <aside className="dossier" aria-label="Clinical documents" data-expanded={expanded}>
      <div className="dossier-header">
        <div className="flex items-center gap-2">
          <Folders size={21} weight="duotone" />
          <h2 className="workspace-title">Your documents</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="ui-badge font-mono">{documents.length}</span>
          <button
            type="button"
            className="ui-button ui-icon-button dossier-toggle"
            aria-label="Toggle documents"
            aria-expanded={expanded}
            aria-controls={contentId}
            onClick={() => setExpanded((value) => !value)}
          >
            <CaretDown size={16} />
          </button>
        </div>
      </div>
      <div className="dossier-content" id={contentId}>
        {uploadError && (
          <div
            role="alert"
            className="mx-4 mt-3 mb-1 p-3.5 rounded-xl border border-destructive/40 bg-destructive/10 text-card-foreground flex items-start gap-2.5 text-xs shadow-sm transition-all animate-in fade-in"
          >
            <ShieldWarning size={20} weight="fill" className="shrink-0 text-destructive mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-destructive text-xs uppercase tracking-wider">
                Upload Rejected
              </p>
              <p className="mt-1 text-xs text-foreground/90 dark:text-foreground/90 leading-relaxed break-words whitespace-pre-wrap">
                {uploadError}
              </p>
            </div>
            {onClearUploadError && (
              <button
                type="button"
                onClick={onClearUploadError}
                className="p-1 -mr-1 -mt-1 text-muted-foreground hover:text-foreground rounded transition-colors"
                aria-label="Dismiss error"
              >
                <X size={14} />
              </button>
            )}
          </div>
        )}

        <input
          ref={fileInputRef}
          aria-label="Choose clinical document"
          type="file"
          accept=".pdf,.docx,.xlsx,.csv,.pptx,.txt,.md"
          className="hidden"
          onChange={async (event) => {
            const file = event.target.files?.[0];
            if (file) await onUpload(file);
            event.target.value = '';
          }}
        />
        <button
          className="upload-zone"
          data-dragging={isDragOver}
          disabled={isUploading}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragOver(true);
          }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={async (event) => {
            event.preventDefault();
            setIsDragOver(false);
            const file = event.dataTransfer.files?.[0];
            if (file && !isUploading) await onUpload(file);
          }}
        >
          {isUploading ? (
            <CircleNotch size={26} className="animate-spin text-primary mx-auto mb-3" />
          ) : (
            <UploadSimple size={26} className="text-primary mx-auto mb-3" />
          )}
          <span className="block text-sm">
            {isUploading ? 'Reading and indexing…' : 'Drop a document here'}
          </span>
          <span className="block ui-label mt-1">
            {isUploading ? 'Extracting passages and connections' : 'or click to browse files'}
          </span>
          <span className="block ui-label mt-3">PDF · DOCX · XLSX · CSV · PPTX · TXT · MD</span>
        </button>
        <div className="flex items-center justify-between px-5 py-4 text-xs text-muted-foreground">
          <span>{selectedDocumentIds.length} selected for this consultation</span>
          {available.length > 0 && (
            <button
              className="text-foreground underline underline-offset-4"
              onClick={() => onSelectAllDocuments(!allSelected)}
            >
              {allSelected ? 'Clear' : 'Select all'}
            </button>
          )}
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto px-4 pb-4 space-y-2">
          {documents.length === 0 ? (
            <div className="empty-dossier">
              <FileText size={30} weight="thin" className="mx-auto mb-3" />
              <p>Your evidence starts here.</p>
              <p className="ui-label mt-2">
                Upload a record or guideline to give your consultation a source to work from.
              </p>
            </div>
          ) : (
            documents.map((doc) => {
              const isFailed = doc.status === 'failed';
              const isGuardrailRejected =
                isFailed &&
                (doc.error_message?.toLowerCase().includes('guardrail') ||
                  doc.error_message?.toLowerCase().includes('detected domain') ||
                  doc.error_message?.toLowerCase().includes('non-healthcare'));

              return (
                <div
                  key={doc.id}
                  className={`document-card ${isFailed ? 'border-destructive/30 bg-destructive/[0.03]' : ''}`}
                  data-selected={selectedDocumentIds.includes(doc.id)}
                >
                  <input
                    type="checkbox"
                    aria-label={'Select ' + doc.filename}
                    checked={selectedDocumentIds.includes(doc.id)}
                    disabled={doc.status !== 'completed' || isUploading}
                    onChange={() => onToggleSelectDocument(doc.id)}
                    className="accent-primary shrink-0"
                  />
                  <FileText
                    size={22}
                    className={`${isFailed ? 'text-destructive' : 'text-primary'} shrink-0`}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate" title={doc.filename}>
                      {doc.filename}
                    </p>
                    {doc.status === 'processing' ? (
                      <p className="ui-label mt-1">
                        <span className="inline-flex items-center gap-1 text-primary">
                          <CircleNotch size={11} className="animate-spin" /> Processing…
                        </span>
                      </p>
                    ) : isFailed ? (
                      <div className="mt-1">
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-destructive bg-destructive/15 px-2 py-0.5 rounded-full">
                          <WarningOctagon size={12} weight="fill" />
                          {isGuardrailRejected ? 'Rejected: Non-Medical' : 'Indexing Failed'}
                        </span>
                        {doc.error_message && (
                          <p
                            className="text-[11px] text-destructive/90 dark:text-destructive/85 mt-1 leading-relaxed line-clamp-3"
                            title={doc.error_message}
                          >
                            {doc.error_message}
                          </p>
                        )}
                      </div>
                    ) : (
                      <p className="ui-label mt-1">
                        <span className="capitalize">{doc.status}</span>
                      </p>
                    )}
                  </div>
                  {doc.status === 'completed' && (
                    <button
                      aria-label={'Reindex ' + doc.filename}
                      title="Reindex document"
                      disabled={isUploading}
                      className="p-1 text-muted-foreground hover:text-foreground"
                      onClick={() => onRetry(doc.id)}
                    >
                      <ArrowsClockwise size={16} />
                    </button>
                  )}
                  {isFailed && !isGuardrailRejected && (
                    <button
                      aria-label={'Retry ' + doc.filename}
                      title="Retry indexing"
                      disabled={isUploading}
                      className="p-1 text-muted-foreground hover:text-foreground"
                      onClick={() => onRetry(doc.id)}
                    >
                      <ArrowsClockwise size={16} />
                    </button>
                  )}
                  <button
                    aria-label={'Delete ' + doc.filename}
                    title={isFailed ? 'Delete rejected document' : 'Remove document'}
                    disabled={isUploading}
                    className="p-1 text-muted-foreground hover:text-destructive"
                    onClick={() => onDelete(doc.id)}
                  >
                    <Trash size={16} />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>
      <div className="dossier-footer px-5 py-4 border-t border-sidebar-border text-xs text-muted-foreground flex items-center gap-2">
        <span className="h-1.5 w-1.5 rounded-full bg-sidebar-primary" /> Private to your workspace
      </div>
    </aside>
  );
}
