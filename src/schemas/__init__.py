"""Paquet d'esquemes Pydantic per a les respostes estructurades dels agents."""

from src.schemas.agent_schemas import (
    ADRAlternative,
    ArchitectureDecisionRecord,
    CodeReviewResponse,
    DeveloperPlan,
    FileItem,
    ImprovementItem,
    ImprovementsResponse,
)

__all__ = [
    "ADRAlternative",
    "ArchitectureDecisionRecord",
    "FileItem",
    "DeveloperPlan",
    "CodeReviewResponse",
    "ImprovementItem",
    "ImprovementsResponse",
]
