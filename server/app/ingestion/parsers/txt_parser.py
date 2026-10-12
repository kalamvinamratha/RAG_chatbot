from pathlib import Path

from app.ingestion.models import ParsedDocument, ParsedPage
from app.ingestion.parsers.base_parser import BaseDocumentParser


class TXTDocumentParser(BaseDocumentParser):
    def parse(self, file_path: Path | str) -> ParsedDocument:
        path = Path(file_path)
        with open(path, encoding="utf-8", errors="replace") as f:
            content = f.read()

        pages = [
            ParsedPage(
                page_number=1,
                text=content.strip(),
            )
        ]

        return ParsedDocument(
            filename=path.name,
            file_type="txt",
            total_pages=1,
            pages=pages,
            metadata={"file_size": path.stat().st_size},
        )
