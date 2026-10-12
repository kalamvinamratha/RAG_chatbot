import csv
from pathlib import Path

from app.ingestion.models import ParsedDocument, ParsedPage
from app.ingestion.parsers.base_parser import BaseDocumentParser


class CSVDocumentParser(BaseDocumentParser):
    def parse(self, file_path: Path | str) -> ParsedDocument:
        path = Path(file_path)
        with path.open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.reader(file))
        rows = [row for row in rows if any(cell.strip() for cell in row)]
        if not rows:
            return ParsedDocument(path.name, "csv", 0, [])

        def markdown(row):
            return "| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in row) + " |"

        table = "\n".join(
            [markdown(rows[0]), markdown(["---"] * len(rows[0])), *map(markdown, rows[1:])]
        )
        return ParsedDocument(path.name, "csv", 1, [ParsedPage(1, "", [table])])
