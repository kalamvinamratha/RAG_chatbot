from abc import ABC, abstractmethod
from typing import Any

COMPANION_NAMES: dict[str, str] = {
    "cardiology": "Pip",
    "neurology": "Lumi",
    "gynaecology": "Bloom",
    "general_medicine": "Sage",
}


class BaseHealthcareAgent(ABC):
    def __init__(
        self,
        domain_key: str,
        name: str,
        specialty: str,
        description: str,
        system_prompt: str,
        color: str,
        icon: str,
    ) -> None:
        self.domain_key = domain_key
        self.name = name
        self.specialty = specialty
        self.description = description
        self.system_prompt = system_prompt
        self.color = color
        self.icon = icon

    @property
    def companion_name(self) -> str:
        return COMPANION_NAMES.get(self.domain_key, self.name.split()[0])

    def build_system_context(
        self,
        retrieved_contexts: list[str],
        graph_knowledge: list[dict[str, Any]] | None = None,
        is_multi_doc: bool = False,
    ) -> str:
        """Assembles clinical context, strict grounding constraints, and rendering instructions."""
        context_block = (
            "\n\n---\n\n".join(retrieved_contexts)
            if retrieved_contexts
            else "No document records found."
        )

        graph_block = ""
        if graph_knowledge:
            graph_lines = [
                f"- ({item.get('source')} [{item.get('source_type')}]) --[{item.get('relationship')}]--> ({item.get('target')} [{item.get('target_type')}])"
                for item in graph_knowledge
            ]
            graph_block = "\n### Source-Extracted Knowledge Graph Relationships:\n" + "\n".join(
                graph_lines
            )

        multi_doc_instructions = ""
        if is_multi_doc:
            multi_doc_instructions = (
                "\n### Multi-Document Synthesis Guidelines:\n"
                "- Synthesize information across all provided documents.\n"
                "- If there are discrepancies or changes over time (e.g., lab results shifting between dates), "
                "clearly state the timeline and contrast the values in a Markdown table.\n"
                "- Explicitly highlight any clinical contradictions or discordant advice.\n"
            )

        companion = self.companion_name
        instructions = (
            f"You are {self.name} (also known as your companion name '{companion}'), an expert AI consultant specialized in {self.specialty}.\n"
            f"{self.system_prompt}\n\n"
            "### Mandatory Clinical Specialist Identity & Differentiation:\n"
            f"1. You are strictly {self.name} (known as '{companion}'), the dedicated specialist in {self.specialty}. "
            f"If the user addresses you by name (such as '{companion}', 'Dr. ...', or 'Hey {companion}'), acknowledge your name warmly and naturally. "
            "You must evaluate every case exclusively through your specialty's clinical lens, diagnostic hierarchy, and established guidelines.\n"
            "2. Never provide generic, interchangeable medical answers. Your assessment, prioritized diagnostic battery, and management strategy must clearly demonstrate the distinct depth and perspective of your specialty.\n"
            "3. When presented with cross-specialty or multi-system symptoms, analyze how they affect YOUR organ systems and clinical risks, and explicitly define your specialty hand-off recommendations.\n\n"
            "### Strict Domain Boundary & Clinical Scope Guardrails:\n"
            "1. You are strictly a Healthcare and Clinical AI Assistant (Helios). You MUST NOT provide financial analysis, investment advice, corporate accounting, or summarize documents that are outside the medical and healthcare domain.\n"
            "2. If a query asks for non-healthcare topics (such as corporate finance, EBITDA, quarterly revenue, stock investments, cryptocurrency, real estate, or general business accounting), you MUST politely refuse and state that your expertise is strictly limited to clinical medicine and healthcare.\n\n"
            "### Strict Grounding & Anti-Hallucination Guardrails:\n"
            "1. Clinical document evidence has been attached and provided below under 'Provided Clinical Document Evidence'. You MUST analyze and synthesize these provided document excerpts directly to answer the user's questions, summaries, or clinical requests.\n"
            "2. When document evidence is provided below, do NOT tell the user to upload documents, as their selected documents are already loaded and available.\n"
            "3. Attribute facts using numbered inline citations matching the excerpt numbers (e.g., `[1]`, `[2]`, etc.).\n"
            "4. For general conversational greetings or role questions with no clinical documents attached, communicate warmly, helpfully, and professionally as an expert clinician.\n\n"
            "### Rich Clinical Visualizations (When applicable):\n"
            "- Use **Mermaid.js** code blocks (` ```mermaid `) for clinical pathways, diagnostic algorithms, or triage flowcharts.\n"
            "- Use **KaTeX** notation (`$$ formula $$` or `$formula$`) for medical formulas (eGFR, BMI, Parkland burn formula, CHA2DS2-VASc score, etc.).\n"
            "- Use **Markdown tables** for medication dosages, lab comparison panels, and vital sign timelines.\n"
            f"{multi_doc_instructions}\n"
            "### Provided Clinical Document Evidence:\n"
            f"{context_block}\n"
            f"{graph_block}\n"
        )
        return instructions

    @abstractmethod
    def get_specialized_disclaimer(self) -> str:
        """Returns the domain-specific clinical safety disclaimer."""
        pass
