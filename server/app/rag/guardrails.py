import json
import logging
import re
from typing import Any

import httpx

from app.config import get_settings
from app.ingestion.models import ParsedDocument

logger = logging.getLogger(__name__)
settings = get_settings()


class DomainGuardrailException(ValueError):
    """Raised when an uploaded document or user query violates domain boundaries."""

    pass


# High-confidence non-medical keywords that indicate off-topic domains (financial, crypto, real estate, etc.)
OFF_TOPIC_FINANCIAL_KEYWORDS = {
    "ebitda",
    "revenue",
    "revenues",
    "financials",
    "financial performance",
    "financial statement",
    "financial statements",
    "financial report",
    "financial overview",
    "profit and loss",
    "balance sheet",
    "cash flow",
    "cash flow statement",
    "gross margin",
    "operating margin",
    "net margin",
    "net income",
    "net profit",
    "gross profit",
    "operating profit",
    "operating expenses",
    "opex",
    "capex",
    "dividend",
    "dividends",
    "shareholder",
    "shareholders",
    "stockholder",
    "quarterly earnings",
    "quarterly results",
    "fiscal quarter",
    "fiscal year",
    "fy24",
    "fy25",
    "fy26",
    "q1 earnings",
    "q2 earnings",
    "q3 earnings",
    "q4 earnings",
    "q1 results",
    "q2 results",
    "q3 results",
    "q4 results",
    "earnings call",
    "earnings per share",
    "eps",
    "stock market",
    "nasdaq",
    "nyse",
    "portfolio management",
    "asset management",
    "hedge fund",
    "private equity",
    "venture capital",
    "cryptocurrency",
    "bitcoin",
    "ethereum",
    "tokenomics",
    "blockchain",
    "real estate",
    "mortgage",
    "reit",
    "tax return",
    "capital gains",
    "roi",
    "return on investment",
    "market cap",
    "valuation",
    "seed round",
    "series a",
    "series b",
    "series c",
    "pitch deck",
    "investor deck",
    "investor presentation",
    "investor relations",
    "unit economics",
    "arr",
    "mrr",
    "cagr",
}

# Broad clinical and biomedical signals
HEALTHCARE_KEYWORDS = {
    "patient",
    "clinical",
    "diagnosis",
    "diagnostic",
    "symptom",
    "symptoms",
    "syndrome",
    "disease",
    "disorder",
    "treatment",
    "therapy",
    "therapeutic",
    "medication",
    "prescription",
    "dosage",
    "dose",
    "pharmacology",
    "drug",
    "hospital",
    "clinic",
    "physician",
    "doctor",
    "nurse",
    "cardiology",
    "neurology",
    "oncology",
    "pediatric",
    "gynaecology",
    "gynecology",
    "surgery",
    "surgical",
    "pathology",
    "laboratory",
    "lab test",
    "biomarker",
    "vital signs",
    "blood pressure",
    "heart rate",
    "ecg",
    "ekg",
    "mri",
    "ct scan",
    "ultrasound",
    "infection",
    "infectious",
    "vaccine",
    "vaccination",
    "biomedical",
    "health",
    "medical",
    "medicine",
    "healthcare",
    "prognosis",
    "contraindication",
    "contraindicated",
    "adverse effect",
    "side effect",
    "triage",
    "intensive care",
    "icu",
    "outpatient",
    "inpatient",
}


class DomainGuardrail:
    """Multi-tiered guardrail engine that prevents non-healthcare documents from being ingested

    and rejects non-healthcare user queries in chat.
    """

    def __init__(self) -> None:
        self.openai_api_key = settings.OPENAI_API_KEY
        self.openai_model_name = settings.OPENAI_MODEL_NAME
        self.groq_api_key = settings.GROQ_API_KEY
        self.groq_model_name = settings.GROQ_MODEL_NAME
        self.gemini_api_key = settings.GEMINI_API_KEY

    def _extract_text_sample(self, parsed_doc: ParsedDocument, max_chars: int = 4000) -> str:
        """Extracts a representative text sample from across document pages/slides."""
        sample_parts: list[str] = []
        for page in parsed_doc.pages:
            if page.text.strip():
                sample_parts.append(page.text.strip())
            if sum(len(p) for p in sample_parts) >= max_chars:
                break
        combined = "\n\n".join(sample_parts)
        return combined[:max_chars]

    async def validate_document_domain(self, parsed_doc: ParsedDocument) -> tuple[bool, str]:
        """Validates that an uploaded document belongs to the healthcare/medical domain.

        Returns (is_valid: bool, reason: str).
        """
        text_sample = self._extract_text_sample(parsed_doc)
        if not text_sample.strip():
            # Multimodal or empty document without text
            if any(len(p.image_paths) > 0 for p in parsed_doc.pages):
                return True, "Visual document accepted for clinical image processing."
            return False, "Document contains no extractable text or content."

        text_lower = text_sample.lower()
        filename_lower = (parsed_doc.filename or "").lower()

        # Heuristic count
        health_matches = sum(
            1 for kw in HEALTHCARE_KEYWORDS if re.search(r"\b" + re.escape(kw) + r"\b", text_lower)
        )
        off_topic_matches = sum(
            1
            for kw in OFF_TOPIC_FINANCIAL_KEYWORDS
            if re.search(r"\b" + re.escape(kw) + r"\b", text_lower)
        )

        # Clear non-healthcare financial document detected
        if (off_topic_matches >= 2 and health_matches == 0) or (
            off_topic_matches >= 1
            and health_matches == 0
            and any(
                fk in filename_lower
                for fk in [
                    "financial",
                    "finance",
                    "earnings",
                    "pitch",
                    "deck",
                    "balance",
                    "revenue",
                    "q1",
                    "q2",
                    "q3",
                    "q4",
                    "investor",
                ]
            )
        ):
            logger.warning(
                "Document %s rejected by heuristic guardrail: %d financial keywords, 0 medical keywords",
                parsed_doc.filename,
                off_topic_matches,
            )
            return (
                False,
                f"Document '{parsed_doc.filename}' appears to be a financial, investment, or corporate business presentation, "
                "not a healthcare or clinical medical file. Only healthcare and medical documents are permitted.",
            )

        # If LLM is available, perform high-precision domain classification
        if self.openai_api_key or self.groq_api_key or self.gemini_api_key:
            llm_result = await self._classify_document_domain_llm(parsed_doc.filename, text_sample)
            if llm_result is not None:
                return llm_result

        # Fallback to heuristic
        if health_matches >= 1:
            return True, "Healthcare domain verified."
        if off_topic_matches > 0:
            return (
                False,
                f"Document '{parsed_doc.filename}' does not contain recognized healthcare content.",
            )

        # Neutral content without any medical keywords
        if health_matches == 0 and len(text_sample) > 80:
            return (
                False,
                f"Document '{parsed_doc.filename}' could not be verified as a healthcare or clinical document. "
                "Helios exclusively ingests clinical records, medical research, pharmaceutical, or hospital documentation.",
            )

        return True, "Document accepted."

    async def _classify_document_domain_llm(
        self, filename: str, sample_text: str
    ) -> tuple[bool, str] | None:
        """Calls fast LLM to verify whether document content is clinical/healthcare."""
        prompt = (
            "You are a strict domain validation guardrail for a specialized Healthcare and Clinical AI platform (Helios).\n"
            "Your job is to determine whether the uploaded document belongs to the healthcare, medicine, clinical care, "
            "pharmacology, patient health, medical biology, or healthcare operations domain.\n\n"
            "STRICT REJECTION RULES:\n"
            "- Reject any document primarily about corporate finance, financial statements, balance sheets, revenues, "
            "investments, stock markets, venture capital, pitch decks, cryptocurrency, real estate, or general business accounting.\n"
            "- Reject general business, sales, or marketing presentations unrelated to medicine.\n"
            "- Accept clinical notes, pathology reports, guideline documents, medical research, drug monographs, patient summaries, "
            "and hospital operations.\n\n"
            f"Filename: {filename}\n"
            f"Document excerpt:\n{sample_text[:2500]}\n\n"
            "Respond in JSON format with keys:\n"
            "- 'is_healthcare': boolean (true if healthcare/clinical, false if non-healthcare like financial, crypto, pitch deck, etc.)\n"
            "- 'detected_domain': string (e.g., 'Finance', 'Corporate Earnings', 'Healthcare / Clinical', 'Real Estate')\n"
            "- 'reason': string (brief explanation of the verdict)\n"
        )

        async def _call_provider(url: str, key: str, model: str) -> dict[str, Any] | None:
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.post(
                        url,
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.0,
                            "response_format": {"type": "json_object"},
                        },
                    )
                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"].get("content", "")
                        return json.loads(content)
            except Exception as e:
                logger.debug("Guardrail LLM check failed on %s: %s", model, e)
            return None

        # Try OpenAI
        data = None
        if self.openai_api_key:
            data = await _call_provider(
                "https://api.openai.com/v1/chat/completions",
                self.openai_api_key,
                self.openai_model_name,
            )

        # Fallback to Groq
        if data is None and self.groq_api_key:
            data = await _call_provider(
                "https://api.groq.com/openai/v1/chat/completions",
                self.groq_api_key,
                self.groq_model_name,
            )

        # Fallback to Gemini
        if data is None and self.gemini_api_key:
            try:
                from google import genai

                client = genai.Client(api_key=self.gemini_api_key)
                response = await client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )
                text = response.text or ""
                clean_json = re.sub(
                    r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE
                ).strip()
                data = json.loads(clean_json)
            except Exception as e:
                logger.debug("Guardrail Gemini check note: %s", e)

        if data and "is_healthcare" in data:
            is_health = bool(data["is_healthcare"])
            domain = data.get("detected_domain", "Unknown")
            reason = data.get("reason", "")
            if not is_health:
                logger.warning(
                    "Document '%s' REJECTED by domain guardrail. Detected domain: %s. Reason: %s",
                    filename,
                    domain,
                    reason,
                )
                return (
                    False,
                    f"Document '{filename}' was rejected by the domain guardrail: detected domain is '{domain}'. "
                    f"Only healthcare, biomedical, and clinical documents are allowed on this platform. ({reason})",
                )
            return True, f"Healthcare domain verified ({domain})."

        return None

    def check_query_domain(self, query: str) -> tuple[bool, str]:
        """Checks if a user chat query asks for out-of-scope non-healthcare tasks.

        Returns (is_valid: bool, refusal_message: str).
        """
        clean_query = query.lower().strip()
        words = set(re.findall(r"\b\w+\b", clean_query))

        financial_words = {
            "ebitda",
            "dividend",
            "dividends",
            "cryptocurrency",
            "bitcoin",
            "ethereum",
            "stock",
            "stocks",
            "nasdaq",
            "forex",
            "financial",
            "finance",
            "revenue",
            "revenues",
            "profit",
            "profits",
            "accounting",
            "earnings",
            "investment",
            "investments",
            "valuation",
            "shareholder",
            "shareholders",
        }

        # Check for explicit financial/business queries without medical context
        has_financial_signal = any(kw in clean_query for kw in OFF_TOPIC_FINANCIAL_KEYWORDS) or any(
            w in words for w in financial_words
        )

        has_medical_signal = any(kw in clean_query for kw in HEALTHCARE_KEYWORDS) or any(
            w in words
            for w in {
                "health",
                "medical",
                "doctor",
                "patient",
                "disease",
                "drug",
                "pain",
                "heart",
                "brain",
                "clinical",
                "surgery",
                "medicine",
            }
        )

        # If exclusively financial / investment request
        if has_financial_signal and not has_medical_signal:
            return (
                False,
                "I am **Helios**, a clinical AI consultation assistant specialized strictly in healthcare, "
                "medicine, and clinical decision support.\n\n"
                "I cannot provide financial analysis, investment evaluations, corporate earnings summaries, or "
                "accounting guidance. Please consult a qualified financial advisor for financial matters, or "
                "ask a health-related question regarding patient care, clinical guidelines, or medical literature.",
            )

        return True, ""


domain_guardrail = DomainGuardrail()
