import json
import logging
import re
from typing import Any

from app.config import get_settings
from app.ingestion.models import ExtractedEntity, ExtractedRelationship, ExtractionResult

logger = logging.getLogger(__name__)
settings = get_settings()

COMMON_MEDICAL_KEYWORDS = {
    "Disease": [
        "hypertension",
        "arrhythmia",
        "atrial fibrillation",
        "heart failure",
        "coronary artery disease",
        "myocardial infarction",
        "endometriosis",
        "pcos",
        "polycystic ovary syndrome",
        "preeclampsia",
        "stroke",
        "ischemic stroke",
        "neuropathy",
        "multiple sclerosis",
        "epilepsy",
        "diabetes mellitus",
        "chronic kidney disease",
        "hyperlipidemia",
        "asthma",
    ],
    "Symptom": [
        "chest pain",
        "shortness of breath",
        "dyspnea",
        "palpitations",
        "syncope",
        "pelvic pain",
        "amenorrhea",
        "dysmenorrhea",
        "headache",
        "dizziness",
        "focal weakness",
        "numbness",
        "seizure",
        "fatigue",
        "edema",
        "nausea",
    ],
    "Medication": [
        "metoprolol",
        "lisinopril",
        "amiodarone",
        "apixaban",
        "warfarin",
        "aspirin",
        "atorvastatin",
        "metformin",
        "levothyroxine",
        "progesterone",
        "estrogen",
        "gabapentin",
        "levetiracetam",
        "alteplase",
        "tissue plasminogen activator",
        "ibuprofen",
    ],
    "Treatment": [
        "percutaneous coronary intervention",
        "catheter ablation",
        "laparoscopy",
        "thrombolysis",
        "mechanical thrombectomy",
        "dialysis",
        "lifestyle modification",
    ],
    "LabTest": [
        "troponin",
        "troponin i",
        "bnp",
        "brain natriuretic peptide",
        "ecg",
        "electrocardiogram",
        "hba1c",
        "serum creatinine",
        "egfr",
        "ca-125",
        "lipid panel",
        "complete blood count",
    ],
}


class MedicalEntityExtractor:
    def __init__(self) -> None:
        self.openai_api_key = settings.OPENAI_API_KEY
        self.openai_model_name = settings.OPENAI_MODEL_NAME
        self.groq_api_key = settings.GROQ_API_KEY
        self.groq_model_name = settings.GROQ_MODEL_NAME
        self.api_key = settings.GEMINI_API_KEY

    async def extract_from_chunk(self, chunk_text: str) -> ExtractionResult:
        """Extract medical entities and relationships from clinical text using LLM or clinical lexicon."""
        if not chunk_text.strip():
            return ExtractionResult()

        prompt = (
            "Extract clinical entities and relationships from this medical passage into JSON format.\n"
            "Allowed Entity Types: Disease, Symptom, Medication, Treatment, LabTest.\n"
            "Allowed Relationship Types: TREATS, CAUSES, CONTRAINDICATES, INDICATES, DIAGNOSED_BY.\n\n"
            "Output STRICT JSON format with keys 'entities' (list of {name, type}) and "
            "'relationships' (list of {source, target, type}). No markdown fences.\n\n"
            f"Passage:\n{chunk_text[:2000]}"
        )

        def _parse_extraction_payload(text_content: str) -> ExtractionResult | None:
            clean_json = re.sub(
                r"^```(?:json)?|```$", "", text_content.strip(), flags=re.MULTILINE
            ).strip()
            try:
                data: dict[str, Any] = json.loads(clean_json)
                entities = [
                    ExtractedEntity(name=e["name"], type=e["type"])
                    for e in data.get("entities", [])
                    if "name" in e and "type" in e
                ]
                relationships = [
                    ExtractedRelationship(source=r["source"], target=r["target"], type=r["type"])
                    for r in data.get("relationships", [])
                    if "source" in r and "target" in r and "type" in r
                ]
                names = {e.name for e in entities}
                valid_rels = [r for r in relationships if r.source in names and r.target in names]
                return ExtractionResult(entities=entities, relationships=valid_rels)
            except Exception:
                return None

        # 1. Primary: OpenAI
        if self.openai_api_key:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.openai_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.openai_model_name,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.1,
                            "response_format": {"type": "json_object"},
                        },
                    )
                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"].get("content", "")
                        parsed = _parse_extraction_payload(content)
                        if parsed is not None:
                            return parsed
            except Exception as e:
                logger.debug("OpenAI entity extraction note: %s", e)

        # 2. Fallback 1: Groq
        if self.groq_api_key:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.groq_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.groq_model_name,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.1,
                            "response_format": {"type": "json_object"},
                        },
                    )
                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"].get("content", "")
                        parsed = _parse_extraction_payload(content)
                        if parsed is not None:
                            return parsed
            except Exception as e:
                logger.debug("Groq entity extraction note: %s", e)

        # 3. Fallback 2: Gemini
        if self.api_key:
            try:
                from google import genai

                client = genai.Client(api_key=self.api_key)
                response = await client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )
                text = response.text or ""
                parsed = _parse_extraction_payload(text)
                if parsed is not None:
                    return parsed
            except Exception as e:
                logger.debug("Gemini entity extraction fallback: %s", e)

        # 4. Fallback 3: Robust heuristic fallback using clinical ontology keywords
        return self._heuristic_extract(chunk_text)

    def _heuristic_extract(self, text: str) -> ExtractionResult:
        text_lower = text.lower()
        found_entities: list[ExtractedEntity] = []

        for entity_type, keywords in COMMON_MEDICAL_KEYWORDS.items():
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                    found_entities.append(ExtractedEntity(name=kw, type=entity_type))

        # A keyword match identifies an entity, never a clinical relationship.
        # Relationships require explicit extraction from the source passage.
        return ExtractionResult(entities=found_entities)


medical_extractor = MedicalEntityExtractor()
