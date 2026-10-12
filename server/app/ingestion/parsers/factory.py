from pathlib import Path

from app.ingestion.parsers.base_parser import BaseDocumentParser
from app.ingestion.parsers.docx_parser import DocxDocumentParser
from app.ingestion.parsers.excel_parser import ExcelDocumentParser
from app.ingestion.parsers.pdf_parser import PDFDocumentParser
from app.ingestion.parsers.pptx_parser import PPTXDocumentParser
from app.ingestion.parsers.txt_parser import TXTDocumentParser


def get_parser_for_file(file_path: Path | str) -> BaseDocumentParser:
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        return PDFDocumentParser()
    elif ext == ".docx":
        return DocxDocumentParser()
    elif ext == ".csv":
        from app.ingestion.parsers.csv_parser import CSVDocumentParser

        return CSVDocumentParser()
    elif ext == ".xlsx":
        return ExcelDocumentParser()
    elif ext == ".pptx":
        return PPTXDocumentParser()
    elif ext in [".txt", ".md", ".log"]:
        return TXTDocumentParser()
    else:
        raise ValueError(f"Unsupported file format: {ext}")
