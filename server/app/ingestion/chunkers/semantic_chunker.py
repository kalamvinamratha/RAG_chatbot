from app.ingestion.models import ExtractedChunk, ParsedDocument


class MedicalSemanticChunker:
    def __init__(self, chunk_size: int = 1500, chunk_overlap: int = 250) -> None:
        if chunk_size <= 0 or not 0 <= chunk_overlap < chunk_size:
            raise ValueError("Require 0 <= overlap < chunk size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _windows(self, text: str, size: int | None = None, overlap: int | None = None):
        size = size or self.chunk_size
        overlap = self.chunk_overlap if overlap is None else overlap
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                # Prefer paragraph/line/word boundaries, with a hard fallback for long tokens.
                floor = start + size // 2
                boundary = max(text.rfind("\n", floor, end), text.rfind(" ", floor, end))
                if boundary > floor:
                    end = boundary
            piece = text[start:end].strip()
            if piece:
                yield piece
            if end == len(text):
                break
            start = max(start + 1, end - overlap)

    def _table_windows(self, table: str):
        lines = table.strip().splitlines()
        separator = next((i for i, line in enumerate(lines) if "---" in line and "|" in line), None)
        if separator is None:
            yield from self._windows(table)
            return
        header = "\n".join(lines[: separator + 1])
        if len(header) >= self.chunk_size // 2:
            yield from self._windows(table)
            return
        buffer = header
        for row in lines[separator + 1 :]:
            for part in self._windows(row, self.chunk_size - len(header) - 1, 0):
                if len(buffer) + len(part) + 1 > self.chunk_size:
                    yield buffer
                    buffer = header
                buffer += "\n" + part
        if buffer:
            yield buffer

    def chunk_document(self, parsed_doc: ParsedDocument) -> list[ExtractedChunk]:
        chunks = []
        for page in parsed_doc.pages:
            sections = [
                (self._table_windows(table), "table") for table in page.tables if table.strip()
            ]
            if page.text.strip():
                sections.append((self._windows(page.text.strip()), "text"))
            for pieces, kind in sections:
                for content in pieces:
                    chunks.append(
                        ExtractedChunk(
                            chunk_index=len(chunks),
                            content=content,
                            page_number=page.page_number,
                            chunk_type=kind,
                            metadata={
                                "filename": parsed_doc.filename,
                                "file_type": parsed_doc.file_type,
                                "page_number": page.page_number,
                            },
                        )
                    )
        return chunks
