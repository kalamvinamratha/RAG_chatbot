import logging
from pathlib import Path

import fitz  # PyMuPDF

from app.config import get_settings
from app.ingestion.models import ParsedDocument, ParsedPage
from app.ingestion.parsers.base_parser import BaseDocumentParser

logger = logging.getLogger(__name__)


class PDFDocumentParser(BaseDocumentParser):
    def __init__(self, extract_images: bool = True, output_dir: Path | None = None) -> None:
        self.extract_images = extract_images
        self.output_dir = output_dir or get_settings().UPLOAD_DIR / "extracted_images"
        if self.extract_images:
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def parse(self, file_path: Path | str) -> ParsedDocument:
        path = Path(file_path)
        doc = fitz.open(str(path))
        pages: list[ParsedPage] = []

        try:
            for page_index in range(len(doc)):
                page = doc[page_index]
                page_number = page_index + 1
                text = page.get_text("text")

                image_paths: list[str] = []
                if self.extract_images:
                    image_list = page.get_images(full=True)
                    for img_index, img_meta in enumerate(image_list):
                        xref = img_meta[0]
                        try:
                            base_image = doc.extract_image(xref)
                            image_bytes = base_image["image"]
                            image_ext = base_image["ext"]
                            image_name = f"{path.stem}_p{page_number}_img{img_index}.{image_ext}"
                            image_save_path = self.output_dir / image_name
                            with open(image_save_path, "wb") as f:
                                f.write(image_bytes)
                            image_paths.append(str(image_save_path))
                        except Exception as img_err:
                            logger.debug("Skipping unextractable image in PDF: %s", img_err)

                # Table extraction
                tables: list[str] = []
                try:
                    tabs = page.find_tables()
                    for t in tabs:
                        df = t.extract()
                        if df:
                            # Convert 2D list into Markdown table
                            headers = [str(col or "") for col in df[0]]
                            rows = [[str(cell or "") for cell in row] for row in df[1:]]
                            md_table = (
                                "| "
                                + " | ".join(headers)
                                + " |\n| "
                                + " | ".join(["---"] * len(headers))
                                + " |\n"
                            )
                            for r in rows:
                                md_table += "| " + " | ".join(r) + " |\n"
                            tables.append(md_table)
                except Exception as t_err:
                    logger.debug("PyMuPDF find_tables note: %s", t_err)

                pages.append(
                    ParsedPage(
                        page_number=page_number,
                        text=text.strip(),
                        tables=tables,
                        image_paths=image_paths,
                    )
                )

            return ParsedDocument(
                filename=path.name,
                file_type="pdf",
                total_pages=len(doc),
                pages=pages,
                metadata={"file_size": path.stat().st_size},
            )
        finally:
            doc.close()
