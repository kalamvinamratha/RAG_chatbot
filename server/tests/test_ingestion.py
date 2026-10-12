from pathlib import Path

import pytest

from app.ingestion.chunkers.semantic_chunker import MedicalSemanticChunker
from app.ingestion.entity_extractor import MedicalEntityExtractor
from app.ingestion.models import ParsedDocument, ParsedPage
from app.ingestion.multimodal_processor import MultimodalImageProcessor
from app.ingestion.parsers.factory import get_parser_for_file
from app.ingestion.parsers.pdf_parser import PDFDocumentParser
from app.ingestion.parsers.txt_parser import TXTDocumentParser


def test_parser_factory_resolution():
    assert isinstance(get_parser_for_file("sample.pdf"), PDFDocumentParser)
    assert isinstance(get_parser_for_file("sample.txt"), TXTDocumentParser)
    assert isinstance(get_parser_for_file("sample.docx").__class__.__name__, str)
    assert isinstance(get_parser_for_file("sample.xlsx").__class__.__name__, str)
    assert isinstance(get_parser_for_file("sample.pptx").__class__.__name__, str)


def test_pdf_parsing_on_actual_scope_document():
    # Test on the real workspace PDF file
    pdf_path = (
        Path(__file__).resolve().parent.parent.parent
        / "docs"
        / "Healthcare_AI_Hybrid_Graph_RAG_Scope (1).pdf"
    )
    assert pdf_path.exists(), "Scope PDF must exist in workspace root"

    parser = PDFDocumentParser(extract_images=False)
    parsed = parser.parse(pdf_path)

    assert parsed.total_pages == 2
    assert "HEALTHCARE AI" in parsed.pages[0].text
    assert "FastAPI" in parsed.pages[1].text or "Backend" in parsed.pages[1].text


def test_semantic_chunker():
    sample_text = (
        "CHIEF COMPLAINT: Patient presents with progressive chest pain and palpitations.\n\n"
        "HISTORY OF PRESENT ILLNESS:\n"
        "The patient is a 58-year-old male with a history of hypertension and atrial fibrillation. "
        "He reports episodes of acute shortness of breath over the past three days.\n\n"
        "MEDICATIONS:\n"
        "Currently prescribed Metoprolol 50mg twice daily and Apixaban 5mg twice daily.\n\n"
        "ASSESSMENT & PLAN:\n"
        "Suspected non-ST elevation myocardial infarction or decompensated heart failure. "
        "Order STAT Troponin I, 12-lead ECG, and echocardiogram."
    )
    parsed_doc = ParsedDocument(
        filename="cardiology_note.txt",
        file_type="txt",
        total_pages=1,
        pages=[ParsedPage(page_number=1, text=sample_text, tables=[])],
    )

    chunker = MedicalSemanticChunker(chunk_size=500, chunk_overlap=100)
    chunks = chunker.chunk_document(parsed_doc)

    assert len(chunks) >= 1
    assert any("Metoprolol" in c.content for c in chunks)
    assert any("Troponin" in c.content for c in chunks)


@pytest.mark.asyncio
async def test_medical_entity_extraction():
    extractor = MedicalEntityExtractor()
    clinical_passage = (
        "Patient has a confirmed diagnosis of atrial fibrillation and hypertension. "
        "Started on Metoprolol 25mg for ventricular rate control. "
        "Ordered STAT Troponin and ECG to rule out myocardial infarction."
    )

    result = await extractor.extract_from_chunk(clinical_passage)
    entity_names = [e.name.lower() for e in result.entities]

    assert "atrial fibrillation" in entity_names
    assert "hypertension" in entity_names
    assert "metoprolol" in entity_names
    assert "troponin" in entity_names or "ecg" in entity_names

    # Co-occurrence alone is not evidence of a clinical relationship.
    assert result.relationships == []


@pytest.mark.asyncio
async def test_multimodal_image_processor(tmp_path):
    processor = MultimodalImageProcessor()
    dummy_img = tmp_path / "sample_ecg_chart.png"
    dummy_img.write_bytes(b"\x89PNG\r\n\x1a\nfake-image-bytes")

    chunk = await processor.process_image(
        image_path=str(dummy_img),
        page_number=3,
        document_filename="cardiology_report.pdf",
        chunk_index=5,
    )

    assert chunk.metadata["is_multimodal"] is True
    assert chunk.page_number == 3
    assert chunk.metadata["image_path"] == str(dummy_img)
    assert chunk.chunk_type == "visual_summary"
    assert len(chunk.content) > 0
    assert "sample_ecg_chart.png" in chunk.content or "cardiology_report.pdf" in chunk.content


@pytest.mark.asyncio
async def test_domain_guardrail_rejects_financial_presentation():
    from app.rag.guardrails import DomainGuardrail

    guardrail = DomainGuardrail()
    # Explicitly clear API keys to test rigorous heuristic boundary
    guardrail.openai_api_key = None
    guardrail.groq_api_key = None
    guardrail.gemini_api_key = None

    financial_ppt = ParsedDocument(
        filename="Q3_Financial_Performance_Deck.pptx",
        file_type="pptx",
        total_pages=2,
        pages=[
            ParsedPage(
                page_number=1,
                text="Q3 Investor Presentation: Financial Performance Overview. Total revenue of $50M, EBITDA margin 22%.",
                tables=[],
            ),
            ParsedPage(
                page_number=2,
                text="Balance sheet and cash flow statement: Quarterly earnings, dividends declared to shareholders.",
                tables=[],
            ),
        ],
    )

    is_valid, reason = await guardrail.validate_document_domain(financial_ppt)
    assert is_valid is False
    assert (
        "financial" in reason.lower()
        or "corporate" in reason.lower()
        or "rejected" in reason.lower()
    )


@pytest.mark.asyncio
async def test_domain_guardrail_accepts_clinical_document():
    from app.rag.guardrails import DomainGuardrail

    guardrail = DomainGuardrail()
    clinical_doc = ParsedDocument(
        filename="cardiology_discharge_summary.pdf",
        file_type="pdf",
        total_pages=1,
        pages=[
            ParsedPage(
                page_number=1,
                text=(
                    "Discharge Summary: Patient admitted with acute myocardial infarction. "
                    "Clinical symptoms included severe substernal chest pain. "
                    "Prescribed Metoprolol and Aspirin. Follow-up with cardiology clinic."
                ),
                tables=[],
            )
        ],
    )

    is_valid, reason = await guardrail.validate_document_domain(clinical_doc)
    assert is_valid is True
    assert (
        "healthcare" in reason.lower()
        or "verified" in reason.lower()
        or "accepted" in reason.lower()
    )


def test_domain_guardrail_query_checks():
    from app.rag.guardrails import domain_guardrail

    # Financial / corporate business query should be rejected
    is_valid_fin, refusal = domain_guardrail.check_query_domain(
        "Summarize the presentation and tell me the Q3 revenue and EBITDA"
    )
    assert is_valid_fin is False
    assert "Helios" in refusal
    assert "financial" in refusal.lower()

    # Clinical query should be accepted
    is_valid_med, _ = domain_guardrail.check_query_domain(
        "What are the clinical contraindications of Metoprolol in heart failure?"
    )
    assert is_valid_med is True
