import json
import logging
import re

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class FollowUpQuestionGenerator:
    def __init__(self) -> None:
        self.openai_api_key = settings.OPENAI_API_KEY
        self.openai_model_name = settings.OPENAI_MODEL_NAME
        self.groq_api_key = settings.GROQ_API_KEY
        self.groq_model_name = settings.GROQ_MODEL_NAME
        self.api_key = settings.GEMINI_API_KEY

    async def generate_suggestions(
        self,
        domain_specialty: str,
        user_query: str,
        assistant_response: str,
    ) -> list[str]:
        """Generate 3 clinically relevant follow-up questions (OpenAI primary, Groq/Gemini fallback)."""
        prompt = (
            f"You are a clinical AI specialized in {domain_specialty}.\n"
            f"User asked: {user_query}\n"
            f"Clinical answer provided: {assistant_response[:1000]}\n\n"
            "Generate exactly 3 concise, highly relevant clinical follow-up questions the practitioner "
            "or patient should explore next (e.g. contraindications, diagnostic tests, dosage adjustments, "
            "monitoring schedule).\n"
            'Output ONLY a JSON array of 3 strings. Example: ["Question 1?", "Question 2?", "Question 3?"]'
        )

        # 1. Primary: OpenAI
        if self.openai_api_key:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.openai_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.openai_model_name,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.2,
                        },
                    )
                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"].get("content", "")
                        clean_json = re.sub(
                            r"^```(?:json)?|```$", "", content.strip(), flags=re.MULTILINE
                        ).strip()
                        questions = json.loads(clean_json)
                        if isinstance(questions, list) and len(questions) >= 3:
                            return [str(q).strip() for q in questions[:3]]
            except Exception as e:
                logger.debug("OpenAI follow-up generation note: %s", e)

        # 2. Fallback 1: Groq
        if self.groq_api_key:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.groq_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.groq_model_name,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.2,
                        },
                    )
                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"].get("content", "")
                        clean_json = re.sub(
                            r"^```(?:json)?|```$", "", content.strip(), flags=re.MULTILINE
                        ).strip()
                        questions = json.loads(clean_json)
                        if isinstance(questions, list) and len(questions) >= 3:
                            return [str(q).strip() for q in questions[:3]]
            except Exception as e:
                logger.debug("Groq follow-up generation note: %s", e)

        # 3. Fallback 2: Google Gemini
        if self.api_key:
            try:
                from google import genai

                client = genai.Client(api_key=self.api_key)
                response = await client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )
                text = response.text or ""
                clean_json = re.sub(
                    r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE
                ).strip()
                questions = json.loads(clean_json)
                if isinstance(questions, list) and len(questions) >= 3:
                    return [str(q).strip() for q in questions[:3]]
            except Exception as e:
                logger.debug("Gemini follow-up generation note: %s", e)

        # Domain-tailored clinical fallback questions
        domain_lower = domain_specialty.lower()
        if "cardio" in domain_lower:
            return [
                "Are there any drug-drug contraindications with current medications?",
                "What are the target blood pressure and heart rate parameters for this patient?",
                "What diagnostic testing (e.g., Echocardiogram, Holter monitor) is recommended next?",
            ]
        elif "gynae" in domain_lower or "obstetric" in domain_lower:
            return [
                "How does this treatment affect pregnancy safety and lactation categories?",
                "What routine lab screening intervals are recommended for these findings?",
                "What differential diagnoses should be ruled out for these symptoms?",
            ]
        elif "neuro" in domain_lower:
            return [
                "What acute neurological warning signs warrant emergency room admission?",
                "What neuro-imaging modalities (MRI vs CT) are indicated?",
                "Are there long-term maintenance or rehabilitation guidelines for this condition?",
            ]
        else:
            return [
                "What follow-up laboratory tests should be ordered?",
                "Are there specific dietary or lifestyle modifications indicated?",
                "What are the key warning symptoms the patient should monitor at home?",
            ]


follow_up_generator = FollowUpQuestionGenerator()
