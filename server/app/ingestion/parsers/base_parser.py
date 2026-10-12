from abc import ABC, abstractmethod
from pathlib import Path

from app.ingestion.models import ParsedDocument


class BaseDocumentParser(ABC):
    @abstractmethod
    def parse(self, file_path: Path | str) -> ParsedDocument:
        """Parse document into a standardized ParsedDocument structure."""
        pass
