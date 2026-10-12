import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HealthcareAgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    domain_key: str
    name: str
    specialty: str
    description: str
    system_prompt: str
    icon: str
    color: str
    is_active: bool
    created_at: datetime


class CreateCustomAgentRequest(BaseModel):
    domain_key: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    specialty: str = Field(..., min_length=2, max_length=100)
    description: str = Field(..., min_length=10)
    system_prompt: str = Field(..., min_length=20)
    icon: str = Field(default="Stethoscope")
    color: str = Field(default="#0D9488")
