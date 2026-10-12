import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HealthcareAgent
from app.db.postgres import get_db
from app.schemas.agent import CreateCustomAgentRequest, HealthcareAgentResponse
from app.security import require_owner

router = APIRouter(
    prefix="/agents", tags=["Healthcare Agents"], dependencies=[Depends(require_owner)]
)


@router.get("", response_model=list[HealthcareAgentResponse])
async def list_healthcare_agents(db: AsyncSession = Depends(get_db)):
    """List all available healthcare domain agents."""
    result = await db.execute(
        select(HealthcareAgent)
        .where(HealthcareAgent.is_active.is_(True))
        .order_by(HealthcareAgent.name)
    )
    agents = result.scalars().all()
    return agents


@router.get("/{agent_id}", response_model=HealthcareAgentResponse)
async def get_healthcare_agent(agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get single healthcare domain agent details."""
    agent = await db.get(HealthcareAgent, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Healthcare agent with ID {agent_id} not found",
        )
    return agent


@router.post("", response_model=HealthcareAgentResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_agent(
    payload: CreateCustomAgentRequest, db: AsyncSession = Depends(get_db)
):
    """Create and register a custom domain healthcare agent."""
    existing = await db.execute(
        select(HealthcareAgent).where(HealthcareAgent.domain_key == payload.domain_key.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent with domain key '{payload.domain_key}' already exists",
        )

    agent = HealthcareAgent(
        domain_key=payload.domain_key.lower(),
        name=payload.name,
        specialty=payload.specialty,
        description=payload.description,
        system_prompt=payload.system_prompt,
        icon=payload.icon,
        color=payload.color,
        is_active=True,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent
