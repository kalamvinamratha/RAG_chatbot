import { Files, Graph, SquaresFour } from '@phosphor-icons/react';

interface DeskDockProps {
  documentsOpen: boolean;
  documentCount: number;
  onDocuments: () => void;
  onEvidence: () => void;
  onChangeCompanion: () => void;
}

export function DeskDock({
  documentsOpen,
  documentCount,
  onDocuments,
  onEvidence,
  onChangeCompanion,
}: DeskDockProps) {
  return (
    <nav className="desk-dock" aria-label="Companion desk tools">
      <button
        type="button"
        aria-label="Documents"
        aria-expanded={documentsOpen}
        aria-controls="desk-documents"
        onClick={onDocuments}
      >
        <Files size={19} />
        <span>Documents</span>
        <span className="dock-count">{documentCount}</span>
      </button>
      <span className="dock-divider" aria-hidden="true" />
      <button type="button" aria-label="Evidence" onClick={onEvidence}>
        <Graph size={19} />
        <span>Evidence</span>
      </button>
      <span className="dock-divider" aria-hidden="true" />
      <button type="button" aria-label="Change companion" onClick={onChangeCompanion}>
        <SquaresFour size={19} />
        <span>Companions</span>
      </button>
    </nav>
  );
}
