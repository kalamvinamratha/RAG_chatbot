from app.agents.base import BaseHealthcareAgent
from app.agents.domains.cardiology import CardiologyAgent
from app.agents.domains.general_medicine import GeneralMedicineAgent
from app.agents.domains.gynaecology import GynaecologyAgent
from app.agents.domains.neurology import NeurologyAgent


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseHealthcareAgent] = {}
        self._register_default_agents()

    def _register_default_agents(self) -> None:
        agents = [
            CardiologyAgent(),
            GynaecologyAgent(),
            NeurologyAgent(),
            GeneralMedicineAgent(),
        ]
        for a in agents:
            self._agents[a.domain_key] = a

    def get_agent(self, domain_key: str) -> BaseHealthcareAgent:
        """Retrieve agent by domain key, falling back to General Medicine."""
        return self._agents.get(domain_key.lower(), self._agents["general_medicine"])

    def list_agents(self) -> list[BaseHealthcareAgent]:
        """List all available healthcare domain agents."""
        return list(self._agents.values())

    def register_custom_agent(self, agent: BaseHealthcareAgent) -> None:
        """Dynamically register new healthcare specialty agents."""
        self._agents[agent.domain_key] = agent

    def from_record(self, record) -> BaseHealthcareAgent:
        # Database configuration is authoritative, including custom domains and edited prompts.
        return ConfiguredHealthcareAgent(
            domain_key=record.domain_key,
            name=record.name,
            specialty=record.specialty,
            description=record.description,
            system_prompt=record.system_prompt,
            color=record.color,
            icon=record.icon,
        )


class ConfiguredHealthcareAgent(BaseHealthcareAgent):
    def get_specialized_disclaimer(self) -> str:
        return "This answer uses uploaded evidence and does not replace a clinician's assessment."


agent_registry = AgentRegistry()
