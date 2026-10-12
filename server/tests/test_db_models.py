import pytest

from app.config import get_settings
from app.db.models import HealthcareAgent
from app.db.postgres import DEFAULT_AGENTS


def test_settings_loaded():
    settings = get_settings()
    assert settings.POSTGRES_DB == "hybrid_rag"
    assert "hybrid_rag" in settings.async_database_url


def test_default_agents_definition():
    assert len(DEFAULT_AGENTS) >= 4
    domains = [a["domain_key"] for a in DEFAULT_AGENTS]
    assert "cardiology" in domains
    assert "gynaecology" in domains
    assert "neurology" in domains
    assert "general_medicine" in domains


def test_model_instantiation():
    agent = HealthcareAgent(
        domain_key="cardiology",
        name="Dr. Cardio",
        specialty="Cardiology",
        description="Cardio specialist",
        system_prompt="Analyze ECG and coronary issues.",
        icon="HeartPulse",
        color="#EF4444",
        is_active=True,
    )
    assert agent.domain_key == "cardiology"
    assert agent.name == "Dr. Cardio"
    assert agent.is_active is True


@pytest.mark.asyncio
async def test_database_seeded_agents(db_session):
    from sqlalchemy import select

    result = await db_session.execute(select(HealthcareAgent))
    agents = result.scalars().all()
    assert len(agents) == 4
    assert {a.domain_key for a in agents} == {
        "cardiology",
        "gynaecology",
        "neurology",
        "general_medicine",
    }
